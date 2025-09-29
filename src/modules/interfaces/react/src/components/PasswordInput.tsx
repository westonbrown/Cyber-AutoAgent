/**
 * Custom Password Input Component
 *
 * Works around ink-text-input paste truncation issue by using
 * raw input handling and accumulating characters directly.
 */

import React, { useState, useEffect } from 'react';
import { Text, Box, useInput } from 'ink';

interface PasswordInputProps {
  onSubmit: (value: string) => void;
  fieldKey?: string;
}

export const PasswordInput: React.FC<PasswordInputProps> = ({ onSubmit, fieldKey }) => {
  const [value, setValue] = useState('');
  const [cursorVisible, setCursorVisible] = useState(true);

  // Cursor blink effect
  useEffect(() => {
    const timer = setInterval(() => {
      setCursorVisible(prev => !prev);
    }, 500);
    return () => clearInterval(timer);
  }, []);

  useInput((input, key) => {
    // Submit on Enter
    if (key.return) {
      if (value.length > 0) {
        onSubmit(value);
      }
      return;
    }

    // Clear on Escape
    if (key.escape) {
      setValue('');
      return;
    }

    // Handle backspace
    if (key.backspace || key.delete) {
      setValue(prev => prev.slice(0, -1));
      return;
    }

    // Skip control key combinations
    if (key.ctrl && input === 'v') return;
    if (key.meta && input === 'v') return;

    // Handle regular input and paste
    if (input && input.length > 0 && !key.ctrl && !key.meta) {
      setValue(prev => prev + input);
    }
  });

  // Display
  const maskedDisplay = '*'.repeat(value.length);
  const cursor = cursorVisible ? '█' : ' ';

  return (
    <Box>
      <Text>
        {value.length > 0 ? maskedDisplay : ''}{cursor}
      </Text>
      {value.length > 0 && (
        <Text color="gray"> {value.length} chars</Text>
      )}
    </Box>
  );
};