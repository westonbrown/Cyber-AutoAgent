/**
 * MetricsRenderer - Renderer for metrics and performance data
 *
 * Handles metrics_update, usage_update events with optional collapse
 */

import React from 'react';
import { Box, Text } from 'ink';
import { DisplayStreamEvent } from '../StreamDisplay.js';
import { formatTokens, formatCost, formatDuration } from '../../utils/streamFormatters.js';

export interface MetricsRendererProps {
  event: DisplayStreamEvent;
  collapsed?: boolean;
}

/**
 * Render metrics update event
 */
export const MetricsUpdateRenderer: React.FC<{ event: any; collapsed?: boolean }> = ({
  event,
  collapsed = false
}) => {
  const metrics = event.metrics || {};
  const usage = event.usage || {};
  const cost = event.cost || {};

  // Compact mode - single line
  if (collapsed) {
    const parts: string[] = [];

    if (usage.totalTokens) {
      parts.push(`${formatTokens(usage.totalTokens)} tokens`);
    }
    if (cost.totalCost !== undefined) {
      parts.push(formatCost(cost.totalCost));
    }
    if (metrics.latencyMs) {
      parts.push(formatDuration(metrics.latencyMs));
    }

    if (parts.length === 0) return null;

    return (
      <Box>
        <Text dimColor>📊 {parts.join(' • ')}</Text>
      </Box>
    );
  }

  // Expanded mode - detailed breakdown
  return (
    <Box flexDirection="column" borderStyle="single" borderColor="blue" paddingX={1}>
      <Text bold color="blue">
        📊 Metrics Update
      </Text>

      {usage.totalTokens !== undefined && (
        <Box paddingLeft={2}>
          <Text dimColor>Tokens: </Text>
          <Text>
            {formatTokens(usage.inputTokens || 0)} in / {formatTokens(usage.outputTokens || 0)} out
            ={' '}
            <Text bold>{formatTokens(usage.totalTokens)}</Text>
          </Text>
        </Box>
      )}

      {cost.totalCost !== undefined && (
        <Box paddingLeft={2}>
          <Text dimColor>Cost: </Text>
          <Text bold>{formatCost(cost.totalCost)}</Text>
          {cost.modelCost !== undefined && (
            <Text dimColor> (model: {formatCost(cost.modelCost)})</Text>
          )}
        </Box>
      )}

      {metrics.latencyMs !== undefined && (
        <Box paddingLeft={2}>
          <Text dimColor>Latency: </Text>
          <Text>{formatDuration(metrics.latencyMs)}</Text>
        </Box>
      )}

      {metrics.toolCallCount !== undefined && (
        <Box paddingLeft={2}>
          <Text dimColor>Tool Calls: </Text>
          <Text>{metrics.toolCallCount}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Render session summary
 */
export const SessionSummaryRenderer: React.FC<{
  sessionId: string;
  operationId?: string;
  target?: string;
  elapsed?: string;
}> = ({ sessionId, operationId, target, elapsed }) => {
  return (
    <Box flexDirection="column" borderStyle="round" borderColor="cyan" paddingX={1}>
      <Text bold color="cyan">
        ℹ Session Info
      </Text>

      {operationId && (
        <Box paddingLeft={2}>
          <Text dimColor>Operation: </Text>
          <Text>{operationId}</Text>
        </Box>
      )}

      {target && (
        <Box paddingLeft={2}>
          <Text dimColor>Target: </Text>
          <Text>{target}</Text>
        </Box>
      )}

      {elapsed && (
        <Box paddingLeft={2}>
          <Text dimColor>Elapsed: </Text>
          <Text>{elapsed}</Text>
        </Box>
      )}

      <Box paddingLeft={2}>
        <Text dimColor>Session: </Text>
        <Text>{sessionId.slice(0, 8)}...</Text>
      </Box>
    </Box>
  );
};

/**
 * Main MetricsRenderer component
 */
export const MetricsRenderer: React.FC<MetricsRendererProps> = ({ event, collapsed = false }) => {
  const eventType = event.type;

  switch (eventType) {
    case 'metrics_update':
    case 'usage_update':
      return <MetricsUpdateRenderer event={event} collapsed={collapsed} />;
    default:
      return null;
  }
};
