/**
 * Configuration Editor
 * 
 * Expandable sections with inline editing for application configuration.
 * Features hierarchical navigation and real-time validation.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import SelectInput from 'ink-select-input';
import TextInput from 'ink-text-input';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { Header } from './Header.js';

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
  { key: 'observability', label: 'Enable Observability', type: 'boolean', section: 'Observability' },
  { key: 'langfuseHost', label: 'Langfuse Host', type: 'text', section: 'Observability' },
  { key: 'langfusePublicKey', label: 'Langfuse Public Key', type: 'password', section: 'Observability' },
  { key: 'langfuseSecretKey', label: 'Langfuse Secret Key', type: 'password', section: 'Observability' },
  { key: 'enableLangfusePrompts', label: 'Enable Prompt Management', type: 'boolean', section: 'Observability' },
  
  // Evaluation
  { key: 'autoEvaluation', label: 'Auto-Evaluation', type: 'boolean', section: 'Evaluation' },
  { key: 'minToolAccuracyScore', label: 'Min Tool Accuracy', type: 'number', section: 'Evaluation' },
  { key: 'minEvidenceQualityScore', label: 'Min Evidence Quality', type: 'number', section: 'Evaluation' },
  { key: 'minAnswerRelevancyScore', label: 'Min Answer Relevancy', type: 'number', section: 'Evaluation' },
  
  // Pricing - Read-only display of model pricing configuration
  { key: 'modelPricingInfo', label: 'Model Pricing Status', type: 'text', section: 'Pricing', 
    description: 'View current model pricing. Edit ~/.cyber-autoagent/config.json to customize.' },
  
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
  { name: 'Observability', label: 'Observability', description: 'Monitoring and tracing', expanded: false },
  { name: 'Evaluation', label: 'Evaluation', description: 'Quality assessment', expanded: false },
  { name: 'Pricing', label: 'Model Pricing', description: 'Token cost configuration per 1K tokens', expanded: false },
  { name: 'Output', label: 'Output', description: 'Report and logging', expanded: false }
];

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
  
  // Use ref to track timeout for cleanup
  const messageTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Screen clearing is handled by modal manager's refreshStatic()
  
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
    };
  }, []);
  
  // Get fields for the current section
  const getCurrentSectionFields = useCallback(() => {
    const currentSection = sections[selectedSectionIndex];
    if (!currentSection?.expanded) return [];
    
    let fields = CONFIG_FIELDS.filter(f => f.section === currentSection.name);
    
    // Filter credentials based on provider
    if (currentSection.name === 'Models') {
      fields = fields.filter(f => {
        // Always show provider and model fields
        if (['modelProvider', 'modelId', 'embeddingModel', 'evaluationModel', 'swarmModel'].includes(f.key)) {
          return true;
        }
        
        // Show provider-specific credentials
        if (config.modelProvider === 'bedrock') {
          return ['awsAccessKeyId', 'awsSecretAccessKey', 'awsBearerToken', 'awsRegion'].includes(f.key);
        } else if (config.modelProvider === 'ollama') {
          return ['ollamaHost'].includes(f.key);
        } else if (config.modelProvider === 'litellm') {
          return ['openaiApiKey', 'anthropicApiKey', 'awsAccessKeyId', 'awsSecretAccessKey', 'awsRegion'].includes(f.key);
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
  }, [sections, selectedSectionIndex, config.modelProvider, config.memoryBackend]);
  
  // Handle keyboard navigation
  const isInteractive = process.stdin.isTTY;
  
  useInput((input, key) => {
    if (!isInteractive) return;
    
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
        // Go back to section navigation and collapse current section
        const newSections = [...sections];
        newSections[selectedSectionIndex].expanded = false;
        setSections(newSections);
        setNavigationMode('sections');
        setSelectedFieldIndex(0);
      } else if (unsavedChanges) {
        setMessage({ text: 'Unsaved changes. Press Ctrl+S to save or Esc again to exit.', type: 'info' });
      } else {
        // Screen clearing on exit is handled by modal manager
        onClose();
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
    
    if (key.ctrl && input === 's') {
      handleSave();
    }
  }, { isActive: isInteractive && !editingField });

  // Separate input handler for when editing to handle Ctrl+S
  useInput((input, key) => {
    if (key.ctrl && input === 's') {
      // Save the current editing value first
      if (editingField && tempValue) {
        const field = getCurrentSectionFields().find(f => f.key === editingField.field);
        if (field) {
          if (field.type === 'number') {
            const numValue = parseInt(tempValue, 10);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            updateConfigValue(field.key, tempValue);
          }
        }
      }
      setEditingField(null);
      setTempValue('');
      handleSave();
      // Prevent the 's' from being added to the input
      return;
    }
    
    if (key.escape) {
      setEditingField(null);
      setTempValue('');
    }
  }, { isActive: isInteractive && editingField !== null });

  const handleSave = useCallback(async () => {
    try {
      // Mark configuration as complete when saving
      updateConfig({ isConfigured: true });
      
      // Small delay to ensure state has updated before saving
      await new Promise(resolve => setTimeout(resolve, 100));
      
      await saveConfig();
      setUnsavedChanges(false);
      setMessage({ text: 'Configuration saved successfully', type: 'success' });
      
      // Clear existing timeout if any
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
      
      // Set new timeout with cleanup
      messageTimeoutRef.current = setTimeout(() => {
        setMessage(null);
        messageTimeoutRef.current = null;
      }, 3000);
    } catch (error) {
      console.error('Config save error:', error);
      setMessage({ text: `Save failed: ${error}`, type: 'error' });
    }
  }, [saveConfig, updateConfig]);

  const updateConfigValue = useCallback((key: string, value: any) => {
    updateConfig({ [key]: value });
    setUnsavedChanges(true);
  }, [updateConfig]);
  
  const startEditing = useCallback((field: ConfigField) => {
    // Prevent editing of read-only fields
    if (field.key === 'modelPricingInfo') {
      setMessage({ 
        text: 'Model pricing is configured in ~/.cyber-autoagent/config.json under "modelPricing"', 
        type: 'info' 
      });
      
      // Clear existing timeout if any
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
      
      // Set new timeout with cleanup
      messageTimeoutRef.current = setTimeout(() => {
        setMessage(null);
        messageTimeoutRef.current = null;
      }, 3000);
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
    if (field.type === 'number') {
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
    
    const value = config[key as keyof typeof config];
    const field = CONFIG_FIELDS.find(f => f.key === key);
    
    if (value === undefined || value === null || value === '') {
      return 'Not set';
    }
    
    if (field?.type === 'password' && value) {
      return '*'.repeat(8);
    }
    
    if (field?.type === 'boolean') {
      return value ? 'Enabled' : 'Disabled';
    }
    
    return String(value);
  };

  const renderHeader = () => {
    return (
      <Box marginBottom={1} flexDirection="column">
        <Box>
          <Text bold color={theme.primary}>Configuration Editor</Text>
          {unsavedChanges && <Text color={theme.warning}> [Unsaved]</Text>}
        </Box>
        <Text color={theme.muted}>
          {navigationMode === 'sections' 
            ? 'Navigate with ↑↓ arrows • Enter to expand section • Ctrl+S to save • Esc to continue and exit'
            : 'Navigate with ↑↓ arrows • Enter to edit field • Tab/Shift+Tab to navigate • Esc to collapse section'}
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
                >
                  {isSelected ? '▸ ' : '  '}
                  {section.expanded ? '▼ ' : '▶ '}
                  {section.label}
                </Text>
                <Text color={theme.muted}>
                  {' '}({configuredCount}/{fields.length} configured)
                </Text>
              </Box>
              
              {/* Section Description */}
              <Box paddingLeft={4}>
                <Text color={theme.muted}>{section.description}</Text>
              </Box>
              
              {/* Fields (if expanded) */}
              {section.expanded && navigationMode === 'fields' && (
                <Box flexDirection="column" paddingLeft={2} marginTop={1}>
                  {getCurrentSectionFields().map((field, fieldIndex) => {
                    const isFieldSelected = fieldIndex === selectedFieldIndex;
                    const isEditing = editingField?.field === field.key;
                    
                    return (
                      <Box key={field.key} marginY={0.25}>
                        <Box width="40%">
                          <Text 
                            bold={isFieldSelected}
                            color={isFieldSelected ? theme.accent : theme.muted}
                          >
                            {isFieldSelected ? '▸ ' : '  '}{field.label}:
                            {field.required && <Text color={theme.danger}> *</Text>}
                          </Text>
                        </Box>
                        <Box width="60%">
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
          }}
        />
      );
    }
    
    return (
      <TextInput
        value={tempValue}
        onChange={setTempValue}
        onSubmit={(value) => {
          if (field.type === 'number') {
            const numValue = parseInt(value, 10);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            updateConfigValue(field.key, value);
          }
          setEditingField(null);
          setTempValue('');
        }}
        mask={field.type === 'password' ? '*' : undefined}
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
  
  const status = getConfigStatus();







  // Main render logic
  return (
    <Box flexDirection="column" width="100%" height="100%">
      <Box 
        flexDirection="column"
        borderStyle="single" 
        borderColor={theme.primary}
        padding={1}
        width="100%"
        marginTop={1}
      >
        {renderHeader()}
      
      {/* Status bar */}
      <Box marginBottom={1}>
        <Text color={
          status.status === 'success' ? theme.success :
          status.status === 'warning' ? theme.warning :
          theme.danger
        }>
          Status: {status.message}
        </Text>
      </Box>
      
      {message && (
        <Box marginBottom={1}>
          <Text color={
            message.type === 'success' ? theme.success :
            message.type === 'error' ? theme.danger :
            theme.info
          }>
            {message.text}
          </Text>
        </Box>
      )}
      
      {/* Main configuration sections */}
      <Box flexDirection="column" flexGrow={1}>
        {renderSections()}
      </Box>
      
        {/* Footer with shortcuts */}
        <Box marginTop={1} borderStyle="single" borderColor={theme.muted} paddingX={1}>
          <Text color={theme.muted}>
            {navigationMode === 'sections'
              ? '↑↓ Navigate sections • Enter to expand/collapse • Ctrl+S to save • Esc to continue and exit'
              : '↑↓ Navigate fields • Enter to edit • Tab/Shift+Tab to navigate • Esc to collapse section • Ctrl+S to save'
            }
          </Text>
        </Box>
      </Box>
    </Box>
  );
};