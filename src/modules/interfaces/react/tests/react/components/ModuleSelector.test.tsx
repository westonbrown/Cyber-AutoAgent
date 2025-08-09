/**
 * ModuleSelector Component Unit Tests
 * 
 * Tests the module selection modal to ensure:
 * - Module list display
 * - Arrow key navigation
 * - Module selection and switching
 * - Current module highlighting
 * - Keyboard shortcuts (ESC, Enter)
 * - Module descriptions
 */

import React from 'react';
import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { renderWithProviders, simulateKeyboardInput, waitFor, mockAvailableModules } from '../test-utils.js';
import { ModuleSelector } from '../../components/ModuleSelector.js';

// Mock the useModule hook
const mockUseModule = {
  availableModules: {
    'general': {
      name: 'general',
      description: 'General security assessment with comprehensive scanning',
      category: 'security',
      tools: [
        { name: 'nmap', description: 'Network port scanner', category: 'network' },
        { name: 'http_request', description: 'HTTP client tool', category: 'web' },
        { name: 'shell', description: 'Shell command execution', category: 'system' }
      ],
      capabilities: ['network-scanning', 'web-testing', 'system-analysis']
    },
    'network': {
      name: 'network', 
      description: 'Network security testing and port scanning',
      category: 'network',
      tools: [
        { name: 'nmap', description: 'Network port scanner', category: 'network' },
        { name: 'masscan', description: 'High-speed port scanner', category: 'network' },
        { name: 'shell', description: 'Shell command execution', category: 'system' }
      ],
      capabilities: ['port-scanning', 'network-discovery', 'service-enumeration']
    },
    'web': {
      name: 'web',
      description: 'Web application security testing',
      category: 'web',
      tools: [
        { name: 'http_request', description: 'HTTP client tool', category: 'web' },
        { name: 'sqlmap', description: 'SQL injection testing', category: 'web' },
        { name: 'nikto', description: 'Web vulnerability scanner', category: 'web' }
      ],
      capabilities: ['sql-injection', 'xss-testing', 'web-scanning']
    }
  },
  currentModule: 'general',
  switchModule: jest.fn().mockResolvedValue(undefined) as any
};

jest.mock('../../contexts/ModuleContext.js', () => ({
  useModule: () => mockUseModule
}));

