/**
 * Container Status Indicator
 * Shows real-time health status of Docker containers
 * Professional monitoring display inspired by enterprise dashboards
 */

import React, { useEffect, useState } from 'react';
import { Box, Text } from 'ink';
import { HealthMonitor, HealthStatus } from '../services/HealthMonitor.js';
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
  const theme = themeManager.getCurrentTheme();

  useEffect(() => {
    const monitor = HealthMonitor.getInstance();
    
    // Start monitoring
    monitor.startMonitoring(5000); // Check every 5 seconds
    
    // Subscribe to updates
    const unsubscribe = monitor.subscribe((status) => {
      setHealthStatus(status);
    });

    // Initial check
    monitor.checkHealth();

    return () => {
      unsubscribe();
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
        <Text color={theme.muted}>sandbox</Text>
        <Text color={theme.muted}> </Text>
        <Text color={getStatusColor()}>
          {getStatusSymbol()} {runningCount}/{totalCount}
        </Text>
        {!healthStatus.dockerRunning && (
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