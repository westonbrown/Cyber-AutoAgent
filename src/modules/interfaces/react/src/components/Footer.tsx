/**
 * Footer Component
 * 
 * Displays model info, context remaining, directory status, and operation metrics.
 */
import React from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';
import { StatusIndicator } from './StatusIndicator.js';
import { useConfig } from '../contexts/ConfigContext.js';

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
    inputTokens?: number;
    outputTokens?: number;
    cost?: number;
    duration: string;
    memoryOps: number;
    evidence: number;
  };
  connectionStatus?: 'connected' | 'connecting' | 'error' | 'offline';
  modelProvider?: string; // Provider from config (bedrock, openai, ollama, etc.)
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
  connectionStatus = 'connected',
  modelProvider = 'bedrock'
}) => {
  const theme = themeManager.getCurrentTheme();
  const { config } = useConfig();

  const formatCost = (cost: number) => {
    return cost < 0.01 ? '<$0.01' : `$${cost.toFixed(2)}`;
  };
  
  const calculateCost = () => {
    if (!operationMetrics || !model) return 0;
    
    // Use input/output tokens if available, otherwise estimate from total
    const inputTokens = operationMetrics.inputTokens || Math.floor((operationMetrics.tokens || 0) * 0.8);
    const outputTokens = operationMetrics.outputTokens || Math.floor((operationMetrics.tokens || 0) * 0.2);
    
    // Get pricing from config or use provider-specific defaults
    let pricing = config?.modelPricing?.[model];
    
    if (!pricing) {
      // Provider-specific defaults when no custom pricing is set
      if (config?.modelProvider === 'ollama') {
        pricing = { inputCostPer1k: 0, outputCostPer1k: 0 }; // Ollama is free
      } else if (config?.modelProvider === 'litellm') {
        pricing = { inputCostPer1k: 0.001, outputCostPer1k: 0.002 }; // LiteLLM example defaults
      } else {
        pricing = { inputCostPer1k: 0.006, outputCostPer1k: 0.030 }; // Claude Sonnet 4 correct AWS pricing
      }
    }
    
    // Calculate cost (pricing is per 1K tokens)
    const inputCost = (inputTokens / 1000) * pricing.inputCostPer1k;
    const outputCost = (outputTokens / 1000) * pricing.outputCostPer1k;
    
    return inputCost + outputCost;
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
        <StatusIndicator 
          compact={true} 
          position="footer" 
          deploymentMode={config?.deploymentMode}
        />
      </Box>

      {/* Spacer */}
      <Box flexGrow={1} />

      {/* Right section - All metrics and info in one line */}
      <Box flexGrow={0} flexShrink={0}>
        {/* Token and cost metrics - always visible */}
        <Text color={theme.muted}>
          {operationMetrics ? (operationMetrics.tokens || 0).toLocaleString() : '0'} tokens
        </Text>
        <Text color={theme.muted}> • </Text>
        <Text color={theme.muted}>
          {operationMetrics ? formatCost(calculateCost()) : '$0.00'}
        </Text>
        
        {/* Duration when available */}
        {operationMetrics && operationMetrics.duration !== '0s' && (
          <>
            <Text color={theme.muted}> • </Text>
            <Text color={theme.muted}>{operationMetrics.duration}</Text>
          </>
        )}
        
        {/* Memory and evidence metrics when available */}
        {operationMetrics && (operationMetrics.memoryOps > 0 || operationMetrics.evidence > 0) && (
          <>
            <Text color={theme.muted}> • </Text>
            {operationMetrics.memoryOps > 0 && (
              <>
                <Text color={theme.muted}>{operationMetrics.memoryOps}</Text>
                <Text color={theme.muted}> mem</Text>
              </>
            )}
            {operationMetrics.memoryOps > 0 && operationMetrics.evidence > 0 && (
              <Text color={theme.muted}> • </Text>
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
        
        {/* Keyboard shortcuts */}
        <Text color={theme.muted}>[ESC] Kill Switch</Text>
        
        {/* Errors if any */}
        {errorCount > 0 && (
          <>
            <Text color={theme.muted}>  |  </Text>
            <Text color={theme.danger}>{errorCount} error{errorCount > 1 ? 's' : ''}</Text>
          </>
        )}
        
        <Text color={theme.muted}>  |  </Text>
        
        {/* Model provider connection status - use provider from config */}
        <Text color={connIcon.color}>{connIcon.icon}</Text>
        <Text color={theme.muted}> {connectionStatus === 'connected' ? modelProvider : connectionStatus}</Text>
        
        {/* Model ID - only show if provided */}
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