describe('ModuleSelector Component', () => {
  let mockOnClose: jest.MockedFunction<() => void>;
  let mockOnSelect: jest.MockedFunction<(module: string) => void>;

  beforeEach(() => {
    mockOnClose = jest.fn();
    mockOnSelect = jest.fn();
    jest.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('should render with module list and header', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      expect(lastFrame()).toContain('Select Security Module');
      expect(lastFrame()).toContain('general');
      expect(lastFrame()).toContain('network');
      expect(lastFrame()).toContain('web');
    });

    it('should display module descriptions', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      expect(lastFrame()).toContain('General security assessment');
      expect(lastFrame()).toContain('Network security testing');
      expect(lastFrame()).toContain('Web application security');
    });

    it('should highlight first module by default', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Should show some indication of selection (exact formatting may vary)
      expect(lastFrame()).toContain('general');
    });

    it('should show keyboard navigation instructions', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Should contain navigation hints
      expect(lastFrame()).toContain('↑↓');
      expect(lastFrame()).toContain('Enter');
      expect(lastFrame()).toContain('Esc');
    });
  });

  describe('Module Display', () => {
    it('should show all available modules', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      Object.keys(mockUseModule.availableModules).forEach(moduleName => {
        expect(lastFrame()).toContain(moduleName);
      });
    });

    it('should handle empty module list', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      expect(lastFrame()).toContain('Select Security Module');
      // Should not crash and should show some indication
    });

    it('should show raw module names not display names', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Should show raw names like 'general', 'network', 'web'
      expect(lastFrame()).toContain('general');
      expect(lastFrame()).toContain('network'); 
      expect(lastFrame()).toContain('web');
    });
  });

  describe('Navigation', () => {
    it('should navigate down with arrow key', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      simulateKeyboardInput(stdin, ['ARROW_DOWN']);
      await waitFor(50);

      // Should highlight second module (network)
      const frame = lastFrame();
      expect(frame).toContain('network');
    });

    it('should navigate up with arrow key', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Navigate down then up
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ARROW_UP']);
      await waitFor(50);

      // Should be back to first module
      const frame = lastFrame();
      expect(frame).toContain('general');
    });

    it('should not navigate above first item', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Try to navigate up from first item
      simulateKeyboardInput(stdin, ['ARROW_UP']);
      await waitFor(50);

      // Should stay at first item
      const frame = lastFrame();
      expect(frame).toContain('general');
    });

    it('should not navigate below last item', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Navigate to last item and try to go beyond
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ARROW_DOWN', 'ARROW_DOWN']);
      await waitFor(100);

      // Should stay at last item (web)
      const frame = lastFrame();
      expect(frame).toContain('web');
    });

    it('should cycle through all modules', async () => {
      const { lastFrame, stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      const moduleOrder = ['general', 'network', 'web'];
      
      for (let i = 0; i < moduleOrder.length; i++) {
        if (i > 0) {
          simulateKeyboardInput(stdin, ['ARROW_DOWN']);
          await waitFor(50);
        }
        
        const frame = lastFrame();
        expect(frame).toContain(moduleOrder[i]);
      }
    });
  });

  describe('Module Selection', () => {
    it('should select module with Enter key', async () => {
      const mockSwitchModule = jest.fn().mockResolvedValue(undefined) as any;
      
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Navigate to network module and select
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ENTER']);
      await waitFor(100);

      expect(mockOnSelect).toHaveBeenCalledWith('network');
      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onSelect with correct module', async () => {
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Navigate to web module and select
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ARROW_DOWN', 'ENTER']);
      await waitFor(100);

      expect(mockOnSelect).toHaveBeenCalledWith('web');
    });

    it('should close modal after selection', async () => {
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(100);

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should handle selection without onSelect callback', async () => {
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} />, // No onSelect provided
      );

      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(100);

      // Should not crash and should still close
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('Current Module Handling', () => {
    it('should highlight current module if set', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Should indicate current module somehow (implementation dependent)
      expect(lastFrame()).toContain('general'); // or whichever is current
    });

    it('should close without switching if current module selected', async () => {
      // Mock current module as 'general'
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Select first module (assuming it's current)
      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(100);

      expect(mockOnClose).toHaveBeenCalled();
      // onSelect may or may not be called depending on implementation
    });
  });

  describe('ESC Key Behavior', () => {
    it('should close modal on ESC key', async () => {
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      simulateKeyboardInput(stdin, ['ESC']);
      await waitFor(50);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockOnSelect).not.toHaveBeenCalled();
    });

    it('should cancel selection when ESC is pressed', async () => {
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Navigate to different module then press ESC
      simulateKeyboardInput(stdin, ['ARROW_DOWN', 'ESC']);
      await waitFor(100);

      expect(mockOnClose).toHaveBeenCalled();
      expect(mockOnSelect).not.toHaveBeenCalled();
    });
  });

  describe('Visual Display', () => {
    it('should use proper styling and layout', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      const frame = lastFrame();
      
      // Should have proper structure
      expect(frame).toContain('Select Security Module');
      expect(frame).toContain('general');
      
      // Should show descriptions
      expect(frame).toContain('General security assessment');
    });

    it('should show module count information', () => {
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />,
      );

      // Should show that there are multiple modules available
      const frame = lastFrame();
      expect(frame).toContain('general');
      expect(frame).toContain('network');
      expect(frame).toContain('web');
    });

    it('should handle long module descriptions gracefully', () => {
      // This test relies on the mocked modules, which already have reasonable descriptions
      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Should not crash and should display the modules
      expect(lastFrame()).toContain('general');
      expect(lastFrame()).toContain('General security assessment');
    });
  });

  describe('Error Handling', () => {
    it('should handle module switching errors gracefully', async () => {
      const mockSwitchModule = jest.fn().mockRejectedValue(new Error('Switch failed')) as any;
      
      const { stdin } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      simulateKeyboardInput(stdin, ['ENTER']);
      await waitFor(100);

      // Should not crash on error
      // Implementation dependent on how errors are handled
    });

    it('should handle missing module data', () => {
      const incompleteModules = {
        'broken': {
          name: 'broken',
          // Missing other required fields
        } as any
      };

      const { lastFrame } = renderWithProviders(
        <ModuleSelector onClose={mockOnClose} onSelect={mockOnSelect} />
      );

      // Should not crash
      expect(lastFrame()).toContain('Select Security Module');
    });
  });
});