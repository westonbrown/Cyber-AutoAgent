#!/usr/bin/env node
import React from 'react';
import {render} from 'ink';
import meow from 'meow';
import {App} from './App.js';
import { Config } from './contexts/ConfigContext.js';

const cli = meow(`
  Usage
    $ cyber-react [options]

  Options
    --target, -t         Target system/network to assess
    --objective, -o      Security assessment objective
    --module, -m         Security module to use (default: general)
    --iterations, -i     Maximum tool executions (default: 50)
    --auto-run          Start assessment immediately without UI
    --auto-approve      Auto-approve tool executions (no confirmations)
    --memory-mode       Memory mode: auto (default) or fresh
    --provider          Model provider: bedrock (default), ollama, or litellm
    --model             Specific model ID to use
    --region            AWS region (default: us-east-1)
    --observability     Enable observability tracing (default: true)
    --debug, -d         Enable debug mode
    --headless          Run in headless mode for scripting
    --deployment-mode   Deployment mode: local-cli, single-container, full-stack

  Examples
    $ cyber-react
    $ cyber-react --module general
    $ cyber-react --target example.com --objective "vulnerability scan" --auto-run
    $ cyber-react -t 192.168.1.100 -o "port scan and service enumeration" -i 25 --auto-approve
`, {
  importMeta: import.meta,
  flags: {
    target: {
      type: 'string',
      shortFlag: 't'
    },
    objective: {
      type: 'string',
      shortFlag: 'o'
    },
    module: {
      type: 'string',
      shortFlag: 'm',
      default: 'general'
    },
    iterations: {
      type: 'number',
      shortFlag: 'i',
      default: 100  // Match Python CLI and config defaults
    },
    autoRun: {
      type: 'boolean',
      default: false
    },
    autoApprove: {
      type: 'boolean',
      default: false
    },
    memoryMode: {
      type: 'string',
      default: 'auto'
    },
    provider: {
      type: 'string',
      default: 'bedrock'
    },
    model: {
      type: 'string'
    },
    region: {
      type: 'string',
      default: 'us-east-1'
    },
    observability: {
      type: 'boolean',
      default: true
    },
    debug: {
      type: 'boolean',
      shortFlag: 'd'
    },
    headless: {
      type: 'boolean',
      default: false
    },
    deploymentMode: {
      type: 'string',
      default: 'local-cli'
    }
  }
});

// Check if we're running in a TTY environment
const isRawModeSupported = process.stdin.isTTY;

