#!/usr/bin/env node

/**
 * Comprehensive Terminal Capture System
 * 
 * Tests every screen and interaction possibility in Cyber-AutoAgent
 * Ensures consistent branding, no flickering, proper alignment
 */

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import path from 'path';
import os from 'os';
import * as pty from 'node-pty';
import { mockConfiguredState, mockSetupState } from './mock-config.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appPath = join(__dirname, '..', 'dist', 'index.js');
const capturesDir = join(__dirname, 'captures');

// Clean and create captures directory
if (fs.existsSync(capturesDir)) {
  fs.rmSync(capturesDir, { recursive: true });
}
fs.mkdirSync(capturesDir, { recursive: true });

class Journey {
  constructor(name, description, config = null) {
    this.name = name;
    this.description = description;
    this.config = config;
    this.journeyDir = join(capturesDir, name.toLowerCase().replace(/\s+/g, '-'));
    this.captureIndex = 0;
    this.captures = [];
    this.term = null;
    this.outputBuffer = '';
    this.lastStableFrame = '';
    
    fs.mkdirSync(this.journeyDir, { recursive: true });
  }

  async start() {
    console.log(`\n📸 Starting Journey: ${this.name}`);
    console.log(`   ${this.description}`);
    console.log('─'.repeat(70));

    // Set up environment
    const env = { ...process.env, NO_COLOR: '1' };
    
    // Set up config file if needed
    if (this.config) {
      const configDir = join(os.homedir(), '.cyber-autoagent');
      const configPath = join(configDir, 'config.json');
      
      // Create directory if it doesn't exist
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      
      // Write config file
      fs.writeFileSync(configPath, JSON.stringify(this.config, null, 2));
      console.log(`  ✓ Created config at: ${configPath}`);
    }

    // Start PTY session
    this.term = pty.spawn('node', [appPath], {
      name: 'xterm-256color',
      cols: 80,
      rows: 24,
      cwd: dirname(appPath),
      env: env
    });

    // Capture output
    this.term.onData((data) => {
      this.outputBuffer += data;
    });

    // Let it initialize
    await this.wait(1000);
  }

  async wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async capture(label, metadata = {}) {
    // Wait for output to stabilize
    await this.wait(300);
    
    const currentFrame = this.outputBuffer;
    
    // Check if frame has stabilized (no changes)
    let attempts = 0;
    while (this.outputBuffer !== currentFrame && attempts < 10) {
      await this.wait(100);
      attempts++;
    }

    const filename = `${String(this.captureIndex).padStart(3, '0')}-${label.toLowerCase().replace(/\s+/g, '-')}.txt`;
    const filepath = join(this.journeyDir, filename);
    
    // Add capture metadata
    const captureData = [
      '=' .repeat(80),
      `CAPTURE ${this.captureIndex}: ${label}`,
      `TIME: ${new Date().toISOString()}`,
      metadata.action ? `ACTION: ${metadata.action}` : null,
      metadata.notes ? `NOTES: ${metadata.notes}` : null,
      '=' .repeat(80),
      '',
      this.outputBuffer
    ].filter(Boolean).join('\n');
    
    fs.writeFileSync(filepath, captureData);
    
    this.captures.push({
      index: this.captureIndex,
      label,
      filename,
      metadata
    });
    
    console.log(`  ✓ Captured: ${label}`);
    this.captureIndex++;
    
    // Store last stable frame for comparison
    this.lastStableFrame = this.outputBuffer;
  }

  async input(text, label = null) {
    if (label) {
      console.log(`  → Input: ${label}`);
    }
    this.term.write(text);
    await this.wait(100);
  }

