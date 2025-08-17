/**
 * useDeploymentDetection
 *
 * Extracts the deployment detection and initialization gating logic from App.tsx
 * to improve modularity and testability.
 */

import React from 'react';
import { DeploymentDetector } from '../services/DeploymentDetector.js';
import { ModalType } from './useModalManager.js';

interface UseDeploymentDetectionParams {
  isConfigLoading: boolean;
  appState: any;
  actions: any;
  applicationConfig: any;
  activeModal: ModalType;
  openConfig: (message?: string) => void;
}

export function useDeploymentDetection({
  isConfigLoading,
  appState,
  actions,
  applicationConfig,
  activeModal,
  openConfig,
  updateConfig,
  saveConfig
}: UseDeploymentDetectionParams & {
  updateConfig?: (updates: any) => void;
  saveConfig?: () => Promise<void>;
}) {
  React.useEffect(() => {
    if (isConfigLoading) return;
    if (appState.isInitializationFlowActive) return;

    const forceSetup = appState.isUserTriggeredSetup || (typeof process !== 'undefined' && process.env.CYBER_SHOW_SETUP === 'true');

    const run = async () => {
      try {
        const detector = DeploymentDetector.getInstance();
        const detection = await detector.detectDeployments(applicationConfig);
        const hasHealthy = detection.availableDeployments?.some(d => d.isHealthy);

        const configMissing = !applicationConfig?.isConfigured || !applicationConfig?.deploymentMode;

        // Respect explicit/forced setup
        if (forceSetup) {
          actions.setInitializationFlow(true);
          return;
        }

        // If a healthy deployment is detected, check if we need to switch modes
        if (hasHealthy) {
          // Check if the configured deployment mode is unhealthy
          const configuredMode = applicationConfig?.deploymentMode;
          if (configuredMode) {
            const configuredDeployment = detection.availableDeployments?.find(
              d => d.mode === configuredMode
            );
            
            // If configured mode is unhealthy, switch to a healthy one
            if (configuredDeployment && !configuredDeployment.isHealthy) {
              const healthyDeployment = detection.availableDeployments?.find(d => d.isHealthy);
              if (healthyDeployment && updateConfig && saveConfig) {
                // Auto-switch to the healthy deployment
                updateConfig({ deploymentMode: healthyDeployment.mode });
                await saveConfig();
                
                // Log the auto-switch for debugging
                console.log(`Auto-switched from unhealthy ${configuredMode} to ${healthyDeployment.mode}`);
              }
            }
          } else if (!applicationConfig?.isConfigured) {
            // No deployment mode configured yet, but we have healthy deployments
            // Auto-select the best available healthy deployment
            const healthyDeployment = detection.availableDeployments?.find(d => d.isHealthy);
            if (healthyDeployment && updateConfig && saveConfig) {
              updateConfig({ 
                deploymentMode: healthyDeployment.mode,
                isConfigured: true,
                hasSeenWelcome: true
              });
              await saveConfig();
              console.log(`Auto-selected healthy deployment: ${healthyDeployment.mode}`);
            }
          }
          
          // Do not show setup wizard - we have healthy deployments
          return;
        }

        // No healthy deployments; for first-time users or when detection indicates, show setup
        if (!appState.hasUserDismissedInit && (configMissing || detection.needsSetup)) {
          actions.setInitializationFlow(true);
          return;
        }
      } catch {
        // On detection failure, be safe and prompt setup for first-time users
        if (!appState.hasUserDismissedInit) {
          actions.setInitializationFlow(true);
          return;
        }
      }

      // If configured but missing model details, prompt config editor as before
      if (
        applicationConfig.isConfigured &&
        appState.hasUserDismissedInit &&
        !applicationConfig.modelId &&
        activeModal === ModalType.NONE &&
        !appState.isInitializationFlowActive
      ) {
        setTimeout(() => {
          openConfig('Please configure your AI model and provider settings to continue.');
        }, 1000);
      }
    };

    run();
  }, [isConfigLoading, appState.isUserTriggeredSetup, appState.isInitializationFlowActive, appState.isConfigLoaded, appState.hasUserDismissedInit, applicationConfig, activeModal, actions, openConfig, updateConfig, saveConfig]);
}
