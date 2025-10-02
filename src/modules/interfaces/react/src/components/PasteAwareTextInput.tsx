/**
 * PasteAwareTextInput - Text input with proper bracketed paste support
 * Uses custom KeypressContext instead of Ink's useInput
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Text } from 'ink';
import chalk from 'chalk';
import { useKeypressContext, type Key } from '../contexts/KeypressContext.js';

interface PasteAwareTextInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  focus?: boolean;
  showCursor?: boolean;
  mask?: string;
}

export const PasteAwareTextInput: React.FC<PasteAwareTextInputProps> = ({
  value: originalValue,
  onChange,
  onSubmit,
  placeholder = '',
  focus = true,
  showCursor = true,
  mask,
}) => {
  const [state, setState] = useState({
    cursorOffset: (originalValue || '').length,
  });

  const { cursorOffset } = state;
  const { subscribe, unsubscribe } = useKeypressContext();

  // Sync cursor when value changes externally
  useEffect(() => {
    setState(previousState => {
      if (!focus || !showCursor) {
        return previousState;
      }

      const newValue = originalValue || '';
      if (previousState.cursorOffset > newValue.length) {
        return { cursorOffset: newValue.length };
      }

      return previousState;
    });
  }, [originalValue, focus, showCursor]);

  const handleKeypress = useCallback(
    (key: Key) => {
      if (!focus) return;

      // Ignore navigation keys that might be used elsewhere
      if (
        (key.ctrl && key.name === 'c') ||
        (key.ctrl && key.name === 'l') ||
        (key.ctrl && key.name === 's')
      ) {
        return;
      }

      // Submit on Enter
      if (key.name === 'return') {
        if (onSubmit) {
          onSubmit(originalValue);
        }
        return;
      }

      let nextCursorOffset = cursorOffset;
      let nextValue = originalValue;

      // Cursor movement
      if (key.name === 'left') {
        if (showCursor) {
          nextCursorOffset = Math.max(0, cursorOffset - 1);
        }
      } else if (key.name === 'right') {
        if (showCursor) {
          nextCursorOffset = Math.min(originalValue.length, cursorOffset + 1);
        }
      } else if (key.name === 'backspace') {
        // Delete before cursor
        if (cursorOffset > 0) {
          nextValue =
            originalValue.slice(0, cursorOffset - 1) +
            originalValue.slice(cursorOffset);
          nextCursorOffset = cursorOffset - 1;
        }
      } else if (key.name === 'delete') {
        // Delete at cursor
        if (cursorOffset < originalValue.length) {
          nextValue =
            originalValue.slice(0, cursorOffset) +
            originalValue.slice(cursorOffset + 1);
        }
      } else if (key.paste) {
        // PASTE - insert entire sequence at cursor
        nextValue =
          originalValue.slice(0, cursorOffset) +
          key.sequence +
          originalValue.slice(cursorOffset);
        nextCursorOffset = cursorOffset + key.sequence.length;
      } else if (key.sequence && !key.ctrl && !key.meta) {
        // Normal character input
        nextValue =
          originalValue.slice(0, cursorOffset) +
          key.sequence +
          originalValue.slice(cursorOffset);
        nextCursorOffset = cursorOffset + key.sequence.length;
      }

      // Update state
      setState({ cursorOffset: nextCursorOffset });

      // Notify parent of value change
      if (nextValue !== originalValue) {
        onChange(nextValue);
      }
    },
    [focus, cursorOffset, originalValue, showCursor, onChange, onSubmit]
  );

  // Subscribe to keypress events
  useEffect(() => {
    if (!focus) return;

    subscribe(handleKeypress);
    return () => {
      unsubscribe(handleKeypress);
    };
  }, [focus, handleKeypress, subscribe, unsubscribe]);

  // Render
  const value = mask ? mask.repeat(originalValue.length) : originalValue;
  let renderedValue = value;
  let renderedPlaceholder = placeholder ? chalk.grey(placeholder) : undefined;

  if (showCursor && focus) {
    renderedPlaceholder =
      placeholder.length > 0
        ? chalk.inverse(placeholder[0]) + chalk.grey(placeholder.slice(1))
        : chalk.inverse(' ');

    renderedValue = value.length > 0 ? '' : chalk.inverse(' ');

    let i = 0;
    for (const char of value) {
      renderedValue += i === cursorOffset ? chalk.inverse(char) : char;
      i++;
    }

    if (value.length > 0 && cursorOffset === value.length) {
      renderedValue += chalk.inverse(' ');
    }
  }

  return (
    <Text>
      {placeholder
        ? value.length > 0
          ? renderedValue
          : renderedPlaceholder
        : renderedValue}
    </Text>
  );
};
