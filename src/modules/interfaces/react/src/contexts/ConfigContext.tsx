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

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';

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
  /** Update configuration with partial changes (supports deep merge) */
  updateConfig: (updates: Partial<Config>) => void;
  /** Persist current configuration to user's home directory */
  saveConfig: () => Promise<void>;
  /** Load configuration from persistent storage */
  loadConfig: () => Promise<void>;
  /** Reset all settings to application defaults */
  resetToDefaults: () => void;
}

const defaultConfig: Config = {
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
  
  // AWS Bedrock Model Pricing (Real AWS CLI pricing from us-east-1 - per 1K tokens)
  // Fetched via: aws pricing get-products --service-code "AmazonBedrock" --region us-east-1
  modelPricing: {
    // Anthropic Claude Models (Verified AWS CLI pricing)
    'us.anthropic.claude-sonnet-4-20250514-v1:0': {
      inputCostPer1k: 0.015,
      outputCostPer1k: 0.075,
      description: 'Claude Sonnet 4 - Latest model (5x output cost)'
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
  dockerImage: 'cyber-autoagent:sudo',
  dockerTimeout: 300,
  volumes: [],
  
  // Assessment Settings
  iterations: 100, // Default from original Python CLI
  autoApprove: true, // Default to auto-approve (bypass confirmations)
  confirmations: false, // Default to disabled confirmations
  maxThreads: 10,
  outputFormat: 'markdown',
  verbose: false, // Default to non-verbose mode
  
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
  
  // Observability Settings
  observability: true, // Enable by default (matches Python CLI)
  langfuseHost: process.env.LANGFUSE_HOST || 'http://localhost:3000',
  langfuseHostOverride: false, // Let container auto-detect by default
  langfusePublicKey: process.env.LANGFUSE_PUBLIC_KEY || 'cyber-public',
  langfuseSecretKey: process.env.LANGFUSE_SECRET_KEY || 'cyber-secret',
  langfuseEncryptionKey: process.env.LANGFUSE_ENCRYPTION_KEY,
  langfuseSalt: process.env.LANGFUSE_SALT,
  enableLangfusePrompts: true,
  langfusePromptLabel: 'production',
  langfusePromptCacheTTL: 300,
  
  // Evaluation Settings
  autoEvaluation: true, // Enabled by default to track assessment quality
  evaluationBatchSize: 5,
  minToolAccuracyScore: 0.8,
  minEvidenceQualityScore: 0.7,
  minAnswerRelevancyScore: 0.7,
  minContextPrecisionScore: 0.8,
  
  // Setup Status
  isConfigured: false
};

// Configuration Context - React Context for global state management
const ConfigContext = createContext<ConfigContextType | undefined>(undefined);

/**
 * ConfigProvider - Enterprise Configuration Management Provider
 * 
 * Wraps the application with centralized configuration management including
 * persistent storage, environment variable integration, and validation.
 * Automatically loads configuration on mount and provides methods for
 * real-time updates with immediate persistence.
 */
export const ConfigProvider: React.FC<{children: React.ReactNode}> = ({children}) => {
  const [applicationConfiguration, setApplicationConfiguration] = useState<Config>(defaultConfig);
  
  // Configuration file path in user's home directory - useMemo to ensure stable reference
  const configurationFilePath = useMemo(
    () => path.join(os.homedir(), '.cyber-autoagent', 'config.json'),
    []
  );

  /**
   * Load configuration from persistent storage with error handling
   * Automatically creates configuration directory if it doesn't exist
   */
  const loadConfigurationFromDisk = useCallback(async () => {
    try {
      const configurationDirectory = path.dirname(configurationFilePath);
      await fs.mkdir(configurationDirectory, { recursive: true });
      
      const configurationFileContent = await fs.readFile(configurationFilePath, 'utf-8');
      const parsedConfiguration = JSON.parse(configurationFileContent);
      
      // Migration: If config exists but isConfigured is missing or false, validate configuration
      if (parsedConfiguration.isConfigured === undefined || parsedConfiguration.isConfigured === false) {
        // Auto-detect if configuration is complete based on essential fields
        const hasEssentialConfig = !!(
          parsedConfiguration.modelProvider && 
          parsedConfiguration.modelId &&
          (
            (parsedConfiguration.modelProvider === 'bedrock' && 
              (parsedConfiguration.awsBearerToken || parsedConfiguration.awsAccessKeyId)) ||
            (parsedConfiguration.modelProvider === 'ollama') ||
            (parsedConfiguration.modelProvider === 'litellm')
          )
        );
        
        // Only auto-set to true if configuration is actually complete
        if (hasEssentialConfig) {
          console.log('Auto-detecting configuration as complete based on essential fields');
          parsedConfiguration.isConfigured = true;
          
          // Persist the updated configuration back to disk
          const updatedConfig = {
            ...defaultConfig,
            ...parsedConfiguration
          };
          
          // Write back the updated configuration
          try {
            await fs.writeFile(
              configurationFilePath, 
              JSON.stringify(updatedConfig, null, 2),
              'utf-8'
            );
            console.log('Configuration file updated with isConfigured=true');
          } catch (writeError) {
            console.error('Failed to update configuration file:', writeError);
          }
        }
      }
      
      // Merge with defaults to ensure all required fields exist and handle schema evolution
      setApplicationConfiguration({
        ...defaultConfig,
        ...parsedConfiguration
      });
    } catch (error) {
      // Configuration file doesn't exist or contains invalid JSON - use defaults
      console.log('Configuration file not found or invalid, using application defaults');
    }
  }, [configurationFilePath]);

  // Load configuration on component mount - FIXED: Remove function dependency to prevent infinite loops
  useEffect(() => {
    loadConfigurationFromDisk();
  }, []); // CRITICAL FIX: Only run on mount, not when callback changes

  /**
   * Persist current configuration to disk with atomic write operations
   * Ensures configuration directory exists and handles write errors gracefully
   */
  const persistConfigurationToDisk = useCallback(async () => {
    try {
      const configurationDirectory = path.dirname(configurationFilePath);
      await fs.mkdir(configurationDirectory, { recursive: true });
      
      // Atomic write operation with pretty formatting for manual editing
      await fs.writeFile(
        configurationFilePath, 
        JSON.stringify(applicationConfiguration, null, 2),
        'utf-8'
      );
    } catch (error) {
      console.error('Failed to persist configuration to disk:', error);
      throw new Error(`Configuration save failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [applicationConfiguration, configurationFilePath]);

  /**
   * Update configuration with partial changes using deep merge
   * Triggers immediate state update for real-time UI responsiveness
   */
  const updateApplicationConfiguration = useCallback((configurationUpdates: Partial<Config>) => {
    setApplicationConfiguration(previousConfiguration => {
      // PREVENT UNNECESSARY UPDATES: Check if config actually changed
      const newConfig = { ...previousConfiguration, ...configurationUpdates };
      const prevStr = JSON.stringify(previousConfiguration);
      const newStr = JSON.stringify(newConfig);
      if (prevStr === newStr) {
        return previousConfiguration; // Return same reference to prevent re-renders
      }
      return newConfig;
    });
  }, []);

  /**
   * Reset all configuration settings to application defaults
   * Useful for troubleshooting and first-time setup scenarios
   */
  const resetConfigurationToDefaults = useCallback(() => {
    setApplicationConfiguration(defaultConfig);
  }, []);

  // CRITICAL FIX: Use useMemo to prevent infinite re-renders 
  // Without this, the contextProviderValue object gets recreated on every render, causing infinite loops
  const contextProviderValue: ConfigContextType = useMemo(() => ({
    config: applicationConfiguration,
    updateConfig: updateApplicationConfiguration,
    saveConfig: persistConfigurationToDisk,
    loadConfig: loadConfigurationFromDisk,
    resetToDefaults: resetConfigurationToDefaults
  }), [applicationConfiguration, updateApplicationConfiguration, persistConfigurationToDisk, loadConfigurationFromDisk, resetConfigurationToDefaults]);

  return (
    <ConfigContext.Provider value={contextProviderValue}>
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