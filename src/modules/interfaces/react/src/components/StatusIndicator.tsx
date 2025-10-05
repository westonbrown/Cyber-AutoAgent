/**
 * Container Status Indicator
 * Shows real-time health status of Docker containers
 * Professional monitoring display inspired by enterprise dashboards
 */

import React, { useEffect, useRef, useState } from 'react';
import { Box, Text } from 'ink';
import { HealthMonitor, HealthStatus } from '../services/HealthMonitor.js';
import { ContainerManager } from '../services/ContainerManager.js';
import { themeManager } from '../themes/theme-manager.js';

interface StatusIndicatorProps {
  compact?: boolean;
  position?: 'header' | 'footer';
  deploymentMode?: string; // Optional override for deployment mode display
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = React.memo(({ 
  compact = false,
  position = 'header',
  deploymentMode: overrideMode
}) => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [deploymentMode, setDeploymentMode] = useState<string>('cli');
  const [lastCheckAt, setLastCheckAt] = useState<number | null>(null);
  const theme = themeManager.getCurrentTheme();
  const lastStatusRef = useRef<HealthStatus | null>(null);
  const lastEmitRef = useRef<number>(0);
  const MIN_EMIT_INTERVAL_MS = 15000; // 15s

  useEffect(() => {
    const monitor = HealthMonitor.getInstance();
    const containerManager = ContainerManager.getInstance();

    // Health monitoring disabled: checkHealth() creates memory leaks during long idle periods
    // Status updates will rely on manual checks via /health command instead
    // monitor.startMonitoring(10000);
    
    // Subscribe to updates
    const unsubscribe = monitor.subscribe((status) => {
      // Deduplicate updates to avoid unnecessary re-renders
      const prev = lastStatusRef.current;
      const now = Date.now();
      const canEmitByTime = now - lastEmitRef.current >= MIN_EMIT_INTERVAL_MS;

      const shallowEqual = (a?: HealthStatus | null, b?: HealthStatus | null): boolean => {
        if (!a || !b) return false;
        if (a.overall !== b.overall) return false;
        if (a.dockerRunning !== b.dockerRunning) return false;
        if (a.services.length !== b.services.length) return false;
        for (let i = 0; i < a.services.length; i++) {
          const sa = a.services[i];
          const sb = b.services[i];
          if (sa.name !== sb.name || sa.status !== sb.status || sa.health !== sb.health) {
            return false;
          }
        }
        return true;
      };

      const changed = !shallowEqual(prev, status);
      if (changed || canEmitByTime) {
        lastStatusRef.current = status;
        lastEmitRef.current = now;
        setHealthStatus(status);
        setLastCheckAt(now);
      }
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
                               'full-stack';
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
        ) : deploymentMode === 'full-stack' ? (
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
        {lastCheckAt && (
          <>
            <Text color={theme.muted}> · </Text>
            <Text color={theme.muted}>Last check {Math.max(0, Math.floor((Date.now() - lastCheckAt)/1000))}s ago</Text>
          </>
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
        {lastCheckAt && (
          <>
            <Text color={theme.muted}> · </Text>
            <Text color={theme.muted}>Last check {Math.max(0, Math.floor((Date.now() - lastCheckAt)/1000))}s ago</Text>
          </>
        )}
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
});

StatusIndicator.displayName = 'StatusIndicator';