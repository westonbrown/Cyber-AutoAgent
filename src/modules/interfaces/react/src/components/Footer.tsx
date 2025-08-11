import React from 'react';
import { Box, Text } from 'ink';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { CyberTheme } from '../themes/types.js';

interface FooterProps {
  model?: string;
  debugMode?: boolean;
  operationMetrics?: {
    tokens?: number;
    inputTokens?: number;
    outputTokens?: number;
    cost?: number;
    duration?: string;
    memoryOps?: number;
    evidence?: number;
  };
  connectionStatus?: 'connected' | 'connecting' | 'error' | 'offline';
  modelProvider?: string;
  deploymentMode?: string;
  errorCount?: number;
  isOperationRunning: boolean;
  isInputPaused: boolean;
  operationName?: string;
}

export const Footer: React.FC<FooterProps> = React.memo(({
  model,
  debugMode = false,
  operationMetrics,
  connectionStatus = 'connected',
  modelProvider = 'bedrock',
  deploymentMode,
  isOperationRunning,
  isInputPaused,
  operationName,
  errorCount = 0,
}) => {
  const theme = themeManager.getCurrentTheme();
  const { config } = useConfig();

  // --- Footer Rendering (always visible) ---
  const formatCost = (cost: number) => {
    if (cost === 0) return '$0.00';
    return cost < 0.01 ? '<$0.01' : `$${cost.toFixed(2)}`;
  };

  const calculateCost = () => {
    if (!operationMetrics || !model) return 0;
    const inputTokens = operationMetrics.inputTokens || Math.floor((operationMetrics.tokens || 0) * 0.8);
    const outputTokens = operationMetrics.outputTokens || Math.floor((operationMetrics.tokens || 0) * 0.2);
    let pricing = config?.modelPricing?.[model];
    
    if (!pricing) {
        pricing = { inputCostPer1k: 0, outputCostPer1k: 0 };
    }
    const cost = (inputTokens / 1000) * pricing.inputCostPer1k + (outputTokens / 1000) * pricing.outputCostPer1k;
    return cost;
  };

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return { icon: '●', color: theme.success };
      case 'connecting':
        return { icon: '◐', color: theme.warning };
      case 'error':
        return { icon: '✗', color: theme.danger };
      default:
        return { icon: '○', color: theme.muted };
    }
  };

  const connIcon = getConnectionIcon();
  const totalCost = formatCost(calculateCost());
  const totalTokens = (operationMetrics?.tokens || 0).toLocaleString();
  const hasDuration = !!operationMetrics?.duration && operationMetrics?.duration !== '0s';
  const hasMem = (operationMetrics?.memoryOps || 0) > 0;
  const hasEv = (operationMetrics?.evidence || 0) > 0;

  return (
    <Box width="100%" flexDirection="row">
      {/* Left section: Connection Status */}
      <Box flexGrow={0} flexShrink={0}>
        <Text color={connIcon.color}>{connIcon.icon}</Text>
        <Text color={theme.muted}> {deploymentMode || modelProvider}</Text>
      </Box>

      {/* Spacer */}
      <Box flexGrow={1} />

      {/* Right section: Metrics and Info */}
      <Box flexGrow={0} flexShrink={0}>
        {model && (
            <>
                <Text color={theme.muted}>{model}</Text>
                <Text color={theme.muted}> | </Text>
            </>
        )}
        <Text color={theme.muted}>{totalTokens} tokens</Text>
        <Text color={theme.muted}> | </Text>
        <Text color={theme.muted}>{totalCost}</Text>
        {hasDuration && (
          <>
            <Text color={theme.muted}> | </Text>
            <Text color={theme.muted}>{operationMetrics?.duration}</Text>
          </>
        )}
        {(hasMem || hasEv) && (
          <>
            <Text color={theme.muted}> | </Text>
            {hasMem && (
              <>
                <Text color={theme.muted}>{operationMetrics?.memoryOps}</Text>
                <Text color={theme.muted}> mem</Text>
              </>
            )}
            {hasMem && hasEv && <Text color={theme.muted}> • </Text>}
            {hasEv && (
              <>
                <Text color={theme.muted}>{operationMetrics?.evidence}</Text>
                <Text color={theme.muted}> ev</Text>
              </>
            )}
          </>
        )}
        {errorCount > 0 && (
          <>
            <Text color={theme.muted}> | </Text>
            <Text color={theme.danger}>{errorCount} error{errorCount > 1 ? 's' : ''}</Text>
          </>
        )}
        <Text color={theme.muted}> | </Text>
        <Text color={theme.muted}>[ESC] Kill Switch</Text>
        {debugMode && <Text color="yellow"> | [DEBUG MODE]</Text>}
      </Box>
    </Box>
  );
});

Footer.displayName = 'Footer';