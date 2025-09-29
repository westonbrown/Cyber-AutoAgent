/**
 * Cyber-AutoAgent Configuration Context - Settings Management
 * 
 * Provides centralized configuration management for all application settings including
 * AI model providers, Docker execution parameters, memory backends, observability,
 * and security assessment preferences. Supports persistent configuration storage
 * with automatic environment variable integration.
 * 
 * Key Features:
 * - Multi-provider AI model support (AWS Bedrock, Ollama, LiteLLM)
 * - Persistent configuration storage in user home directory
 * - Automatic environment variable integration for sensitive credentials
 * - Comprehensive validation and default value management
 * - Type safety with TypeScript interfaces
 * 
 * Configuration Structure:
 * - Model Provider Settings: AI models, regions, authentication
 * - Docker Execution: Container settings, volumes, timeouts
 * - Assessment Parameters: iterations, confirmations, output formats
 * - Memory Management: backends, paths, retention policies
 * - Observability: Langfuse integration, evaluation metrics
 * - UI Preferences: themes, display options, debugging
 * 
 * Configuration management for all application settings
 */

import React, { createContext, useContext, useState, useCallback, useMemo, useRef, useEffect, FC, ReactNode } from 'react';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';
import { loggingService } from '../services/LoggingService.js';
import { detectDeploymentMode, getDeploymentDefaults } from '../config/deployment.js';
import { DeploymentDetector } from '../services/DeploymentDetector.js';

/**
 * Main Configuration Interface - Complete Settings Schema
 * 
 * Defines the complete configuration structure for Cyber-AutoAgent with
 * comprehensive type safety and detailed documentation for each setting.
 * All sensitive credentials support environment variable integration.
 */
export interface Config {
  // AI Model Provider Configuration
  /** Primary AI model provider (AWS Bedrock, Ollama local, or LiteLLM proxy) */
  modelProvider: 'bedrock' | 'ollama' | 'litellm';
  /** Main assessment model identifier (e.g., 'claude-sonnet-4', 'llama3.1:8b') */
  modelId: string;
  /** Vector embedding model for memory operations */
  embeddingModel?: string;
  /** Quality evaluation model for assessment validation */
  evaluationModel?: string;
  /** Multi-agent swarm coordination model */
  swarmModel?: string;
  /** AWS region for Bedrock API calls */
  awsRegion: string;
  /** AWS Bearer token for Bedrock authentication (optional) */
  awsBearerToken?: string;
  /** AWS Access Key ID for programmatic access */
  awsAccessKeyId?: string;
  /** AWS Secret Access Key for programmatic access */
  awsSecretAccessKey?: string;
  /** AWS Session Token for temporary credentials */
  awsSessionToken?: string;
  /** Ollama server host URL for local model serving */
  ollamaHost?: string;
  
  // Model Pricing Configuration (per 1K tokens)
  /** Custom model pricing configuration - overrides defaults */
  modelPricing?: {
    [modelId: string]: {
      inputCostPer1k: number;
      outputCostPer1k: number;
      description?: string;
    };
  };
  
  // LiteLLM API Integration - Third-party model provider credentials
  /** OpenAI API key for GPT models via LiteLLM */
  openaiApiKey?: string;
  /** Anthropic API key for Claude models via LiteLLM */
  anthropicApiKey?: string;
  /** Cohere API key for Command models via LiteLLM */
  cohereApiKey?: string;
  
  // Docker Container Execution Configuration
  /** Docker image name for assessment execution */
  dockerImage: string;
  /** Container execution timeout in seconds */
  dockerTimeout: number;
  /** Additional volume mounts for container access */
  volumes?: string[];
  
  // Security Assessment Execution Parameters
  /** Maximum tool executions before automatic termination */
  iterations: number;
  /** Automatically approve tool executions without user confirmation */
  autoApprove: boolean;
  /** Enable interactive tool confirmation prompts (inverse of autoApprove) */
  confirmations: boolean;
  /** Maximum concurrent assessment threads */
  maxThreads: number;
  /** Output report format preference */
  outputFormat: 'markdown' | 'json' | 'html';
  /** Enable detailed debug logging and verbose output */
  verbose: boolean;
  
