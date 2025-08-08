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
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ 
  compact = false,
  position = 'header' 
}) => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [deploymentMode, setDeploymentMode] = useState<string>('cli');
  const theme = themeManager.getCurrentTheme();

  useEffect(() => {
    const monitor = HealthMonitor.getInstance();
    const containerManager = ContainerManager.getInstance();
    
    // Start monitoring more frequently during setup changes
    monitor.startMonitoring(1000); // Check every 1 second for responsive updates
    
    // Subscribe to updates
    const unsubscribe = monitor.subscribe((status) => {
      setHealthStatus(status);
    });

    // Update deployment mode and handle changes
    const updateDeploymentMode = async () => {
      try {
        const currentMode = await containerManager.getCurrentMode();
        const modeDisplayName = currentMode === 'local-cli' ? 'cli' : 
                               currentMode === 'single-container' ? 'agent' : 
                               'enterprise';
        setDeploymentMode(modeDisplayName);
      } catch (error) {
        console.error('Failed to get deployment mode:', error);
      }
    };

    // Set initial deployment mode
    updateDeploymentMode();

    // Poll for deployment mode changes more frequently during setup transitions
    const deploymentModeInterval = setInterval(updateDeploymentMode, 500);

    // Initial check
    monitor.checkHealth();

    return () => {
      unsubscribe();
      clearInterval(deploymentModeInterval);
      // Stop monitoring when component unmounts to prevent memory leaks
      monitor.stopMonitoring();
    };
  }, []);

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
        ) : deploymentMode === 'agent' && totalCount === 0 ? (
          // Single container mode - show Docker status
          <Text color={getStatusColor()}>
            {getStatusSymbol()} Docker
          </Text>
        ) : (
          <Text color={getStatusColor()}>
            {getStatusSymbol()} {runningCount}/{totalCount}
          </Text>
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