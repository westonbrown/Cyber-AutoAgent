/**
 * Unified Input Prompt Component
 * Supports both guided flow (module→target→objective→execute) and natural language input
 * Provides intelligent autocomplete and suggestions based on current flow state
 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
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
  const { currentModule, availableModules: contextModules } = useModule();
  
  // Use modules from context if not provided as prop
  const modules = availableModules.length > 1 || availableModules[0] !== 'general' 
    ? availableModules 
    : Object.keys(contextModules);
  const [value, setValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<Suggestion[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);
  const previousStep = useRef(flowState.step);
  
  // Track a key to force TextInput re-mount when needed
  const [inputKey, setInputKey] = useState(0);

  // Generate smart suggestions based on flow state and input
  // Don't use useCallback here to avoid infinite loop
  const generateSuggestions = (input: string): Suggestion[] => {
    const suggestions: Suggestion[] = [];
    
    if (!input.trim()) {
      // No input - show appropriate suggestions based on flow state and user journey
      switch (flowState.step) {
        case 'idle':
          // Check if user has existing memories to suggest continuation
          const hasMemories = recentTargets.length > 0;
          
          if (hasMemories) {
            // Returning user - suggest continuing previous work
            suggestions.push(
              { text: `target ${recentTargets[0]}`, description: 'Continue testing recent target', type: 'command' },
              { text: 'target https://testphp.vulnweb.com', description: 'Test on authorized target', type: 'command' },
              { text: '/docs', description: 'Browse documentation', type: 'command' },
              { text: '/config', description: 'Configure settings', type: 'command' }
            );
          } else {
            // First-time user - guide them through basics
            suggestions.push(
              { text: 'target https://testphp.vulnweb.com', description: 'Set authorized test target', type: 'command' },
              { text: '/docs', description: 'Read user instructions', type: 'command' },
              { text: '/help', description: 'Show all commands', type: 'command' },
              { text: '/setup', description: 'Choose deployment mode', type: 'command' },
              { text: '/config', description: 'Configure AI provider', type: 'command' }
            );
          }
          break;
        case 'module':
          suggestions.push(
            { text: '/plugins', description: 'Browse available security modules', type: 'command' }
          );
          break;
        case 'target':
          // Prioritize authorized test targets and recent targets
          suggestions.push(
            { text: 'target https://testphp.vulnweb.com', description: 'Authorized test application', type: 'target' },
            { text: 'target https://your-authorized-target.com', description: 'Your authorized web application', type: 'target' },
            { text: 'target https://api.example.com', description: 'Your authorized API endpoint', type: 'target' },
            { text: 'target 192.168.1.0/24', description: 'Your authorized network range', type: 'target' }
          );
          // Add recent targets at the top
          recentTargets.slice(0, 3).forEach(target => {
            suggestions.unshift({ text: `target ${target}`, description: `Recent: Continue testing`, type: 'target' });
          });
          break;
        case 'objective':
          // Objective stage: Enter sets objective only, 'execute' sets objective and starts
          suggestions.push(
            { text: '', description: '⏎ Press Enter to set default objective (then execute)', type: 'command' },
            { text: 'execute', description: 'Start assessment with default objective', type: 'command' },
            { text: 'execute focus on OWASP Top 10', description: 'Start with OWASP Top 10 focus', type: 'command' },
            { text: 'execute test authentication', description: 'Start with auth testing focus', type: 'command' },
            { text: 'focus on SQL injection', description: 'Set SQL injection as objective', type: 'command' },
            { text: 'check for misconfigurations', description: 'Set configuration review as objective', type: 'command' }
          );
          break;
        case 'ready':
          suggestions.push(
            { text: 'execute', description: '▶ Start security assessment', type: 'command' },
            { text: '', description: '⏎ Press Enter to start assessment', type: 'command' },
            { text: 'reset', description: 'Change configuration', type: 'command' }
          );
          break;
      }
    } else {
      // Filter suggestions based on input with comprehensive command set
      const allSuggestions: Suggestion[] = [
        // Primary commands
        { text: '/help', description: 'Show all available commands', type: 'command' },
        { text: '/docs', description: 'Browse documentation interactively', type: 'command' },
        { text: '/config', description: 'View and edit configuration', type: 'command' },
        { text: '/plugins', description: 'Select security assessment module', type: 'command' },
        { text: '/health', description: 'Check system and container status', type: 'command' },
        { text: '/setup', description: 'Deployment mode configuration', type: 'command' },
        
        // Target patterns (matching user-instructions.md examples)
        { text: 'target https://testphp.vulnweb.com', description: 'Public authorized test target', type: 'command' },
        { text: 'target https://your-authorized-target.com', description: 'Your authorized application', type: 'command' },
        { text: 'target 192.168.1.0/24', description: 'Your authorized network range', type: 'command' },
        
        // Flow commands
        { text: 'target', description: 'Set assessment target', type: 'command' },
        { text: 'execute', description: 'Start security assessment', type: 'command' },
        { text: 'reset', description: 'Clear current configuration', type: 'command' },
        { text: '/clear', description: 'Clear terminal screen', type: 'command' },
        { text: '/exit', description: 'Exit application', type: 'command' }
      ];

      const filtered = allSuggestions.filter(suggestion => 
        suggestion.text.toLowerCase().includes(input.toLowerCase()) ||
        suggestion.description.toLowerCase().includes(input.toLowerCase())
      );

      suggestions.push(...filtered);
    }

    return suggestions.slice(0, 8); // Limit to 8 suggestions
  };

  // Update suggestions when input changes - use stable dependencies
  useEffect(() => {
    // Don't show suggestions during user handoff - they're not relevant
    if (userHandoffActive) {
      setShowSuggestions(false);
      setFilteredSuggestions([]);
      return;
    }
    
    const suggestions = generateSuggestions(value);
    
    // Prevent infinite loops by only updating if suggestions actually changed
    setFilteredSuggestions(prev => {
      if (JSON.stringify(prev) === JSON.stringify(suggestions)) {
        return prev; // Keep same reference if content hasn't changed
      }
      return suggestions;
    });
    
    const shouldShow = suggestions.length > 0 && value.length > 0;
    setShowSuggestions(prev => prev !== shouldShow ? shouldShow : prev);
    setSelectedSuggestionIndex(prev => prev !== 0 ? 0 : prev);
  }, [value, flowState.step, userHandoffActive]); // Only depend on stable values

  // Clear input when flow state changes to help with transitions
  useEffect(() => {
    if (previousStep.current !== flowState.step) {
      // Clear input and force TextInput re-mount when flow state changes
      setValue('');
      setShowSuggestions(false);
      setSelectedSuggestionIndex(0);
      setInputKey(prev => prev + 1); // Force re-mount for clean state
      
      // Update the previous step ref
      previousStep.current = flowState.step;
    }
  }, [flowState.step]);

  // Get prompt indicator
  const getPromptIndicator = () => {
    if (disabled && !userHandoffActive) return '⏸';
    if (userHandoffActive) return 'response:';
    
    // Show module name if loaded - use currentModule from context
    if (currentModule) {
      return `◆ ${currentModule} >`;
    }
    
    // Default prompt
    return '◆ general >'
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
        return 'target https://your-authorized-target.com';
      case 'objective':
        return 'Type "execute" (default) or "execute <your objective>" (custom) to start';
      case 'ready':
        return 'Press Enter or type "execute" to start assessment';
      default:
        // If we have a module loaded (by default 'general'), prompt for target
        if (currentModule) {
          return 'target <url> or type "execute" after setting target';
        }
        return 'target <url> or /plugins or /help';
    }
  };

  // Handle keyboard input
  useInput((input, key) => {
    if (disabled) return;

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
        // Only handle ESC for hiding suggestions if we're not disabled
        // When disabled (e.g., during assessment), let ESC bubble up to stop the operation
        if (!disabled && showSuggestions) {
          setShowSuggestions(false);
          return;
        }
        // Don't consume the ESC key if disabled - let it bubble up for kill switch
      }
    }

    // Note: Ctrl+L and Ctrl+C are handled at the App level
  }, { isActive: !disabled }); // Don't capture keyboard when disabled (during assessment)

  const handleSubmit = (submittedValue: string) => {
    // Allow submission during user handoff even if otherwise disabled
    if (!disabled || userHandoffActive) {
      // Clear state and force re-mount of TextInput to ensure clean state
      setValue('');
      setShowSuggestions(false);
      setInputKey(prev => prev + 1); // Force TextInput to re-mount with clean state
      
      // Process the command after ensuring clean state
      setTimeout(() => {
        onInput(submittedValue);
      }, 0);
    }
  };

  const handleChange = (newValue: string) => {
    setValue(newValue);
  };

  return (
    <Box flexDirection="column" width="100%">
      {/* Input prompt with full width */}
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
            key={inputKey}
            value={value}
            onChange={handleChange}
            onSubmit={handleSubmit}
            placeholder={disabled && !userHandoffActive ? 'Operation running...' : getPlaceholder()}
            showCursor={!disabled || userHandoffActive}
            focus={!disabled || userHandoffActive}
          />
        </Box>
      </Box>

      {/* Suggestions dropdown positioned below input */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <Box flexDirection="column" borderStyle="single" borderColor={theme.muted} paddingX={1} marginTop={1} marginBottom={1}>
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

      {/* Helpful hints - more subtle */}
      {!showSuggestions && value.length === 0 && !userHandoffActive && (
        <Box marginTop={1} marginBottom={2}>
          <Text color={theme.muted}>
            {(() => {
              if (currentModule && flowState.step === 'target') {
                return `Set your target: target https://your-authorized-target.com`;
              } else if (flowState.step === 'objective') {
                return `Type 'execute' to start with default objective, or 'execute <your objective>' for custom`;
              } else if (flowState.step === 'ready') {
                return `Press Enter or type "execute" to start assessment`;
              } else {
                return `Quick start: target <url> or use /help for all commands`;
              }
            })()}
          </Text>
        </Box>
      )}
    </Box>
  );
};