  // Execution Configuration  
  /** Preferred execution mode for assessments */
  executionMode?: 'python-cli' | 'docker-single' | 'docker-stack';
  /** Allow fallback to other execution modes if preferred is unavailable */
  allowExecutionFallback: boolean;
  
  // Memory Settings
  memoryPath?: string; // Path to existing FAISS memory store to load
  memoryMode: 'auto' | 'fresh'; // Memory initialization mode
  keepMemory: boolean; // Keep memory data after operation completes
  memoryBackend: 'FAISS' | 'mem0' | 'opensearch'; // Memory storage backend
  mem0ApiKey?: string; // Mem0 Platform API key
  opensearchHost?: string; // OpenSearch host URL
  opensearchUsername?: string;
  opensearchPassword?: string;
  
  // Output Settings
  outputDir: string; // Base directory for output artifacts
  unifiedOutput: boolean; // Enable unified output directory structure
  
  // UI Settings
  theme: 'default' | 'dark' | 'light' | 'hacker' | 'retro';
  showMemoryUsage: boolean;
  showOperationId: boolean; // Show operation ID in UI
  
  // Environment Variables
  environment: Record<string, string>;
  
  // Report Settings
  reportSettings: {
    includeRemediation: boolean;
    includeCWE: boolean;
    includeTimestamps: boolean;
    includeEvidence: boolean;
    includeMemoryOps: boolean;
  };
  
  // Observability Settings
  observability: boolean; // Enable observability with Langfuse
  langfuseHost?: string;
  langfuseHostOverride?: boolean; // Force use of langfuseHost even in Docker
  langfusePublicKey?: string;
  langfuseSecretKey?: string;
  langfuseEncryptionKey?: string;
  langfuseSalt?: string;
  enableLangfusePrompts?: boolean; // Enable Langfuse prompt management
  langfusePromptLabel?: string; // Prompt label (production, staging, dev)
  langfusePromptCacheTTL?: number; // Cache TTL in seconds
  
  // Evaluation Settings
  autoEvaluation: boolean; // Enable automatic evaluation after operations
  evaluationBatchSize?: number; // Number of items per evaluation batch
  minToolAccuracyScore?: number;
  minEvidenceQualityScore?: number;
  minAnswerRelevancyScore?: number;
  minContextPrecisionScore?: number;
  // LLM-driven evaluation tunables
  minToolCalls?: number;
  minEvidence?: number;
  evalMaxWaitSecs?: number;
  evalPollIntervalSecs?: number;
  evalSummaryMaxChars?: number;
  
  // Setup Status
  isConfigured: boolean;
  hasSeenWelcome?: boolean; // Track if user has seen welcome tutorial
  deploymentMode?: 'local-cli' | 'single-container' | 'full-stack'; // Selected deployment mode
  
  // Backward compatibility
  enableObservability?: boolean; // Deprecated, use observability instead
  updateChannel?: string; // Update channel for future use
}

/**
 * Configuration Context Interface - Provider Methods
 * 
 * Defines the complete API for configuration management including
 * CRUD operations, persistence, and validation.
 */
interface ConfigContextType {
  /** Current configuration state with all settings */
  config: Config;
  /** Whether the config is still loading from disk */
  isConfigLoading: boolean;
  /** Update configuration with partial changes (supports deep merge) */
  updateConfig: (updates: Partial<Config>) => void;
  /** Persist current configuration to user's home directory */
  saveConfig: () => Promise<void>;
  /** Load configuration from persistent storage */
  loadConfig: () => Promise<void>;
  /** Reset all settings to application defaults */
  resetToDefaults: () => void;
}

// Get deployment-aware defaults for observability settings
const deploymentDefaults = getDeploymentDefaults();

