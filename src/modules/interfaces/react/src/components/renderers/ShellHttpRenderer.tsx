/**
 * ShellHttpRenderer - Renderer for shell commands and HTTP requests
 *
 * Handles shell_command, shell_output, shell_error, http_request, http_response events
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DisplayStreamEvent } from '../StreamDisplay.js';
import { truncateString, formatDuration } from '../../utils/streamFormatters.js';

export interface ShellHttpRendererProps {
  event: DisplayStreamEvent;
  terminalWidth?: number;
}

/**
 * Render shell command event
 */
export const ShellCommandRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({
  event
}) => {
  const command = event.command || event.content;

  return (
    <Box>
      <Text bold color="cyan">
        $
      </Text>
      <Text> {command}</Text>
    </Box>
  );
};

/**
 * Render shell output event
 */
export const ShellOutputRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({
  event,
  terminalWidth = 80
}) => {
  const output = event.output || event.content || '';
  const lines = output.split('\n');
  const maxLines = 10;
  const displayLines = lines.slice(0, maxLines);
  const hasMore = lines.length > maxLines;

  return (
    <Box flexDirection="column" paddingLeft={2}>
      {displayLines.map((line: string, idx: number) => (
        <Text key={idx}>{truncateString(line, terminalWidth)}</Text>
      ))}
      {hasMore && (
        <Text dimColor italic>
          ... {lines.length - maxLines} more lines
        </Text>
      )}
    </Box>
  );
};

/**
 * Render shell error event
 */
export const ShellErrorRenderer: React.FC<{ event: any }> = ({ event }) => {
  const error = event.error || event.content;
  const exitCode = event.exitCode;

  return (
    <Box flexDirection="column" paddingLeft={2}>
      <Text color="red">{error}</Text>
      {exitCode !== undefined && (
        <Text dimColor>Exit code: {exitCode}</Text>
      )}
    </Box>
  );
};

/**
 * Render HTTP request event
 */
export const HttpRequestRenderer: React.FC<{ event: any }> = ({ event }) => {
  const method = event.method || 'GET';
  const url = event.url || '';

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="blue">
          → HTTP
        </Text>
        <Text> {method} {truncateString(url, 60)}</Text>
      </Box>
      {event.headers && Object.keys(event.headers).length > 0 && (
        <Box paddingLeft={2}>
          <Text dimColor>Headers: {Object.keys(event.headers).length} items</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render HTTP response event
 */
export const HttpResponseRenderer: React.FC<{ event: any }> = ({ event }) => {
  const statusCode = event.statusCode || 200;
  const responseTime = event.responseTime ? formatDuration(event.responseTime) : null;
  const isSuccess = statusCode >= 200 && statusCode < 300;
  const isError = statusCode >= 400;

  return (
    <Box flexDirection="column" paddingLeft={2}>
      <Box>
        <Text bold color={isSuccess ? 'green' : isError ? 'red' : 'yellow'}>
          ← {statusCode}
        </Text>
        {responseTime && <Text dimColor> ({responseTime})</Text>}
      </Box>
      {event.body && (
        <Box paddingLeft={2}>
          <Text dimColor>{truncateString(JSON.stringify(event.body), 100)}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Main ShellHttpRenderer component - routes to appropriate sub-renderer
 */
export const ShellHttpRenderer: React.FC<ShellHttpRendererProps> = ({ event, terminalWidth }) => {
  const eventType = event.type;

  switch (eventType) {
    case 'shell_command':
    case 'command':
      return <ShellCommandRenderer event={event} terminalWidth={terminalWidth} />;
    case 'shell_output':
      return <ShellOutputRenderer event={event} terminalWidth={terminalWidth} />;
    case 'shell_error':
      return <ShellErrorRenderer event={event} />;
    case 'http_request':
      return <HttpRequestRenderer event={event} />;
    case 'http_response':
      return <HttpResponseRenderer event={event} />;
    default:
      return null;
  }
};
