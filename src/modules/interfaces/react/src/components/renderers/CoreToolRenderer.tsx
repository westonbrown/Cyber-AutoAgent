/**
 * CoreToolRenderer - Renderer for core security assessment tools
 *
 * Handles rendering of tool_start, tool_output, tool_end events
 * with consistent formatting and truncation.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DisplayStreamEvent } from '../StreamDisplay.js';
import {
  formatToolParameters,
  formatDuration,
  truncateString,
  sanitizeContent
} from '../../utils/streamFormatters.js';

export interface CoreToolRendererProps {
  event: DisplayStreamEvent;
  terminalWidth?: number;
}

/**
 * Render tool_start event
 */
export const ToolStartRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({
  event,
  terminalWidth = 80
}) => {
  const toolName = event.tool_name || event.tool || 'unknown';
  const params = formatToolParameters(event.tool_input || event.arguments);

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="cyan">
          ▶ Tool:
        </Text>
        <Text> {toolName}</Text>
      </Box>
      {params && (
        <Box paddingLeft={2}>
          <Text dimColor>{params}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render tool_output event
 */
export const ToolOutputRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({
  event,
  terminalWidth = 80
}) => {
  const output = sanitizeContent(event.output || event.content);
  const truncated = truncateString(output, terminalWidth * 2);

  return (
    <Box flexDirection="column" paddingLeft={2}>
      <Text>{truncated}</Text>
      {output.length > truncated.length && (
        <Text dimColor italic>
          ... (output truncated)
        </Text>
      )}
    </Box>
  );
};

/**
 * Render tool_end event
 */
export const ToolEndRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({ event }) => {
  const toolName = event.tool || 'tool';
  const duration = event.duration ? formatDuration(event.duration) : null;
  const success = !event.error;

  return (
    <Box>
      <Text bold color={success ? 'green' : 'red'}>
        {success ? '✓' : '✗'}
      </Text>
      <Text> {toolName} completed</Text>
      {duration && <Text dimColor> ({duration})</Text>}
    </Box>
  );
};

/**
 * Render tool_error event
 */
export const ToolErrorRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({ event }) => {
  const toolName = event.tool || 'tool';
  const errorMsg = event.error || event.message || 'Unknown error';

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="red">
          ✗ Tool Error:
        </Text>
        <Text> {toolName}</Text>
      </Box>
      <Box paddingLeft={2}>
        <Text color="red">{errorMsg}</Text>
      </Box>
    </Box>
  );
};

/**
 * Main CoreToolRenderer component - routes to appropriate sub-renderer
 */
export const CoreToolRenderer: React.FC<CoreToolRendererProps> = ({ event, terminalWidth }) => {
  const eventType = event.type;

  switch (eventType) {
    case 'tool_start':
      return <ToolStartRenderer event={event} terminalWidth={terminalWidth} />;
    case 'tool_output':
      return <ToolOutputRenderer event={event} terminalWidth={terminalWidth} />;
    case 'tool_end':
      return <ToolEndRenderer event={event} terminalWidth={terminalWidth} />;
    case 'tool_error':
      return <ToolErrorRenderer event={event} terminalWidth={terminalWidth} />;
    default:
      return null;
  }
};
