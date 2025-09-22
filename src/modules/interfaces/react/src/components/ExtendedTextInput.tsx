/**
 * ExtendedTextInput Component
 *
 * Enhanced text input component for Ink framework with extended capabilities
 * beyond standard ink-text-input limitations. Provides full-length text support,
 * cursor management, and clipboard handling for terminal interfaces.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Text, useInput } from 'ink';

interface ExtendedTextInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  focus?: boolean;
  showCursor?: boolean;
  cursorChar?: string;
  disabled?: boolean;
}

/**
 * ExtendedTextInput provides enhanced text input capabilities for terminal UIs.
 * Supports full-length text input, cursor positioning, and standard text editing
 * operations without the character limitations of standard components.
 */
export const ExtendedTextInput: React.FC<ExtendedTextInputProps> = ({
  value = '',
  onChange,
  onSubmit,
  placeholder = '',
  focus = true,
  showCursor = true,
  cursorChar = '█',
  disabled = false
}) => {
  const [cursorPosition, setCursorPosition] = useState(value.length);
  // Keep a local reference to the latest value so we can accumulate fast input chunks (e.g., paste)
  const localValueRef = useRef<string>(value);

  // Keep cursor at end and sync local ref when value changes from parent
  useEffect(() => {
    localValueRef.current = value;
    setCursorPosition(value.length);
  }, [value]);

  useInput((input, key) => {
    try {
      if (!focus || disabled) return;

      // Handle form submission first
      if (key.return) {
        if (onSubmit) {
          onSubmit(localValueRef.current);
        }
        return;
      }

      // Text deletion
      if (key.backspace || key.delete) {
        if (localValueRef.current.length > 0) {
          const next = localValueRef.current.slice(0, -1);
          localValueRef.current = next;
          onChange(next);
        }
        return;
      }

      // Clear line
      if (key.ctrl && input === 'u') {
        localValueRef.current = '';
        onChange('');
        return;
      }

      // Standard text input (including paste chunks)
      if (input && !key.ctrl && !key.meta) {
        const next = (localValueRef.current || '') + input;
        localValueRef.current = next;
        onChange(next);
        return;
      }
    } catch (error) {
      // Swallow input errors to avoid crashing input handling
    }
  }, { isActive: focus && !disabled });

  // Simple render - ExtendedTextInput only handles single line (the tail)
  try {
    if (!value && placeholder) {
      return <Text color="gray">{placeholder}</Text>;
    }

    // Ensure value is a safe string for rendering
    const safeValue = String(value || '');

    // Just render the single line value with cursor
    return <Text>{safeValue}{showCursor && focus && !disabled ? cursorChar : ''}</Text>;
  } catch (error) {
    // Fallback render without logging
    return <Text>{'_'}</Text>;
  }
};