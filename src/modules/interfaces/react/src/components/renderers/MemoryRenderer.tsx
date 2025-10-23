/**
 * MemoryRenderer - Renderer for memory operations and reasoning
 *
 * Handles memory_store, memory_retrieve, memory_search, reasoning events
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DisplayStreamEvent } from '../StreamDisplay.js';
import { truncateString, formatAsTree } from '../../utils/streamFormatters.js';

export interface MemoryRendererProps {
  event: DisplayStreamEvent;
  terminalWidth?: number;
}

/**
 * Render memory store event
 */
export const MemoryStoreRenderer: React.FC<{ event: any }> = ({ event }) => {
  const key = event.key || '';
  const value = event.value;

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="magenta">
          💾 Memory Store
        </Text>
        {key && <Text>: {truncateString(key, 40)}</Text>}
      </Box>
      {value && (
        <Box paddingLeft={2} flexDirection="column">
          <Text dimColor>{truncateString(JSON.stringify(value), 100)}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render memory retrieve event
 */
export const MemoryRetrieveRenderer: React.FC<{ event: any }> = ({ event }) => {
  const key = event.key || '';
  const results = event.results || [];

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="magenta">
          🔍 Memory Retrieve
        </Text>
        {key && <Text>: {truncateString(key, 40)}</Text>}
      </Box>
      {results.length > 0 && (
        <Box paddingLeft={2}>
          <Text dimColor>{results.length} result(s) found</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render memory search event
 */
export const MemorySearchRenderer: React.FC<{ event: any }> = ({ event }) => {
  const query = event.query || '';
  const results = event.results || [];

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="magenta">
          🔎 Memory Search
        </Text>
        {query && <Text>: {truncateString(query, 50)}</Text>}
      </Box>
      {results.length > 0 && (
        <Box paddingLeft={2}>
          <Text dimColor>{results.length} match(es) found</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render reasoning event
 */
export const ReasoningRenderer: React.FC<{ event: any; terminalWidth?: number }> = ({
  event,
  terminalWidth = 80
}) => {
  const content = event.content || event.delta || '';
  const isReasoning = event.isReasoning !== false;

  if (!content) return null;

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="yellow">
          💭 {isReasoning ? 'Reasoning' : 'Thinking'}
        </Text>
      </Box>
      <Box paddingLeft={2}>
        <Text dimColor>{truncateString(content, terminalWidth * 2)}</Text>
      </Box>
    </Box>
  );
};

/**
 * Render reasoning delta (streaming)
 */
export const ReasoningDeltaRenderer: React.FC<{ event: any }> = ({ event }) => {
  const delta = event.delta || '';

  if (!delta) return null;

  return (
    <Box paddingLeft={2}>
      <Text dimColor>{delta}</Text>
    </Box>
  );
};

/**
 * Main MemoryRenderer component - routes to appropriate sub-renderer
 */
export const MemoryRenderer: React.FC<MemoryRendererProps> = ({ event, terminalWidth }) => {
  const eventType = event.type;

  switch (eventType) {
    case 'memory_store':
      return <MemoryStoreRenderer event={event} />;
    case 'memory_retrieve':
      return <MemoryRetrieveRenderer event={event} />;
    case 'memory_search':
      return <MemorySearchRenderer event={event} />;
    case 'reasoning':
    case 'reasoning_start':
      return <ReasoningRenderer event={event} terminalWidth={terminalWidth} />;
    case 'reasoning_delta':
      return <ReasoningDeltaRenderer event={event} />;
    default:
      return null;
  }
};
