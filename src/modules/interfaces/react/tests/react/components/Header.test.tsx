/**
 * Header Component Unit Tests
 * 
 * Tests the application header to ensure:
 * - Responsive logo display based on terminal width
 * - ASCII art rendering for wide terminals
 * - Compact logo for narrow terminals
 * - Version information display
 * - Nightly build indicators
 * - Theme integration (gradients)
 * - Proper spacing and layout
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { renderWithProviders, waitFor } from '../test-utils.js';
import { Header } from '../../components/Header.js';

describe('Header Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('should render with default props', () => {
      const { lastFrame } = renderWithProviders(
        <Header />
      );

      expect(lastFrame()).toContain('v0.1.3');
      expect(lastFrame()).toContain('Full Spectrum Cyber Operations');
    });

    it('should display custom version', () => {
      const { lastFrame } = renderWithProviders(
        <Header version="1.2.3" />
      );

      expect(lastFrame()).toContain('v1.2.3');
    });

    it('should show nightly indicator when enabled', () => {
      const { lastFrame } = renderWithProviders(
        <Header nightly={true} />
      );

      expect(lastFrame()).toContain('NIGHTLY');
    });

    it('should not show nightly indicator by default', () => {
      const { lastFrame } = renderWithProviders(
        <Header nightly={false} />
      );

      expect(lastFrame()).not.toContain('NIGHTLY');
    });
  });

  describe('Responsive Logo Display', () => {
    it('should show long ASCII art for wide terminals (≥90 chars)', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={120} />
      );

      // Should contain ASCII art characters from the long logo
      expect(lastFrame()).toContain('██████╗');
      expect(lastFrame()).toContain('CYBER');
      expect(lastFrame()).toContain('AUTOAGENT');
    });

    it('should show short ASCII art for medium terminals (60-89 chars)', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={75} />
      );

      // Should contain ASCII art characters from the short logo
      expect(lastFrame()).toContain('╔═╗');
      expect(lastFrame()).toContain('CYBER');
      expect(lastFrame()).toContain('AUTO');
    });

    it('should show compact logo for smaller terminals (40-59 chars)', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={50} />
      );

      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
      // Should not contain ASCII art
      expect(lastFrame()).not.toContain('██');
      expect(lastFrame()).not.toContain('╔═╗');
    });

    it('should show ultra-compact logo for very small terminals (<40 chars)', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={30} />
      );

      expect(lastFrame()).toContain('🔐 CAA');
      expect(lastFrame()).not.toContain('Cyber-AutoAgent');
    });

    it('should handle edge cases for terminal width boundaries', () => {
      const boundaries = [
        { width: 90, shouldContain: '██████╗' }, // Long ASCII
        { width: 89, shouldContain: '╔═╗' },     // Short ASCII
        { width: 60, shouldContain: '╔═╗' },     // Short ASCII
        { width: 59, shouldContain: '🔐 Cyber-AutoAgent' }, // Compact
        { width: 40, shouldContain: '🔐 Cyber-AutoAgent' }, // Compact
        { width: 39, shouldContain: '🔐 CAA' }    // Ultra-compact
      ];

      boundaries.forEach(({ width, shouldContain }) => {
        const { lastFrame } = renderWithProviders(
          <Header terminalWidth={width} />
        );

        expect(lastFrame()).toContain(shouldContain);
      });
    });
  });

  describe('ASCII Art Mode Layout', () => {
    it('should position version info below ASCII art', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} version="2.0.0" />
      );

      const frame = lastFrame();
      expect(frame).toContain('██████╗'); // ASCII art
      expect(frame).toContain('Full Spectrum Cyber Operations v2.0.0');
    });

    it('should show nightly indicator with ASCII art', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} nightly={true} />
      );

      expect(lastFrame()).toContain('██████╗'); // ASCII art
      expect(lastFrame()).toContain('NIGHTLY');
    });

    it('should not show version on same line as ASCII art', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} />
      );

      const frame = lastFrame();
      const lines = frame.split('\n');
      
      // ASCII art lines should not contain version info
      const asciiLines = lines.filter(line => line.includes('██'));
      asciiLines.forEach(line => {
        expect(line).not.toContain('v0.1.3');
        expect(line).not.toContain('Full Spectrum');
      });
    });
  });

  describe('Compact Mode Layout', () => {
    it('should show logo and version on same line in compact mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={50} version="1.5.0" />
      );

      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
      expect(lastFrame()).toContain('v1.5.0');
      expect(lastFrame()).toContain('Full Spectrum Cyber Operations');
    });

    it('should include nightly indicator in compact mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={50} nightly={true} />
      );

      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
      expect(lastFrame()).toContain('NIGHTLY');
    });

    it('should handle ultra-compact layout properly', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={25} version="3.0.0" nightly={true} />
      );

      expect(lastFrame()).toContain('🔐 CAA');
      expect(lastFrame()).toContain('v3.0.0');
      expect(lastFrame()).toContain('NIGHTLY');
    });
  });

  describe('Version Information', () => {
    it('should handle semantic version numbers', () => {
      const versions = ['1.0.0', '2.1.3', '10.5.22', '0.0.1'];

      versions.forEach(version => {
        const { lastFrame } = renderWithProviders(
          <Header version={version} />
        );

        expect(lastFrame()).toContain(`v${version}`);
      });
    });

    it('should handle pre-release versions', () => {
      const preReleaseVersions = ['1.0.0-alpha', '2.1.0-beta.1', '3.0.0-rc.2'];

      preReleaseVersions.forEach(version => {
        const { lastFrame } = renderWithProviders(
          <Header version={version} />
        );

        expect(lastFrame()).toContain(`v${version}`);
      });
    });

    it('should handle missing or empty version', () => {
      const { lastFrame } = renderWithProviders(
        <Header version="" />
      );

      expect(lastFrame()).toContain('v'); // Should still show 'v' prefix
    });
  });

  describe('Theme Integration', () => {
    it('should render without crashing with theme colors', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} />
      );

      // Should render successfully (theme colors are applied internally)
      expect(lastFrame()).toContain('██████╗');
      expect(lastFrame()).toContain('Full Spectrum Cyber Operations');
    });

    it('should handle gradient rendering in ASCII art mode', () => {
      // Note: Testing actual gradient appearance would require more complex setup
      // We can test that it renders without crashing
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} />
      );

      expect(lastFrame()).toBeTruthy();
      expect(lastFrame()).toContain('██████╗');
    });

    it('should handle gradient rendering in compact mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={50} />
      );

      expect(lastFrame()).toBeTruthy();
      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
    });
  });

  describe('Layout and Spacing', () => {
    it('should include proper spacing after header', () => {
      const { lastFrame } = renderWithProviders(
        <Header />
      );

      // Should render without layout issues
      expect(lastFrame()).toBeTruthy();
    });

    it('should handle full width layout', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={120} />
      );

      // ASCII art should render within terminal boundaries
      const frame = lastFrame();
      const lines = frame.split('\n');
      
      // No line should be excessively long (basic sanity check)
      lines.forEach(line => {
        expect(line.length).toBeLessThan(200); // Reasonable max line length
      });
    });

    it('should maintain proper alignment in compact mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={50} />
      );

      // Should contain both logo and version info properly aligned
      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
      expect(lastFrame()).toContain('v0.1.3');
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle extremely small terminal widths', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={10} />
      );

      // Should not crash and should show ultra-compact version
      expect(lastFrame()).toContain('🔐 CAA');
    });

    it('should handle extremely large terminal widths', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={300} />
      );

      // Should show full ASCII art
      expect(lastFrame()).toContain('██████╗');
      expect(lastFrame()).toContain('CYBER');
    });

    it('should handle zero or negative terminal width', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={0} />
      );

      // Should not crash (will likely show ultra-compact)
      expect(lastFrame()).toBeTruthy();
    });

    it('should handle undefined terminal width', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={undefined} />
      );

      // Should use default width (80) and show compact logo
      expect(lastFrame()).toContain('🔐 Cyber-AutoAgent');
    });

    it('should handle special characters in version', () => {
      const { lastFrame } = renderWithProviders(
        <Header version="1.0.0-α.β.γ" />
      );

      expect(lastFrame()).toContain('v1.0.0-α.β.γ');
    });
  });

  describe('Branding and Content', () => {
    it('should always show proper branding text', () => {
      const { lastFrame } = renderWithProviders(
        <Header />
      );

      expect(lastFrame()).toContain('Full Spectrum Cyber Operations');
    });

    it('should contain security/cyber security branding', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={100} />
      );

      expect(lastFrame()).toContain('CYBER');
      expect(lastFrame()).toContain('AUTOAGENT');
    });

    it('should use appropriate emoji in compact modes', () => {
      const compactSizes = [50, 30, 20];

      compactSizes.forEach(width => {
        const { lastFrame } = renderWithProviders(
          <Header terminalWidth={width} />
        );

        expect(lastFrame()).toContain('🔐'); // Security lock emoji
      });
    });
  });

  describe('Memoization and Performance', () => {
    it('should be properly memoized', () => {
      expect(Header.displayName).toBe('Header');
    });

    it('should not re-render with same props', () => {
      const props = { version: '1.0.0', terminalWidth: 80, nightly: false };
      const { lastFrame, rerender } = renderWithProviders(
        <Header {...props} />
      );

      const initialFrame = lastFrame();

      rerender(<Header {...props} />);

      expect(lastFrame()).toBe(initialFrame);
    });

    it('should re-render when props change', () => {
      const { lastFrame, rerender } = renderWithProviders(
        <Header version="1.0.0" />
      );

      expect(lastFrame()).toContain('v1.0.0');

      rerender(<Header version="2.0.0" />);

      expect(lastFrame()).toContain('v2.0.0');
    });
  });

  describe('ASCII Art Content Validation', () => {
    it('should contain proper ASCII art structure in long mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={120} />
      );

      const frame = lastFrame();
      
      // Should contain box drawing characters
      expect(frame).toContain('██');
      expect(frame).toContain('╗');
      expect(frame).toContain('╚');
      
      // Should span multiple lines
      expect(frame.split('\n').length).toBeGreaterThan(5);
    });

    it('should contain proper ASCII art structure in short mode', () => {
      const { lastFrame } = renderWithProviders(
        <Header terminalWidth={70} />
      );

      const frame = lastFrame();
      
      // Should contain box drawing characters from short logo
      expect(frame).toContain('╔');
      expect(frame).toContain('╦');
      expect(frame).toContain('╝');
    });
  });
});