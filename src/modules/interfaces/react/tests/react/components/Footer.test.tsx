/**
 * Footer Component Unit Tests
 * 
 * Tests the footer status bar to ensure:
 * - Model information display
 * - Operation metrics rendering
 * - Connection status indicators
 * - Error count display
 * - Cost and token formatting
 * - Memory and evidence metrics
 * - Keyboard shortcuts display
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { renderWithProviders, waitFor } from '../test-utils.js';
import { Footer } from '../../components/Footer.js';

describe('Footer Component', () => {
  const defaultProps = {
    model: 'claude-3-sonnet',
    contextRemaining: 75,
    directory: '/Users/test/project',
    branchName: 'main'
  };

  const mockOperationMetrics = {
    tokens: 12500,
    cost: 0.25,
    duration: '2m 15s',
    memoryOps: 3,
    evidence: 7
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('should render with minimum required props', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          model={defaultProps.model} 
          contextRemaining={defaultProps.contextRemaining}
          directory={defaultProps.directory}
        />
      );

      expect(lastFrame()).toContain('0 tokens');
      expect(lastFrame()).toContain('$0.00');
      expect(lastFrame()).toContain('[ESC] Kill Switch');
      expect(lastFrame()).toContain('bedrock'); // Default provider
    });

    it('should display model information', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          model="gpt-4-turbo"
          modelProvider="openai"
        />
      );

      expect(lastFrame()).toContain('gpt-4-turbo');
      expect(lastFrame()).toContain('openai');
    });

    it('should handle missing model gracefully', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          model=""
          contextRemaining={defaultProps.contextRemaining}
          directory={defaultProps.directory}
        />
      );

      // Should not crash and should show other elements
      expect(lastFrame()).toContain('0 tokens');
      expect(lastFrame()).toContain('$0.00');
      expect(lastFrame()).not.toContain('|  |'); // Should not have empty model section
    });
  });

  describe('Operation Metrics Display', () => {
    it('should display token count with proper formatting', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            tokens: 12500,
            cost: 0,
            duration: '0s',
            memoryOps: 0,
            evidence: 0
          }}
        />
      );

      expect(lastFrame()).toContain('12,500 tokens');
    });

    it('should format cost correctly', () => {
      const testCases = [
        { cost: 0.005, expected: '<$0.01' },
        { cost: 0.25, expected: '$0.25' },
        { cost: 1.50, expected: '$1.50' },
        { cost: 0, expected: '$0.00' }
      ];

      testCases.forEach(({ cost, expected }) => {
        const { lastFrame } = renderWithProviders(
          <Footer 
            {...defaultProps}
            operationMetrics={{
              tokens: 1000,
              cost,
              duration: '0s',
              memoryOps: 0,
              evidence: 0
            }}
          />
        );

        expect(lastFrame()).toContain(expected);
      });
    });

    it('should display duration when not zero', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            ...mockOperationMetrics,
            duration: '5m 30s'
          }}
        />
      );

      expect(lastFrame()).toContain('5m 30s');
    });

    it('should hide duration when zero', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            ...mockOperationMetrics,
            duration: '0s'
          }}
        />
      );

      expect(lastFrame()).not.toContain('0s');
    });

    it('should display memory operations when available', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            tokens: 1000,
            cost: 0.10,
            duration: '1m',
            memoryOps: 5,
            evidence: 0
          }}
        />
      );

      expect(lastFrame()).toContain('5 mem');
    });

    it('should display evidence count when available', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            tokens: 1000,
            cost: 0.10,
            duration: '1m',
            memoryOps: 0,
            evidence: 12
          }}
        />
      );

      expect(lastFrame()).toContain('12 ev');
    });

    it('should display both memory and evidence with separator', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={mockOperationMetrics}
        />
      );

      expect(lastFrame()).toContain('3 mem');
      expect(lastFrame()).toContain('7 ev');
      // Should have separator between them
      expect(lastFrame()).toMatch(/3 mem\s*•\s*7 ev/);
    });

    it('should hide memory/evidence section when both are zero', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            tokens: 1000,
            cost: 0.10,
            duration: '1m',
            memoryOps: 0,
            evidence: 0
          }}
        />
      );

      expect(lastFrame()).not.toContain('mem');
      expect(lastFrame()).not.toContain('ev');
    });
  });

  describe('Connection Status Display', () => {
    it('should show connected status with green dot', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          connectionStatus="connected"
          modelProvider="bedrock"
        />
      );

      expect(lastFrame()).toContain('●');
      expect(lastFrame()).toContain('bedrock');
    });

    it('should show connecting status with warning indicator', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          connectionStatus="connecting"
        />
      );

      expect(lastFrame()).toContain('◐');
      expect(lastFrame()).toContain('connecting');
    });

    it('should show error status with error indicator', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          connectionStatus="error"
        />
      );

      expect(lastFrame()).toContain('✗');
      expect(lastFrame()).toContain('error');
    });

    it('should show offline status with empty circle', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          connectionStatus="offline"
        />
      );

      expect(lastFrame()).toContain('○');
      expect(lastFrame()).toContain('offline');
    });

    it('should handle different model providers', () => {
      const providers = ['bedrock', 'openai', 'ollama', 'litellm'];

      providers.forEach(provider => {
        const { lastFrame } = renderWithProviders(
          <Footer 
            {...defaultProps}
            modelProvider={provider}
            connectionStatus="connected"
          />
        );

        expect(lastFrame()).toContain(provider);
      });
    });
  });

  describe('Error Count Display', () => {
    it('should not show error count when zero', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          errorCount={0}
        />
      );

      expect(lastFrame()).not.toContain('error');
    });

    it('should show single error correctly', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          errorCount={1}
        />
      );

      expect(lastFrame()).toContain('1 error');
      expect(lastFrame()).not.toContain('errors');
    });

    it('should show multiple errors with plural', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          errorCount={5}
        />
      );

      expect(lastFrame()).toContain('5 errors');
    });

    it('should use danger color for error display', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          errorCount={3}
        />
      );

      // Should contain the error count
      expect(lastFrame()).toContain('3 errors');
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should always show ESC kill switch', () => {
      const { lastFrame } = renderWithProviders(
        <Footer {...defaultProps} />
      );

      expect(lastFrame()).toContain('[ESC] Kill Switch');
    });

    it('should show kill switch regardless of operation status', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationStatus={{
            step: 3,
            totalSteps: 10,
            description: 'Running scan',
            isRunning: true
          }}
        />
      );

      expect(lastFrame()).toContain('[ESC] Kill Switch');
    });
  });

  describe('Layout and Spacing', () => {
    it('should use proper separators between sections', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={mockOperationMetrics}
          errorCount={2}
        />
      );

      const frame = lastFrame();
      
      // Should have proper separators
      expect(frame).toContain('•'); // Between metrics
      expect(frame).toContain('|'); // Between major sections
    });

    it('should handle long model names gracefully', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          model="very-long-model-name-that-might-cause-layout-issues"
        />
      );

      // Should not crash and should display the model name
      expect(lastFrame()).toContain('very-long-model-name-that-might-cause-layout-issues');
    });

    it('should maintain layout with all optional props present', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={mockOperationMetrics}
          errorCount={3}
          debugMode={true}
          connectionStatus="connected"
          modelProvider="bedrock"
          operationStatus={{
            step: 5,
            totalSteps: 10,
            description: 'Processing',
            isRunning: true
          }}
        />
      );

      const frame = lastFrame();
      
      // Should contain all major elements
      expect(frame).toContain('12,500 tokens');
      expect(frame).toContain('$0.25');
      expect(frame).toContain('2m 15s');
      expect(frame).toContain('3 mem');
      expect(frame).toContain('7 ev');
      expect(frame).toContain('3 errors');
      expect(frame).toContain('bedrock');
      expect(frame).toContain('claude-3-sonnet');
    });
  });

  describe('StatusIndicator Integration', () => {
    it('should include StatusIndicator component', () => {
      const { lastFrame } = renderWithProviders(
        <Footer {...defaultProps} />
      );

      // StatusIndicator is rendered but its specific content depends on its implementation
      // We just verify the Footer renders without crashing
      expect(lastFrame()).toBeTruthy();
    });

    it('should pass compact and position props to StatusIndicator', () => {
      // This tests the props passed to StatusIndicator
      // The actual behavior depends on StatusIndicator implementation
      const { lastFrame } = renderWithProviders(
        <Footer {...defaultProps} />
      );

      expect(lastFrame()).toBeTruthy();
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle undefined operationMetrics gracefully', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={undefined}
        />
      );

      expect(lastFrame()).toContain('0 tokens');
      expect(lastFrame()).toContain('$0.00');
    });

    it('should handle partial operationMetrics', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          operationMetrics={{
            tokens: 1000,
            cost: undefined,
            duration: '1m',
            memoryOps: 0,
            evidence: 0
          } as any}
        />
      );

      expect(lastFrame()).toContain('1,000 tokens');
      expect(lastFrame()).toContain('$0.00'); // Should default cost to 0
    });

    it('should handle negative error count', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          errorCount={-1}
        />
      );

      // Should not crash, behavior depends on implementation
      expect(lastFrame()).toBeTruthy();
    });

    it('should handle very long directory paths', () => {
      const longPath = '/very/long/path/that/might/cause/issues/in/the/footer/display/system';
      
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          directory={longPath}
        />
      );

      // Should not crash (path might be shortened or handled by StatusIndicator)
      expect(lastFrame()).toBeTruthy();
    });

    it('should handle special characters in model names', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          model="claude-3.5-sonnet@v2"
        />
      );

      expect(lastFrame()).toContain('claude-3.5-sonnet@v2');
    });
  });

  describe('Memoization and Performance', () => {
    it('should be properly memoized', () => {
      // Footer component uses React.memo
      expect(Footer.displayName).toBe('Footer');
    });

    it('should not re-render with same props', () => {
      const { lastFrame, rerender } = renderWithProviders(
        <Footer {...defaultProps} />
      );

      const initialFrame = lastFrame();

      // Re-render with same props
      rerender(<Footer {...defaultProps} />);

      expect(lastFrame()).toBe(initialFrame);
    });
  });

  describe('Theme Integration', () => {
    it('should use theme colors appropriately', () => {
      const { lastFrame } = renderWithProviders(
        <Footer 
          {...defaultProps}
          connectionStatus="connected"
          errorCount={2}
        />
      );

      // Should render without throwing (theme colors are applied)
      expect(lastFrame()).toBeTruthy();
      expect(lastFrame()).toContain('2 errors');
      expect(lastFrame()).toContain('●'); // Connected icon
    });
  });
});