/**
 * StatusIndicator Component Unit Tests
 * 
 * Tests the container status monitoring component to ensure:
 * - Health status monitoring and display
 * - Compact vs detailed view modes
 * - Docker status indication
 * - Service status rendering
 * - Deployment mode detection
 * - Real-time status updates
 * - Error handling and edge cases
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { renderWithProviders, waitFor } from '../test-utils.js';
import { StatusIndicator } from '../../components/StatusIndicator.js';

// Mock the HealthMonitor and ContainerManager services
const mockHealthMonitorInstance = {
  startMonitoring: jest.fn(),
  stopMonitoring: jest.fn(),
  subscribe: jest.fn(),
  checkHealth: jest.fn()
};

const mockContainerManagerInstance = {
  getCurrentMode: jest.fn().mockResolvedValue('local-cli' as any)
};

const mockHealthMonitor = {
  getInstance: jest.fn().mockReturnValue(mockHealthMonitorInstance)
};

const mockContainerManager = {
  getInstance: jest.fn().mockReturnValue(mockContainerManagerInstance)
};

// Mock the services
jest.mock('../../services/HealthMonitor.js', () => ({
  HealthMonitor: mockHealthMonitor
}));

jest.mock('../../services/ContainerManager.js', () => ({
  ContainerManager: mockContainerManager
}));

describe('StatusIndicator Component', () => {
  let mockSubscribe: jest.MockedFunction<any>;
  let mockUnsubscribe: jest.MockedFunction<any>;
  let statusCallback: Function;

  const mockHealthyStatus = {
    overall: 'healthy' as const,
    dockerRunning: true,
    services: [
      { name: 'langfuse', displayName: 'Langfuse', status: 'running', uptime: '2h 30m' },
      { name: 'postgres', displayName: 'PostgreSQL', status: 'running', uptime: '2h 31m' },
      { name: 'redis', displayName: 'Redis', status: 'running', uptime: '2h 29m' }
    ]
  };

  const mockDegradedStatus = {
    overall: 'degraded' as const,
    dockerRunning: true,
    services: [
      { name: 'langfuse', displayName: 'Langfuse', status: 'running', uptime: '1h 15m' },
      { name: 'postgres', displayName: 'PostgreSQL', status: 'exited', uptime: null },
      { name: 'redis', displayName: 'Redis', status: 'running', uptime: '1h 16m' }
    ]
  };

  const mockUnhealthyStatus = {
    overall: 'unhealthy' as const,
    dockerRunning: false,
    services: []
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    mockUnsubscribe = jest.fn();
    mockSubscribe = jest.fn().mockImplementation((callback: any) => {
      statusCallback = callback;
      return mockUnsubscribe;
    });

    mockHealthMonitorInstance.subscribe = mockSubscribe;
    mockContainerManagerInstance.getCurrentMode = jest.fn().mockResolvedValue('local-cli' as any);

    // Clear all timers
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Initial Rendering', () => {
    it('should render nothing when no health status available', () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator />
      );

      // Should render empty/null since no health status is set initially
      expect(lastFrame()).toBe('');
    });

    it('should start health monitoring on mount', () => {
      renderWithProviders(<StatusIndicator />);

      expect(mockHealthMonitor.getInstance).toHaveBeenCalled();
      expect(mockSubscribe).toHaveBeenCalled();
    });

    it('should check initial health on mount', () => {
      const mockInstance = {
        startMonitoring: jest.fn(),
        stopMonitoring: jest.fn(),
        subscribe: mockSubscribe,
        checkHealth: jest.fn()
      };
      
      mockHealthMonitor.getInstance.mockReturnValue(mockInstance);

      renderWithProviders(<StatusIndicator />);

      expect(mockInstance.checkHealth).toHaveBeenCalled();
    });
  });

  describe('Compact Mode Display', () => {
    it('should display CLI mode status in compact view', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('local-cli' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      // Trigger status update
      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('cli');
      expect(lastFrame()).toContain('● Python');
    });

    it('should display agent mode with service count in compact view', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('single-container' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('agent');
      expect(lastFrame()).toContain('● 3/3'); // All 3 services running
    });

    it('should display enterprise mode correctly in compact view', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('enterprise' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('enterprise');
      expect(lastFrame()).toContain('● 3/3');
    });

    it('should show degraded status in compact view', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockDegradedStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('◐ 2/3'); // 2 of 3 services running
    });

    it('should show Docker off warning in compact view', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockUnhealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('Docker Off');
    });
  });

  describe('Detailed Mode Display', () => {
    it('should display detailed status with service list', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      const frame = lastFrame();
      expect(frame).toContain('Container Status');
      expect(frame).toContain('HEALTHY');
      expect(frame).toContain('Langfuse');
      expect(frame).toContain('PostgreSQL');
      expect(frame).toContain('Redis');
      expect(frame).toContain('2h 30m'); // Uptime
    });

    it('should show individual service status indicators', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(mockDegradedStatus);
      }

      await waitFor(50);

      const frame = lastFrame();
      expect(frame).toContain('✓'); // Running services
      expect(frame).toContain('✗'); // Failed services
      expect(frame).toContain('DEGRADED');
    });

    it('should display Docker warning in detailed view', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(mockUnhealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('⚠ Docker is not running');
    });

    it('should show service uptime when available', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      const frame = lastFrame();
      expect(frame).toContain('(2h 30m)');
      expect(frame).toContain('(2h 31m)');
      expect(frame).toContain('(2h 29m)');
    });

    it('should handle services without uptime', async () => {
      const statusWithoutUptime = {
        overall: 'healthy' as const,
        dockerRunning: true,
        services: [
          { name: 'test', displayName: 'Test Service', status: 'running', uptime: null }
        ]
      };

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(statusWithoutUptime);
      }

      await waitFor(50);

      const frame = lastFrame();
      expect(frame).toContain('Test Service');
      expect(frame).not.toContain('('); // No uptime parentheses
    });
  });

  describe('Status Colors and Symbols', () => {
    it('should use correct colors for healthy status', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('●'); // Healthy symbol
    });

    it('should use correct colors for degraded status', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockDegradedStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('◐'); // Degraded symbol
    });

    it('should use correct colors for unhealthy status', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockUnhealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('○'); // Unhealthy symbol
    });
  });

  describe('Deployment Mode Detection', () => {
    it('should detect CLI mode correctly', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('local-cli' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('cli');
    });

    it('should detect single-container mode correctly', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('single-container' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('agent');
    });

    it('should handle unknown deployment modes', async () => {
      mockContainerManagerInstance.getCurrentMode.mockResolvedValue('unknown-mode' as any);

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('enterprise'); // Default fallback
    });
  });

  describe('Error Handling', () => {
    it('should handle deployment mode detection errors', async () => {
      mockContainerManagerInstance.getCurrentMode.mockRejectedValue(new Error('Connection failed') as any);

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      renderWithProviders(<StatusIndicator />);

      await waitFor(100);

      expect(consoleSpy).toHaveBeenCalledWith('Failed to get deployment mode:', expect.any(Error));
      
      consoleSpy.mockRestore();
    });

    it('should handle missing service data gracefully', async () => {
      const incompleteStatus = {
        overall: 'healthy' as const,
        dockerRunning: true,
        services: [
          { name: 'incomplete', displayName: 'Incomplete Service' } as any // Missing required fields
        ]
      };

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(incompleteStatus);
      }

      await waitFor(50);

      // Should not crash
      expect(lastFrame()).toBeTruthy();
    });

    it('should handle null health status gracefully', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator />
      );

      if (statusCallback) {
        statusCallback(null);
      }

      await waitFor(50);

      expect(lastFrame()).toBe(''); // Should render nothing
    });
  });

  describe('Component Lifecycle', () => {
    it('should cleanup subscriptions on unmount', () => {
      const { unmount } = renderWithProviders(<StatusIndicator />);

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });

    it('should stop monitoring on unmount', () => {
      const { unmount } = renderWithProviders(<StatusIndicator />);

      unmount();

      expect(mockHealthMonitorInstance.stopMonitoring).toHaveBeenCalled();
    });

    it('should clear deployment mode interval on unmount', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      const { unmount } = renderWithProviders(<StatusIndicator />);

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();

      clearIntervalSpy.mockRestore();
    });
  });

  describe('Real-time Updates', () => {
    it('should update display when status changes', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      // Initial healthy status
      if (statusCallback) {
        statusCallback(mockHealthyStatus);
      }

      await waitFor(50);
      expect(lastFrame()).toContain('● 3/3');

      // Change to degraded status
      if (statusCallback) {
        statusCallback(mockDegradedStatus);
      }

      await waitFor(50);
      expect(lastFrame()).toContain('◐ 2/3');
    });

    it('should handle rapid status updates', async () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      // Rapid status changes
      if (statusCallback) {
        statusCallback(mockHealthyStatus);
        statusCallback(mockDegradedStatus);
        statusCallback(mockUnhealthyStatus);
        statusCallback(mockHealthyStatus);
      }

      await waitFor(100);

      // Should show the final status
      expect(lastFrame()).toContain('● 3/3');
    });
  });

  describe('Position Props', () => {
    it('should accept header position prop', () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator position="header" />
      );

      // Should not crash with position prop
      expect(lastFrame()).toBe(''); // No status yet
    });

    it('should accept footer position prop', () => {
      const { lastFrame } = renderWithProviders(
        <StatusIndicator position="footer" />
      );

      expect(lastFrame()).toBe(''); // No status yet
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty services array', async () => {
      const emptyServicesStatus = {
        overall: 'healthy' as const,
        dockerRunning: true,
        services: []
      };

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={true} />
      );

      if (statusCallback) {
        statusCallback(emptyServicesStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('0/0'); // Zero services
    });

    it('should handle very long service names', async () => {
      const longNameStatus = {
        overall: 'healthy' as const,
        dockerRunning: true,
        services: [
          { 
            name: 'very-long-service-name-that-might-cause-layout-issues', 
            displayName: 'Very Long Service Name That Might Cause Layout Issues',
            status: 'running',
            uptime: '1h'
          }
        ]
      };

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(longNameStatus);
      }

      await waitFor(50);

      expect(lastFrame()).toContain('Very Long Service Name');
    });

    it('should handle unknown service status', async () => {
      const unknownStatusService = {
        overall: 'degraded' as const,
        dockerRunning: true,
        services: [
          { 
            name: 'unknown', 
            displayName: 'Unknown Service',
            status: 'unknown' as any,
            uptime: null
          }
        ]
      };

      const { lastFrame } = renderWithProviders(
        <StatusIndicator compact={false} />
      );

      if (statusCallback) {
        statusCallback(unknownStatusService);
      }

      await waitFor(50);

      // Should not crash with unknown status
      expect(lastFrame()).toBeTruthy();
      expect(lastFrame()).toContain('Unknown Service');
    });
  });
});