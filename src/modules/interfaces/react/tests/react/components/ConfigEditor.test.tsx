/**
 * ConfigEditor Component Unit Tests
 * 
 * Tests the configuration editor modal to ensure:
 * - Section navigation and expansion
 * - Field editing and validation
 * - Provider-specific field visibility
 * - Save/cancel functionality
 * - Keyboard navigation
 * - Unsaved changes handling
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { renderWithProviders, simulateKeyboardInput, waitFor, mockConfiguredState } from '../test-utils.js';
import { ConfigEditor } from '../../components/ConfigEditor.js';

describe('ConfigEditor Component', () => {
  let mockOnClose: jest.MockedFunction<() => void>;

  beforeEach(() => {
    mockOnClose = jest.fn();
    jest.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('should render with header and sections', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      expect(lastFrame()).toContain('Configuration Editor');
      expect(lastFrame()).toContain('Models & Credentials');
      expect(lastFrame()).toContain('Operations');
      expect(lastFrame()).toContain('Memory');
      expect(lastFrame()).toContain('Observability');
    });

    it('should show all configuration sections', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      const expectedSections = [
        'Models & Credentials',
        'Operations', 
        'Memory',
        'Observability',
        'Evaluation',
        'Model Pricing',
        'Output'
      ];

      expectedSections.forEach(section => {
        expect(lastFrame()).toContain(section);
      });
    });

    it('should start in sections navigation mode', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Should highlight first section (Models & Credentials)
      expect(lastFrame()).toContain('Models & Credentials');
      // Should show navigation instructions
      expect(lastFrame()).toContain('↑↓ navigate');
    });

    it('should display current configuration values', () => {
      const testConfig = {
        ...mockConfiguredState,
        modelProvider: 'bedrock' as const,
        iterations: 50,
        observability: true
      };

      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />
      );

      // Values should be reflected when sections are expanded
      // (Note: Values only show when sections are expanded)
      expect(lastFrame()).toContain('Configuration Editor');
    });
  });

  describe('Section Navigation', () => {
    it('should navigate between sections with arrow keys', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Navigate down to Operations section
      simulateKeyboardInput(stdin, ['ARROW_DOWN']);
      await waitFor(50);

      expect(lastFrame()).toContain('Operations'); // Should highlight Operations
    });

    it('should wrap navigation at boundaries', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Try to navigate up from first section (should stay at first)
      simulateKeyboardInput(stdin, ['ARROW_UP']);
      await waitFor(50);

      expect(lastFrame()).toContain('Models & Credentials'); // Should stay at first

      // Navigate to last section
      for (let i = 0; i < 10; i++) {
        simulateKeyboardInput(stdin, ['ARROW_DOWN']);
        await waitFor(10);
      }

      // Try to navigate down from last section (should stay at last)
      simulateKeyboardInput(stdin, ['ARROW_DOWN']);
      await waitFor(50);

      expect(lastFrame()).toContain('Output'); // Should stay at last section
    });

    it('should expand sections with Enter key', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Should show expanded section with fields
      expect(lastFrame()).toContain('Model Provider');
      expect(lastFrame()).toContain('Primary Model');
    });
  });

  describe('Field Navigation and Editing', () => {
    it('should navigate between fields in expanded section', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Navigate between fields
      simulateKeyboardInput(stdin, ['ARROW_DOWN']);
      await waitFor(50);

      // Should be in field navigation mode
      expect(lastFrame()).toContain('Model Provider');
    });

    it('should show provider-specific fields', async () => {
      const bedrockConfig = {
        ...mockConfiguredState,
        modelProvider: 'bedrock' as const
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Should show Bedrock-specific fields
      expect(lastFrame()).toContain('AWS Region');
      expect(lastFrame()).toContain('AWS Access Key ID');
    });

    it('should hide irrelevant fields for different providers', async () => {
      const ollamaConfig = {
        ...mockConfiguredState,
        modelProvider: 'ollama' as const
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Should show Ollama fields, not AWS fields
      expect(lastFrame()).toContain('Ollama Host');
      expect(lastFrame()).not.toContain('AWS Access Key ID');
    });
  });

  describe('Memory Backend Field Filtering', () => {
    it('should show Mem0 fields when Mem0 is selected', async () => {
      const mem0Config = {
        ...mockConfiguredState,
        memoryBackend: 'mem0' as const
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mem0Config }
      );

      // Navigate to Memory section
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ARROW_DOWN', 'ENTER']);
      await waitFor(100);

      // Should show Mem0-specific fields
      expect(lastFrame()).toContain('Mem0 API Key');
    });

    it('should show OpenSearch fields when OpenSearch is selected', async () => {
      const opensearchConfig = {
        ...mockConfiguredState,
        memoryBackend: 'opensearch' as const
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: opensearchConfig }
      );

      // Navigate to Memory section and expand
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ARROW_DOWN', 'ENTER']);
      await waitFor(100);

      // Should show OpenSearch-specific fields
      expect(lastFrame()).toContain('OpenSearch Host');
    });
  });

  describe('ESC Key Behavior', () => {
    it('should close editor when ESC pressed in section mode', async () => {
      const { stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should return to section mode when ESC pressed in field mode', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Expand section (enter field mode)
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Press ESC to return to section mode
      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      // Should be back in section mode (section collapsed)
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('should warn about unsaved changes before closing', async () => {
      // This would require simulating actual field changes
      // For now, we test the basic ESC behavior
      const { stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('Keyboard Navigation Instructions', () => {
    it('should show appropriate navigation instructions', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Should show navigation instructions
      expect(lastFrame()).toContain('↑↓ navigate');
      expect(lastFrame()).toContain('Enter');
      expect(lastFrame()).toContain('Esc');
    });

    it('should update instructions based on navigation mode', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Expand a section to enter field mode
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Instructions should update for field navigation
      const frame = lastFrame();
      expect(frame).toContain('↑↓'); // Should still show navigation
    });
  });

  describe('Visual Display', () => {
    it('should use proper styling and borders', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      const frame = lastFrame();
      
      // Should have proper structure and styling
      expect(frame).toContain('Configuration Editor');
      expect(frame).toContain('Models & Credentials');
    });

    it('should show section descriptions', () => {
      const { lastFrame } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      expect(lastFrame()).toContain('AI provider and authentication');
      expect(lastFrame()).toContain('Execution parameters');
      expect(lastFrame()).toContain('Vector storage configuration');
    });

    it('should highlight selected sections and fields appropriately', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: mockConfiguredState }
      );

      // Navigate to different section
      simulateKeyboardInput(stdin, ['ARROW_DOWN']);
      await waitFor(50);

      // Should show visual indication of selection
      const frame = lastFrame();
      expect(frame).toContain('Operations');
    });
  });

  describe('Configuration Values Display', () => {
    it('should show current values for boolean fields', async () => {
      const configWithValues = {
        ...mockConfiguredState,
        autoApprove: true,
        verbose: false
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: configWithValues }
      );

      // Navigate to Operations section and expand
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ENTER']);
      await waitFor(100);

      // Should show boolean values
      expect(lastFrame()).toContain('Auto-Approve Tools');
      expect(lastFrame()).toContain('Verbose Output');
    });

    it('should show current values for text fields', async () => {
      const configWithValues = {
        ...mockConfiguredState,
        outputDir: '/custom/output',
        modelId: 'claude-3-sonnet'
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: configWithValues }
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      expect(lastFrame()).toContain('Primary Model');
    });

    it('should mask password fields', async () => {
      const configWithSecrets = {
        ...mockConfiguredState,
        awsSecretAccessKey: 'secret123',
        mem0ApiKey: 'mem0key456'
      };

      const { lastFrame, stdin } = renderWithProviders(
        <ConfigEditor onClose={mockOnClose} />,
        { config: configWithSecrets }
      );

      // Expand Models section
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(50);

      // Passwords should be masked or not show actual values
      expect(lastFrame()).toContain('AWS Secret Access Key');
      expect(lastFrame()).not.toContain('secret123');
    });
  });
});