/**
 * Enhanced Test Utilities for Component Testing
 * Provides common testing helpers and mocks for consistent testing
 */

import React from 'react';
import { render as inkRender } from 'ink-testing-library';
import type { Config } from '../contexts/ConfigContext.js';
import type { ModuleInfo } from '../contexts/ModuleContext.js';

// Mock configuration states matching the full Config interface
export const mockConfiguredState: Config = {
  // AI Model Provider Configuration
  modelProvider: 'bedrock',
  modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
  embeddingModel: 'amazon.titan-embed-text-v2:0',
  evaluationModel: 'claude-3-5-sonnet-20241022-v2:0',
  swarmModel: 'claude-3-5-sonnet-20241022-v2:0',
  awsRegion: 'us-east-1',
  awsBearerToken: 'test-bearer-token',
  awsAccessKeyId: 'test-access-key',
  awsSecretAccessKey: 'test-secret-key',
  ollamaHost: 'http://localhost:11434',
  
  // Docker Container Execution Configuration
  dockerImage: 'cyber-autoagent:latest',
  dockerTimeout: 300,
  volumes: [],
  
  // Security Assessment Execution Parameters
  iterations: 100,
  autoApprove: true,
  confirmations: false,
  maxThreads: 10,
  outputFormat: 'markdown',
  verbose: false,
  
  // Execution Configuration
  allowExecutionFallback: true,
  
  // Memory Settings
  memoryMode: 'auto',
  keepMemory: true,
  memoryBackend: 'FAISS',
  
  // Output Settings
  outputDir: './outputs',
  unifiedOutput: true,
  
  // UI Settings
  theme: 'retro',
  showMemoryUsage: false,
  showOperationId: true,
  
  // Environment Variables
  environment: {},
  
  // Report Settings
  reportSettings: {
    includeRemediation: true,
    includeCWE: true,
    includeTimestamps: true,
    includeEvidence: true,
    includeMemoryOps: true
  },
  
  // Observability Settings
  observability: true,
  langfuseHost: 'http://localhost:3000',
  langfuseHostOverride: false,
  langfusePublicKey: 'test-key',
  langfuseSecretKey: 'test-secret',
  enableLangfusePrompts: true,
  langfusePromptLabel: 'production',
  langfusePromptCacheTTL: 300,
  
  // Evaluation Settings
  autoEvaluation: true,
  evaluationBatchSize: 5,
  minToolAccuracyScore: 0.8,
  minEvidenceQualityScore: 0.7,
  minAnswerRelevancyScore: 0.7,
  minContextPrecisionScore: 0.8,
  
  // Setup Status
  isConfigured: true,
  hasSeenWelcome: true,
  deploymentMode: 'local-cli',
  
  // Backward compatibility
  enableObservability: true
};

export const mockUnconfiguredState: Config = {
  ...mockConfiguredState,
  isConfigured: false,
  hasSeenWelcome: false,
  modelId: '',
  awsBearerToken: undefined,
  awsAccessKeyId: undefined,
  awsSecretAccessKey: undefined,
  observability: false,
  langfusePublicKey: '',
  langfuseSecretKey: ''
};

// Mock modules data matching ModuleInfo interface
export const mockAvailableModules: Record<string, ModuleInfo> = {
  'general': {
    name: 'general',
    description: 'General security assessment',
    category: 'security',
    tools: [
      { name: 'nmap', description: 'Network port scanner', category: 'network' },
      { name: 'http_request', description: 'HTTP client tool', category: 'web' },
      { name: 'shell', description: 'Shell command execution', category: 'system' }
    ],
    capabilities: ['network-scanning', 'web-testing', 'system-analysis']
  },
  'network': {
    name: 'network',
    description: 'Network security testing',
    category: 'network',
    tools: [
      { name: 'nmap', description: 'Network port scanner', category: 'network' },
      { name: 'masscan', description: 'High-speed port scanner', category: 'network' },
      { name: 'shell', description: 'Shell command execution', category: 'system' }
    ],
    capabilities: ['port-scanning', 'network-discovery', 'service-enumeration']
  },
  'web': {
    name: 'web',
    description: 'Web application security',
    category: 'web',
    tools: [
      { name: 'http_request', description: 'HTTP client tool', category: 'web' },
      { name: 'sqlmap', description: 'SQL injection testing', category: 'web' },
      { name: 'nikto', description: 'Web vulnerability scanner', category: 'web' }
    ],
    capabilities: ['sql-injection', 'xss-testing', 'web-scanning']
  }
};

// Enhanced render function for unit testing (no providers needed)
export function renderWithProviders(
  component: React.ReactElement,
  options: {
    config?: Config;
    modules?: Record<string, ModuleInfo>;
  } = {}
) {
  // For unit testing, render components directly
  // This allows testing component behavior in isolation
  return inkRender(component);
}

// Keyboard input simulation
export function simulateKeyboardInput(stdin: any, keys: string[]) {
  keys.forEach(key => {
    switch (key) {
      case 'ENTER':
        stdin.write('\r');
        break;
      case 'ESC':
        stdin.write('\x1B');
        break;
      case 'TAB':
        stdin.write('\t');
        break;
      case 'ARROW_UP':
        stdin.write('\x1B[A');
        break;
      case 'ARROW_DOWN':
        stdin.write('\x1B[B');
        break;
      case 'ARROW_LEFT':
        stdin.write('\x1B[D');
        break;
      case 'ARROW_RIGHT':
        stdin.write('\x1B[C');
        break;
      case 'CTRL_C':
        stdin.write('\x03');
        break;
      case 'SPACE':
        stdin.write(' ');
        break;
      default:
        stdin.write(key);
    }
  });
}

// Wait helper for async operations
export function waitFor(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Mock operation history entries
export const mockOperationHistory = [
  { type: 'info', message: 'Assessment started', timestamp: Date.now() },
  { type: 'success', message: 'Target configured', timestamp: Date.now() },
  { type: 'warning', message: 'Some warnings detected', timestamp: Date.now() }
];

// Mock assessment state
export const mockAssessmentState = {
  stage: 'ready' as const,
  module: 'general',
  target: 'testphp.vulnweb.com',
  objective: 'Comprehensive security assessment'
};

// Mock app state
export const mockAppState = {
  isConfigLoaded: true,
  hasUserDismissedInit: true,
  isInitializationFlowActive: false,
  userHandoffActive: false,
  terminalVisible: true,
  activeOperation: null,
  completedOperation: false,
  errorCount: 0
};

// Mock metrics for footer testing
export const mockOperationMetrics = {
  tokens: 1500,
  cost: 0.05,
  duration: '2m 30s',
  memoryOps: 5,
  evidence: 12
};

// Mock connection states
export const mockConnectionStates = {
  connected: 'connected' as const,
  connecting: 'connecting' as const,
  error: 'error' as const,
  offline: 'offline' as const
};

export default {
  renderWithProviders,
  simulateKeyboardInput,
  waitFor,
  mockConfiguredState,
  mockUnconfiguredState,
  mockAvailableModules,
  mockOperationHistory,
  mockAssessmentState,
  mockAppState,
  mockOperationMetrics,
  mockConnectionStates
};