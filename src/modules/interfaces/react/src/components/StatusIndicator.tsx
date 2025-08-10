/**
 * Container Status Indicator
 * Shows real-time health status of Docker containers
 * Professional monitoring display inspired by enterprise dashboards
 */

import React, { useEffect, useState } from 'react';
import { Box, Text } from 'ink';
import { HealthMonitor, HealthStatus } from '../services/HealthMonitor.js';
import { ContainerManager } from '../services/ContainerManager.js';
import { themeManager } from '../themes/theme-manager.js';

interface StatusIndicatorProps {
  compact?: boolean;
  position?: 'header' | 'footer';
  deploymentMode?: string; // Optional override for deployment mode display
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ 
  compact = false,
  position = 'header',
  deploymentMode: overrideMode
}) => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [deploymentMode, setDeploymentMode] = useState<string>('cli');
  const theme = themeManager.getCurrentTheme();

  useEffect(() => {
    const monitor = HealthMonitor.getInstance();
    const containerManager = ContainerManager.getInstance();
    
    // Use slower polling to prevent memory issues - 5 seconds is sufficient for status monitoring
    monitor.startMonitoring(5000); // Check every 5 seconds for better performance
    
    // Subscribe to updates
    const unsubscribe = monitor.subscribe((status) => {
      setHealthStatus(status);
    });

    // Update deployment mode - use override if provided, otherwise auto-detect
    const updateDeploymentMode = async () => {
      if (overrideMode) {
        // Use provided deployment mode
        setDeploymentMode(overrideMode);
        return;
      }
      
      try {
        // Auto-detect from container manager
        const currentMode = await containerManager.getCurrentMode();
        const modeDisplayName = currentMode === 'local-cli' ? 'cli' : 
                               currentMode === 'single-container' ? 'agent' : 
                               'enterprise';
        setDeploymentMode(modeDisplayName);
      } catch (error) {
        console.error('Failed to get deployment mode:', error);
        setDeploymentMode('cli'); // Safe fallback
      }
    };

    // Set initial deployment mode
    updateDeploymentMode();

    // Reduce polling frequency to prevent memory leaks - 10 seconds is sufficient for mode detection
    const deploymentModeInterval = overrideMode ? null : setInterval(updateDeploymentMode, 10000);

    // Initial check
    monitor.checkHealth();

    return () => {
      unsubscribe();
      if (deploymentModeInterval) {
        clearInterval(deploymentModeInterval);
      }
      // Stop monitoring when component unmounts to prevent memory leaks
      monitor.stopMonitoring();
    };
  }, [overrideMode]); // Add overrideMode dependency to re-run when it changes

  if (!healthStatus) {
    return null;
  }

  // Get status color
  const getStatusColor = () => {
    switch (healthStatus.overall) {
      case 'healthy':
        return theme.success;
      case 'degraded':
        return theme.warning;
      case 'unhealthy':
        return theme.danger;
      default:
        return theme.muted;
    }
  };

  // Get status symbol
  const getStatusSymbol = () => {
    switch (healthStatus.overall) {
      case 'healthy':
        return '●';
      case 'degraded':
        return '◐';
      case 'unhealthy':
        return '○';
      default:
        return '○';
    }
  };

  // Count running services
  const runningCount = healthStatus.services.filter(s => s.status === 'running').length;
  const totalCount = healthStatus.services.length;

  if (compact) {
    // Compact view for header/footer
    return (
      <Box>
        <Text color={theme.muted}>{deploymentMode}</Text>
        <Text color={theme.muted}> </Text>
        {deploymentMode === 'cli' ? (
          <Text color={theme.success}>● Python</Text>
        ) : deploymentMode === 'agent' ? (
          // Single container mode - show Docker status
          <Text color={getStatusColor()}>
            {getStatusSymbol()} Docker
          </Text>
        ) : deploymentMode === 'enterprise' ? (
          // Full stack mode - show container count
          <Text color={getStatusColor()}>
            {getStatusSymbol()} {runningCount}/{totalCount}
          </Text>
        ) : (
          // Fallback - show appropriate status
          <Text color={theme.muted}>● Ready</Text>
        )}
        {!healthStatus.dockerRunning && deploymentMode !== 'cli' && (
          <Text color={theme.danger}> Docker Off</Text>
        )}
      </Box>
    );
  }

  // Detailed view
  return (
    <Box flexDirection="column" borderStyle="single" borderColor={theme.muted} padding={1}>
      <Box marginBottom={1}>
        <Text bold color={theme.primary}>Container Status</Text>
        <Text color={theme.muted}> - </Text>
        <Text color={getStatusColor()}>{healthStatus.overall.toUpperCase()}</Text>
      </Box>
      
      {!healthStatus.dockerRunning && (
        <Box marginBottom={1}>
          <Text color={theme.danger}>⚠ Docker is not running</Text>
        </Box>
      )}
      
      <Box flexDirection="column">
        {healthStatus.services.map((service) => {
          const isRunning = service.status === 'running';
          const statusColor = isRunning ? theme.success : theme.danger;
          const statusSymbol = isRunning ? '✓' : '✗';
          
          return (
            <Box key={service.name} marginY={0.25}>
              <Text color={statusColor}>{statusSymbol} </Text>
              <Text color={isRunning ? theme.foreground : theme.muted}>
                {service.displayName}
              </Text>
              {service.uptime && (
                <Text color={theme.muted}> ({service.uptime})</Text>
              )}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};