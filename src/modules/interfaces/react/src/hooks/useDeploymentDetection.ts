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
    if (appState.isUserTriggeredSetup || appState.isInitializationFlowActive) return;

    const run = async () => {
      // Only consider (re)activating setup if the user hasn't dismissed it this session
      if (!appState.hasUserDismissedInit) {
        // First, hard gate: if config not set or no deploymentMode, show setup
        const configMissing = !applicationConfig?.isConfigured || !applicationConfig?.deploymentMode;
        if (appState.isConfigLoaded && configMissing) {
          actions.setInitializationFlow(true);
          return;
        }

        // Secondary: consult live environment via DeploymentDetector
        try {
          const detector = DeploymentDetector.getInstance();
          const detection = await detector.detectDeployments(applicationConfig);
          if (detection.needsSetup) {
            actions.setInitializationFlow(true);
            return;
          }
        } catch {
          // On detection failure, be safe and prompt setup
          actions.setInitializationFlow(true);
          return;
        }
      }

      // If configured but missing model details, prompt config editor
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
