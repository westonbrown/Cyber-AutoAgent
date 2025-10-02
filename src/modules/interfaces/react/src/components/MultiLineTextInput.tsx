/**
 * MultiLineTextInput - Wrapper around ink-text-input that handles multi-line display
 *
 * Renders previous lines as static text, only the last line is editable.
 * Uses state for display but blocks external updates during active typing/pasting.
 *
 * See docs/PASTE_HANDLING_FIX.md for detailed explanation.
 */

import React from 'react';
import { Box, Text } from 'ink';
import TextInput from 'ink-text-input';

interface MultiLineTextInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  focus?: boolean;
  showCursor?: boolean;
  textColor?: string;
}

export const MultiLineTextInput: React.FC<MultiLineTextInputProps> = ({
  value,
  onChange,
  onSubmit,
  placeholder,
  focus,
  showCursor,
  textColor = 'white',
}) => {
  // State for the current line being edited - updates immediately for typing
  const [currentLine, setCurrentLine] = React.useState(() => {
    const lines = value.split('\n');
    return lines[lines.length - 1] || '';
  });

  const fullValueRef = React.useRef(value);
  const updateTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const ourUpdateRef = React.useRef(false); // Track our own updates
  const [inputKey, setInputKey] = React.useState(0); // Force remount for tab completion

  // Handle changes to the current line
  const handleCurrentLineChange = React.useCallback((newCurrentLine: string) => {
    // Update state immediately for responsive typing
    setCurrentLine(newCurrentLine);

    // Clear any pending update
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
    }

    // Debounce parent updates to batch rapid paste chunks
    updateTimeoutRef.current = setTimeout(() => {
      const currentPreviousLines = fullValueRef.current.split('\n').slice(0, -1);
      const newFullValue = currentPreviousLines.length > 0
        ? currentPreviousLines.join('\n') + '\n' + newCurrentLine
        : newCurrentLine;

      fullValueRef.current = newFullValue;

      // Mark as our update to prevent bouncing back
      ourUpdateRef.current = true;
      onChange(newFullValue);

      updateTimeoutRef.current = null;
    }, 100);
  }, [onChange]);

  // Handle submit
  const handleSubmit = React.useCallback((submittedLine: string) => {
    if (updateTimeoutRef.current) {
      clearTimeout(updateTimeoutRef.current);
      updateTimeoutRef.current = null;
    }

    if (onSubmit) {
      const currentPreviousLines = fullValueRef.current.split('\n').slice(0, -1);
      const fullValue = currentPreviousLines.length > 0
        ? currentPreviousLines.join('\n') + '\n' + submittedLine
        : submittedLine;
      onSubmit(fullValue);
    }
  }, [onSubmit]);

  // Detect external value changes (tab completion) but block during active input
  React.useEffect(() => {
    // Check if this is our own update bouncing back
    if (ourUpdateRef.current) {
      ourUpdateRef.current = false;
      return;
    }

    // Block external updates during active typing/pasting
    if (updateTimeoutRef.current !== null) {
      return;
    }

    // If value changed externally while idle, apply it and remount to move cursor to end
    if (value !== fullValueRef.current) {
      fullValueRef.current = value;
      const lines = value.split('\n');
      setCurrentLine(lines[lines.length - 1] || '');
      setInputKey(prev => prev + 1); // Remount to reset cursor position to end
    }
  }, [value]);

  // Split current full value for rendering previous lines
  const lines = fullValueRef.current.split('\n');
  const previousLines = lines.slice(0, -1);

  return (
    <Box flexDirection="column">
      {previousLines.map((line, idx) => (
        <Text key={`line-${idx}`} color={textColor}>
          {line}
        </Text>
      ))}
      <TextInput
        key={inputKey}
        value={currentLine}
        onChange={handleCurrentLineChange}
        onSubmit={handleSubmit}
        placeholder={placeholder}
        focus={focus}
        showCursor={showCursor}
      />
    </Box>
  );
};