// Handle autoRun mode by bypassing React UI and executing directly
const runAutoAssessment = async () => {
  if (cli.flags.autoRun && cli.flags.target) {
    console.log(`🔐 Starting assessment: ${cli.flags.module} → ${cli.flags.target}`);
    console.log(`📌 Objective: ${cli.flags.objective || 'General security assessment'}`);
    
    try {
      // Import config system to get proper defaults and merge with CLI overrides
      const configModule = await import('./contexts/ConfigContext.js');
      
      // Load default config and apply CLI overrides
      const configOverrides: Partial<Config> = {};
      
      // Apply CLI flag overrides
      if (cli.flags.provider) configOverrides.modelProvider = cli.flags.provider as 'bedrock' | 'ollama' | 'litellm';
      if (cli.flags.model) configOverrides.modelId = cli.flags.model;
      if (cli.flags.region) configOverrides.awsRegion = cli.flags.region;
      if (cli.flags.iterations) configOverrides.iterations = cli.flags.iterations;
      if (cli.flags.observability !== undefined) configOverrides.observability = cli.flags.observability;
      if (cli.flags.debug) configOverrides.verbose = cli.flags.debug;
      if (cli.flags.deploymentMode) configOverrides.deploymentMode = cli.flags.deploymentMode as 'local-cli' | 'single-container' | 'full-stack';
      
      // Use the imported default config
      const defaultConfig = configModule.defaultConfig || {
        // Fallback defaults if import fails
        modelProvider: 'bedrock' as const,
        modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
        embeddingModel: 'amazon.titan-embed-text-v2:0',
        evaluationModel: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        swarmModel: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
        awsRegion: 'us-east-1',
        dockerImage: 'cyber-autoagent:latest',
        dockerTimeout: 300,
        volumes: [],
        iterations: 100,
        autoApprove: true,
        confirmations: false,
        maxThreads: 10,
        outputFormat: 'markdown' as const,
        verbose: false,
        memoryMode: 'auto' as const,
        keepMemory: true,
        memoryBackend: 'FAISS' as const,
        outputDir: './outputs',
        unifiedOutput: true,
        theme: 'retro' as const,
        showMemoryUsage: false,
        showOperationId: true,
        environment: {},
        reportSettings: {
          includeRemediation: true,
          includeCWE: true,
          includeTimestamps: true,
          includeEvidence: true,
          includeMemoryOps: true
        },
        observability: true,
        langfuseHost: 'http://localhost:3000',
        langfuseHostOverride: false,
        langfusePublicKey: 'cyber-public',
        langfuseSecretKey: 'cyber-secret',
        enableLangfusePrompts: true,
        langfusePromptLabel: 'production',
        langfusePromptCacheTTL: 300,
        autoEvaluation: true,
        evaluationBatchSize: 5,
        minToolAccuracyScore: 0.8,
        minEvidenceQualityScore: 0.7,
        minAnswerRelevancyScore: 0.7,
        minContextPrecisionScore: 0.8,
        isConfigured: true
      };
      
      // Merge defaults with CLI overrides
      const finalConfig = { ...defaultConfig, ...configOverrides } as Config;
      
      console.log(`⚙️  Config: ${finalConfig.iterations} iterations, ${finalConfig.modelProvider}/${finalConfig.modelId}`);
      console.log(`🔭 Observability: ${finalConfig.observability ? 'enabled' : 'disabled'}`);
      console.log(`🏗️  Deployment Mode: ${finalConfig.deploymentMode || 'local-cli'}`);
      
      // Import and use ExecutionServiceFactory to select proper service
      const { ExecutionServiceFactory } = await import('./services/ExecutionServiceFactory.js');
      const serviceResult = await ExecutionServiceFactory.selectService(finalConfig);
      const executionService = serviceResult.service;
      
      console.log(`🔧 Using execution service: ${serviceResult.mode} (preferred: ${serviceResult.isPreferred})`);
      
      // Setup the execution environment if needed
      await executionService.setup(finalConfig, (message) => {
        console.log(`📦 Setup: ${message}`);
      });
      
      const assessmentParams = {
        module: cli.flags.module,
        target: cli.flags.target,
        objective: cli.flags.objective || `Comprehensive ${cli.flags.module} security assessment`
      };
      
      // Execute assessment and wait for completion
      const handle = await executionService.execute(assessmentParams, finalConfig);
      const result = await handle.result;
      
      if (result.success) {
        console.log(`✅ Assessment completed successfully in ${result.durationMs}ms`);
        console.log(`📊 Steps executed: ${result.stepsExecuted || 'unknown'}`);
        console.log(`🔍 Findings: ${result.findingsCount || 'unknown'}`);
      } else {
        console.error(`❌ Assessment failed: ${result.error}`);
      }
      
      // Cleanup
      executionService.cleanup();
    } catch (error) {
      console.error('Assessment failed:', error);
      process.exit(1);
    }
    
    return true; // Indicates autoRun was handled
  }
  return false; // Indicates normal React mode should continue
};

// Execute autoRun check in async IIFE
(async () => {
  if (await runAutoAssessment()) {
    process.exit(0); // Exit after successful autoRun
  }
  
  // Continue with normal React app rendering if not autoRun mode
  renderReactApp();
})();

function renderReactApp() {
  // Check for non-interactive mode without autoRun or headless
  if (!isRawModeSupported && !cli.flags.headless && !cli.flags.autoRun) {
    console.log('⚠️  Running in non-interactive mode. Use --headless flag for scripting.');
    console.log('💡 For interactive mode, run directly in a terminal.');
    console.log('\nUsage: cyber-react --target <target> --auto-run');
    process.exit(1);
  }
  
  // In headless mode, run without Ink rendering to avoid TTY issues
  if (cli.flags.headless) {
    console.log('🔧 Running in headless mode');
    // Exit gracefully - headless mode should use --auto-run for execution
    if (!cli.flags.autoRun) {
      console.log('💡 Use --auto-run with --headless to execute assessments');
      process.exit(0);
    }
    return;
  }

  // Render the app with CLI arguments
  const app = render(<App 
    module={cli.flags.module}
    target={cli.flags.target}
    objective={cli.flags.objective}
    autoRun={cli.flags.autoRun}
    iterations={cli.flags.iterations}
    provider={cli.flags.provider}
    model={cli.flags.model}
    region={cli.flags.region}
  />);

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    app.unmount();
    process.exit(0);
  });
}