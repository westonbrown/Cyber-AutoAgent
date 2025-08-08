/**
 * Footer Component
 * 
 * Displays model info, context remaining, directory status, and operation metrics.
 */
import React from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';
import { StatusIndicator } from './StatusIndicator.js';

interface FooterProps {
  model: string;
  contextRemaining: number;  // Percentage 0-100
  directory: string;
  branchName?: string;
  operationStatus?: {
    step: number;
    totalSteps: number;
    description: string;
    isRunning: boolean;
  };
  errorCount?: number;
  debugMode?: boolean;
  operationMetrics?: {
    tokens?: number;
    cost?: number;
    duration: string;
    memoryOps: number;
    evidence: number;
  };
  connectionStatus?: 'connected' | 'connecting' | 'error' | 'offline';
}

export const Footer: React.FC<FooterProps> = React.memo(({
  model,
  contextRemaining,
  directory,
  branchName,
  operationStatus,
  errorCount = 0,
  debugMode = false,
  operationMetrics,
  connectionStatus = 'connected'
}) => {
  const theme = themeManager.getCurrentTheme();

  const formatCost = (cost: number) => {
    return cost < 0.01 ? '<$0.01' : `$${cost.toFixed(2)}`;
  };

  const shortenPath = (path: string, maxLength: number = 50) => {
    if (path.length <= maxLength) return path;
    return '...' + path.slice(-(maxLength - 3));
  };

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return { icon: '●', color: theme.success };
      case 'connecting':
        return { icon: '◐', color: theme.warning };
      case 'error':
        return { icon: '✗', color: theme.danger };
      case 'offline':
        return { icon: '○', color: theme.danger };
      default:
        return { icon: '○', color: theme.muted };
    }
  };

  const connIcon = getConnectionIcon();

  return (
    <Box width="100%" flexDirection="row">
      {/* Left section - Status */}
      <Box flexGrow={0} flexShrink={0}>
        <StatusIndicator compact={true} position="footer" />
      </Box>

      {/* Spacer */}
      <Box flexGrow={1} />

      {/* Right section - All metrics and info in one line */}
      <Box flexGrow={0} flexShrink={0}>
        {/* Token and cost metrics - always visible */}
        <Text color={theme.muted}>
          {operationMetrics ? (operationMetrics.tokens || 0).toLocaleString() : '0'} tokens
        </Text>
        <Text color={theme.muted}> | </Text>
        <Text color={theme.muted}>
          {operationMetrics ? formatCost(operationMetrics.cost || 0) : '$0.00'}
        </Text>
        
        {/* Duration when available */}
        {operationMetrics && operationMetrics.duration !== '0s' && (
          <>
            <Text color={theme.muted}> | </Text>
            <Text color={theme.muted}>{operationMetrics.duration}</Text>
          </>
        )}
        
        {/* Memory and evidence metrics when available */}
        {operationMetrics && (operationMetrics.memoryOps > 0 || operationMetrics.evidence > 0) && (
          <>
            <Text color={theme.muted}> | </Text>
            {operationMetrics.memoryOps > 0 && (
              <>
                <Text color={theme.muted}>{operationMetrics.memoryOps}</Text>
                <Text color={theme.muted}> mem</Text>
              </>
            )}
            {operationMetrics.memoryOps > 0 && operationMetrics.evidence > 0 && (
              <Text color={theme.muted}> | </Text>
            )}
            {operationMetrics.evidence > 0 && (
              <>
                <Text color={theme.muted}>{operationMetrics.evidence}</Text>
                <Text color={theme.muted}> ev</Text>
              </>
            )}
          </>
        )}
        
        <Text color={theme.muted}>  |  </Text>
        
        {/* Errors if any */}
        {errorCount > 0 && (
          <>
            <Text color={theme.danger}>{errorCount} error{errorCount > 1 ? 's' : ''}</Text>
            <Text color={theme.muted}>  |  </Text>
          </>
        )}
        
        {/* Keyboard shortcuts */}
        <Text color={theme.muted}>[ESC] Kill Switch</Text>
        
        <Text color={theme.muted}>  |  </Text>
        
        {/* Provider and connection */}
        <Text color={connIcon.color}>{connIcon.icon}</Text>
        <Text color={theme.muted}> {connectionStatus === 'connected' ? 'bedrock' : connectionStatus}</Text>
        
        {/* Model - only show if provided */}
        {model && (
          <>
            <Text color={theme.muted}>  |  </Text>
            <Text color={theme.muted}>{model}</Text>
          </>
        )}
      </Box>
    </Box>
  );
});

Footer.displayName = 'Footer';