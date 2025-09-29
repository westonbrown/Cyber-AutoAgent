/**
 * Token Input Component
 *
 * Input for long tokens that handles paste truncation.
 * Accepts input in parts if needed and auto-submits when complete.
 */

import React, { useState, useEffect } from 'react';
import { Text, Box, useInput } from 'ink';
import { loggingService } from '../services/LoggingService.js';

interface TokenInputProps {
  onSubmit: (value: string) => void;
  fieldKey?: string;
}

export const TokenInput: React.FC<TokenInputProps> = ({
  onSubmit,
  fieldKey
}) => {
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
        // Avoid verbose logging to prevent large payloads in Ink
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

  // Display masked value
  const maskedDisplay = '*'.repeat(value.length);
  const cursor = cursorVisible ? '█' : ' ';

  return (
    <Box flexDirection="column">
      {/* Simple prompt if no input yet */}
      {value.length === 0 && (
        <Text color="gray">Paste token and press Enter</Text>
      )}

      {/* Token display */}
      <Box>
        <Text>
          {value.length > 0 ? maskedDisplay : ''}{cursor}
        </Text>
        {value.length > 0 && (
          <Text color="gray"> {value.length} chars</Text>
        )}
      </Box>

      {/* Status indicator for AWS Bearer tokens */}
      {fieldKey === 'awsBearerToken' && value.length > 0 && (
        <Text color={value.length >= 132 ? 'green' : 'yellow'}>
          {value.length >= 132 ? '✓ Press Enter to save' : `Paste remaining ${132 - value.length} chars`}
        </Text>
      )}
    </Box>
  );
};