  async finish() {
    if (this.term) {
      this.term.kill();
    }
    
    // Create journey summary
    const summaryPath = join(this.journeyDir, '000-JOURNEY-SUMMARY.md');
    const summary = [
      `# Journey: ${this.name}`,
      '',
      `**Description:** ${this.description}`,
      `**Total Captures:** ${this.captures.length}`,
      `**Generated:** ${new Date().toISOString()}`,
      '',
      '## Capture Sequence',
      '',
      ...this.captures.map(c => 
        `${c.index}. **${c.label}** - \`${c.filename}\`${c.metadata.notes ? ` - ${c.metadata.notes}` : ''}`
      ),
      '',
      '## Quality Checklist',
      '',
      '### Branding & Headers',
      '- [ ] CYBER ASCII art appears only once per screen',
      '- [ ] "Full Spectrum Cyber Operations" tagline is consistent',
      '- [ ] Version number displayed correctly',
      '',
      '### UI Consistency',
      '- [ ] Box borders align properly',
      '- [ ] Colors are consistent across screens',
      '- [ ] No flickering between transitions',
      '- [ ] Text alignment is correct',
      '',
      '### Content Quality',
      '- [ ] No duplicate log entries',
      '- [ ] No overlapping UI elements',
      '- [ ] No visible escape sequences (^[)',
      '- [ ] No error logs in user view',
      '- [ ] Progress indicators work smoothly',
      '',
      '### Functionality',
      '- [ ] All inputs respond correctly',
      '- [ ] Navigation works as expected',
      '- [ ] Modal dialogs render properly',
      '- [ ] Commands execute successfully'
    ].join('\n');
    
    fs.writeFileSync(summaryPath, summary);
    console.log(`✅ Journey complete: ${this.captures.length} captures saved`);
  }
}

