import React from 'react';
import { render } from 'ink-testing-library';
import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { App } from '../../App.js';
import * as fs from 'fs/promises';

// Mock file system
jest.mock('fs/promises');
jest.mock('glob', () => ({
  glob: jest.fn()
}));

describe('Module Loading Integration', () => {
  beforeEach(() => {
    // Mock module directory structure
    (fs.readdir as jest.MockedFunction<typeof fs.readdir>).mockResolvedValue([
      'general'
    ] as any);
    
    // Mock module.yaml files exist
    (fs.access as jest.MockedFunction<typeof fs.access>).mockResolvedValue(undefined);
  });
  
  describe('Module Discovery', () => {
    it('should discover available modules on startup', async () => {
      const { lastFrame, stdin } = render(<App />);
      
      // Wait for initial render
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Type help to see available modules
      stdin.write('help');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('module general');
    });
  });
  
  describe('Module Selection Flow', () => {
    it('should load module and advance to target stage', async () => {
      const { lastFrame, stdin } = render(<App />);
      
      // Skip welcome screen if shown
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      // Load general module
      stdin.write('module general');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('Module loaded: general');
      expect(lastFrame()).toContain('Now set your target:');
      expect(lastFrame()).toContain('[general] >');
    });
    
    it('should reject invalid module names', async () => {
      const { lastFrame, stdin } = render(<App />);
      
      // Skip welcome screen
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      // Try invalid module
      stdin.write('module invalid_module');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('Unknown module: invalid_module');
      expect(lastFrame()).toContain('Available modules:');
    });
  });
  
  describe('Complete Assessment Flow', () => {
    it('should complete module->target->objective flow', async () => {
      const { lastFrame, stdin } = render(<App />);
      
      // Skip welcome
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      // Load module
      stdin.write('module general');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      // Set target
      stdin.write('target https://api.example.com');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('Target set: https://api.example.com');
      expect(lastFrame()).toContain('Enter objective or press Enter for default:');
      
      // Set objective
      stdin.write('Test authentication endpoints');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('Objective set');
      expect(lastFrame()).toContain('Press Enter to start assessment');
      expect(lastFrame()).toContain('[general → api.example.com] >');
    });
  });
  
  describe('Module List Command', () => {
    it('should display module list when requested', async () => {
      const { lastFrame, stdin } = render(<App />);
      
      // Mock glob for module discovery
      const { glob } = require('glob');
      glob.mockResolvedValue([
        'general/module.yaml'
      ]);
      
      // Skip welcome and request module list
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      stdin.write('modules');
      stdin.write('\r');
      await new Promise(resolve => setTimeout(resolve, 50));
      
      expect(lastFrame()).toContain('Available Modules');
      expect(lastFrame()).toContain('general');
    });
  });
  
  describe('CLI Arguments', () => {
    it('should auto-load module from CLI arguments', async () => {
      const { lastFrame } = render(<App module="network" />);
      
      // Wait for initialization
      await new Promise(resolve => setTimeout(resolve, 100));
      
      expect(lastFrame()).toContain('[network] >');
    });
    
    it('should complete full flow from CLI arguments', async () => {
      const { lastFrame } = render(
        <App 
          module="general" 
          target="example.com"
          objective="XSS testing"
        />
      );
      
      // Wait for flow completion
      await new Promise(resolve => setTimeout(resolve, 200));
      
      // Should be ready to start assessment
      expect(lastFrame()).toContain('Press Enter to start assessment');
      expect(lastFrame()).toContain('[general → example.com] >');
    });
  });
});