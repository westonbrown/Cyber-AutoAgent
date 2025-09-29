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

  // Bracketed paste handling and simple coalescing
  const isPastingRef = useRef(false);
  const pasteBufferRef = useRef('');
  const pasteFlushTimerRef = useRef<NodeJS.Timeout | null>(null);
  const flushPaste = (immediate = false) => {
    const buf = pasteBufferRef.current;
    if (!buf) return;
    const append = (localValueRef.current || '') + buf;
    localValueRef.current = append;
    pasteBufferRef.current = '';
    onChange(append);
    if (immediate && pasteFlushTimerRef.current) {
      clearTimeout(pasteFlushTimerRef.current);
      pasteFlushTimerRef.current = null;
    }
  };

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

      // Bracketed paste start/end sequences
      if (input === '\u001b[200~') { // start
        isPastingRef.current = true;
        pasteBufferRef.current = '';
        return;
      }
      if (input === '\u001b[201~') { // end
        isPastingRef.current = false;
        flushPaste(true);
        return;
      }

      // During bracketed paste: accumulate without re-rendering every chunk
      if (isPastingRef.current && input && !key.ctrl && !key.meta) {
        pasteBufferRef.current += input;
        // Optional safety: flush occasionally in very long pastes
        if (!pasteFlushTimerRef.current) {
          pasteFlushTimerRef.current = setTimeout(() => {
            flushPaste();
            pasteFlushTimerRef.current = null;
          }, 30);
        }
        return;
      }

      // Standard text input (including non-bracketed large chunks)
      if (input && !key.ctrl && !key.meta) {
        // If this looks like a large paste chunk, coalesce briefly
        if (input.length > 10) {
          pasteBufferRef.current += input;
          if (pasteFlushTimerRef.current) clearTimeout(pasteFlushTimerRef.current);
          pasteFlushTimerRef.current = setTimeout(() => {
            flushPaste(true);
          }, 30);
          return;
        }
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