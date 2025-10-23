/**
 * GenericRenderer - Fallback renderer for unknown/generic events
 *
 * Provides graceful degradation for unrecognized event types with
 * metadata-driven enrichment.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DisplayStreamEvent } from '../StreamDisplay.js';
import { formatAsTree, sanitizeContent, truncateString } from '../../utils/streamFormatters.js';

export interface GenericRendererProps {
  event: DisplayStreamEvent;
  terminalWidth?: number;
  showMetadata?: boolean;
}

/**
 * Extract display-worthy content from unknown event
 */
function extractEventContent(event: any): {
  title: string;
  content?: string;
  metadata?: Record<string, any>;
} {
  const eventType = event.type || 'unknown';

  // Try to find meaningful content
  const content =
    event.content || event.message || event.output || event.data || event.result;

  // Collect metadata (excluding common fields)
  const excludeKeys = new Set(['type', 'id', 'timestamp', 'sessionId', 'content', 'message']);
  const metadata: Record<string, any> = {};

  Object.entries(event).forEach(([key, value]) => {
    if (!excludeKeys.has(key) && value !== undefined && value !== null) {
      metadata[key] = value;
    }
  });

  return {
    title: eventType.replace(/_/g, ' ').toUpperCase(),
    content: content ? sanitizeContent(content) : undefined,
    metadata: Object.keys(metadata).length > 0 ? metadata : undefined
  };
}

/**
 * Render metadata section
 */
const MetadataSection: React.FC<{ metadata: Record<string, any>; terminalWidth: number }> = ({
  metadata,
  terminalWidth
}) => {
  const entries = Object.entries(metadata).slice(0, 5); // Limit to prevent overflow

  return (
    <Box flexDirection="column" paddingLeft={2} marginTop={1}>
      <Text dimColor italic>
        Metadata:
      </Text>
      {entries.map(([key, value]) => (
        <Box key={key} paddingLeft={1}>
          <Text dimColor>
            {key}: {truncateString(String(value), terminalWidth - 20)}
          </Text>
        </Box>
      ))}
      {Object.keys(metadata).length > 5 && (
        <Box paddingLeft={1}>
          <Text dimColor>... {Object.keys(metadata).length - 5} more fields</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Main GenericRenderer component
 *
 * Provides a consistent fallback rendering for any event type that
 * doesn't have a specialized renderer.
 */
export const GenericRenderer: React.FC<GenericRendererProps> = ({
  event,
  terminalWidth = 80,
  showMetadata = true
}) => {
  const { title, content, metadata } = extractEventContent(event);

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="gray">
          ⚡
        </Text>
        <Text> {title}</Text>
      </Box>

      {content && (
        <Box paddingLeft={2} marginTop={1}>
          <Text>{truncateString(content, terminalWidth * 2)}</Text>
        </Box>
      )}

      {showMetadata && metadata && (
        <MetadataSection metadata={metadata} terminalWidth={terminalWidth} />
      )}
    </Box>
  );
};

/**
 * Render unknown tool invocation with best-effort formatting
 */
export const UnknownToolRenderer: React.FC<{
  event: any;
  terminalWidth?: number;
}> = ({ event, terminalWidth = 80 }) => {
  const toolName = event.tool_name || event.tool || 'Unknown Tool';
  const input = event.tool_input || event.input || event.arguments;
  const output = event.output || event.result;

  return (
    <Box flexDirection="column">
      <Box>
        <Text bold color="cyan">
          🔧
        </Text>
        <Text> {toolName}</Text>
      </Box>

      {input && (
        <Box paddingLeft={2} flexDirection="column" marginTop={1}>
          <Text dimColor italic>
            Input:
          </Text>
          <Text dimColor>{truncateString(sanitizeContent(input), terminalWidth)}</Text>
        </Box>
      )}

      {output && (
        <Box paddingLeft={2} flexDirection="column" marginTop={1}>
          <Text dimColor italic>
            Output:
          </Text>
          <Text>{truncateString(sanitizeContent(output), terminalWidth)}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Determine if event represents an unknown tool
 */
export function isUnknownToolEvent(event: any): boolean {
  return (
    (event.type === 'tool_start' || event.type === 'tool_output' || event.type === 'tool_end') &&
    event.tool_name !== undefined
  );
}
