/**
 * Configuration Editor
 * 
 * Expandable sections with inline editing for application configuration.
 * Features hierarchical navigation and real-time validation.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import SelectInput from 'ink-select-input';
import TextInput, { UncontrolledTextInput } from 'ink-text-input';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { Header } from './Header.js';
import { loggingService } from '../services/LoggingService.js';
import { PasswordInput } from './PasswordInput.js';
import { TokenInput } from './TokenInput.js';

interface ConfigEditorProps {
  onClose: () => void;
}

type EditingField = {
  field: string;
  type: 'text' | 'number' | 'boolean' | 'select';
  options?: Array<{label: string; value: string}>;
} | null;

interface ConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'password';
  options?: Array<{label: string; value: string}>;
  description?: string;
  section: string;
  required?: boolean;
}

interface ConfigSection {
  name: string;
  label: string;
  description: string;
  expanded: boolean;
}

// Define all configuration fields with their metadata
const CONFIG_FIELDS: ConfigField[] = [
  // Models - Primary configuration
  { key: 'modelProvider', label: 'Model Provider', type: 'select', section: 'Models', required: true,
    options: [
      { label: 'AWS Bedrock', value: 'bedrock' },
      { label: 'Ollama (Local)', value: 'ollama' },
      { label: 'LiteLLM', value: 'litellm' }
    ]
  },
  { key: 'modelId', label: 'Primary Model', type: 'text', section: 'Models', required: true },
  { key: 'embeddingModel', label: 'Embedding Model', type: 'text', section: 'Models' },
  { key: 'evaluationModel', label: 'Evaluation Model', type: 'text', section: 'Models' },
  { key: 'swarmModel', label: 'Swarm Model', type: 'text', section: 'Models' },
  
  // Models - Credentials (shown in Models section based on provider)
  { key: 'awsAccessKeyId', label: 'AWS Access Key ID', type: 'password', section: 'Models' },
  { key: 'awsSecretAccessKey', label: 'AWS Secret Access Key', type: 'password', section: 'Models' },
  { key: 'awsBearerToken', label: 'AWS Bearer Token', type: 'password', section: 'Models' },
  { key: 'awsRegion', label: 'AWS Region', type: 'text', section: 'Models' },
  { key: 'ollamaHost', label: 'Ollama Host', type: 'text', section: 'Models' },
  { key: 'openaiApiKey', label: 'OpenAI API Key', type: 'password', section: 'Models' },
  { key: 'anthropicApiKey', label: 'Anthropic API Key', type: 'password', section: 'Models' },
  { key: 'geminiApiKey', label: 'Gemini API Key', type: 'password', section: 'Models' },
  { key: 'xaiApiKey', label: 'X.AI API Key', type: 'password', section: 'Models' },
  { key: 'cohereApiKey', label: 'Cohere API Key', type: 'password', section: 'Models' },
  { key: 'azureApiKey', label: 'Azure API Key', type: 'password', section: 'Models' },
  { key: 'azureApiBase', label: 'Azure API Base', type: 'text', section: 'Models' },
  { key: 'azureApiVersion', label: 'Azure API Version', type: 'text', section: 'Models' },
  { key: 'temperature', label: 'Temperature (optional)', type: 'number', section: 'Models',
    description: 'Sampling temperature (0.0-2.0). Leave as Auto for provider defaults.' },
  { key: 'maxTokens', label: 'Max Output Tokens (optional)', type: 'number', section: 'Models',
    description: 'Leave as Auto for provider/model defaults.' },
  { key: 'topP', label: 'Top P (optional)', type: 'number', section: 'Models',
    description: 'Nucleus sampling (0.0-1.0). Leave as Auto. Note: Anthropic requires temperature OR top_p, not both.' },
  { key: 'thinkingBudget', label: 'Thinking Budget (optional)', type: 'number', section: 'Models',
    description: 'Claude thinking models only. Leave as Auto for model defaults.' },
  { key: 'reasoningEffort', label: 'Reasoning Effort (optional)', type: 'select', section: 'Models',
    description: 'OpenAI O1/GPT-5 only. Leave as Auto for default.',
    options: [
      { label: 'Auto', value: '' },
      { label: 'Low', value: 'low' },
      { label: 'Medium', value: 'medium' },
      { label: 'High', value: 'high' }
    ]
  },
  { key: 'maxCompletionTokens', label: 'Max Completion Tokens (optional)', type: 'number', section: 'Models',
    description: 'OpenAI O1/GPT-5 only. Leave as Auto for default.' },

  // Operations (renamed from Assessment)
  { key: 'iterations', label: 'Max Iterations', type: 'number', section: 'Operations' },
  { key: 'autoApprove', label: 'Auto-Approve Tools', type: 'boolean', section: 'Operations' },
  { key: 'maxThreads', label: 'Max Threads', type: 'number', section: 'Operations' },
  { key: 'dockerTimeout', label: 'Docker Timeout (s)', type: 'number', section: 'Operations' },
  { key: 'verbose', label: 'Verbose Output', type: 'boolean', section: 'Operations' },
  
  // Memory
  { key: 'memoryBackend', label: 'Memory Backend', type: 'select', section: 'Memory',
    options: [
      { label: 'FAISS (Local)', value: 'FAISS' },
      { label: 'Mem0 Platform', value: 'mem0' },
      { label: 'OpenSearch', value: 'opensearch' }
    ]
  },
  { key: 'keepMemory', label: 'Keep Memory After Operations', type: 'boolean', section: 'Memory' },
  { key: 'mem0ApiKey', label: 'Mem0 API Key', type: 'password', section: 'Memory' },
  { key: 'opensearchHost', label: 'OpenSearch Host', type: 'text', section: 'Memory' },
  
  // Observability
  { key: 'observability', label: 'Enable Remote Observability', type: 'boolean', section: 'Observability',
    description: 'Export traces to Langfuse. Requires Langfuse infrastructure. Auto-detected based on deployment mode. Token counting always enabled.' },
  { key: 'langfuseHost', label: 'Langfuse Host', type: 'text', section: 'Observability' },
  { key: 'langfusePublicKey', label: 'Langfuse Public Key', type: 'password', section: 'Observability' },
  { key: 'langfuseSecretKey', label: 'Langfuse Secret Key', type: 'password', section: 'Observability' },
  { key: 'enableLangfusePrompts', label: 'Enable Prompt Management', type: 'boolean', section: 'Observability' },
  
  // Evaluation
  { key: 'autoEvaluation', label: 'Auto-Evaluation', type: 'boolean', section: 'Evaluation',
    description: 'Requires Langfuse infrastructure for Ragas metrics. Auto-detected based on deployment mode.' },
  { key: 'minToolAccuracyScore', label: 'Min Tool Accuracy', type: 'number', section: 'Evaluation' },
  { key: 'minEvidenceQualityScore', label: 'Min Evidence Quality', type: 'number', section: 'Evaluation' },
  { key: 'minAnswerRelevancyScore', label: 'Min Answer Relevancy', type: 'number', section: 'Evaluation' },
  
  // Dynamic Pricing - Current Model pricing (populated based on active modelId)
  { key: 'currentModel.inputCostPer1k', 
    label: 'Current Model - Input Cost (per 1K tokens)', type: 'number', section: 'Pricing',
    description: 'Cost per 1000 input tokens for your selected model' },
  { key: 'currentModel.outputCostPer1k', 
    label: 'Current Model - Output Cost (per 1K tokens)', type: 'number', section: 'Pricing',
    description: 'Cost per 1000 output tokens for your selected model' },
  
  // Output
  { key: 'outputDir', label: 'Output Directory', type: 'text', section: 'Output' },
  { key: 'outputFormat', label: 'Output Format', type: 'select', section: 'Output',
    options: [
      { label: 'Markdown', value: 'markdown' },
      { label: 'JSON', value: 'json' },
      { label: 'HTML', value: 'html' }
    ]
  },
  { key: 'unifiedOutput', label: 'Unified Output Structure', type: 'boolean', section: 'Output' }
];

const SECTIONS: ConfigSection[] = [
  { name: 'Models', label: 'Models & Credentials', description: 'AI provider and authentication', expanded: false },
  { name: 'Operations', label: 'Operations', description: 'Execution parameters', expanded: false },
  { name: 'Memory', label: 'Memory', description: 'Vector storage configuration', expanded: false },
  { name: 'Observability', label: 'Observability', description: 'Remote tracing (auto-detected, token counting always enabled)', expanded: false },
  { name: 'Evaluation', label: 'Evaluation', description: 'Quality assessment with Ragas (auto-detected)', expanded: false },
  { name: 'Pricing', label: 'Model Pricing', description: 'Token cost configuration per 1K tokens', expanded: false },
  { name: 'Output', label: 'Output', description: 'Report and logging', expanded: false }
];

/**
 * Detect model capabilities based on model ID
 * Simple pattern matching - easily extensible for new models
 */
