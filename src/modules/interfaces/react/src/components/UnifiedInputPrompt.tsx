/**
 * Unified Input Prompt Component
 * Supports both guided flow (module→target→objective→execute) and natural language input
 * Provides intelligent autocomplete and suggestions based on current flow state
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import TextInput from 'ink-text-input';
import { themeManager } from '../themes/theme-manager.js';
import { useModule } from '../contexts/ModuleContext.js';

interface FlowState {
  step: 'idle' | 'module' | 'target' | 'objective' | 'ready';
  module?: string;
  target?: string;
  objective?: string;
}

interface Suggestion {
  text: string;
  description: string;
  type: 'command' | 'module' | 'target' | 'natural';
}

interface UnifiedInputPromptProps {
  flowState: FlowState;
  onInput: (input: string) => void;
  disabled?: boolean;
  userHandoffActive?: boolean;
  suggestions?: Suggestion[];
  availableModules?: string[];
  recentTargets?: string[];
}

export const UnifiedInputPrompt: React.FC<UnifiedInputPromptProps> = ({
  flowState,
  onInput,
  disabled = false,
  userHandoffActive = false,
  suggestions = [],
  availableModules = ['general'],
  recentTargets = []
}) => {
  const theme = themeManager.getCurrentTheme();
  const { currentModule } = useModule();
  const [value, setValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<Suggestion[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);

  // Generate smart suggestions based on flow state and input
  const generateSuggestions = useCallback((input: string): Suggestion[] => {
    const suggestions: Suggestion[] = [];
    
    if (!input.trim()) {
      // No input - show appropriate suggestions based on flow state
      switch (flowState.step) {
        case 'idle':
          suggestions.push(
            { text: 'scan https://example.com', description: 'Quick security scan', type: 'natural' },
            { text: '/plugins', description: 'Select security plugin', type: 'command' },
            { text: '/config', description: 'Configure settings', type: 'command' },
            { text: '/memory', description: 'Search memory', type: 'command' }
          );
          break;
        case 'module':
          suggestions.push(
            { text: '/plugins', description: 'Open plugin selector', type: 'command' }
          );
          break;
        case 'target':
          suggestions.push(
            { text: 'target https://example.com', description: 'Web application target', type: 'target' },
            { text: 'target 192.168.1.1', description: 'Network target', type: 'target' },
            { text: 'target api.example.com', description: 'API endpoint target', type: 'target' }
          );
          recentTargets.forEach(target => {
            suggestions.push({ text: `target ${target}`, description: `Recent target`, type: 'target' });
          });
          break;
        case 'objective':
          suggestions.push(
            { text: 'execute', description: 'Start with default objective', type: 'command' },
            { text: 'execute focus on authentication', description: 'Custom: Authentication testing', type: 'command' },
            { text: 'execute look for SQL injection', description: 'Custom: SQL injection testing', type: 'command' },
            { text: 'execute comprehensive scan', description: 'Custom: Full security assessment', type: 'command' }
          );
          break;
        case 'ready':
          suggestions.push(
            { text: '', description: 'Press Enter to start assessment', type: 'command' },
            { text: 'reset', description: 'Start over', type: 'command' },
            { text: '/plugins', description: 'Change plugin', type: 'command' }
          );
          break;
      }
    } else {
      // Filter suggestions based on input
      const allSuggestions: Suggestion[] = [
        // Commands
        { text: '/config', description: 'Configure settings', type: 'command' },
        { text: '/memory', description: 'Search memory', type: 'command' },
        { text: '/plugins', description: 'Select security plugin', type: 'command' },
        { text: '/help', description: 'Show help', type: 'command' },
        { text: '/health', description: 'Check container health', type: 'command' },
        { text: '/clear', description: 'Clear screen', type: 'command' },
        { text: '/exit', description: 'Exit application', type: 'command' },
        
        // Natural language patterns
        { text: 'scan https://example.com', description: 'Quick security scan', type: 'natural' },
        { text: 'analyze code in ./src/', description: 'Code security analysis', type: 'natural' },
        { text: 'test api at api.example.com', description: 'API security testing', type: 'natural' },
        
        // Flow commands
        { text: 'execute', description: 'Start operation', type: 'command' },
        { text: 'reset', description: 'Reset flow', type: 'command' }
      ];

      const filtered = allSuggestions.filter(suggestion => 
        suggestion.text.toLowerCase().includes(input.toLowerCase()) ||
        suggestion.description.toLowerCase().includes(input.toLowerCase())
      );

      suggestions.push(...filtered);
    }

    return suggestions.slice(0, 8); // Limit to 8 suggestions
  }, [flowState, availableModules, recentTargets]);

  // Update suggestions when input changes
  useEffect(() => {
    const suggestions = generateSuggestions(value);
    setFilteredSuggestions(suggestions);
    setShowSuggestions(suggestions.length > 0 && value.length > 0);
    setSelectedSuggestionIndex(0);
  }, [value, generateSuggestions]);

  // Clear input when flow state changes to target (after module loads)
  useEffect(() => {
    if (flowState.step === 'target' && value.includes('module ')) {
      setValue('');
    }
  }, [flowState.step]);

  // Get prompt indicator (Gemini CLI style)
  const getPromptIndicator = () => {
    if (disabled && !userHandoffActive) return '⏸';
    if (userHandoffActive) return 'response:';
    
    // Show module name if loaded - use currentModule from context
    if (currentModule) {
      return `${currentModule}:`;
    }
    
    // Default prompt
    return 'general:'
  };

  // Get placeholder text
  const getPlaceholder = () => {
    if (userHandoffActive) {
      return 'Enter your response to the agent...';
    }
    
    switch (flowState.step) {
      case 'module':
        return '/plugins to select security plugin';
      case 'target':
        return 'target https://example.com';
      case 'objective':
        return 'execute (or "execute [custom objective]")';
      case 'ready':
        return 'Press Enter to start';
      default:
        // If we have a module loaded (by default 'general'), prompt for target
        if (currentModule) {
          return 'Type target <url> and press Enter';
        }
        return 'scan example.com or /plugins or /help';
    }
  };

  // Handle keyboard input - check if raw mode is supported
  const isInteractive = process.stdin.isTTY;
  
  useInput((input, key) => {
    if (!isInteractive || disabled) return;

    if (showSuggestions && filteredSuggestions.length > 0) {
      if (key.upArrow) {
        setSelectedSuggestionIndex(prev => 
          prev > 0 ? prev - 1 : filteredSuggestions.length - 1
        );
        return;
      }
      if (key.downArrow) {
        setSelectedSuggestionIndex(prev => 
          prev < filteredSuggestions.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (key.tab || (key.return && !key.ctrl)) {
        const suggestion = filteredSuggestions[selectedSuggestionIndex];
        if (suggestion) {
          setValue(suggestion.text);
          setShowSuggestions(false);
          return;
        }
      }
      if (key.escape) {
        setShowSuggestions(false);
        return;
      }
    }

    // Handle other shortcuts
    if (key.ctrl && input === 'l') {
      onInput('/clear');
      setValue('');
      return;
    }
    
    if (key.ctrl && input === 'c') {
      if (value.length > 0) {
        setValue('');
        setShowSuggestions(false);
      }
      return;
    }
  }, { isActive: isInteractive });

  const handleSubmit = (submittedValue: string) => {
    if (!disabled) {
      onInput(submittedValue);
      setValue('');
      setShowSuggestions(false);
    }
  };

  const handleChange = (newValue: string) => {
    setValue(newValue);
  };

  return (
    <Box flexDirection="column" width="100%">
      {/* Suggestions dropdown */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <Box flexDirection="column" borderStyle="single" borderColor={theme.muted} paddingX={1} marginBottom={1}>
          <Text color={theme.info} bold>Suggestions:</Text>
          {filteredSuggestions.map((suggestion, index) => (
            <Box key={index}>
              <Text color={index === selectedSuggestionIndex ? theme.primary : theme.foreground}>
                {index === selectedSuggestionIndex ? '> ' : '  '}
                {suggestion.text}
              </Text>
              <Text color={theme.muted}> - {suggestion.description}</Text>
            </Box>
          ))}
          <Text color={theme.muted} italic>Use ↑↓ to navigate, Tab/Enter to select, Esc to cancel</Text>
        </Box>
      )}

      {/* Input prompt - Gemini CLI style with full width */}
      <Box 
        borderStyle="round" 
        borderColor={disabled ? theme.muted : theme.accent} 
        paddingX={1}
        width="100%"
      >
        <Text color={disabled ? theme.muted : theme.accent}>
          {getPromptIndicator()} 
        </Text>
        <Box marginLeft={1} flexGrow={1}>
          <TextInput
            value={value}
            onChange={handleChange}
            onSubmit={handleSubmit}
            placeholder={disabled ? 'Operation running...' : getPlaceholder()}
            showCursor={!disabled}
            focus={!disabled}
          />
        </Box>
      </Box>

      {/* Helpful hints - more subtle */}
      {!showSuggestions && value.length === 0 && (
        <Box marginTop={1} marginBottom={2}>
          <Text color={theme.muted}>
            {(() => {
              if (currentModule && flowState.step === 'target') {
                return `Type target <url> and press Enter`;
              } else if (flowState.step === 'objective') {
                return `Type 'execute' and optionally add custom objective, then press Enter`;
              } else if (flowState.step === 'ready') {
                return `Press Enter to start assessment`;
              } else {
                return `Type your command or '/help' for available options`;
              }
            })()}
          </Text>
        </Box>
      )}
    </Box>
  );
};