/**
 * SafetyWarning Component Unit Tests
 * 
 * Tests the critical safety authorization component to ensure:
 * - Proper authorization flow enforcement
 * - Double confirmation requirement
 * - Security controls cannot be bypassed
 * - Keyboard input handling
 * - Visual display validation
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { renderWithProviders, simulateKeyboardInput, waitFor } from '../test-utils.js';
import { SafetyWarning } from '../../components/SafetyWarning.js';

describe('SafetyWarning Component', () => {
  let mockOnConfirm: jest.MockedFunction<() => void>;
  let mockOnCancel: jest.MockedFunction<() => void>;

  const defaultProps = {
    target: 'testphp.vulnweb.com',
    module: 'general',
    onConfirm: jest.fn(),
    onCancel: jest.fn()
  };

  beforeEach(() => {
    mockOnConfirm = jest.fn();
    mockOnCancel = jest.fn();
    jest.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('should render with proper warning header', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      expect(lastFrame()).toContain('⚠️  SECURITY ASSESSMENT AUTHORIZATION WARNING');
      expect(lastFrame()).toContain('IMPORTANT: Only proceed if you have:');
    });

    it('should display target and module information', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning 
          target="https://api.example.com" 
          module="web" 
          onConfirm={mockOnConfirm} 
          onCancel={mockOnCancel} 
        />
      );

      expect(lastFrame()).toContain('Target: https://api.example.com');
      expect(lastFrame()).toContain('web security assessment');
    });

    it('should show initial authorization question', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      expect(lastFrame()).toContain('Do you acknowledge that you have proper authorization? (y/N)');
      expect(lastFrame()).not.toContain('Proceed with cyber operation?');
    });

    it('should display all required authorization points', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      expect(lastFrame()).toContain('EXPLICIT WRITTEN AUTHORIZATION');
      expect(lastFrame()).toContain('LEGAL PERMISSION');
      expect(lastFrame()).toContain('PROPER SAFETY MEASURES');
      expect(lastFrame()).toContain('APPROPRIATE SCOPE');
    });

    it('should show legal warning text', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      expect(lastFrame()).toContain('Unauthorized security testing may violate');
      expect(lastFrame()).toContain('You assume full legal responsibility');
    });

    it('should display keyboard instructions', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      expect(lastFrame()).toContain("Press 'y' to continue, 'n' to cancel, or Esc to abort");
    });
  });

  describe('First Authorization Step', () => {
    it('should advance to second step when y is pressed', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Press 'y' for first authorization
      stdin.write('y');
      await waitFor(50);

      expect(lastFrame()).toContain('✓ Authorization acknowledged');
      expect(lastFrame()).toContain('Proceed with cyber operation? (y/N)');
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('should accept uppercase Y', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      stdin.write('Y');
      await waitFor(50);

      expect(lastFrame()).toContain('✓ Authorization acknowledged');
      expect(lastFrame()).toContain('Proceed with cyber operation?');
    });

    it('should cancel when n is pressed', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      stdin.write('n');
      await waitFor(50);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('should cancel when N is pressed', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      stdin.write('N');
      await waitFor(50);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it('should cancel on ESC key', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('should ignore other keys in first step', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Try various invalid inputs
      stdin.write('x');
      stdin.write('1');
      simulateKeyboardInput(stdin, ['ENTER', 'TAB', 'SPACE']);
      await waitFor(50);

      // Should still be in first step
      expect(lastFrame()).toContain('Do you acknowledge that you have proper authorization?');
      expect(lastFrame()).not.toContain('✓ Authorization acknowledged');
      expect(mockOnConfirm).not.toHaveBeenCalled();
      expect(mockOnCancel).not.toHaveBeenCalled();
    });
  });

  describe('Second Authorization Step', () => {
    it('should confirm when y is pressed after acknowledgment', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // First authorization
      stdin.write('y');
      await waitFor(50);

      // Second confirmation
      stdin.write('y');
      await waitFor(50);

      expect(mockOnConfirm).toHaveBeenCalledTimes(1);
      expect(mockOnCancel).not.toHaveBeenCalled();
    });

    it('should cancel when n is pressed in second step', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // First authorization
      stdin.write('y');
      await waitFor(50);

      // Cancel at second step
      stdin.write('n');
      await waitFor(50);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('should cancel on ESC in second step', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // First authorization
      stdin.write('y');
      await waitFor(50);

      // ESC at second step
      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });
  });

  describe('Security Control Validation', () => {
    it('should require double confirmation - cannot bypass', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Try to press 'y' multiple times rapidly
      stdin.write('y');
      stdin.write('y');
      stdin.write('y');
      await waitFor(100);

      // Should only call confirm once (after proper double confirmation)
      expect(mockOnConfirm).toHaveBeenCalledTimes(1);
    });

    it('should not allow proceeding without first acknowledgment', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Try to enter second step immediately (should not work)
      expect(lastFrame()).not.toContain('Proceed with cyber operation?');
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('should maintain state through multiple inputs', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // First step
      stdin.write('y');
      await waitFor(50);
      expect(lastFrame()).toContain('✓ Authorization acknowledged');

      // Try some invalid inputs
      stdin.write('x');
      stdin.write('z');
      await waitFor(50);

      // Should still be in confirmed state
      expect(lastFrame()).toContain('✓ Authorization acknowledged');
      expect(lastFrame()).toContain('Proceed with cyber operation?');
    });
  });

  describe('Visual Display Validation', () => {
    it('should use proper styling and borders', () => {
      const { lastFrame } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      const frame = lastFrame();
      
      // Should contain proper warning symbols and styling
      expect(frame).toContain('⚠️');
      expect(frame).toContain('•');
      
      // Should have proper structure
      expect(frame).toContain('SECURITY ASSESSMENT AUTHORIZATION WARNING');
    });

    it('should handle different target formats properly', () => {
      const testCases = [
        'https://api.example.com:8080/v1',
        '192.168.1.1',
        'localhost:3000',
        'subdomain.example.org/path'
      ];

      testCases.forEach(target => {
        const { lastFrame } = renderWithProviders(
          <SafetyWarning 
            target={target} 
            module="network" 
            onConfirm={mockOnConfirm} 
            onCancel={mockOnCancel} 
          />
        );

        expect(lastFrame()).toContain(`Target: ${target}`);
      });
    });

    it('should handle different module names', () => {
      const modules = ['general', 'network', 'web', 'wireless'];

      modules.forEach(module => {
        const { lastFrame } = renderWithProviders(
          <SafetyWarning 
            target="example.com" 
            module={module} 
            onConfirm={mockOnConfirm} 
            onCancel={mockOnCancel} 
          />
        );

        expect(lastFrame()).toContain(`${module} security assessment`);
      });
    });
  });

  describe('Callback Validation', () => {
    it('should call onConfirm only after proper double confirmation', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Complete proper flow
      stdin.write('y'); // First acknowledgment
      await waitFor(50);
      stdin.write('y'); // Final confirmation
      await waitFor(50);

      expect(mockOnConfirm).toHaveBeenCalledTimes(1);
      expect(mockOnCancel).not.toHaveBeenCalled();
    });

    it('should call onCancel from any cancellation point', async () => {
      const cancellationPoints = ['n', 'N'];

      for (const input of cancellationPoints) {
        const localMockCancel = jest.fn();
        const { stdin } = renderWithProviders(
          <SafetyWarning {...defaultProps} onCancel={localMockCancel} />
        );

        stdin.write(input);
        await waitFor(50);

        expect(localMockCancel).toHaveBeenCalledTimes(1);
      }
    });

    it('should handle rapid sequential inputs properly', async () => {
      const { stdin } = renderWithProviders(
        <SafetyWarning {...defaultProps} onConfirm={mockOnConfirm} onCancel={mockOnCancel} />
      );

      // Rapid sequence
      stdin.write('y');
      stdin.write('n');
      await waitFor(50);

      // Should have acknowledged first, then cancelled
      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });
  });
});