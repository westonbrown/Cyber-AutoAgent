/**
 * Icon Components for Cyber-AutoAgent
 * 
 * Provides consistent, accessible status indicators and icons
 * for terminal UI display.
 */

import React from 'react';
import { Text } from 'ink';
import Spinner from 'ink-spinner';
import { themeManager } from '../themes/theme-manager.js';

/**
 * Status icons for different states
 */
export const StatusIcons = {
  // Success states
  Success: () => <Text color="green">✓</Text>,
  Complete: () => <Text color="green">✔</Text>,
  
  // Error states
  Error: () => <Text color="red">✗</Text>,
  Failed: () => <Text color="red" bold>✖</Text>,
  
  // Warning states
  Warning: () => <Text color="yellow">⚠</Text>,
  Caution: () => <Text color="yellow">!</Text>,
  
  // Progress states
  Pending: () => <Text color="cyan">○</Text>,
  Running: () => <Text color="cyan">●</Text>,
  Loading: () => <Spinner type="dots" />,
  
  // Information states
  Info: () => <Text color="blue">ℹ</Text>,
  Question: () => <Text color="yellow">?</Text>,
  
  // Action states
  Canceled: () => <Text color="yellow" bold>-</Text>,
  Skipped: () => <Text color="gray">⊘</Text>,
  Paused: () => <Text color="yellow">⏸</Text>,
  
  // Navigation
  Arrow: () => <Text color="cyan">→</Text>,
  Chevron: () => <Text color="gray">›</Text>,
  
  // Security specific
  Secure: () => <Text color="green">🔒</Text>,
  Insecure: () => <Text color="red">🔓</Text>,
  Shield: () => <Text color="green">🛡</Text>,
  Alert: () => <Text color="red">🚨</Text>,
};

/**
 * Tool execution status indicator
 */
interface ToolStatusIndicatorProps {
  status: 'pending' | 'executing' | 'success' | 'error' | 'canceled' | 'confirming';
  compact?: boolean;
}

export const ToolStatusIndicator: React.FC<ToolStatusIndicatorProps> = ({ status, compact = false }) => {
  const theme = themeManager.getCurrentTheme();
  
  const indicators = {
    pending: compact ? '○' : '○ Pending',
    executing: compact ? <Spinner type="dots" /> : <><Spinner type="dots" /> Executing</>,
    success: compact ? '✓' : '✓ Success',
    error: compact ? '✗' : '✗ Error',
    canceled: compact ? '-' : '- Canceled',
    confirming: compact ? '?' : '? Confirming',
  };
  
  const colors = {
    pending: theme.info,
    executing: theme.primary,
    success: theme.success,
    error: theme.danger,
    canceled: theme.warning,
    confirming: theme.warning,
  };
  
  return (
    <Text color={colors[status]}>
      {indicators[status]}
    </Text>
  );
};

/**
 * Progress indicator with percentage
 */
interface ProgressIndicatorProps {
  current: number;
  total: number;
  width?: number;
  showPercentage?: boolean;
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({ 
  current, 
  total, 
  width = 20,
  showPercentage = true 
}) => {
  const theme = themeManager.getCurrentTheme();
  const percentage = Math.round((current / total) * 100);
  const filled = Math.round((current / total) * width);
  const empty = width - filled;
  
  return (
    <Text>
      <Text color={theme.muted}>[</Text>
      <Text color={theme.primary}>{'█'.repeat(filled)}</Text>
      <Text color={theme.muted}>{'░'.repeat(empty)}</Text>
      <Text color={theme.muted}>]</Text>
      {showPercentage && <Text color={theme.foreground}> {percentage}%</Text>}
    </Text>
  );
};

/**
 * Connection status indicator
 */
interface ConnectionStatusProps {
  status: 'connected' | 'connecting' | 'disconnected' | 'error';
  showLabel?: boolean;
}

export const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ status, showLabel = true }) => {
  const theme = themeManager.getCurrentTheme();
  
  const indicators = {
    connected: { icon: '●', color: theme.success, label: 'Connected' },
    connecting: { icon: <Spinner type="dots" />, color: theme.warning, label: 'Connecting' },
    disconnected: { icon: '○', color: theme.muted, label: 'Disconnected' },
    error: { icon: '✗', color: theme.danger, label: 'Error' }
  };
  
  const { icon, color, label } = indicators[status];
  
  return (
    <Text color={color}>
      {icon}
      {showLabel && ` ${label}`}
    </Text>
  );
};

/**
 * Bullet point for lists
 */
export const Bullet: React.FC<{ level?: number }> = ({ level = 0 }) => {
  const theme = themeManager.getCurrentTheme();
  const bullets = ['•', '◦', '▪', '▫'];
  const bullet = bullets[level % bullets.length];
  
  return <Text color={theme.muted}>{bullet} </Text>;
};

/**
 * Divider line
 */
export const Divider: React.FC<{ width?: number; char?: string }> = ({ width = 50, char = '─' }) => {
  const theme = themeManager.getCurrentTheme();
  return <Text color={theme.muted}>{char.repeat(width)}</Text>;
};

/**
 * Log level indicators
 */
export const LogLevelIcon: React.FC<{ level: 'info' | 'success' | 'warning' | 'error' | 'debug' }> = ({ level }) => {
  const theme = themeManager.getCurrentTheme();
  
  const icons = {
    info: { icon: 'ℹ', color: theme.info },
    success: { icon: '✓', color: theme.success },
    warning: { icon: '⚠', color: theme.warning },
    error: { icon: '✗', color: theme.danger },
    debug: { icon: '⟡', color: theme.muted }
  };
  
  const { icon, color } = icons[level];
  return <Text color={color}>{icon} </Text>;
};

/**
 * Security assessment status icons
 */
export const SecurityIcon: React.FC<{ type: 'scanning' | 'vulnerable' | 'secure' | 'unknown' }> = ({ type }) => {
  const theme = themeManager.getCurrentTheme();
  
  const icons = {
    scanning: { icon: <Spinner type="dots" />, color: theme.primary },
    vulnerable: { icon: '⚠', color: theme.danger },
    secure: { icon: '✓', color: theme.success },
    unknown: { icon: '?', color: theme.muted }
  };
  
  const { icon, color } = icons[type];
  return <Text color={color}>{icon}</Text>;
};

/**
 * Operation step indicator
 */
export const StepIndicator: React.FC<{ 
  current: number; 
  total: number; 
  status?: 'active' | 'completed' | 'pending' 
}> = ({ current, total, status = 'active' }) => {
  const theme = themeManager.getCurrentTheme();
  
  const statusColors = {
    active: theme.primary,
    completed: theme.success,
    pending: theme.muted
  };
  
  return (
    <Text color={statusColors[status]}>
      Step {current}/{total}
    </Text>
  );
};