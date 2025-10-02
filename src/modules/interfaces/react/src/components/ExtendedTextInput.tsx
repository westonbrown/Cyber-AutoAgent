/**
 * ExtendedTextInput Component
 *
 * Enhanced text input component for Ink framework with extended capabilities
 * beyond standard ink-text-input limitations. Provides full-length text support,
 * cursor management, and clipboard handling for terminal interfaces.
 *
 * Uses reducer-based state management inspired by gemini-cli for atomic operations
 * and reliable paste handling.
 */

import React, { useEffect } from 'react';
import { Text, useInput } from 'ink';
import { useTextBuffer } from '../hooks/useTextBuffer.js';

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
  // Use reducer-based text buffer for atomic operations
  const buffer = useTextBuffer({
    initialValue: value,
    onChange
  });

  // Sync buffer with external value changes
  useEffect(() => {
    if (buffer.text !== value) {
      buffer.setText(value, Math.min(buffer.cursorPosition, value.length));
    }
  }, [value]);

  useInput((input, key) => {
    try {
      if (!focus || disabled) return;

      // Handle form submission first
      if (key.return) {
        if (onSubmit) {
          onSubmit(buffer.text);
        }
        return;
      }

      // Cursor movement - left arrow
      if (key.leftArrow) {
        buffer.moveLeft();
        return;
      }

      // Cursor movement - right arrow
      if (key.rightArrow) {
        buffer.moveRight();
        return;
      }

      // Home - move to beginning
      if (key.ctrl && input === 'a') {
        buffer.moveToStart();
        return;
      }

      // End - move to end
      if (key.ctrl && input === 'e') {
        buffer.moveToEnd();
        return;
      }

      // Backspace - delete before cursor
      if (key.backspace) {
        buffer.deleteBeforeCursor();
        return;
      }

      // Delete key - delete at cursor
      if (key.delete) {
        buffer.deleteAfterCursor();
        return;
      }

      // Clear line
      if (key.ctrl && input === 'u') {
        buffer.clear();
        return;
      }

      // Character insertion at cursor position
      // This handles both normal typing AND paste
      // The reducer ensures atomic updates without race conditions
      if (input && !key.ctrl && !key.meta) {
        buffer.insert(input);
        return;
      }
    } catch (error) {
      // Swallow input errors to avoid crashing input handling
    }
  }, { isActive: focus && !disabled });

  // Render with cursor at correct position
  try {
    if (!buffer.text && placeholder) {
      return <Text color="gray">{placeholder}</Text>;
    }

    // Ensure value is a safe string for rendering
    const safeValue = String(buffer.text || '');

    if (!showCursor || !focus || disabled) {
      return <Text>{safeValue}</Text>;
    }

    // Split text at cursor position and insert cursor character
    const beforeCursor = safeValue.slice(0, buffer.cursorPosition);
    const atCursor = safeValue.slice(buffer.cursorPosition, buffer.cursorPosition + 1) || ' ';
    const afterCursor = safeValue.slice(buffer.cursorPosition + 1);

    // Render with cursor at position
    if (buffer.cursorPosition >= safeValue.length) {
      // Cursor at end
      return <Text>{safeValue}{cursorChar}</Text>;
    } else {
      // Cursor in middle - show inverse character
      return <Text>{beforeCursor}<Text inverse>{atCursor}</Text>{afterCursor}</Text>;
    }
  } catch (error) {
    // Fallback render without logging
    return <Text>{'_'}</Text>;
  }
};