export const defaultConfig: Config = {
  // Model Provider Settings
  modelProvider: 'bedrock',
  modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
  embeddingModel: 'amazon.titan-embed-text-v2:0',
  evaluationModel: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
  swarmModel: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
  awsRegion: process.env.AWS_REGION || 'us-east-1',
  awsBearerToken: process.env.AWS_BEARER_TOKEN_BEDROCK,
  awsAccessKeyId: process.env.AWS_ACCESS_KEY_ID,
  awsSecretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  awsSessionToken: process.env.AWS_SESSION_TOKEN,
  ollamaHost: process.env.OLLAMA_HOST || 'http://localhost:11434',
  
  // Model Pricing (per 1K tokens)
  // AWS Bedrock: Real AWS CLI pricing from us-east-1
  // Ollama: Free local models (0 cost)
  modelPricing: {
    // Ollama Models (Free - local execution)
    'qwen3-coder:30b-a3b-q4_K_M': {
      inputCostPer1k: 0,
      outputCostPer1k: 0,
      description: 'Qwen3 Coder 30B - Advanced coding model, Local Ollama (free)'
    },
    'qwen3:1.7b': {
      inputCostPer1k: 0,
      outputCostPer1k: 0,
      description: 'Qwen3 1.7B - Small fast model, Local Ollama (free)'
    },
    'llama3.2:3b': {
      inputCostPer1k: 0,
      outputCostPer1k: 0,
      description: 'Llama 3.2 3B - Local Ollama model (free)'
    },
    'mxbai-embed-large': {
      inputCostPer1k: 0,
      outputCostPer1k: 0,
      description: 'MXBAI Embeddings - Local Ollama model (free)'
    },
    // Anthropic Claude Models (Verified AWS CLI pricing)
    'us.anthropic.claude-sonnet-4-20250514-v1:0': {
      inputCostPer1k: 0.006,
      outputCostPer1k: 0.030,
      description: 'Claude Sonnet 4 - Advanced reasoning with thinking mode (AWS verified pricing)'
    },
    'us.anthropic.claude-opus-4-1-20250805-v1:0': {
      inputCostPer1k: 0.015,
      outputCostPer1k: 0.075,
      description: 'Claude Opus 4.1 - Flagship model with advanced thinking capabilities'
    },
    'claude-3-5-sonnet-20241022-v2:0': {
      inputCostPer1k: 0.003,
      outputCostPer1k: 0.015,
      description: 'Claude 3.5 Sonnet v2 - High performance (5x output cost)'
    },
    'claude-3-5-sonnet-20240620-v1:0': {
      inputCostPer1k: 0.003,
      outputCostPer1k: 0.015,
      description: 'Claude 3.5 Sonnet v1 - Previous generation (5x output cost)'
    },
    'claude-3-haiku-20240307-v1:0': {
      inputCostPer1k: 0.00025, // AWS CLI verified: $0.00025 per 1K input tokens
      outputCostPer1k: 0.00125, // Standard 5x multiplier for output tokens
      description: 'Claude 3 Haiku - Fast, cost-effective (AWS CLI verified)'
    },
    'claude-3-sonnet-20240229-v1:0': {
      inputCostPer1k: 0.003, // AWS CLI verified: $0.003 per 1K input tokens
      outputCostPer1k: 0.015, // Standard 5x multiplier for output tokens
      description: 'Claude 3 Sonnet - Balanced performance (AWS CLI verified)'
    },
    'claude-3-opus-20240229-v1:0': {
      inputCostPer1k: 0.015,
      outputCostPer1k: 0.075,
      description: 'Claude 3 Opus - Maximum capability, highest cost (5x output cost)'
    },
    'anthropic.claude-v2': {
      inputCostPer1k: 0.008, // AWS CLI verified: $0.008 per 1K input tokens
      outputCostPer1k: 0.024, // Standard 3x multiplier for Claude v2
      description: 'Claude 2.0 - Previous generation (AWS CLI verified)'
    },
    'anthropic.claude-v2:1': {
      inputCostPer1k: 0.008, // AWS CLI verified: $0.008 per 1K input tokens  
      outputCostPer1k: 0.024, // Standard 3x multiplier for Claude v2.1
      description: 'Claude 2.1 - Previous generation (AWS CLI verified)'
    },
    'anthropic.claude-instant-v1': {
      inputCostPer1k: 0.0008, // AWS CLI verified: $0.0008 per 1K input tokens
      outputCostPer1k: 0.0024, // Standard 3x multiplier for Claude Instant
      description: 'Claude Instant - Fast, lightweight (AWS CLI verified)'
    },
    // Meta Llama Models (Standard AWS Bedrock pricing)
    'meta.llama3-1-405b-instruct-v1:0': {
      inputCostPer1k: 0.00532,
      outputCostPer1k: 0.016,
      description: 'Llama 3.1 405B - Open source, high capability'
    },
    'meta.llama3-1-70b-instruct-v1:0': {
      inputCostPer1k: 0.00099,
      outputCostPer1k: 0.00297,
      description: 'Llama 3.1 70B - Balanced performance and cost'
    },
    'meta.llama3-1-8b-instruct-v1:0': {
      inputCostPer1k: 0.0003,
      outputCostPer1k: 0.0006,
      description: 'Llama 3.1 8B - Fast and efficient'
    },
    // Amazon Titan Models
    'amazon.titan-text-premier-v1:0': {
      inputCostPer1k: 0.0005,
      outputCostPer1k: 0.0015,
      description: 'Amazon Titan Text Premier - AWS native'
    },
    'amazon.titan-text-express-v1': {
      inputCostPer1k: 0.0002,
      outputCostPer1k: 0.0006,
      description: 'Amazon Titan Text Express - Fast, cost-effective'
    },
    // Cohere Models
    'cohere.command-r-plus-v1:0': {
      inputCostPer1k: 0.003,
      outputCostPer1k: 0.015,
      description: 'Cohere Command R+ - Enterprise RAG optimized'
    },
    'cohere.command-r-v1:0': {
      inputCostPer1k: 0.0005,
      outputCostPer1k: 0.0015,
      description: 'Cohere Command R - Balanced RAG performance'
    }
  },
  
  // LiteLLM API Keys
  openaiApiKey: process.env.OPENAI_API_KEY,
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  cohereApiKey: process.env.COHERE_API_KEY,
  
  // Docker Settings
  dockerImage: 'cyber-autoagent:latest',
  dockerTimeout: 300,
  volumes: [],
  
  // Assessment Settings
  iterations: 100, // Default from original Python CLI
  autoApprove: true, // Default to auto-approve (bypass confirmations)
  confirmations: false, // Default to disabled confirmations
  maxThreads: 10,
  outputFormat: 'markdown',
  verbose: false, // Default to non-verbose mode
  
  // Execution Configuration
  executionMode: undefined, // Auto-select based on availability
  allowExecutionFallback: true, // Allow fallback modes by default
  
  // Memory Settings
  memoryPath: undefined, // No existing memory path by default
  memoryMode: 'auto', // Auto-load existing memory if found
  keepMemory: true, // Keep memory data after operation (default from Python CLI)
  memoryBackend: 'FAISS', // Default to local FAISS
  mem0ApiKey: process.env.MEM0_API_KEY,
  opensearchHost: process.env.OPENSEARCH_HOST,
  opensearchUsername: process.env.OPENSEARCH_USERNAME,
  opensearchPassword: process.env.OPENSEARCH_PASSWORD,
  
  // Output Settings
  outputDir: './outputs', // Default base directory for output artifacts
  unifiedOutput: true, // Enable unified output by default
  
  // UI Settings
  theme: 'retro', // Default to retro theme for 80s aesthetic
  showMemoryUsage: false,
  showOperationId: true, // Show operation ID for tracking
  
  // Environment Variables
  environment: {},
  
  // Report Settings
  reportSettings: {
    includeRemediation: true,
    includeCWE: true,
    includeTimestamps: true,
    includeEvidence: true, // Include evidence in reports
    includeMemoryOps: true // Include memory operations in reports
  },
  
  // Observability Settings - deployment-aware defaults
  observability: deploymentDefaults.observabilityDefault || false, // Smart defaults based on deployment mode
  langfuseHost: process.env.LANGFUSE_HOST || deploymentDefaults.langfuseHost || 'http://localhost:3000',
  langfuseHostOverride: false, // Let container auto-detect by default
  langfusePublicKey: process.env.LANGFUSE_PUBLIC_KEY || 'cyber-public',
  langfuseSecretKey: process.env.LANGFUSE_SECRET_KEY || 'cyber-secret',
  langfuseEncryptionKey: process.env.LANGFUSE_ENCRYPTION_KEY,
  langfuseSalt: process.env.LANGFUSE_SALT,
  enableLangfusePrompts: deploymentDefaults.observabilityDefault || false,
  langfusePromptLabel: 'production',
  langfusePromptCacheTTL: 300,
  
  // Evaluation Settings - deployment-aware defaults  
  autoEvaluation: deploymentDefaults.evaluationDefault || false, // Smart defaults based on deployment mode
  evaluationBatchSize: 5,
  minToolAccuracyScore: 0.8,
  minEvidenceQualityScore: 0.7,
  minAnswerRelevancyScore: 0.7,
  minContextPrecisionScore: 0.8,
  // LLM-driven evaluation tunables (UI defaults)
  minToolCalls: 3,
  minEvidence: 1,
  evalMaxWaitSecs: 30,
  evalPollIntervalSecs: 5,
  evalSummaryMaxChars: 8000,
  
  // Setup Status
  isConfigured: false,
  deploymentMode: 'local-cli' // Default to Local CLI for minimal setup
};