// Define all journeys based on user instructions
const journeys = [
  // SETUP WIZARD TESTING
  {
    name: 'Setup Wizard - Complete Flow',
    description: 'Test full setup wizard with all screens and transitions',
    steps: async (j) => {
      await j.capture('Welcome Screen - Initial Load');
      await j.input('\r', 'Press Enter to begin');
      await j.wait(500);
      await j.capture('Deployment Mode Selection - Initial');
      
      // Test navigation
      await j.input('\x1B[B', 'Arrow Down');
      await j.wait(300);
      await j.capture('Deployment Mode - Single Container Highlighted');
      
      await j.input('\x1B[B', 'Arrow Down');
      await j.wait(300);
      await j.capture('Deployment Mode - Enterprise Highlighted');
      
      await j.input('\x1B[A', 'Arrow Up');
      await j.wait(300);
      await j.capture('Deployment Mode - Single Container Again');
      
      await j.input('\x1B[A', 'Arrow Up');
      await j.wait(300);
      await j.capture('Deployment Mode - Local CLI Again');
      
      // Select Local CLI
      await j.input('\r', 'Select Local CLI');
      await j.wait(1000);
      await j.capture('Python Environment Setup - Start');
      
      await j.wait(2000);
      await j.capture('Setup Progress - Python Check');
      
      await j.wait(2000);
      await j.capture('Setup Progress - Dependencies');
      
      await j.wait(2000);
      await j.capture('Setup Complete Screen');
      
      await j.input('\r', 'Continue to Main');
      await j.wait(500);
      await j.capture('Main Interface - After Setup');
    }
  },
  
  {
    name: 'Setup Wizard - Back Navigation',
    description: 'Test ESC/back functionality in setup wizard',
    steps: async (j) => {
      await j.capture('Welcome Screen');
      await j.input('\r', 'Enter to begin');
      await j.wait(500);
      await j.capture('Deployment Mode Selection');
      
      await j.input('\x1B', 'ESC to go back');
      await j.wait(500);
      await j.capture('Back at Welcome Screen');
      
      await j.input('\x1B', 'ESC to exit');
      await j.wait(500);
      await j.capture('Exit Confirmation or Closed');
    }
  },

  // MAIN INTERFACE TESTING
  {
    name: 'Main Interface - All Commands',
    description: 'Test every command available in main interface',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface - Initial');
      
      // Help command
      await j.input('/help', 'Type help command');
      await j.capture('Typing help command');
      await j.input('\r', 'Execute help');
      await j.wait(500);
      await j.capture('Help Modal Open');
      await j.input('\x1B', 'ESC to close');
      await j.wait(300);
      await j.capture('Back to Main After Help');
      
      // Config command
      await j.input('/config', 'Type config command');
      await j.capture('Typing config command');
      await j.input('\r', 'Execute config');
      await j.wait(500);
      await j.capture('Config Editor Open');
      
      // Navigate config fields
      await j.input('\x1B[B', 'Navigate down');
      await j.wait(200);
      await j.capture('Config - Model Provider Field');
      
      await j.input('\x1B[B', 'Navigate to observability');
      await j.wait(200);
      await j.capture('Config - Observability Section');
      
      await j.input('\x1B', 'ESC to exit config');
      await j.wait(300);
      await j.capture('Back to Main After Config');
      
      // Memory command
      await j.input('/memory', 'Type memory command');
      await j.capture('Typing memory command');
      await j.input('\r', 'Execute memory');
      await j.wait(500);
      await j.capture('Memory Search Interface');
      await j.input('\x1B', 'ESC to exit memory');
      await j.wait(300);
      await j.capture('Back to Main After Memory');
      
      // Plugins command
      await j.input('/plugins', 'Type plugins command');
      await j.capture('Typing plugins command');
      await j.input('\r', 'Execute plugins');
      await j.wait(500);
      await j.capture('Plugin Selection Interface');
      await j.input('\x1B', 'ESC to exit plugins');
      await j.wait(300);
      await j.capture('Back to Main After Plugins');
      
      // Docs command
      await j.input('/docs', 'Type docs command');
      await j.capture('Typing docs command');
      await j.input('\r', 'Execute docs');
      await j.wait(500);
      await j.capture('Documentation Viewer');
      await j.input('\x1B', 'ESC to exit docs');
      await j.wait(300);
      await j.capture('Back to Main After Docs');
      
      // Health command
      await j.input('/health', 'Type health command');
      await j.capture('Typing health command');
      await j.input('\r', 'Execute health');
      await j.wait(500);
      await j.capture('Health Status Display');
      
      // Clear command
      await j.input('/clear', 'Type clear command');
      await j.capture('Typing clear command');
      await j.input('\r', 'Execute clear');
      await j.wait(300);
      await j.capture('Screen After Clear');
    }
  },

  // ASSESSMENT WORKFLOW
  {
    name: 'Assessment - Basic Flow',
    description: 'Test basic assessment workflow from target to execution',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface - Start');
      
      // Set target
      await j.input('target https://testphp.vulnweb.com', 'Type target command');
      await j.capture('Typing Target Command');
      await j.input('\r', 'Execute target');
      await j.wait(300);
      await j.capture('Target Set Confirmation');
      
      // Execute assessment
      await j.input('execute', 'Type execute command');
      await j.capture('Typing Execute Command');
      await j.input('\r', 'Execute assessment');
      await j.wait(500);
      await j.capture('Authorization Screen - First');
      
      await j.input('y', 'First authorization');
      await j.wait(300);
      await j.capture('Authorization Screen - Second');
      
      await j.input('y', 'Second authorization');
      await j.wait(500);
      await j.capture('Assessment Starting');
      
      await j.wait(2000);
      await j.capture('Assessment Running - Progress');
      
      // Kill operation
      await j.input('\x1B', 'ESC to kill');
      await j.wait(500);
      await j.capture('Operation Killed');
    }
  },

  // EDGE CASES AND ERROR STATES
  {
    name: 'Error States',
    description: 'Test various error conditions and edge cases',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Invalid command
      await j.input('/invalid', 'Type invalid command');
      await j.capture('Typing Invalid Command');
      await j.input('\r', 'Execute');
      await j.wait(300);
      await j.capture('Invalid Command Error');
      
      // Execute without target
      await j.input('execute', 'Execute without target');
      await j.capture('Typing Execute No Target');
      await j.input('\r', 'Execute');
      await j.wait(300);
      await j.capture('No Target Error');
      
      // Invalid target
      await j.input('target not-a-url', 'Invalid target');
      await j.capture('Typing Invalid Target');
      await j.input('\r', 'Execute');
      await j.wait(300);
      await j.capture('Invalid Target Error');
      
      // Very long input
      await j.input('target ' + 'x'.repeat(100), 'Very long input');
      await j.capture('Long Input Handling');
      await j.input('\x1B', 'Clear input');
      await j.wait(200);
      await j.capture('Input Cleared');
    }
  },

  // CONFIGURATION TESTING
  {
    name: 'Configuration - All Options',
    description: 'Test all configuration options and validation',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      await j.input('/config', 'Open config');
      await j.input('\r');
      await j.wait(500);
      await j.capture('Config Editor - Initial');
      
      // Test each section
      await j.input('\r', 'Edit first field');
      await j.wait(300);
      await j.capture('Config - Editing Model Provider');
      
      await j.input('\x1B[B', 'Select different option');
      await j.wait(200);
      await j.capture('Config - Option Selected');
      
      await j.input('\r', 'Confirm selection');
      await j.wait(300);
      await j.capture('Config - After Selection');
      
      // Test observability toggle
      await j.input('\t\t\t', 'Tab to observability');
      await j.wait(200);
      await j.capture('Config - Observability Section');
      
      await j.input(' ', 'Toggle option');
      await j.wait(200);
      await j.capture('Config - After Toggle');
      
      // Save
      await j.input('\r', 'Save config');
      await j.wait(500);
      await j.capture('Config - Save Confirmation');
    }
  },

  // MEMORY OPERATIONS
  {
    name: 'Memory Operations',
    description: 'Test memory search and listing functionality',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Memory list
      await j.input('/memory list', 'Memory list command');
      await j.capture('Typing Memory List');
      await j.input('\r');
      await j.wait(500);
      await j.capture('Memory List Results');
      
      // Memory search
      await j.input('/memory search SQL', 'Memory search command');
      await j.capture('Typing Memory Search');
      await j.input('\r');
      await j.wait(500);
      await j.capture('Memory Search Results');
      
      // Interactive memory search
      await j.input('/memory', 'Open memory interface');
      await j.input('\r');
      await j.wait(500);
      await j.capture('Memory Search Interface');
      
      await j.input('injection', 'Type search query');
      await j.capture('Memory Search - Typing Query');
      
      await j.input('\r', 'Execute search');
      await j.wait(700);
      await j.capture('Memory Search - Results Display');
      
      await j.input('\x1B', 'Exit memory');
      await j.wait(300);
      await j.capture('Back to Main');
    }
  },

  // RAPID INPUT TESTING
  {
    name: 'Performance - Rapid Input',
    description: 'Test UI responsiveness with rapid inputs',
    config: { isConfigured: true, hasSeenWelcome: true },
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Rapid typing
      const rapidText = 'target https://example.com/api/v1/users';
      for (const char of rapidText) {
        await j.input(char);
        await j.wait(10); // Very short delay
      }
      await j.capture('After Rapid Typing');
      
      // Rapid command switching
      await j.input('\x1B', 'Clear');
      await j.input('/help\r', 'Help');
      await j.wait(200);
      await j.input('\x1B', 'Close');
      await j.input('/config\r', 'Config');
      await j.wait(200);
      await j.input('\x1B', 'Close');
      await j.input('/memory\r', 'Memory');
      await j.wait(200);
      await j.capture('After Rapid Commands');
    }
  },

  // NEW: DOCUMENTATION VIEWER TESTING
  {
    name: 'Documentation Viewer - Full Navigation',
    description: 'Test documentation viewer with navigation and scrolling',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Open docs menu
      await j.input('/docs', 'Type docs command');
      await j.capture('Typing docs command');
      await j.input('\r', 'Execute docs');
      await j.wait(500);
      await j.capture('Documentation Menu');
      
      // Select first document
      await j.input('1', 'Select user instructions');
      await j.wait(500);
      await j.capture('User Instructions Document');
      
      // Test navigation
      await j.input('j', 'Scroll down');
      await j.wait(200);
      await j.capture('After Scroll Down');
      
      await j.input('k', 'Scroll up');
      await j.wait(200);
      await j.capture('After Scroll Up');
      
      await j.input('G', 'Go to end');
      await j.wait(200);
      await j.capture('At Document End');
      
      await j.input('g', 'Go to beginning');
      await j.wait(200);
      await j.capture('At Document Beginning');
      
      // Test page navigation
      await j.input(' ', 'Page down');
      await j.wait(200);
      await j.capture('After Page Down');
      
      // Go back to menu
      await j.input('\x1B', 'Back to menu');
      await j.wait(300);
      await j.capture('Back at Documentation Menu');
      
      // Select different document
      await j.input('2', 'Select architecture doc');
      await j.wait(500);
      await j.capture('Architecture Document');
      
      // Exit docs
      await j.input('\x1B', 'Exit to main');
      await j.wait(300);
      await j.capture('Back to Main Interface');
    }
  },

  // NEW: PLUGIN/MODULE SELECTION TESTING
  {
    name: 'Plugin Module Selection',
    description: 'Test plugin/module selection and switching',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Open plugin selector
      await j.input('/plugins', 'Type plugins command');
      await j.capture('Typing plugins command');
      await j.input('\r', 'Execute plugins');
      await j.wait(500);
      await j.capture('Plugin Selector Open');
      
      // Navigate through plugins
      await j.input('\x1B[B', 'Arrow down');
      await j.wait(200);
      await j.capture('Second Plugin Highlighted');
      
      await j.input('\x1B[B', 'Arrow down again');
      await j.wait(200);
      await j.capture('Third Plugin Highlighted');
      
      await j.input('\x1B[A', 'Arrow up');
      await j.wait(200);
      await j.capture('Back to Second Plugin');
      
      // Select a plugin
      await j.input('\r', 'Select plugin');
      await j.wait(500);
      await j.capture('Plugin Selected Confirmation');
      
      // Try quick plugin switch with argument
      await j.input('/plugins general', 'Quick plugin switch');
      await j.capture('Typing plugin with argument');
      await j.input('\r', 'Execute');
      await j.wait(300);
      await j.capture('Plugin Switched Via Command');
    }
  },

  // NEW: DEPLOYMENT MODE SWITCHING
  {
    name: 'Deployment Mode Switching',
    description: 'Test switching between deployment modes',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface - Local Mode');
      
      // Open setup to change mode
      await j.input('/setup', 'Type setup command');
      await j.capture('Typing setup command');
      await j.input('\r', 'Execute setup');
      await j.wait(1000);
      await j.capture('Setup Wizard Reopened');
      
      // Continue through welcome
      await j.input('\r', 'Continue');
      await j.wait(500);
      await j.capture('Deployment Mode Selection');
      
      // Select single container mode
      await j.input('\x1B[B', 'Arrow to single container');
      await j.wait(200);
      await j.capture('Single Container Highlighted');
      
      await j.input('\r', 'Select single container');
      await j.wait(1000);
      await j.capture('Container Setup Progress');
      
      await j.wait(3000);
      await j.capture('Container Setup Complete');
      
      await j.input('\r', 'Continue to main');
      await j.wait(500);
      await j.capture('Main Interface - Container Mode');
      
      // Switch to enterprise mode
      await j.input('/setup', 'Type setup again');
      await j.input('\r', 'Execute');
      await j.wait(1000);
      await j.input('\r', 'Continue through welcome');
      await j.wait(500);
      
      await j.input('\x1B[B', 'Arrow down');
      await j.wait(200);
      await j.input('\x1B[B', 'Arrow to enterprise');
      await j.wait(200);
      await j.capture('Enterprise Mode Highlighted');
      
      await j.input('\r', 'Select enterprise');
      await j.wait(1000);
      await j.capture('Enterprise Setup Progress');
      
      await j.wait(3000);
      await j.capture('Enterprise Setup Complete');
      
      await j.input('\r', 'Continue');
      await j.wait(500);
      await j.capture('Main Interface - Enterprise Mode');
    }
  },

  // TEST-VALIDATION-SPECIFICATION.md FOCUSED TESTS
  
  {
    name: 'Tool Display Format Validation',
    description: 'Test tool execution display format according to specification requirements',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface Ready');
      
      // Set up for tool execution
      await j.input('target testphp.vulnweb.com', 'Set target');
      await j.capture('Target Set');
      await j.input('\r', 'Confirm target');
      await j.wait(500);
      
      await j.input('objective "Test tool display format validation"', 'Set objective');
      await j.capture('Objective Set');
      await j.input('\r', 'Confirm objective');
      await j.wait(500);
      
      // Start assessment to trigger tool execution
      await j.input('/run', 'Start assessment');
      await j.capture('Assessment Starting');
      await j.input('\r', 'Confirm start');
      await j.wait(1000);
      
      // Let it run to capture tool executions
      await j.capture('Safety Authorization Screen');
      await j.input(' ', 'Check authorization checkbox');
      await j.wait(300);
      await j.input('\r', 'Confirm authorization');
      await j.wait(2000);
      
      await j.capture('First Tool Execution Started');
      await j.wait(3000);
      await j.capture('Tool Execution With Parameters');
      await j.wait(3000);
      await j.capture('Tool Execution Animation');
      await j.wait(4000);
      await j.capture('Tool Execution Complete');
      
      // Let multiple tools execute to test various formats
      await j.wait(5000);
      await j.capture('Second Tool Execution');
      await j.wait(5000);
      await j.capture('Multiple Tool Results');
      
      // Cancel to stop execution
      await j.input('\x1B', 'ESC to cancel');
      await j.wait(1000);
      await j.capture('Assessment Cancelled');
    }
  },

  {
    name: 'Animation Behavior Testing',
    description: 'Test ThinkingIndicator animation to ensure no static display',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Quick setup for tool execution
      await j.input('target testphp.vulnweb.com', 'Set target');
      await j.input('\r', 'Confirm');
      await j.wait(300);
      
      // Start assessment quickly
      await j.input('/run', 'Quick run');
      await j.input('\r', 'Confirm');
      await j.wait(500);
      
      // Skip safety (for testing)
      await j.input(' ', 'Check safety');
      await j.input('\r', 'Confirm safety');
      await j.wait(1000);
      
      // Capture multiple frames of animation quickly
      await j.capture('Animation Frame 1');
      await j.wait(200);
      await j.capture('Animation Frame 2');
      await j.wait(200);
      await j.capture('Animation Frame 3');
      await j.wait(200);
      await j.capture('Animation Frame 4');
      await j.wait(200);
      await j.capture('Animation Frame 5');
      
      // Cancel
      await j.input('\x1B', 'Cancel with ESC');
      await j.wait(500);
      await j.capture('Cancelled State');
    }
  },

  {
    name: 'Modal System Validation',
    description: 'Test modal behavior and keyboard navigation',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Test configuration modal
      await j.input('/config', 'Open config');
      await j.capture('Typing config command');
      await j.input('\r', 'Execute config');
      await j.wait(1000);
      await j.capture('Configuration Modal Open');
      
      // Test keyboard navigation
      await j.input('\t', 'Tab navigation');
      await j.wait(200);
      await j.capture('Tab Navigation 1');
      
      await j.input('\t', 'Tab again');
      await j.wait(200);
      await j.capture('Tab Navigation 2');
      
      await j.input('\x1B[B', 'Arrow down');
      await j.wait(200);
      await j.capture('Arrow Navigation');
      
      // Test modal sections
      await j.input('\r', 'Expand section');
      await j.wait(300);
      await j.capture('Section Expanded');
      
      // Test ESC to close
      await j.input('\x1B', 'ESC to close');
      await j.wait(500);
      await j.capture('Modal Closed');
      
      // Test memory search modal
      await j.input('/memory', 'Open memory search');
      await j.input('\r', 'Execute');
      await j.wait(800);
      await j.capture('Memory Search Modal');
      
      await j.input('test query', 'Type search query');
      await j.wait(300);
      await j.capture('Search Query Typed');
      
      await j.input('\x1B', 'ESC to close');
      await j.wait(300);
      await j.capture('Memory Modal Closed');
    }
  },

  {
    name: 'Safety Authorization Enforcement',
    description: 'Test that safety authorization cannot be bypassed',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Set up assessment
      await j.input('target testphp.vulnweb.com', 'Set target');
      await j.input('\r', 'Confirm target');
      await j.wait(300);
      
      // Try to run without objective
      await j.input('/run', 'Try to run');
      await j.input('\r', 'Execute run');
      await j.wait(1000);
      await j.capture('Safety Modal Appears');
      
      // Test trying to proceed without checkbox
      await j.input('\r', 'Try to proceed without checkbox');
      await j.wait(300);
      await j.capture('Cannot Proceed Without Checkbox');
      
      // Test ESC cancellation
      await j.input('\x1B', 'ESC to cancel');
      await j.wait(500);
      await j.capture('Safety Cancelled');
      
      // Try again with proper flow
      await j.input('/run', 'Run again');
      await j.input('\r', 'Execute');
      await j.wait(500);
      await j.capture('Safety Modal Again');
      
      // Proper authorization flow
      await j.input(' ', 'Check authorization checkbox');
      await j.wait(200);
      await j.capture('Checkbox Checked');
      
      await j.input('\r', 'Confirm authorization');
      await j.wait(1000);
      await j.capture('Authorization Accepted');
      
      // Stop before full execution
      await j.wait(2000);
      await j.input('\x1B', 'ESC to stop');
      await j.wait(500);
      await j.capture('Assessment Stopped');
    }
  },

  {
    name: 'Step Header Format Validation',
    description: 'Test step header display format during assessment',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Quick assessment setup
      await j.input('target testphp.vulnweb.com', 'Set target');
      await j.input('\r', 'Confirm');
      await j.wait(200);
      
      await j.input('objective "Test step headers"', 'Set objective');
      await j.input('\r', 'Confirm');
      await j.wait(200);
      
      // Start assessment
      await j.input('/run', 'Start');
      await j.input('\r', 'Confirm');
      await j.wait(500);
      
      // Safety authorization
      await j.input(' ', 'Check safety');
      await j.input('\r', 'Confirm');
      await j.wait(1500);
      
      // Capture step headers
      await j.capture('Step 1 Header');
      await j.wait(4000);
      await j.capture('Step 2 Header');
      await j.wait(4000);
      await j.capture('Step 3 Header');
      await j.wait(4000);
      await j.capture('Step 4 Header');
      
      // Cancel before completion
      await j.input('\x1B', 'Cancel');
      await j.wait(500);
      await j.capture('Assessment Cancelled');
    }
  },

  {
    name: 'Footer Information Display',
    description: 'Test footer metrics and information display format',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface With Footer');
      
      // Test with some activity to generate metrics
      await j.input('/help', 'Generate some activity');
      await j.input('\r', 'Execute');
      await j.wait(500);
      await j.capture('Footer After Command');
      
      // Close help and test config to see more footer updates
      await j.input('\x1B', 'Close help');
      await j.wait(300);
      
      await j.input('/config', 'Open config');
      await j.input('\r', 'Execute');
      await j.wait(800);
      await j.capture('Footer With Config Modal');
      
      await j.input('\x1B', 'Close config');
      await j.wait(300);
      await j.capture('Footer After Config Close');
      
      // Test with target setting to show more footer info
      await j.input('target testphp.vulnweb.com', 'Set target');
      await j.input('\r', 'Confirm');
      await j.wait(300);
      await j.capture('Footer With Target Set');
      
      // Test clear command impact on footer
      await j.input('/clear', 'Clear screen');
      await j.input('\r', 'Execute');
      await j.wait(300);
      await j.capture('Footer After Clear');
    }
  },

  // NEW: HEALTH CHECK TESTING
  {
    name: 'Health Check Command',
    description: 'Test health check functionality and display',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Execute health check
      await j.input('/health', 'Type health command');
      await j.capture('Typing health command');
      await j.input('\r', 'Execute health');
      await j.wait(1000);
      await j.capture('Health Check Results');
      
      // Test with Docker not running scenario
      await j.wait(500);
      await j.capture('Health Status Details');
      
      // Clear and test again
      await j.input('/clear', 'Clear screen');
      await j.input('\r');
      await j.wait(300);
      await j.capture('After Clear');
      
      // Quick health check
      await j.input('/health\r', 'Quick health check');
      await j.wait(1000);
      await j.capture('Second Health Check');
    }
  },

  // NEW: OPERATION CANCELLATION TESTING
  {
    name: 'Operation Cancellation',
    description: 'Test ESC key cancellation at various stages',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main Interface');
      
      // Start typing command and cancel
      await j.input('target https://test', 'Start typing target');
      await j.capture('Partial Target Input');
      
      await j.input('\x1B', 'ESC to cancel input');
      await j.wait(300);
      await j.capture('Input Cancelled');
      
      // Set target and start assessment
      await j.input('target https://testphp.vulnweb.com\r', 'Set target');
      await j.wait(300);
      await j.capture('Target Set');
      
      await j.input('execute\r', 'Start execution');
      await j.wait(500);
      await j.capture('Authorization Screen');
      
      // Cancel at authorization
      await j.input('\x1B', 'ESC to cancel auth');
      await j.wait(300);
      await j.capture('Authorization Cancelled');
      
      // Try again and proceed
      await j.input('execute\r', 'Execute again');
      await j.wait(500);
      await j.input('y', 'First auth');
      await j.wait(300);
      await j.capture('Second Authorization');
      
      // Cancel at second auth
      await j.input('\x1B', 'ESC to cancel');
      await j.wait(300);
      await j.capture('Second Auth Cancelled');
      
      // Full execution and cancel during operation
      await j.input('execute\r', 'Execute once more');
      await j.wait(500);
      await j.input('y', 'First auth');
      await j.wait(300);
      await j.input('y', 'Second auth');
      await j.wait(1000);
      await j.capture('Assessment Running');
      
      // Cancel running operation
      await j.input('\x1B', 'ESC to stop operation');
      await j.wait(1000);
      await j.capture('Operation Stopped');
      
      // Test Ctrl+C during operation
      await j.input('execute\r', 'Start another');
      await j.wait(500);
      await j.input('y', 'Auth 1');
      await j.wait(300);
      await j.input('y', 'Auth 2');
      await j.wait(1000);
      await j.capture('Assessment Running Again');
      
      await j.input('\x03', 'Ctrl+C to pause');
      await j.wait(500);
      await j.capture('Operation Paused');
      
      await j.input('resume\r', 'Resume operation');
      await j.wait(500);
      await j.capture('Operation Resumed');
      
      await j.input('\x1B', 'Final cancel');
      await j.wait(500);
      await j.capture('Final State');
    }
  }
];

