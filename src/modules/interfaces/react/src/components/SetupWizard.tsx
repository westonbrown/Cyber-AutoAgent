/**
 * SetupWizard Component
 * 
 * Main setup wizard orchestrator. Manages the flow between welcome, deployment selection,
 * and progress screens. Replaces the complex InitializationFlow with a simplified architecture.
 */

import React, { useCallback, useEffect, useState, useRef } from 'react';
import { Box, Text, useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';
import { useSetupWizard } from '../hooks/useSetupWizard.js';
import { useConfig } from '../contexts/ConfigContext.js';
import { WelcomeScreen } from './setup/WelcomeScreen.js';
import { DeploymentSelectionScreen } from './setup/DeploymentSelectionScreen.js';
import { ProgressScreen } from './setup/ProgressScreen.js';
import { DeploymentMode } from '../services/SetupService.js';
// Banner/Header is rendered centrally by parent; do not render here

interface SetupWizardProps {
  onComplete: (completionMessage?: string) => void;
  terminalWidth?: number;
}

export const SetupWizard: React.FC<SetupWizardProps> = React.memo(({
  onComplete,
  terminalWidth = 80,
}) => {
  const { state, actions } = useSetupWizard();
  const { config, updateConfig, saveConfig } = useConfig();
  const { stdout } = useStdout();
  const [stepRenderKey, setStepRenderKey] = useState(0);
  const [isExiting, setIsExiting] = useState(false);
  const prevStepRef = useRef(state.currentStep);

  // Handle setup completion
  const handleSetupComplete = useCallback(async () => {
    if (state.selectedMode) {
      try {
        // Update configuration with selected deployment mode
        updateConfig({ 
          deploymentMode: state.selectedMode,
          hasSeenWelcome: true,
          isConfigured: true 
        });
        
        // Save configuration to disk
        await saveConfig();
        
        // Clear the deployment detector cache after setup
        const { DeploymentDetector } = await import('../services/DeploymentDetector.js');
        DeploymentDetector.getInstance().clearCache();
        
        // Provide completion message
        const modeDisplayName = 
          state.selectedMode === 'local-cli' ? 'Local CLI' :
          state.selectedMode === 'single-container' ? 'Agent Container' :
          'Full Stack';
        
        // Clear the setup flag
        delete process.env.CYBER_SHOW_SETUP;
        
        onComplete(`${modeDisplayName} setup completed successfully`);
      } catch (error) {
        actions.setError('Failed to save configuration');
      }
    } else {
      onComplete();
    }
  }, [state.selectedMode, updateConfig, saveConfig, onComplete, actions.setError]);

  // Handle deployment mode selection and start setup
  const handleModeSelection = useCallback(async (mode: DeploymentMode) => {
    // Immediately show progress screen so UI updates without delay
    actions.selectMode(mode);
    actions.nextStep();
    setStepRenderKey(prev => prev + 1);

    // Avoid clearing here; modal manager owns terminal clears during transitions

    // Start setup immediately for responsive UI
    // Use microtask to ensure UI has rendered first
    queueMicrotask(async () => {
      const DETECTION_BUDGET_MS = 350; // small budget to avoid visible delay
      let didFastSwitch = false;

      try {
        const { DeploymentDetector } = await import('../services/DeploymentDetector.js');
        const detector = DeploymentDetector.getInstance();
        const detectionPromise = detector.detectDeployments(config, { noCache: true });
        const timeoutPromise = new Promise<null>(resolve => setTimeout(() => resolve(null), DETECTION_BUDGET_MS));

        const result = await Promise.race([detectionPromise, timeoutPromise]);

        if (result && (result as any).availableDeployments) {
          const detection = result as Awaited<typeof detectionPromise>;
          const isAlreadyActive = detection.availableDeployments.some(d => d.mode === mode && d.isHealthy);
          if (isAlreadyActive) {
            // Fast path: switch config and exit the wizard
            const modeDisplayName = 
              mode === 'local-cli' ? 'Local CLI' :
              mode === 'single-container' ? 'Agent Container' :
              'Full Stack';

            updateConfig({ 
              deploymentMode: mode,
              hasSeenWelcome: true,
              isConfigured: true 
            });
            await saveConfig();
            detector.clearCache();

            delete process.env.CYBER_SHOW_SETUP;
            setIsExiting(true);
            setTimeout(() => onComplete(`Switched to ${modeDisplayName} deployment`), 0);
            didFastSwitch = true;
            // eslint-disable-next-line no-console
            console.log('[OK] setup: fast-switched to healthy deployment');
          }
        }
      } catch (e) {
        // Detection failed; proceed to setup
      }

      if (!didFastSwitch) {
        // Start setup after budget window; ProgressScreen is already mounted
        void actions.startSetup(mode);
      }
    });
  }, [actions, config, updateConfig, saveConfig, onComplete]);

  // Handle setup retry
  const handleRetry = useCallback(async () => {
    actions.resetError();
    await actions.startSetup();
  }, [actions.resetError, actions.startSetup]);

  // Auto-complete when setup finishes successfully
  useEffect(() => {
    if (state.isComplete && !state.error) {
      // Small delay to show completion state
      const timer = setTimeout(() => {
        handleSetupComplete();
      }, 1500);
      
      return () => clearTimeout(timer);
    }
  }, [state.isComplete, state.error, handleSetupComplete]);

  const renderCurrentScreen = () => {
    switch (state.currentStep) {
      case 'welcome':
        return (
          <WelcomeScreen
            onContinue={actions.nextStep}
            onSkip={() => {
              // User chose to skip the setup wizard from the welcome screen
              // Clear any forced setup flag so detection does not immediately re-open the wizard
              try {
                delete (process as any).env?.CYBER_SHOW_SETUP;
              } catch {}
              setIsExiting(true);
              // Defer onComplete to allow the UI to paint the state change cleanly
              setTimeout(() => onComplete('Setup skipped'), 0);
            }}
            terminalWidth={terminalWidth}
          />
        );

      case 'deployment':
        return (
          <DeploymentSelectionScreen
            onSelect={handleModeSelection}
            onBack={actions.previousStep}
            terminalWidth={terminalWidth}
          />
        );

      case 'progress':
        return (
          <ProgressScreen
            deploymentMode={state.selectedMode!}
            progress={state.progress}
            isComplete={state.isComplete}
            isLoading={state.isLoading}
            error={state.error}
            onComplete={handleSetupComplete}
            onRetry={handleRetry}
            onBack={actions.previousStep}
            terminalWidth={terminalWidth}
          />
        );

      default:
        // Safe fallback to avoid any blank screen on unexpected state
        return (
          <Box>
            <span />
          </Box>
        );
    }
  };

  // Clear terminal only on welcome -> deployment, and defer clear to after paint to avoid black screen
  useEffect(() => {
    const prev = prevStepRef.current;
    const curr = state.currentStep;

    // Decide whether to clear based on transition
    const shouldClear = prev === 'welcome' && curr === 'deployment';

    if (shouldClear) {
      // Defer clear to next tick so the next screen mounts before the clear
      setTimeout(() => {
        try { stdout.write(ansiEscapes.clearTerminal); } catch {}
      }, 0);
    }

    // Always bump key to force a fresh render of the new step
    setStepRenderKey(prevKey => prevKey + 1);

    // Update prev step
    prevStepRef.current = curr;
  }, [state.currentStep, stdout]);

  return (
    <Box flexDirection="column" width="100%">
      {/* Current setup screen */}
      <Box key={`setup-content-${stepRenderKey}`}>
        {isExiting ? (
          <Box width="100%" paddingY={1} justifyContent="center">
            <Text>
              [WAIT] Switching deployment…
            </Text>
          </Box>
        ) : (
          renderCurrentScreen()
        )}
      </Box>
    </Box>
  );
});