const getModelCapabilities = (modelId: string | undefined) => {
  if (!modelId) return { hasThinking: false, hasReasoning: false, requiresTemp1: false };

  const id = modelId.toLowerCase();

  // Thinking models (Claude extended thinking with THINKING_BUDGET)
  const hasThinking =
    id.includes('claude-sonnet-4-5') ||
    id.includes('claude-sonnet-4-20') ||
    id.includes('claude-opus-4');

  // Reasoning models (OpenAI O1/GPT-5 with REASONING_EFFORT)
  const hasReasoning =
    id.includes('o1-') ||
    id.includes('o3-') ||
    id.includes('gpt-5') ||
    id.includes('reasoning');

  // Models that require temperature=1.0 exactly (Claude thinking + OpenAI reasoning)
  const requiresTemp1 = hasThinking || hasReasoning;

  return { hasThinking, hasReasoning, requiresTemp1 };
};

export const ConfigEditor: React.FC<ConfigEditorProps> = ({ onClose }) => {
  const { config, updateConfig, saveConfig } = useConfig();
  const theme = themeManager.getCurrentTheme();
  
  const [sections, setSections] = useState(SECTIONS);
  const [selectedSectionIndex, setSelectedSectionIndex] = useState(0);
  const [selectedFieldIndex, setSelectedFieldIndex] = useState(0);
  const [editingField, setEditingField] = useState<EditingField>(null);
  const [tempValue, setTempValue] = useState('');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [navigationMode, setNavigationMode] = useState<'sections' | 'fields'>('sections');
  const [lastEscTime, setLastEscTime] = useState<number | null>(null);
  
  // Use ref to track timeout for cleanup
  const messageTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const messageIdRef = React.useRef(0);
  const messagePriorityRef = React.useRef(-1);
  const messageLockRef = React.useRef(0);
  
  // Use ref for handleSave to avoid stale closure issues
  const handleSaveRef = React.useRef<(() => void) | undefined>(undefined);
  
  // Use ref to protect message during saves
  const isSavingRef = React.useRef(false);
  

  // Screen clearing is handled by modal manager's refreshStatic()
  
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
    };
  }, []);

  const showMessage = useCallback((text: string, type: 'success' | 'error' | 'info', ttl = 3000) => {
    const priority = type === 'error' ? 2 : type === 'success' ? 1 : 0;
    const now = Date.now();
    if (messageLockRef.current > now && priority <= messagePriorityRef.current) {
      return;
    }
    if (messagePriorityRef.current > priority) {
      return;
    }
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current);
      messageTimeoutRef.current = null;
    }
    const nextId = messageIdRef.current + 1;
    messageIdRef.current = nextId;
    setMessage({ text, type });
    messagePriorityRef.current = priority;
    messageLockRef.current = ttl > 0 ? now + ttl : 0;
    if (ttl > 0) {
      messageTimeoutRef.current = setTimeout(() => {
        if (messageIdRef.current === nextId) {
          setMessage(null);
          messageTimeoutRef.current = null;
          messagePriorityRef.current = -1;
          messageLockRef.current = 0;
        }
      }, ttl);
    }
  }, []);
  
  // Auto-adjust observability and evaluation based on deployment mode
  useEffect(() => {
    const deploymentMode = config.deploymentMode;
    
    // For local-cli and single-container, default to disabled
    if (deploymentMode === 'local-cli' || deploymentMode === 'single-container') {
      // Only update if not explicitly set by user (check if still at default true values)
      if (config.observability === true && !config.langfuseHostOverride) {
        updateConfig({ observability: false });
        showMessage('Observability disabled for local/single-container mode', 'info');
      }
      if (config.autoEvaluation === true) {
        updateConfig({ autoEvaluation: false });
        showMessage('Auto-evaluation disabled for local/single-container mode', 'info');
      }
    }
    // For full-stack, these can remain enabled (user can still toggle)
  }, [config.deploymentMode, updateConfig, showMessage]);
  
  // Get fields for the current section
  const getCurrentSectionFields = useCallback(() => {
    const currentSection = sections[selectedSectionIndex];
    if (!currentSection?.expanded) return [];

    let fields = CONFIG_FIELDS.filter(f => f.section === currentSection.name);

    // Filter credentials based on provider
    if (currentSection.name === 'Models') {
      // Detect model capabilities
      const capabilities = getModelCapabilities(config.modelId);

      fields = fields.filter(f => {
        // Always show provider and model fields
        if (['modelProvider', 'modelId', 'embeddingModel', 'evaluationModel', 'swarmModel'].includes(f.key)) {
          return true;
        }

        // Model-specific advanced parameters (only show if model supports them)
        if (f.key === 'thinkingBudget' && !capabilities.hasThinking) return false;
        if (f.key === 'reasoningEffort' && !capabilities.hasReasoning) return false;
        if (f.key === 'maxCompletionTokens' && !capabilities.hasReasoning) return false;

        // Show provider-specific credentials and token configs
        if (config.modelProvider === 'bedrock') {
          return ['awsAccessKeyId', 'awsSecretAccessKey', 'awsBearerToken', 'awsRegion',
                  'temperature', 'maxTokens', 'thinkingBudget'].includes(f.key);
        } else if (config.modelProvider === 'ollama') {
          return ['ollamaHost', 'temperature', 'maxTokens'].includes(f.key);
        } else if (config.modelProvider === 'litellm') {
          return ['openaiApiKey', 'anthropicApiKey', 'geminiApiKey', 'xaiApiKey', 'cohereApiKey',
                  'azureApiKey', 'azureApiBase', 'azureApiVersion',
                  'awsAccessKeyId', 'awsSecretAccessKey', 'awsBearerToken', 'awsRegion',
                  'temperature', 'maxTokens', 'topP', 'thinkingBudget', 'reasoningEffort', 'maxCompletionTokens'].includes(f.key);
        }

        return false;
      });
    }
    
    // Filter memory fields based on backend
    if (currentSection.name === 'Memory') {
      fields = fields.filter(f => {
        if (['memoryBackend', 'keepMemory'].includes(f.key)) return true;
        if (config.memoryBackend === 'mem0' && f.key === 'mem0ApiKey') return true;
        if (config.memoryBackend === 'opensearch' && f.key === 'opensearchHost') return true;
        return false;
      });
    }
    
    return fields;
  }, [sections, selectedSectionIndex, config.modelProvider, config.memoryBackend, config.modelId]);
  
  // Basic pre-save validation for required fields and dependent settings
  const validateBeforeSave = useCallback(() => {
    // Required fields
    const requiredFields: Array<{ key: string; label: string }> = [
      { key: 'modelProvider', label: 'Model Provider' },
      { key: 'modelId', label: 'Primary Model' },
    ];
    const missing = requiredFields.filter(f => !(config as any)[f.key]);
    if (missing.length > 0) {
      return `Missing required: ${missing.map(m => m.label).join(', ')}`;
    }
    // Observability requirements when enabled
    if (config.observability) {
      if (!config.langfuseHost && !config.langfuseHostOverride) {
        return 'Observability is enabled but Langfuse Host is not set.';
      }
      if (!config.langfusePublicKey || !config.langfuseSecretKey) {
        return 'Observability requires Langfuse Public and Secret keys.';
      }
    }
    return '';
  }, [config]);

  const handleSave = useCallback(() => {
    // Don't show intermediate "Saving..." message to reduce re-renders

    (async () => {
      try {
        await saveConfig();

        const timestamp = new Date().toLocaleTimeString();
        setUnsavedChanges(false);

        // Delay notification to prevent rapid re-renders that cause WASM memory issues
        // This is especially important in long-running sessions with multiple operations
        // Increased to 300ms to match Terminal.tsx throttle intervals
        setTimeout(() => {
          showMessage(`Configuration saved at ${timestamp}`, 'success', 5000);
        }, 300);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        setTimeout(() => {
          showMessage(`Save failed: ${errorMessage}`, 'error', 5000);
        }, 300);
      }
    })();
  }, [saveConfig, showMessage]);
  
  // Store handleSave in ref to avoid stale closures
  React.useEffect(() => {
    handleSaveRef.current = handleSave;
  }, [handleSave]);
  
  // Handle keyboard navigation
  useInput((input, key) => {
    
    if (editingField) {
      // In edit mode
      if (key.escape) {
        setEditingField(null);
        setTempValue('');
      }
      return;
    }
    
    // Navigation mode
    if (key.escape) {
      if (navigationMode === 'fields') {
        // Go back to section navigation but KEEP section expanded
        setNavigationMode('sections');
        setSelectedFieldIndex(0);
      } else {
        // Double-ESC to exit from sections list
        const now = Date.now();
        const withinWindow = lastEscTime && now - lastEscTime < 1200;
        if (unsavedChanges) {
          showMessage('Unsaved changes. Press Ctrl+S to save or Esc twice to exit without saving.', 'info');
          setLastEscTime(now);
        } else if (withinWindow) {
          onClose();
        } else {
          showMessage('Press Esc again to exit', 'info');
          setLastEscTime(now);
        }
      }
    }
    
    if (key.upArrow) {
      if (navigationMode === 'sections') {
        setSelectedSectionIndex(prev => Math.max(0, prev - 1));
      } else {
        const fields = getCurrentSectionFields();
        setSelectedFieldIndex(prev => Math.max(0, prev - 1));
      }
    }
    
    if (key.downArrow) {
      if (navigationMode === 'sections') {
        setSelectedSectionIndex(prev => Math.min(sections.length - 1, prev + 1));
      } else {
        const fields = getCurrentSectionFields();
        setSelectedFieldIndex(prev => Math.min(fields.length - 1, prev + 1));
      }
    }
    
    if (key.return) {
      if (navigationMode === 'sections') {
        // Toggle section expansion
        const newSections = [...sections];
        newSections[selectedSectionIndex].expanded = !newSections[selectedSectionIndex].expanded;
        setSections(newSections);
        
        // If expanding, switch to field navigation
        if (newSections[selectedSectionIndex].expanded) {
          setNavigationMode('fields');
          setSelectedFieldIndex(0);
        }
      } else {
        // Edit field
        const fields = getCurrentSectionFields();
        const field = fields[selectedFieldIndex];
        if (field) {
          startEditing(field);
        }
      }
    }
    
    if ((key.ctrl || key.meta) && (input?.toLowerCase?.() === 's')) {
      showMessage('Saving configuration...', 'info', 0);
      handleSaveRef.current?.();
      return;
    }
    
    // Expand/collapse with arrows in sections mode
    if (navigationMode === 'sections') {
      if (key.leftArrow) {
        const newSections = [...sections];
        if (newSections[selectedSectionIndex].expanded) {
          newSections[selectedSectionIndex].expanded = false;
          setSections(newSections);
        }
      }
      if (key.rightArrow) {
        const newSections = [...sections];
        if (!newSections[selectedSectionIndex].expanded) {
          newSections[selectedSectionIndex].expanded = true;
          setSections(newSections);
          setNavigationMode('fields');
          setSelectedFieldIndex(0);
        }
      }
    }
  }, { isActive: !editingField });

  // Separate input handler for when editing to handle Ctrl+S and Ctrl+V
  useInput((input, key) => {
    // Handle Ctrl/Cmd+S for save
    if ((key.ctrl || key.meta) && (input?.toLowerCase?.() === 's')) {
      // Save the current editing value first
      if (editingField && tempValue) {
        const field = getCurrentSectionFields().find(f => f.key === editingField.field);
        if (field) {
          if (field.type === 'number') {
            const numValue = parseFloat(tempValue);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            // Clean and sanitize the value, especially for tokens/keys
            const cleanedValue = cleanInputForKey(field.key, tempValue);
            updateConfigValue(field.key, cleanedValue);
          }
        }
      }
      setEditingField(null);
      setTempValue('');
      showMessage('Saving configuration...', 'info', 0);
      handleSaveRef.current?.();
      // Prevent the 's' from being added to the input
      return;
    }

    // Handle Ctrl+V for paste - prevent 'v' from being inserted
    if (key.ctrl && input === 'v') {
      // Don't allow the 'v' to be inserted - just ignore for now
      // Users can use regular system paste (Cmd+V on Mac, which Ink handles)
      return;
    }

    if (key.escape) {
      setEditingField(null);
      setTempValue('');
    }
  }, { isActive: editingField !== null });

  // Sanitize input values for specific keys (tokens, API keys, etc.)
  const cleanInputForKey = (key: string, raw: string): string => {
    if (typeof raw !== 'string') return raw;

    // List of fields that should have all whitespace stripped
    const secretFields = new Set([
      'awsBearerToken',
      'awsAccessKeyId',
      'awsSecretAccessKey',
      'awsSessionToken',
      'openaiApiKey',
      'anthropicApiKey',
      'geminiApiKey',
      'xaiApiKey',
      'cohereApiKey',
      'mem0ApiKey',
      'langfusePublicKey',
      'langfuseSecretKey',
      'langfuseEncryptionKey'
    ]);

    if (secretFields.has(key)) {
      // Remove ALL whitespace (spaces, tabs, newlines, etc.) from secrets
      let cleaned = raw.replace(/\s+/g, '');

      // For bearer tokens, ensure it's valid base64
      if (key === 'awsBearerToken') {
        // Remove any non-base64 characters
        cleaned = cleaned.replace(/[^A-Za-z0-9+/=]/g, '');
      }

      return cleaned;
    }

    // For other fields, just trim outer whitespace
    return raw.trim();
  };

  const updateConfigValue = useCallback((key: string, value: any) => {
    // Validate temperature for models that require temperature=1.0
    if (key === 'temperature' && value !== null && value !== undefined && value !== '') {
      const capabilities = getModelCapabilities(config.modelId);
      if (capabilities.requiresTemp1) {
        const tempValue = typeof value === 'string' ? parseFloat(value) : value;
        if (tempValue !== 1.0) {
          showMessage(
            `${config.modelId} requires temperature=1.0 (reasoning models only support this value)`,
            'error',
            5000
          );
          return; // Block the change
        }
      }
    }

    // Special handling for provider changes - set appropriate default models
    if (key === 'modelProvider') {
      const updates: any = { modelProvider: value };

      // Set default models based on provider
      if (value === 'ollama') {
        // Set Ollama-specific defaults
        updates.modelId = 'qwen3-coder:30b-a3b-q4_K_M';
        updates.embeddingModel = 'mxbai-embed-large';
        updates.evaluationModel = 'qwen3-coder:30b-a3b-q4_K_M';
        updates.swarmModel = 'qwen3-coder:30b-a3b-q4_K_M';
        // Clear temperature to null so backend uses model-specific defaults
        updates.temperature = null;
      } else if (value === 'bedrock') {
        // Set AWS Bedrock defaults - Latest Sonnet 4.5 with 1M context + thinking
        updates.modelId = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
        updates.embeddingModel = 'amazon.titan-embed-text-v2:0';
        updates.evaluationModel = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.swarmModel = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        // Clear temperature to null so backend uses model-specific defaults (1.0 for Sonnet 4.5)
        updates.temperature = null;
      } else if (value === 'litellm') {
        // Set LiteLLM defaults
        updates.modelId = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.embeddingModel = 'bedrock/amazon.titan-embed-text-v2:0';
        updates.evaluationModel = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.swarmModel = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        // Clear temperature to null so backend uses model-specific defaults
        updates.temperature = null;
      }

      updateConfig(updates);
      setUnsavedChanges(true);
      showMessage(`Switched to ${value} provider with default models`, 'info');
      return;
    }
    
    // Special handling for currentModel pricing - update the actual model's pricing
    if (key.startsWith('currentModel.')) {
      const pricingKey = key.replace('currentModel.', '');
      const currentModelId = config.modelId;
      
      if (!currentModelId) {
        showMessage('No model selected to configure pricing', 'error');
        return;
      }
      
      // Update pricing for the current model
      const newConfig = { ...config };
      if (!newConfig.modelPricing) {
        newConfig.modelPricing = {};
      }
      if (!newConfig.modelPricing[currentModelId]) {
        newConfig.modelPricing[currentModelId] = {
          inputCostPer1k: 0,
          outputCostPer1k: 0
        };
      }
      
      // Update the specific pricing field
      (newConfig.modelPricing[currentModelId] as any)[pricingKey] = value;
      
      updateConfig(newConfig);
      setUnsavedChanges(true);
      return;
    }
    
    // Handle nested keys
    if (key.includes('.')) {
      const parts = key.split('.');
      const newConfig = { ...config };
      let current: any = newConfig;
      
      // Navigate to the parent object
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) {
          current[parts[i]] = {};
        }
        current = current[parts[i]];
      }
      
      // Set the final value
      current[parts[parts.length - 1]] = value;
      
      // Update the entire config
      updateConfig(newConfig);
    } else {
      updateConfig({ [key]: value });
    }
    setUnsavedChanges(true);
  }, [config, updateConfig]);

  
  const startEditing = useCallback((field: ConfigField) => {
    // Prevent editing of read-only fields
    if (field.key === 'modelPricingInfo') {
      showMessage('Model pricing is configured in ~/.cyber-autoagent/config.json under "modelPricing"', 'info');
      return;
    }

    const currentValue = config[field.key as keyof typeof config];

    if (field.type === 'boolean') {
      // Toggle boolean immediately
      updateConfigValue(field.key, !currentValue);
      return;
    }

    // Set up editing state
    setEditingField({
      field: field.key,
      type: field.type as any,
      options: field.options
    });

    // Set initial value for editing
    // For password/secret fields, start with empty to avoid paste issues
    if (field.type === 'password') {
      // Always start with empty field for password types to ensure clean paste
      // This prevents the issue where pasting inserts in the middle of masked text
      setTempValue('');
      if (currentValue) {
        // Show brief message that field is cleared for re-entry
        showMessage('Field cleared. Enter or paste new value (Cmd+V on Mac)', 'info', 2000);
      }
    } else if (field.type === 'number') {
      setTempValue(String(currentValue || 0));
    } else {
      setTempValue(String(currentValue || ''));
    }
  }, [config, updateConfigValue]);
  
  const getValue = (key: string): string => {
    // Special handling for model pricing info
    if (key === 'modelPricingInfo') {
      if (config.modelPricing && Object.keys(config.modelPricing).length > 0) {
        const modelCount = Object.keys(config.modelPricing).length;
        return `${modelCount} models configured with custom pricing`;
      }
      return 'Using default AWS Bedrock pricing';
    }
    
    // Special handling for currentModel pricing - use actual modelId from config
    if (key.startsWith('currentModel.')) {
      const pricingKey = key.replace('currentModel.', '');
      const currentModelId = config.modelId;
      
      if (!currentModelId) {
        return 'No model selected';
      }
      
      // Check if pricing exists for current model
      const modelPricing = config.modelPricing?.[currentModelId];
      if (modelPricing && pricingKey in modelPricing) {
        const value = modelPricing[pricingKey as keyof typeof modelPricing];
        return String(value || 0);
      }
      
      // Provider-specific defaults
      if (config.modelProvider === 'ollama') {
        return '0.000'; // Ollama is free
      } else if (config.modelProvider === 'litellm') {
        return pricingKey === 'inputCostPer1k' ? '0.001' : '0.002'; // LiteLLM example defaults
      } else {
        return pricingKey === 'inputCostPer1k' ? '0.003' : '0.015'; // Bedrock defaults
      }
    }
    
    // Handle nested keys (e.g., modelPricing.model.inputCostPer1k)
    let value: any = config;
    const parts = key.split('.');
    for (const part of parts) {
      if (value && typeof value === 'object') {
        value = value[part as keyof typeof value];
      } else {
        value = undefined;
        break;
      }
    }
    
    const field = CONFIG_FIELDS.find(f => f.key === key);

    if (value === undefined || value === null || value === '') {
      // Show computed defaults for model-specific parameters
      if (key === 'temperature') {
        // Thinking/reasoning models require temperature=1.0
        const capabilities = getModelCapabilities(config.modelId);
        if (capabilities.requiresTemp1) {
          return '1.0 (required)';
        }
        return 'Auto';
      }
      if (key === 'maxTokens' && config.modelId?.includes('claude-sonnet-4-5-20250929')) {
        return '16000';
      }
      if (key === 'thinkingBudget' && config.modelId?.includes('claude-sonnet-4-5-20250929')) {
        return '7000';
      }
      if (key === 'maxTokens' && config.modelId?.includes('claude-sonnet-4-20250514')) {
        return '32000';
      }
      if (key === 'thinkingBudget' && config.modelId?.includes('claude-sonnet-4-20250514')) {
        return '10000';
      }

      // Show provider defaults for common optional fields
      if (key === 'topP') {
        return 'Auto';
      }
      if (key === 'reasoningEffort') {
        return 'Auto';
      }
      if (key === 'maxCompletionTokens') {
        return 'Auto';
      }
      if (key === 'maxTokens') {
        return 'Auto (provider default)';
      }
      if (key === 'thinkingBudget') {
        return 'Auto (provider default)';
      }

      return 'Not set';
    }

    if (field?.type === 'password' && value) {
      return '*'.repeat(8);
    }

    if (field?.type === 'boolean') {
      return value ? 'Enabled' : 'Disabled';
    }

    // Add "(required)" hint for temperature=1.0 on reasoning models
    if (key === 'temperature' && value !== null && value !== undefined && value !== '') {
      const capabilities = getModelCapabilities(config.modelId);
      if (capabilities.requiresTemp1) {
        return `${value} (required)`;
      }
    }

    return String(value);
  };

  const renderNotification = () => {
    if (!message) return null;
    
    // Create a prominent notification box that stands out
    return (
      <Box
        borderStyle="double"
        borderColor={
          message.type === 'success' ? theme.success :
          message.type === 'error' ? theme.danger :
          theme.primary
        }
        paddingX={1}
        marginBottom={1}
      >
        <Text
          bold
          color={
            message.type === 'success' ? theme.success :
            message.type === 'error' ? theme.danger :
            theme.primary
          }
        >
          {message.type === 'success' && '━━━ '}
          {message.text}
          {message.type === 'success' && ' ━━━'}
        </Text>
      </Box>
    );
  };

  const renderHeader = () => {
    return (
      <Box marginBottom={1} flexDirection="column">
        <Box>
          <Text bold color={theme.primary} wrap="wrap">Configuration Editor</Text>
          {unsavedChanges && <Text color={theme.warning} wrap="wrap"> [Unsaved]</Text>}
        </Box>
        <Text color={theme.muted} wrap="wrap">
          {navigationMode === 'sections'
            ? 'Navigate with ↑↓ arrows • Enter to expand section • Ctrl+S to save • Esc to continue and exit'
            : 'Navigate with ↑↓ arrows • Enter to edit field • Cmd+V to paste (Mac) • Ctrl+S to save • Esc to collapse section'}
        </Text>
      </Box>
    );
  };

  const renderSections = () => {
    return (
      <Box flexDirection="column">
        {sections.map((section, sectionIndex) => {
          const isSelected = sectionIndex === selectedSectionIndex && navigationMode === 'sections';
          const fields = CONFIG_FIELDS.filter(f => f.section === section.name);
          const configuredCount = fields.filter(f => {
            const value = config[f.key as keyof typeof config];
            return value !== undefined && value !== null && value !== '';
          }).length;
          
          return (
            <Box key={section.name} flexDirection="column" marginBottom={1}>
              {/* Section Header */}
              <Box>
                <Text
                  bold={isSelected}
                  color={isSelected ? theme.accent : theme.foreground}
                  wrap="wrap"
                >
                  {isSelected ? '▸ ' : '  '}
                  {section.expanded ? '▼ ' : '▶ '}
                  {section.label}
                </Text>
                <Text color={theme.muted} wrap="wrap">
                  {' '}({configuredCount}/{fields.length} configured)
                </Text>
              </Box>

              {/* Section Description */}
              <Box paddingLeft={4}>
                <Text color={theme.muted} wrap="wrap">{section.description}</Text>
              </Box>
              
              {/* Fields (if expanded) */}
              {section.expanded && navigationMode === 'fields' && sectionIndex === selectedSectionIndex && (
                <Box flexDirection="column" paddingLeft={2} marginTop={1}>
                  {getCurrentSectionFields().map((field, fieldIndex) => {
                    const isFieldSelected = fieldIndex === selectedFieldIndex;
                    const isEditing = editingField?.field === field.key;
                    
                    return (
                      <Box key={field.key} marginY={0.25}>
                        {(() => {
                          const cols = (() => { try { return Math.max(40, Math.min(Number((process as any)?.stdout?.columns || 80), 200)); } catch { return 80; } })();
                          const labelWidth = Math.max(20, Math.min(48, Math.floor(cols * 0.38)));
                          return (
                            <>
                              <Box width={labelWidth}>
                                <Text 
                                  bold={isFieldSelected}
                                  color={isFieldSelected ? theme.accent : theme.muted}
                                >
                                  {isFieldSelected ? '▸ ' : '  '}{field.label}:
                                  {field.required && <Text color={theme.danger}> *</Text>}
                                </Text>
                              </Box>
                              <Box flexGrow={1}>
                                {isEditing ? renderEditingField(field) : (
                                  <Text 
                                    bold={isFieldSelected}
                                    color={
                                      getValue(field.key) === 'Not set' ? theme.muted : 
                                      field.type === 'boolean' && getValue(field.key) === 'Enabled' ? theme.success :
                                      isFieldSelected ? theme.foreground : theme.primary
                                    }
                                  >
                                    {getValue(field.key)}
                                  </Text>
                                )}
                              </Box>
                            </>
                          );
                        })()}
                      </Box>
                    );
                  })}
                </Box>
              )}
            </Box>
          );
        })}
      </Box>
    );
  };

  const renderEditingField = (field: ConfigField) => {
    if (!editingField) return null;

    if (field.type === 'select' && editingField.options) {
      return (
        <SelectInput
          items={editingField.options.map(opt => ({
            label: opt.label,
            value: opt.value
          }))}
          onSelect={(item) => {
            updateConfigValue(field.key, item.value);
            setEditingField(null);

            // Ensure section stays expanded and move to next field
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after selection
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
          }}
          indicatorComponent={({ isSelected }) => (
            <Text color={isSelected ? theme.primary : 'transparent'}>❯ </Text>
          )}
          itemComponent={({ isSelected, label }) => (
            <Text color={isSelected ? theme.primary : theme.foreground}>
              {label}
            </Text>
          )}
        />
      );
    }

    // Use TokenInput for AWS Bearer token
    if (field.key === 'awsBearerToken') {
      return (
        <TokenInput
          fieldKey={field.key}
          onSubmit={(value) => {
            // Clean and sanitize the value
            const cleanedValue = cleanInputForKey(field.key, value);
            updateConfigValue(field.key, cleanedValue);
            setEditingField(null);
            setTempValue('');

            // Brief success message
            showMessage(`Token saved (${cleanedValue.length} chars)`, 'success', 2000);

            // Ensure we stay in fields navigation mode and section stays expanded
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after saving
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
          }}
        />
      );
    }

    // Use custom PasswordInput for other password fields
    if (field.type === 'password') {
      return (
        <PasswordInput
          fieldKey={field.key}
          onSubmit={(value) => {
            // Clean and sanitize the value
            const cleanedValue = cleanInputForKey(field.key, value);
            updateConfigValue(field.key, cleanedValue);
            setEditingField(null);
            setTempValue('');

            // Ensure we stay in fields navigation mode and section stays expanded
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after saving
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
          }}
        />
      );
    }

    return (
      <TextInput
        value={tempValue}
        onChange={(newValue) => {
          // Debug logging for non-password fields
          // Directly update temp value (no verbose debug logging)
          setTempValue(newValue);
        }}
        onSubmit={(value) => {
          // Debug logging for non-password fields
          // Avoid verbose debug logging of field values

          if (field.type === 'number') {
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            // Clean and sanitize the value, especially for tokens/keys
            const cleanedValue = cleanInputForKey(field.key, value);

            // More debug logging
            // No debug logging of cleaned token values
            updateConfigValue(field.key, cleanedValue);
          }
          setEditingField(null);
          setTempValue('');

          // Ensure we stay in fields navigation mode and section stays expanded
          setNavigationMode('fields');
          const newSections = [...sections];
          newSections[selectedSectionIndex].expanded = true;
          setSections(newSections);

          // Move to next field after saving
          const fields = getCurrentSectionFields();
          if (selectedFieldIndex < fields.length - 1) {
            setSelectedFieldIndex(prev => prev + 1);
          }
        }}
        mask={undefined}
      />
    );
  };

  // Quick status summary
  const getConfigStatus = () => {
    const hasProvider = config.modelProvider;
    const hasCredentials = 
      (config.modelProvider === 'bedrock' && (config.awsAccessKeyId || config.awsBearerToken)) ||
      (config.modelProvider === 'ollama' && config.ollamaHost) ||
      (config.modelProvider === 'litellm');
    const hasModel = config.modelId;
    
    if (!hasProvider) return { status: 'error', message: 'No provider selected' };
    if (!hasCredentials) return { status: 'warning', message: 'Missing credentials' };
    if (!hasModel) return { status: 'warning', message: 'No model selected' };
    
    return { status: 'success', message: 'Ready' };
  };
  
  // Deployment mode status
  const getDeploymentModeDisplay = () => {
    const mode = config.deploymentMode || 'unknown';
    const observabilityStatus = config.observability ? 'enabled' : 'disabled';
    const evaluationStatus = config.autoEvaluation ? 'enabled' : 'disabled';
    
    return {
      mode: mode.replace('-', ' ').toUpperCase(),
      observability: observabilityStatus,
      evaluation: evaluationStatus,
      description: getDeploymentDescription(mode)
    };
  };
  
  const getDeploymentDescription = (mode: string) => {
    switch (mode) {
      case 'cli': return 'Python CLI mode (token counting enabled, remote traces disabled)';
      case 'container': return 'Single container mode (token counting enabled, remote traces disabled)';
      case 'compose': return 'Full stack mode (token counting + remote traces enabled)';
      default: return 'Deployment mode detection in progress';
    }
  };
  
  const status = getConfigStatus();
  const deploymentStatus = getDeploymentModeDisplay();







  // Main render logic
  return (
    <Box flexDirection="column">
      <Box
        flexDirection="column"
        borderStyle="single"
        borderColor={theme.primary}
        padding={1}
        marginTop={1}
        width="100%"
      >
        {/* Notification appears INSIDE the main border at the very top */}
        {message && (
          <Box
            borderStyle="double"
            borderColor={
              message.type === 'success' ? theme.success :
              message.type === 'error' ? theme.danger :
              theme.primary
            }
            paddingX={1}
            marginBottom={1}
          >
            <Text
              bold
              wrap="wrap"
              color={
                message.type === 'success' ? theme.success :
                message.type === 'error' ? theme.danger :
                theme.primary
              }
            >
              {message.type === 'success' && '✓ '}
              {message.type === 'error' && '✗ '}
              {message.type === 'info' && '⏳ '}
              {message.text}
            </Text>
          </Box>
        )}
        
        {renderHeader()}
      
      {/* Status bar */}
      <Box marginBottom={1} flexDirection="column">
        <Text
          wrap="wrap"
          color={
            status.status === 'success' ? theme.success :
            status.status === 'warning' ? theme.warning :
            theme.danger
          }
        >
          Status: {status.message}
        </Text>
        <Text color={theme.muted} wrap="wrap">
          Deployment: {deploymentStatus.mode} |
          Observability: {deploymentStatus.observability} |
          Evaluation: {deploymentStatus.evaluation}
        </Text>
        <Text color={theme.muted} wrap="wrap">
          {deploymentStatus.description}
        </Text>
      </Box>
      
      {/* Main configuration sections */}
      <Box flexDirection="column" flexGrow={1}>
        {renderSections()}
      </Box>
      
        {/* Footer with shortcuts */}
        <Box marginTop={1} borderTop borderColor={unsavedChanges ? theme.warning : theme.muted} paddingTop={1}>
          <Text color={theme.muted} wrap="wrap">
            {navigationMode === 'sections'
              ? '↑↓ Navigate sections • Enter to expand/collapse • Ctrl+S to save • Esc to exit'
              : '↑↓ Navigate fields • Enter to edit • Esc to collapse • Ctrl+S to save'
            }
          </Text>
          {unsavedChanges && (
            <Text color={theme.warning} bold wrap="wrap">
              {' '}[Unsaved Changes]
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
