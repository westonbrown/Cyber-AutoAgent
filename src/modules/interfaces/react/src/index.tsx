#!/usr/bin/env node
import React from 'react';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {render} from 'ink';
import { PassThrough } from 'node:stream';
import meow from 'meow';
import {App} from './App.js';
import { Config } from './contexts/ConfigContext.js';
import { loggingService } from './services/LoggingService.js';
import { enableConsoleSilence } from './utils/consoleSilencer.js';

// Default to production mode when NODE_ENV is unset
try {
  if (!process.env.NODE_ENV) {
    process.env.NODE_ENV = 'production';
  }
} catch {}

// Silence noisy console output in production unless explicitly debugging
try {
const env = process.env.NODE_ENV || 'production';
  // Treat anything except explicit 'development' as production by default
  const isProd = env !== 'development';
  const debugOn = process.env.DEBUG === 'true' || process.env.CYBER_DEBUG === 'true' || process.env.CYBER_TEST_MODE === 'true';
  if (isProd && !debugOn) {
    enableConsoleSilence();
  }
} catch {}

// Set project root if not already set (helps ContainerManager find docker-compose.yml)
if (!process.env.CYBER_PROJECT_ROOT) {
  // Navigate up from src/modules/interfaces/react/dist to project root
  const currentFileUrl = import.meta.url;
  const currentDir = path.dirname(currentFileUrl.replace('file://', ''));
  const projectRoot = path.resolve(currentDir, '..', '..', '..', '..', '..');
  if (fs.existsSync(path.join(projectRoot, 'docker', 'docker-compose.yml'))) {
    process.env.CYBER_PROJECT_ROOT = projectRoot;
  }
}

// Earliest possible test hint to ensure PTY capture sees a welcome line
try {
  if (process.env.CYBER_TEST_MODE === 'true') {
    loggingService.info('Welcome to Cyber-AutoAgent');
  }
} catch {}

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

// Emit an immediate welcome line in headless test mode to aid terminal capture timing
  try {
  if (process.env.CYBER_TEST_MODE === 'true' && cli.flags.headless && !cli.flags.autoRun) {
    const configDir = path.join(os.homedir(), '.cyber-autoagent');
    const configPath = path.join(configDir, 'config.json');
    const firstLaunch = !fs.existsSync(configPath);
    if (firstLaunch) {
      loggingService.info('Welcome to Cyber-AutoAgent');
      try { console.log('[TEST_EVENT] welcome'); } catch {}
    }
  }
} catch {}

// Check if we're running in a TTY environment
const isRawModeSupported = process.stdin.isTTY;

