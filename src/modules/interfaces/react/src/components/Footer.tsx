import React from 'react';
import { Box, Text } from 'ink';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';

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
  modelProvider,
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

  // Build a single-line footer string and hard-truncate to terminal width to avoid Ink layout bugs
  const cols = Number.isFinite(process.stdout.columns) && process.stdout.columns ? Math.floor(process.stdout.columns) : 80;
  const left = `${connIcon.icon} ${deploymentMode || ''}`.trim();
  const rightParts: string[] = [];
  if (model) rightParts.push(model);
  rightParts.push(`${totalTokens} tokens`, totalCost);
  if (hasDuration) rightParts.push(operationMetrics!.duration);
  if (hasMem) rightParts.push(`${operationMetrics!.memoryOps} mem`);
  if (errorCount > 0) rightParts.push(`${errorCount} error${errorCount > 1 ? 's' : ''}`);
  rightParts.push('[ESC] Kill Switch');
  if (debugMode) rightParts.push('[DEBUG MODE]');
  const right = rightParts.join(' | ');

  // Ensure at least one space between left and right; clamp to available columns
  const spacer = ' ';
  let line = `${left}${spacer}${right}`;
  if (line.length > cols) {
    // Prefer keeping the right-side info; trim left if necessary
    const keepRight = Math.min(right.length + 1, cols - 1);
    const trimmedLeft = left.slice(0, Math.max(0, cols - keepRight - 1));
    line = `${trimmedLeft}${spacer}${right}`.slice(0, cols);
  }

  return (
    <Box>
      <Text color={theme.muted}>{line}</Text>
    </Box>
  );
});

Footer.displayName = 'Footer';