// Run all journeys
async function runAllJourneys() {
  console.log('🎬 Comprehensive Terminal Capture System');
  console.log('=====================================');
  console.log(`Output directory: ${capturesDir}`);
  console.log('');

  const results = [];
  
  for (const journeyDef of journeys) {
    const journey = new Journey(journeyDef.name, journeyDef.description, journeyDef.config);
    
    try {
      await journey.start();
      await journeyDef.steps(journey);
      await journey.finish();
      
      results.push({
        name: journeyDef.name,
        success: true,
        captures: journey.captures.length
      });
    } catch (error) {
      console.error(`❌ Journey failed: ${error.message}`);
      results.push({
        name: journeyDef.name,
        success: false,
        error: error.message
      });
    }
    
    // Brief pause between journeys
    await new Promise(r => setTimeout(r, 1000));
  }

  // Create master report
  createMasterReport(results);
}

function createMasterReport(results) {
  const reportPath = join(capturesDir, 'MASTER-VALIDATION-REPORT.md');
  
  const report = [
    '# Cyber-AutoAgent UI Validation Report',
    '',
    `**Generated:** ${new Date().toISOString()}`,
    `**Total Journeys:** ${results.length}`,
    `**Successful:** ${results.filter(r => r.success).length}`,
    `**Failed:** ${results.filter(r => !r.success).length}`,
    '',
    '## Journey Results',
    '',
    ...results.map(r => 
      r.success 
        ? `✅ **${r.name}** - ${r.captures} captures`
        : `❌ **${r.name}** - Failed: ${r.error}`
    ),
    '',
    '## Key Validation Points',
    '',
    '### 1. Branding Consistency',
    '- Check each journey for consistent CYBER ASCII art',
    '- Verify "Full Spectrum Cyber Operations" tagline',
    '- Ensure version number is displayed correctly',
    '',
    '### 2. UI Quality',
    '- No flickering between screen transitions',
    '- Box borders align properly',
    '- Colors remain consistent',
    '- Text alignment is correct',
    '',
    '### 3. Content Issues',
    '- No duplicate log entries',
    '- No error logs visible to user',
    '- No overlapping UI elements',
    '- No raw escape sequences',
    '',
    '### 4. Functional Testing',
    '- All commands work as expected',
    '- Navigation flows are smooth',
    '- Error states display properly',
    '- Input handling is responsive',
    '',
    '## Review Instructions',
    '',
    '1. Open each journey folder',
    '2. Review captures in sequence (000, 001, 002...)',
    '3. Check for issues listed in journey summaries',
    '4. Pay special attention to setup wizard flows',
    '5. Verify consistent branding across all screens',
    '',
    '## Known Issues to Check',
    '',
    '- Setup wizard back navigation',
    '- Operation plugin loading errors',
    '- Log entries appearing in UI',
    '- Screen clearing artifacts',
    '- Progress bar rendering'
  ].join('\n');
  
  fs.writeFileSync(reportPath, report);
  
  console.log('\n✅ All captures complete!');
  console.log(`📊 Master report: ${reportPath}`);
  console.log(`📁 Captures directory: ${capturesDir}`);
  console.log('\n🔍 Ready for Claude validation');
}

// Execute
runAllJourneys().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});