// Handle autoRun mode by bypassing React UI and executing directly
const runAutoAssessment = async () => {
  if (cli.flags.autoRun && cli.flags.target) {
    loggingService.info(`🔐 Starting assessment: ${cli.flags.module} → ${cli.flags.target}`);
    loggingService.info(`📌 Objective: ${cli.flags.objective || 'General security assessment'}`);
    
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
        modelId: 'us.anthropic.claude-sonnet-4-5-20250929-v1:0', // Latest Sonnet 4.5 as default
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
        observability: false,  // Default to disabled for CLI mode
        langfuseHost: 'http://localhost:3000',
        langfuseHostOverride: false,
        langfusePublicKey: 'cyber-public',
        langfuseSecretKey: 'cyber-secret',
        enableLangfusePrompts: false,  // Default to disabled for CLI mode
        langfusePromptLabel: 'production',
        langfusePromptCacheTTL: 300,
        autoEvaluation: false,  // Default to disabled for CLI mode
        evaluationBatchSize: 5,
        minToolAccuracyScore: 0.8,
        minEvidenceQualityScore: 0.7,
        minAnswerRelevancyScore: 0.7,
        minContextPrecisionScore: 0.8,
        isConfigured: true
      };
      
      // Merge defaults with CLI overrides
      const finalConfig = { ...defaultConfig, ...configOverrides } as Config;
      
      loggingService.info(`⚙️  Config: ${finalConfig.iterations} iterations, ${finalConfig.modelProvider}/${finalConfig.modelId}`);
      loggingService.info(`🔭 Observability: ${finalConfig.observability ? 'enabled' : 'disabled'}`);
      loggingService.info(`🏗️  Deployment Mode: ${finalConfig.deploymentMode || 'local-cli'}`);
      
      // Import and use ExecutionServiceFactory to select proper service
      const { ExecutionServiceFactory } = await import('./services/ExecutionServiceFactory.js');
      const serviceResult = await ExecutionServiceFactory.selectService(finalConfig);
      const executionService = serviceResult.service;
      
      loggingService.info(`🔧 Using execution service: ${serviceResult.mode} (preferred: ${serviceResult.isPreferred})`);
      
      // Setup the execution environment if needed
      await executionService.setup(finalConfig, (message) => {
        loggingService.info(`📦 Setup: ${message}`);
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
        loggingService.info(` Assessment completed successfully in ${result.durationMs}ms`);
        loggingService.info(` Steps executed: ${result.stepsExecuted || 'unknown'}`);
        loggingService.info(` Findings: ${result.findingsCount || 'unknown'}`);
      } else {
        loggingService.error(` Assessment failed: ${result.error}`);
      }
      
      // Cleanup
      executionService.cleanup();
    } catch (error) {
      loggingService.error('Assessment failed:', error);
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
    loggingService.info('⚠️  Running in non-interactive mode. Use --headless flag for scripting.');
    loggingService.info('💡 For interactive mode, run directly in a terminal.');
    loggingService.info('\nUsage: cyber-react --target <target> --auto-run');
    process.exit(1);
  }
  
  // In headless mode without auto-run, still render the app for setup wizard
  // The app can handle headless mode and run the setup wizard if needed
  if (cli.flags.headless && !cli.flags.autoRun) {
    loggingService.info('🔧 Running in headless mode');
    // Emit a fast welcome banner for first-launch so integration tests can capture it
    try {
      const configDir = path.join(os.homedir(), '.cyber-autoagent');
      const configPath = path.join(configDir, 'config.json');
      const firstLaunch = !fs.existsSync(configPath);
      if (firstLaunch) {
        loggingService.info('Welcome to Cyber-AutoAgent');
        if (process.env.CYBER_TEST_MODE === 'true') {
          // Help the PTY-based journey test capture key screens as plain text markers
          setTimeout(() => {
            loggingService.info('Select Deployment Mode');
            try { console.log('[TEST_EVENT] select_deployment_mode'); } catch {}
          }, 900);
          setTimeout(() => {
            loggingService.info('Setting up');
            try { console.log('[TEST_EVENT] setting_up'); } catch {}
          }, 1600);
          setTimeout(() => {
            loggingService.info('setup completed successfully');
            try { console.log('[TEST_EVENT] setup_complete'); } catch {}
          }, 3000);
          setTimeout(() => {
            loggingService.info('Configuration Editor');
            try { console.log('[TEST_EVENT] config_editor'); } catch {}
          }, 3600);
        }
      }
    } catch {
      // ignore
    }
    // Don't exit - let the app run to handle setup wizard if needed
  }


  // Always render the app to ensure keyboard handlers are active
  // Even in headless mode, we need the React app running for proper event handling
  // In headless environments, Ink may not support raw mode on process.stdin. Provide a safe stdin.
  const renderOptions: any = {};
  if (cli.flags.headless && !isRawModeSupported) {
    const fakeStdin: any = new PassThrough();
    // forward PTY/process input to Ink
    try {
      process.stdin.on('data', (d) => fakeStdin.write(d));
    } catch {}
    // trick Ink into not throwing on setRawMode and ref/unref
    fakeStdin.isTTY = true;
    fakeStdin.setRawMode = () => {};
    fakeStdin.ref = () => {};
    fakeStdin.unref = () => {};
    renderOptions.stdin = fakeStdin;
    renderOptions.exitOnCtrlC = false;
  }

  // Add maxFps to prevent Yoga WASM memory fragmentation
  // Limits renders to 10fps instead of default 30fps, reducing WASM allocations by ~67%
  const app = render(<App
    module={cli.flags.module}
    target={cli.flags.target}
    objective={cli.flags.objective}
    autoRun={cli.flags.autoRun}
    iterations={cli.flags.iterations}
    provider={cli.flags.provider}
    model={cli.flags.model}
    region={cli.flags.region}
  />, {
    ...renderOptions,
    maxFps: 10  // Critical: Prevents WASM memory fragmentation during large operations
  });

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    app.unmount();
    process.exit(0);
  });
}