const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

/**
 * ConfigProvider - Enterprise Configuration Management Provider
 * 
 * Wraps the application with centralized configuration management including
 * persistence, validation, and deployment-aware defaults.
 * 
 * Automatically loads configuration on mount and provides methods for
 * real-time updates with immediate persistence.
 */
export const ConfigProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<Config>(defaultConfig);
  const [isConfigLoading, setIsConfigLoading] = useState(true);
  const configFilePath = useMemo(() => path.join(os.homedir(), '.cyber-autoagent', 'config.json'), []);

  // Use a ref to get the latest config in callbacks without adding a dependency
  const configRef = useRef(config);
  useEffect(() => {
    configRef.current = config;
  }, [config]);

  const deepMerge = (target: any, source: any) => {
    const output = { ...target };
    if (target && typeof target === 'object' && source && typeof source === 'object') {
      Object.keys(source).forEach(key => {
        const value = (source as any)[key];
        // Skip undefined so defaults are preserved
        if (value === undefined) {
          return;
        }
        if (value && typeof value === 'object' && !Array.isArray(value) && key in target) {
          (output as any)[key] = deepMerge((target as any)[key], value);
        } else {
          (output as any)[key] = value;
        }
      });
    }
    return output;
  };

  const updateConfig = useCallback((updates: Partial<Config>) => {
    setConfig(prevConfig => {
      const next = deepMerge(prevConfig, updates);
      // Keep ref in sync immediately so saveConfig sees latest values
      configRef.current = next;
      return next;
    });
  }, []);

  // Persist confirmations/autoApprove changes immediately to survive app restarts
  useEffect(() => {
    (async () => {
      try {
        // Only persist when confirmations or autoApprove change to avoid excessive writes
        // Compare with ref to avoid writing on initial load
        const prev = configRef.current;
        if (prev.confirmations !== config.confirmations || prev.autoApprove !== config.autoApprove) {
          await fs.mkdir(path.dirname(configFilePath), { recursive: true });
          await fs.writeFile(configFilePath, JSON.stringify(config, null, 2));
          loggingService.info('Persisted confirmations/autoApprove to:', configFilePath);
        }
      } catch (e) {
        loggingService.warn?.('Non-fatal: failed to persist confirmations/autoApprove', e);
      }
    })();
  }, [config.confirmations, config.autoApprove, configFilePath]);

  const saveConfig = useCallback(async () => {
    try {
      await fs.mkdir(path.dirname(configFilePath), { recursive: true });
      // Always save the most up-to-date config from ref to avoid stale writes
      await fs.writeFile(configFilePath, JSON.stringify(configRef.current, null, 2));
      loggingService.info('Config saved successfully to:', configFilePath);
    } catch (error) {
      loggingService.error('Failed to save config:', error);
      throw error; // Re-throw so ConfigEditor can show error message
    }
  }, [configFilePath]);

  const loadConfig = useCallback(async () => {
    setIsConfigLoading(true);
    try {
      const data = await fs.readFile(configFilePath, 'utf-8');
      const loadedConfig = JSON.parse(data);

      // Preserve saved confirmations/autoApprove exactly as-is
      if (loadedConfig.confirmations !== undefined) {
        // no-op, will be merged below
      }
      if (loadedConfig.autoApprove !== undefined) {
        // no-op, will be merged below
      }
      
      // Apply deployment-aware defaults for observability and evaluation
      const deploymentMode = loadedConfig.deploymentMode || 'local-cli';
      if ((deploymentMode === 'local-cli' || deploymentMode === 'single-container')) {
        // Default to disabled for local/single-container modes unless explicitly set
        if (loadedConfig.observability === undefined) {
          loadedConfig.observability = false;
        }
        if (loadedConfig.autoEvaluation === undefined) {
          loadedConfig.autoEvaluation = false;
        }
      }
      
      // For sensitive fields like passwords/tokens, respect the saved value
      // even if it's empty. Don't let env vars override explicitly saved empty values.
      // Only use env vars as defaults when the field is undefined (not saved).
      if (loadedConfig.awsBearerToken === '') {
        // User explicitly saved an empty bearer token, keep it empty
        loadedConfig.awsBearerToken = '';
      }
      if (loadedConfig.awsAccessKeyId === '') {
        loadedConfig.awsAccessKeyId = '';
      }
      if (loadedConfig.awsSecretAccessKey === '') {
        loadedConfig.awsSecretAccessKey = '';
      }
      
      setConfig(prev => deepMerge(prev, loadedConfig));
    } catch (error) {
      // If the file doesn't exist or is invalid, we just use the default config
    } finally {
      setIsConfigLoading(false);
    }
  }, [configFilePath]);

  const validateAndLoadConfig = useCallback(async () => {
    setIsConfigLoading(true);
    let loadedConfig: Partial<Config> = {};
    try {
      const data = await fs.readFile(configFilePath, 'utf-8');
      loadedConfig = JSON.parse(data);
    } catch (error) {
      // File not found or invalid, proceed with defaults
    }

    const detector = DeploymentDetector.getInstance();
    detector.clearCache(); // Always get fresh data on startup
    const liveDeployments = await detector.detectDeployments(loadedConfig as Config);
    const configuredMode = loadedConfig.deploymentMode;

    if (configuredMode) {
      const isModeHealthy = liveDeployments.availableDeployments.find(
        d => d.mode === configuredMode && d.isHealthy
      );

      if (!isModeHealthy) {
        // The configured deployment is not active. Invalidate it.
        delete loadedConfig.deploymentMode;
        loadedConfig.isConfigured = false; // Force setup
      }
    }
    
    // Apply deployment-aware defaults for observability and evaluation
    const deploymentMode = loadedConfig.deploymentMode || 'local-cli';
    if ((deploymentMode === 'local-cli' || deploymentMode === 'single-container')) {
      // Default to disabled for local/single-container modes unless explicitly set
      if (loadedConfig.observability === undefined) {
        loadedConfig.observability = false;
      }
      if (loadedConfig.autoEvaluation === undefined) {
        loadedConfig.autoEvaluation = false;
      }
    }

    setConfig(prev => deepMerge(prev, loadedConfig));
    setIsConfigLoading(false);
  }, [configFilePath]);

  const resetToDefaults = useCallback(() => {
    setConfig(defaultConfig);
  }, []);

  // Load and validate configuration on component mount
  useEffect(() => {
    validateAndLoadConfig();
  }, [validateAndLoadConfig]);

  const contextValue = useMemo(() => ({
    config,
    isConfigLoading,
    updateConfig,
    saveConfig,
    loadConfig,
    validateAndLoadConfig,
    resetToDefaults,
  }), [config, isConfigLoading, updateConfig, saveConfig, loadConfig, validateAndLoadConfig, resetToDefaults]);

  return (
    <ConfigContext.Provider value={contextValue}>
      {children}
    </ConfigContext.Provider>
  );
};

/**
 * useConfig Hook - Configuration Access and Management
 * 
 * Custom React hook for accessing configuration state and methods.
 * Must be used within a ConfigProvider component tree.
 * 
 * @returns {ConfigContextType} Complete configuration API
 * @throws {Error} When used outside of ConfigProvider
 * 
 * @example
 * ```tsx
 * const { config, updateConfig, saveConfig } = useConfig();
 * 
 * // Update model provider
 * updateConfig({ modelProvider: 'ollama' });
 * 
 * // Persist changes
 * await saveConfig();
 * ```
 */
export const useConfig = (): ConfigContextType => {
  const configurationContext = useContext(ConfigContext);
  if (!configurationContext) {
    throw new Error('useConfig hook must be used within a ConfigProvider component. Ensure your component is wrapped with <ConfigProvider>.');
  }
  return configurationContext;
};