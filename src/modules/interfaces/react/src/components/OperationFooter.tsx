/**
 * OperationFooter - Minimal footer for long-running operations
 */

import React from 'react';
import { Box, Text } from 'ink';

interface OperationFooterProps {
  tokens: number;
  duration: string;
  memoryOps: number;
  evidence: number;
}

const DIVIDER = '─'.repeat(process.stdout.columns || 80);

export const OperationFooter: React.FC<OperationFooterProps> = ({
  tokens,
  duration,
  memoryOps,
  evidence,
}) => {
  return (
    <Box flexDirection="column">
      <Text dimColor>{DIVIDER}</Text>
      <Text>
        Tokens: <Text bold>{tokens.toLocaleString()}</Text> | 
        Duration: <Text bold>{duration}</Text> | 
        Memory: <Text bold>{memoryOps}</Text> ops | 
        Evidence: <Text bold>{evidence}</Text> items
      </Text>
      <Text dimColor>[CTRL+C] Kill operation</Text>
      <Text dimColor>{DIVIDER}</Text>
    </Box>
  );
};