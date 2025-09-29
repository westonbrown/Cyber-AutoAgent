/**
 * useAutoRun
 *
 * Encapsulates the auto-run behavior previously inline in App.tsx.
 * Starts an assessment automatically when CLI flags are provided.
 */

import React from 'react';

interface UseAutoRunParams {
  autoRun?: boolean;
  target?: string;
  module?: string;
  objective?: string;
  iterations?: number;
  provider?: string;
  model?: string;
  region?: string;
  appState: any;
  actions: any;
  applicationConfig: any;
  operationManager: any;
  registerTimeout: (fn: () => void, ms: number) => any;
}

export function useAutoRun({
  autoRun,
  target,
  module,
  objective,
  iterations,
  provider,
  model,
  region,
  appState,
  actions,
  applicationConfig,
  operationManager,
  registerTimeout
}: UseAutoRunParams) {
  React.useEffect(() => {
    if (autoRun && target && module && appState.isConfigLoaded) {
      // Skip initialization flow
      actions.dismissInit();

      // Apply CLI parameter overrides to config if provided (note: requires persist function to save)
      const configUpdates: Partial<typeof applicationConfig> = {};
      if (iterations && iterations !== applicationConfig.iterations) {
        configUpdates.iterations = iterations;
      }
      if (provider && provider !== applicationConfig.modelProvider) {
        configUpdates.modelProvider = provider as 'bedrock' | 'ollama' | 'litellm';
      }
      if (model && model !== applicationConfig.modelId) {
        configUpdates.modelId = model;
      }
      if (region && region !== applicationConfig.awsRegion) {
        configUpdates.awsRegion = region;
      }
      // Note: Persisting config updates would require a context method; omitted intentionally.

      // Set assessment parameters (module first to ensure correct plugin prompts/tools)
      if (module) {
        operationManager.assessmentFlowManager.processUserInput(`module ${module}`);
      }
      operationManager.assessmentFlowManager.processUserInput(`target ${target}`);
      if (objective) {
        operationManager.assessmentFlowManager.processUserInput(`objective ${objective}`);
      } else {
        // Use empty string to trigger default objective
        operationManager.assessmentFlowManager.processUserInput('');
      }

      // Start assessment execution automatically
      registerTimeout(() => {
        operationManager.startAssessmentExecution();
      }, 100); // Small delay to ensure state is set
    }
  }, [
    autoRun,
    target,
    module,
    objective,
    iterations,
    provider,
    model,
    region,
    appState.isConfigLoaded,
    actions,
    operationManager,
    applicationConfig,
    registerTimeout
  ]);
}
