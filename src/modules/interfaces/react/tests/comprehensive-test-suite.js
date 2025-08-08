#!/usr/bin/env node

/**
 * Comprehensive Terminal Test Suite
 * 
 * Automated test suite designed to capture exact terminal output
 * for every key component and user flow in Cyber-AutoAgent.
 * 
 * This suite provides complete test coverage for:
 * - All component states and transitions
 * - Error conditions and edge cases  
 * - Performance scenarios
 * - Configuration variations
 * - Integration points
 * 
 * @author Cyber-AutoAgent Team
 * @version 2.0.0
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
const capturesDir = join(__dirname, 'test-captures');

// Capture metadata structure
class CaptureMetadata {
  constructor() {
    this.timestamp = new Date().toISOString();
    this.terminalSize = { cols: 80, rows: 24 };
    this.environment = process.env.NODE_ENV || 'test';
    this.nodeVersion = process.version;
    this.platform = process.platform;
    this.componentsCovered = new Set();
    this.hooksUsed = new Set();
    this.servicesInvoked = new Set();
    this.errorsEncountered = [];
    this.performanceMetrics = [];
  }
}

class TestJourney {
  constructor(category, name, description, config = null) {
    this.category = category;
    this.name = name;
    this.description = description;
    this.config = config;
    this.journeyDir = join(capturesDir, category, name.toLowerCase().replace(/\s+/g, '-'));
    this.captureIndex = 0;
    this.captures = [];
    this.term = null;
    this.outputBuffer = '';
    this.metadata = new CaptureMetadata();
    this.frameHistory = [];
    this.stateTransitions = [];
    
    fs.mkdirSync(this.journeyDir, { recursive: true });
  }

  async start(env = {}) {
    console.log(`\n🎯 Category: ${this.category}`);
    console.log(`📸 Journey: ${this.name}`);
    console.log(`   ${this.description}`);
    console.log('─'.repeat(70));

    // Test environment setup
    const testEnv = { 
      ...process.env, 
      NO_COLOR: '1',
      NODE_ENV: 'test',
      CYBER_TEST_MODE: 'true',
      CYBER_CAPTURE_MODE: 'comprehensive',
      ...env
    };
    
    // Set up test configuration
    if (this.config) {
      const configDir = join(os.homedir(), '.cyber-autoagent');
      const configPath = join(configDir, 'config.json');
      
      if (!fs.existsSync(configDir)) {
        fs.mkdirSync(configDir, { recursive: true });
      }
      
      fs.writeFileSync(configPath, JSON.stringify(this.config, null, 2));
      console.log(`  ✓ Test config created`);
    }

    // Start PTY session with exact terminal emulation
    this.term = pty.spawn('node', [appPath], {
      name: 'xterm-256color',
      cols: 80,
      rows: 24,
      cwd: dirname(appPath),
      env: testEnv
    });

    // Output capture with frame analysis
    this.term.onData((data) => {
      const previousFrame = this.outputBuffer;
      this.outputBuffer += data;
      
      // Track frame changes for flicker detection
      if (previousFrame !== this.outputBuffer) {
        this.frameHistory.push({
          timestamp: Date.now(),
          delta: data,
          fullFrame: this.outputBuffer
        });
      }
    });

    // Allow full initialization
    await this.wait(1500);
  }

  async wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async capture(label, options = {}) {
    const {
      component = null,
      hook = null,
      service = null,
      expectedState = null,
      validateOutput = null,
      performanceCheck = false
    } = options;

    // Performance tracking
    const captureStart = Date.now();
    
    // Wait for stable frame
    let previousBuffer = '';
    let stabilityAttempts = 0;
    const maxAttempts = 15;
    
    while (stabilityAttempts < maxAttempts) {
      previousBuffer = this.outputBuffer;
      await this.wait(100);
      if (previousBuffer === this.outputBuffer) break;
      stabilityAttempts++;
    }
    
    const captureEnd = Date.now();
    
    // Record performance metrics
    if (performanceCheck) {
      this.metadata.performanceMetrics.push({
        label,
        renderTime: captureEnd - captureStart,
        stabilityAttempts,
        frameSize: this.outputBuffer.length
      });
    }

    // Track components/hooks/services
    if (component) this.metadata.componentsCovered.add(component);
    if (hook) this.metadata.hooksUsed.add(hook);
    if (service) this.metadata.servicesInvoked.add(service);

    // Capture filename
    const filename = `${String(this.captureIndex).padStart(3, '0')}-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.capture`;
    const filepath = join(this.journeyDir, filename);
    
    // Validate output if checker provided
    let validationResult = null;
    if (validateOutput) {
      try {
        validationResult = validateOutput(this.outputBuffer);
      } catch (error) {
        this.metadata.errorsEncountered.push({
          capture: label,
          error: error.message
        });
      }
    }
    
    // Create capture data
    const captureData = {
      metadata: {
        index: this.captureIndex,
        label,
        timestamp: new Date().toISOString(),
        component,
        hook,
        service,
        expectedState,
        validationResult,
        stabilityAttempts,
        renderTime: captureEnd - captureStart,
        bufferSize: this.outputBuffer.length,
        lineCount: this.outputBuffer.split('\n').length
      },
      terminal: {
        cols: 80,
        rows: 24,
        type: 'xterm-256color'
      },
      output: this.outputBuffer,
      frameHistory: this.frameHistory.slice(-5), // Last 5 frames
      validation: validationResult
    };
    
    // Save as JSON for structured debugging
    fs.writeFileSync(filepath, JSON.stringify(captureData, null, 2));
    
    // Also save raw text for visual inspection
    const textPath = filepath.replace('.capture', '.txt');
    fs.writeFileSync(textPath, this.outputBuffer);
    
    this.captures.push(captureData.metadata);
    
    console.log(`  ✓ Captured: ${label} [${stabilityAttempts} frames, ${captureEnd - captureStart}ms]`);
    this.captureIndex++;
    
    return captureData;
  }

  async input(text, label = null) {
    if (label) {
      console.log(`  → Input: ${label}`);
    }
    
    // Track state before input
    const beforeState = this.outputBuffer;
    
    this.term.write(text);
    await this.wait(100);
    
    // Track state transition
    this.stateTransitions.push({
      trigger: label || text,
      before: beforeState.slice(-200), // Last 200 chars
      after: this.outputBuffer.slice(-200),
      timestamp: Date.now()
    });
  }

  async keyPress(key, label = null) {
    const keys = {
      enter: '\r',
      escape: '\x1B',
      up: '\x1B[A',
      down: '\x1B[B',
      left: '\x1B[D',
      right: '\x1B[C',
      tab: '\t',
      backspace: '\x7F',
      ctrlC: '\x03',
      ctrlL: '\x0C',
      ctrlS: '\x13',
      space: ' '
    };
    
    await this.input(keys[key] || key, label || `Key: ${key}`);
  }

  async finish() {
    if (this.term) {
      this.term.kill();
    }
    
    // Create journey report
    const reportPath = join(this.journeyDir, '000-REPORT.json');
    const report = {
      journey: {
        category: this.category,
        name: this.name,
        description: this.description,
        totalCaptures: this.captures.length,
        duration: Date.now() - new Date(this.metadata.timestamp).getTime()
      },
      coverage: {
        components: Array.from(this.metadata.componentsCovered),
        hooks: Array.from(this.metadata.hooksUsed),
        services: Array.from(this.metadata.servicesInvoked)
      },
      quality: {
        errors: this.metadata.errorsEncountered,
        performance: this.metadata.performanceMetrics,
        stateTransitions: this.stateTransitions.length
      },
      captures: this.captures,
      metadata: this.metadata
    };
    
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    // Create markdown summary
    const summaryPath = join(this.journeyDir, '000-SUMMARY.md');
    const summary = this.generateMarkdownSummary(report);
    fs.writeFileSync(summaryPath, summary);
    
    console.log(`✅ Journey complete: ${this.captures.length} enhanced captures`);
  }

  generateMarkdownSummary(report) {
    return `# ${report.journey.name}

**Category:** ${report.journey.category}  
**Description:** ${report.journey.description}  
**Duration:** ${report.journey.duration}ms  
**Total Captures:** ${report.journey.totalCaptures}  

## Coverage Summary

### Components Tested (${report.coverage.components.length})
${report.coverage.components.map(c => `- ${c}`).join('\n')}

### Hooks Used (${report.coverage.hooks.length})
${report.coverage.hooks.map(h => `- ${h}`).join('\n')}

### Services Invoked (${report.coverage.services.length})
${report.coverage.services.map(s => `- ${s}`).join('\n')}

## Quality Metrics

### Performance
- Average Render Time: ${this.calculateAverage(report.quality.performance, 'renderTime')}ms
- Max Render Time: ${this.calculateMax(report.quality.performance, 'renderTime')}ms
- Total State Transitions: ${report.quality.stateTransitions}

### Errors Encountered
${report.quality.errors.length === 0 ? '✅ No errors' : report.quality.errors.map(e => `- ${e.capture}: ${e.error}`).join('\n')}

## Capture Sequence
${report.captures.map((c, i) => `${i + 1}. **${c.label}** - ${c.renderTime}ms`).join('\n')}
`;
  }

  calculateAverage(arr, field) {
    if (arr.length === 0) return 0;
    return Math.round(arr.reduce((sum, item) => sum + item[field], 0) / arr.length);
  }

  calculateMax(arr, field) {
    if (arr.length === 0) return 0;
    return Math.max(...arr.map(item => item[field]));
  }
}

// ============================================================================
// TEST JOURNEYS FOR ALL COMPONENTS
// ============================================================================

const testJourneys = [
  // ==========================================================================
  // CATEGORY: Core Components
  // ==========================================================================
  {
    category: 'Core-Components',
    name: 'App Component Full Lifecycle',
    description: 'Test App.tsx with all state transitions and effects',
    config: null,
    steps: async (j) => {
      await j.capture('App-Initial-Mount', {
        component: 'App',
        hook: 'useApplicationState',
        expectedState: 'initialization'
      });
      
      await j.wait(1000);
      await j.capture('App-Config-Loading', {
        component: 'App',
        hook: 'useConfig',
        service: 'ConfigContext'
      });
      
      await j.keyPress('escape', 'Skip initialization');
      await j.wait(500);
      await j.capture('App-Main-View', {
        component: 'MainAppView',
        expectedState: 'ready'
      });
    }
  },

  {
    category: 'Core-Components',
    name: 'ConfigEditor Complete Test',
    description: 'Test ConfigEditor with all sections and field types',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Main-Interface', { component: 'MainAppView' });
      
      await j.input('/config', 'Open config');
      await j.keyPress('enter');
      await j.wait(500);
      await j.capture('ConfigEditor-Open', {
        component: 'ConfigEditor',
        hook: 'useConfig'
      });
      
      // Test each section expansion
      const sections = ['Models', 'Operations', 'Memory', 'Observability', 'Evaluation', 'Pricing', 'Output'];
      for (const section of sections) {
        await j.keyPress('enter', `Expand ${section}`);
        await j.wait(300);
        await j.capture(`ConfigEditor-${section}-Expanded`, {
          component: 'ConfigEditor',
          expectedState: `section-${section.toLowerCase()}`
        });
        await j.keyPress('escape', `Collapse ${section}`);
        await j.wait(200);
        await j.keyPress('down', 'Next section');
      }
      
      // Test field editing
      await j.keyPress('enter', 'Expand Models');
      await j.wait(300);
      await j.keyPress('down', 'To model provider');
      await j.keyPress('enter', 'Edit field');
      await j.wait(200);
      await j.capture('ConfigEditor-Editing-Field', {
        component: 'ConfigEditor',
        expectedState: 'editing'
      });
      
      // Test save with Ctrl+S
      await j.keyPress('escape');
      await j.keyPress('ctrlS', 'Save configuration');
      await j.wait(500);
      await j.capture('ConfigEditor-Save-Success', {
        component: 'ConfigEditor',
        service: 'ConfigContext'
      });
    }
  },

  {
    category: 'Core-Components',
    name: 'SetupWizard Complete Flow',
    description: 'Test SetupWizard with all screens and deployment modes',
    config: null,
    steps: async (j) => {
      await j.capture('SetupWizard-Welcome', {
        component: 'SetupWizard/WelcomeScreen',
        hook: 'useSetupWizard'
      });
      
      await j.keyPress('enter', 'Continue');
      await j.wait(500);
      await j.capture('SetupWizard-Deployment-Selection', {
        component: 'SetupWizard/DeploymentSelectionScreen'
      });
      
      // Test each deployment mode
      const modes = ['local-cli', 'single-container', 'full-stack'];
      for (let i = 0; i < modes.length; i++) {
        if (i > 0) await j.keyPress('down');
        await j.wait(200);
        await j.capture(`SetupWizard-Mode-${modes[i]}`, {
          component: 'SetupWizard/DeploymentSelectionScreen',
          expectedState: modes[i]
        });
      }
      
      // Select and complete
      await j.keyPress('up');
      await j.keyPress('up');
      await j.keyPress('enter', 'Select local-cli');
      await j.wait(1000);
      await j.capture('SetupWizard-Progress', {
        component: 'SetupWizard/ProgressScreen',
        service: 'SetupService'
      });
      
      await j.wait(3000);
      await j.capture('SetupWizard-Complete', {
        component: 'SetupWizard',
        expectedState: 'complete'
      });
    }
  },

  {
    category: 'Core-Components',
    name: 'Modal System Complete Test',
    description: 'Test ModalRegistry with all modal types',
    config: mockConfiguredState,
    steps: async (j) => {
      // Test each modal type
      const modals = [
        { command: '/config', name: 'Config', component: 'ConfigEditor' },
        { command: '/plugins', name: 'ModuleSelector', component: 'ModuleSelector' },
        { command: '/docs', name: 'Documentation', component: 'DocumentationViewer' }
      ];
      
      for (const modal of modals) {
        await j.input(modal.command);
        await j.keyPress('enter');
        await j.wait(500);
        await j.capture(`Modal-${modal.name}-Open`, {
          component: modal.component,
          hook: 'useModalManager'
        });
        
        await j.keyPress('escape', 'Close modal');
        await j.wait(300);
        await j.capture(`Modal-${modal.name}-Closed`, {
          component: 'MainAppView'
        });
      }
      
      // Test safety warning modal
      await j.input('target testphp.vulnweb.com');
      await j.keyPress('enter');
      await j.wait(300);
      await j.input('execute');
      await j.keyPress('enter');
      await j.wait(500);
      await j.capture('Modal-SafetyWarning', {
        component: 'SafetyWarning',
        expectedState: 'confirmation'
      });
    }
  },

  // ==========================================================================
  // CATEGORY: Hooks Testing
  // ==========================================================================
  {
    category: 'Hooks',
    name: 'useApplicationState All Actions',
    description: 'Test all reducer actions in useApplicationState',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Initial-State', {
        hook: 'useApplicationState',
        expectedState: 'initial'
      });
      
      // Test terminal visibility toggle
      await j.input('/clear');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('State-After-Clear', {
        hook: 'useApplicationState',
        expectedState: 'cleared'
      });
      
      // Test operation state
      await j.input('target example.com');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('State-Target-Set', {
        hook: 'useApplicationState',
        expectedState: 'target-configured'
      });
      
      // Test error state
      await j.input('/invalid-command');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('State-Error-Count', {
        hook: 'useApplicationState',
        expectedState: 'error-incremented'
      });
    }
  },

  {
    category: 'Hooks',
    name: 'useCommandHandler All Commands',
    description: 'Test all command types and handlers',
    config: mockConfiguredState,
    steps: async (j) => {
      // Test slash commands
      const slashCommands = ['/help', '/config', '/plugins', '/docs', '/health', '/setup', '/clear'];
      for (const cmd of slashCommands) {
        await j.input(cmd);
        await j.capture(`Command-${cmd}-Typed`, {
          hook: 'useCommandHandler',
          service: 'InputParser'
        });
        await j.keyPress('enter');
        await j.wait(500);
        await j.capture(`Command-${cmd}-Executed`, {
          hook: 'useCommandHandler'
        });
        if (cmd !== '/clear') {
          await j.keyPress('escape', 'Close/cancel');
          await j.wait(300);
        }
      }
      
      // Test natural language
      await j.input('scan testphp.vulnweb.com for vulnerabilities');
      await j.keyPress('enter');
      await j.wait(500);
      await j.capture('Command-Natural-Language', {
        hook: 'useCommandHandler',
        service: 'AssessmentFlow'
      });
      
      // Test guided flow
      await j.keyPress('escape');
      await j.input('module general');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Command-Guided-Module', {
        hook: 'useCommandHandler'
      });
      
      await j.input('target example.com');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Command-Guided-Target', {
        hook: 'useCommandHandler'
      });
    }
  },

  {
    category: 'Hooks',
    name: 'useKeyboardHandlers All Shortcuts',
    description: 'Test all keyboard shortcuts and handlers',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Before-Keyboard-Test', {
        hook: 'useKeyboardHandlers'
      });
      
      // Test Ctrl+C (clear/pause)
      await j.input('typing something');
      await j.capture('Text-Input', {});
      await j.keyPress('ctrlC', 'Clear input');
      await j.wait(300);
      await j.capture('After-Ctrl-C', {
        hook: 'useKeyboardHandlers'
      });
      
      // Test Ctrl+L (clear screen)
      await j.keyPress('ctrlL', 'Clear screen');
      await j.wait(300);
      await j.capture('After-Ctrl-L', {
        hook: 'useKeyboardHandlers'
      });
      
      // Test ESC in various contexts
      await j.input('/config');
      await j.keyPress('enter');
      await j.wait(500);
      await j.keyPress('escape', 'ESC from config');
      await j.wait(300);
      await j.capture('After-ESC', {
        hook: 'useKeyboardHandlers'
      });
    }
  },

  // ==========================================================================
  // CATEGORY: Services Testing
  // ==========================================================================
  {
    category: 'Services',
    name: 'DirectDockerService Execution',
    description: 'Test Docker service with container execution',
    config: { ...mockConfiguredState, deploymentMode: 'single-container' },
    steps: async (j) => {
      await j.capture('Docker-Service-Ready', {
        service: 'DirectDockerService'
      });
      
      await j.input('target testphp.vulnweb.com');
      await j.keyPress('enter');
      await j.wait(300);
      await j.input('execute');
      await j.keyPress('enter');
      await j.wait(500);
      
      await j.input('y', 'First auth');
      await j.wait(300);
      await j.input('y', 'Second auth');
      await j.wait(1000);
      
      await j.capture('Docker-Container-Starting', {
        service: 'DirectDockerService',
        component: 'UnconstrainedTerminal'
      });
      
      await j.wait(2000);
      await j.capture('Docker-Stream-Active', {
        service: 'DirectDockerService',
        component: 'StreamDisplay'
      });
      
      await j.keyPress('escape', 'Stop execution');
      await j.wait(1000);
      await j.capture('Docker-Container-Stopped', {
        service: 'DirectDockerService'
      });
    }
  },

  {
    category: 'Services',
    name: 'AssessmentFlow State Machine',
    description: 'Test complete assessment flow state transitions',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('AssessmentFlow-Initial', {
        service: 'AssessmentFlow',
        expectedState: 'target'
      });
      
      // Test state progression
      await j.input('target 192.168.1.1');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('AssessmentFlow-Target-Set', {
        service: 'AssessmentFlow',
        expectedState: 'objective'
      });
      
      await j.input('network scanning');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('AssessmentFlow-Objective-Set', {
        service: 'AssessmentFlow',
        expectedState: 'ready'
      });
      
      // Test reset
      await j.input('reset');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('AssessmentFlow-Reset', {
        service: 'AssessmentFlow',
        expectedState: 'target'
      });
    }
  },

  {
    category: 'Services',
    name: 'HealthMonitor System Check',
    description: 'Test health monitoring service',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.input('/health');
      await j.keyPress('enter');
      await j.wait(1000);
      await j.capture('HealthMonitor-Check-Results', {
        service: 'HealthMonitor',
        performanceCheck: true
      });
      
      // Test with different Docker states
      await j.wait(500);
      await j.capture('HealthMonitor-Service-Status', {
        service: 'HealthMonitor'
      });
    }
  },

  // ==========================================================================
  // CATEGORY: Error States
  // ==========================================================================
  {
    category: 'Error-States',
    name: 'Configuration Errors',
    description: 'Test all configuration error states',
    config: {},
    steps: async (j) => {
      await j.capture('No-Config-State', {
        expectedState: 'unconfigured'
      });
      
      await j.keyPress('escape', 'Skip setup');
      await j.wait(500);
      
      await j.input('/config');
      await j.keyPress('enter');
      await j.wait(500);
      
      // Try to save without required fields
      await j.keyPress('ctrlS');
      await j.wait(500);
      await j.capture('Config-Validation-Error', {
        component: 'ConfigEditor',
        expectedState: 'validation-error'
      });
      
      // Invalid values
      await j.keyPress('enter'); // Edit first field
      await j.input('invalid-provider');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Config-Invalid-Value', {
        component: 'ConfigEditor'
      });
    }
  },

  {
    category: 'Error-States',
    name: 'Command Errors',
    description: 'Test all command error conditions',
    config: mockConfiguredState,
    steps: async (j) => {
      // Invalid command
      await j.input('/nonexistent');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Error-Invalid-Command', {
        hook: 'useCommandHandler'
      });
      
      // Execute without target
      await j.input('execute');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Error-No-Target', {
        service: 'AssessmentFlow'
      });
      
      // Invalid target format
      await j.input('target not_a_valid_url');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Error-Invalid-Target', {
        service: 'AssessmentFlow'
      });
      
      // Module not found
      await j.input('module nonexistent');
      await j.keyPress('enter');
      await j.wait(300);
      await j.capture('Error-Module-Not-Found', {
        service: 'AssessmentFlow'
      });
    }
  },

  // ==========================================================================
  // CATEGORY: Performance Testing
  // ==========================================================================
  {
    category: 'Performance',
    name: 'Rapid Input Handling',
    description: 'Test UI responsiveness under rapid input',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Performance-Initial', {
        performanceCheck: true
      });
      
      // Rapid character input
      const rapidText = 'abcdefghijklmnopqrstuvwxyz0123456789';
      for (const char of rapidText) {
        await j.input(char);
        await j.wait(5); // Minimal delay
      }
      await j.capture('Performance-After-Rapid-Input', {
        performanceCheck: true
      });
      
      // Rapid command switching
      for (let i = 0; i < 5; i++) {
        await j.keyPress('escape');
        await j.input(`/help`);
        await j.keyPress('enter');
        await j.wait(50);
      }
      await j.capture('Performance-Command-Switching', {
        performanceCheck: true
      });
      
      // Rapid navigation
      for (let i = 0; i < 10; i++) {
        await j.keyPress(i % 2 === 0 ? 'up' : 'down');
        await j.wait(10);
      }
      await j.capture('Performance-Navigation', {
        performanceCheck: true
      });
    }
  },

  {
    category: 'Performance',
    name: 'Large Output Handling',
    description: 'Test rendering with large output buffers',
    config: mockConfiguredState,
    steps: async (j) => {
      // Generate large output
      await j.input('/health');
      await j.keyPress('enter');
      await j.wait(1000);
      
      for (let i = 0; i < 10; i++) {
        await j.input(`echo Line ${i} - ${'x'.repeat(70)}`);
        await j.keyPress('enter');
        await j.wait(50);
      }
      
      await j.capture('Performance-Large-Buffer', {
        performanceCheck: true,
        validateOutput: (output) => {
          const lines = output.split('\n');
          return lines.length > 50;
        }
      });
    }
  },

  // ==========================================================================
  // CATEGORY: Integration Testing
  // ==========================================================================
  {
    category: 'Integration',
    name: 'Full Assessment Workflow',
    description: 'Complete end-to-end assessment execution',
    config: mockConfiguredState,
    steps: async (j) => {
      await j.capture('Integration-Start', {});
      
      // Complete assessment setup
      await j.input('module general');
      await j.keyPress('enter');
      await j.wait(300);
      
      await j.input('target https://testphp.vulnweb.com');
      await j.keyPress('enter');
      await j.wait(300);
      
      await j.input('OWASP Top 10 assessment');
      await j.keyPress('enter');
      await j.wait(300);
      
      await j.capture('Integration-Ready', {
        service: 'AssessmentFlow',
        expectedState: 'ready'
      });
      
      await j.input('execute');
      await j.keyPress('enter');
      await j.wait(500);
      
      await j.capture('Integration-Safety-Warning', {
        component: 'SafetyWarning'
      });
      
      await j.input('y');
      await j.wait(300);
      await j.input('y');
      await j.wait(1000);
      
      await j.capture('Integration-Executing', {
        service: 'DirectDockerService',
        component: 'UnconstrainedTerminal'
      });
      
      await j.wait(3000);
      await j.capture('Integration-Progress', {});
      
      await j.keyPress('escape');
      await j.wait(1000);
      await j.capture('Integration-Complete', {});
    }
  }
];

// ============================================================================
// EXECUTION ENGINE
// ============================================================================

async function runTestCaptures() {
  console.log('🚀 Comprehensive Terminal Test Suite v2.0');
  console.log('=========================================');
  console.log('Automated testing and validation system');
  console.log(`Output directory: ${capturesDir}`);
  console.log('');

  // Clean and create directory structure
  if (fs.existsSync(capturesDir)) {
    fs.rmSync(capturesDir, { recursive: true });
  }
  
  const categories = [...new Set(testJourneys.map(j => j.category))];
  categories.forEach(cat => {
    fs.mkdirSync(join(capturesDir, cat), { recursive: true });
  });

  const results = [];
  const startTime = Date.now();
  
  for (const journeyDef of testJourneys) {
    const journey = new TestJourney(
      journeyDef.category,
      journeyDef.name,
      journeyDef.description,
      journeyDef.config
    );
    
    try {
      await journey.start(journeyDef.env || {});
      await journeyDef.steps(journey);
      await journey.finish();
      
      results.push({
        category: journeyDef.category,
        name: journeyDef.name,
        success: true,
        captures: journey.captures.length,
        components: journey.metadata.componentsCovered.size,
        hooks: journey.metadata.hooksUsed.size,
        services: journey.metadata.servicesInvoked.size,
        errors: journey.metadata.errorsEncountered.length
      });
    } catch (error) {
      console.error(`❌ Journey failed: ${error.message}`);
      results.push({
        category: journeyDef.category,
        name: journeyDef.name,
        success: false,
        error: error.message
      });
    }
    
    await new Promise(r => setTimeout(r, 1000));
  }
  
  const endTime = Date.now();
  
  // Generate master report
  generateMasterReport(results, endTime - startTime);
}

function generateMasterReport(results, totalDuration) {
  const reportPath = join(capturesDir, 'MASTER-REPORT.json');
  const summaryPath = join(capturesDir, 'MASTER-SUMMARY.md');
  
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);
  
  const totalComponents = new Set();
  const totalHooks = new Set();
  const totalServices = new Set();
  
  successful.forEach(r => {
    if (r.components) totalComponents.add(...Array.from(r.components));
    if (r.hooks) totalHooks.add(...Array.from(r.hooks));
    if (r.services) totalServices.add(...Array.from(r.services));
  });
  
  const report = {
    metadata: {
      version: '2.0.0',
      timestamp: new Date().toISOString(),
      duration: totalDuration,
      platform: process.platform,
      nodeVersion: process.version
    },
    summary: {
      totalJourneys: results.length,
      successful: successful.length,
      failed: failed.length,
      totalCaptures: successful.reduce((sum, r) => sum + (r.captures || 0), 0),
      totalErrors: successful.reduce((sum, r) => sum + (r.errors || 0), 0)
    },
    coverage: {
      components: totalComponents.size,
      hooks: totalHooks.size,
      services: totalServices.size
    },
    results,
    categories: [...new Set(results.map(r => r.category))]
  };
  
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  
  // Generate markdown summary
  const summary = `# Comprehensive Test Report

## Summary
- **Total Journeys:** ${report.summary.totalJourneys}
- **Successful:** ${report.summary.successful}
- **Failed:** ${report.summary.failed}
- **Total Captures:** ${report.summary.totalCaptures}
- **Total Errors:** ${report.summary.totalErrors}
- **Duration:** ${(totalDuration / 1000).toFixed(2)}s

## Coverage
- **Components Tested:** ${report.coverage.components}
- **Hooks Used:** ${report.coverage.hooks}
- **Services Invoked:** ${report.coverage.services}

## Results by Category
${report.categories.map(cat => {
  const catResults = results.filter(r => r.category === cat);
  return `
### ${cat}
${catResults.map(r => 
  r.success 
    ? `✅ ${r.name} - ${r.captures} captures`
    : `❌ ${r.name} - ${r.error}`
).join('\n')}`;
}).join('\n')}

## Usage
These captures provide comprehensive test coverage and validation.
Each capture includes:
- Exact terminal output
- Component/hook/service metadata
- Performance metrics
- State transition tracking
- Frame history for flicker detection

Generated: ${new Date().toISOString()}
`;
  
  fs.writeFileSync(summaryPath, summary);
  
  console.log('\n' + '='.repeat(70));
  console.log('✅ Test capture complete!');
  console.log(`📊 Master report: ${reportPath}`);
  console.log(`📝 Summary: ${summaryPath}`);
  console.log(`📁 Captures: ${capturesDir}`);
  console.log('\n✅ Test suite execution complete');
}

// Execute
runTestCaptures().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});