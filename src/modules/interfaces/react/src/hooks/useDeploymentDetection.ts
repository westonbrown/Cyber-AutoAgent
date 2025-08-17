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
  openConfig
}: UseDeploymentDetectionParams) {
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

        // If a healthy deployment is detected, do not show the setup wizard.
        if (hasHealthy) {
          // Do not auto-open the config editor here; allow the main app to load.
          // The later block will handle prompting the config editor only after setup
          // when the app is configured but model details are missing.
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
  }, [isConfigLoading, appState.isUserTriggeredSetup, appState.isInitializationFlowActive, appState.isConfigLoaded, appState.hasUserDismissedInit, applicationConfig, activeModal, actions, openConfig]);
}
