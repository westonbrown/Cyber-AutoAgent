#!/usr/bin/env node

/**
 * Automated Test Suite for Cyber-AutoAgent React Interface
 * 
 * Comprehensive automated testing of all UI components, user journeys,
 * and interactive features with validation against TEST-VALIDATION-SPECIFICATION.
 * 
 * Features:
 * - PTY-based terminal interaction testing
 * - Automated validation of UI elements
 * - Flicker detection and performance monitoring
 * - Tool animation verification
 * - Configuration persistence testing
 * - Safety mechanism validation
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import path from 'path';
import os from 'os';
import chalk from 'chalk';
import stripAnsi from 'strip-ansi';

const __dirname = dirname(fileURLToPath(import.meta.url));
// Resolve app dist path: tests/integration -> tests -> react -> dist/index.js
const appPathCandidates = [
  join(__dirname, '..', '..', 'dist', 'index.js'),
  join(__dirname, '..', 'dist', 'index.js'), // fallback if dist is colocated
];
const appPath = appPathCandidates.find(p => fs.existsSync(p)) || appPathCandidates[0];
const testResultsDir = join(__dirname, 'test-results');

// Test configuration
const TEST_CONFIG = {
  terminalCols: 80,
  terminalRows: 24,
  stabilityTimeout: 500,
  maxStabilityAttempts: 20,
  flickerThreshold: 3,
  performanceThreshold: 2000, // ms
};

// Create test results directory
if (!fs.existsSync(testResultsDir)) {
  fs.mkdirSync(testResultsDir, { recursive: true });
}

/**
 * Test Framework Base Class
 */
class AutomatedTestRunner {
  constructor(testName, config = {}) {
    this.testName = testName;
    this.config = { ...TEST_CONFIG, ...config };
    this.term = null;
    this.output = '';
    this.frameHistory = [];
    this.errors = [];
    this.assertions = [];
    this.performanceMetrics = [];
    this.startTime = Date.now();
    this.testPassed = true;
  }

  /**
   * Start terminal session with application
   */
  async start(envOverrides = {}) {
    const env = {
      ...process.env,
      NO_COLOR: '1',
      CI: 'true',
      NODE_ENV: 'test',
      CYBER_TEST_MODE: 'true',
      ...envOverrides
    };

    // Set up test configuration if needed
    if (this.config.setupConfig) {
      await this.setupTestConfig(this.config.setupConfig);
    }

    return new Promise((resolve, reject) => {
      try {
        this.term = spawn('node', [appPath, '--headless'], {
          name: 'xterm-256color',
          cols: this.config.terminalCols,
          rows: this.config.terminalRows,
          cwd: dirname(appPath),
          env
        });

        this.term.onData((data) => {
          const previousFrame = this.output;
          this.output += data;
          
          // Track frame changes for flicker detection
          this.frameHistory.push({
            timestamp: Date.now(),
            content: this.output,
            delta: data
          });
          
          // Detect potential flicker
          this.detectFlicker();
        });

        this.term.onExit(({ exitCode }) => {
          if (exitCode !== 0 && exitCode !== null) {
            this.errors.push(`Process exited with code ${exitCode}`);
          }
        });

        // Wait for initial render
        setTimeout(() => resolve(), 1500);
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Setup test configuration
   */
  async setupTestConfig(config) {
    const configDir = join(os.homedir(), '.cyber-autoagent');
    const configPath = join(configDir, 'config.json');
    
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }
    
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  }

  /**
   * Wait for specific text to appear in output
   */
  async waitForText(text, timeout = 5000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      if (this.output.includes(text)) {
        return true;
      }
      await this.wait(100);
    }
    
    throw new Error(`Timeout waiting for text: "${text}"`);
  }

  /**
   * Wait for output to stabilize (no changes)
   */
  async waitForStability() {
    let previousOutput = '';
    let stabilityCount = 0;
    
    while (stabilityCount < 3) {
      previousOutput = this.output;
      await this.wait(this.config.stabilityTimeout);
      
      if (previousOutput === this.output) {
        stabilityCount++;
      } else {
        stabilityCount = 0;
      }
      
      if (stabilityCount > this.config.maxStabilityAttempts) {
        throw new Error('Output never stabilized');
      }
    }
  }

  /**
   * Send input to terminal
   */
  async input(text) {
    this.term.write(text);
    await this.wait(100);
  }

  /**
   * Send keyboard key
   */
  async sendKey(key) {
    const keys = {
      ENTER: '\r',
      ESC: '\x1B',
      TAB: '\t',
      SPACE: ' ',
      UP: '\x1B[A',
      DOWN: '\x1B[B',
      LEFT: '\x1B[D',
      RIGHT: '\x1B[C',
      CTRL_C: '\x03',
      BACKSPACE: '\x7F',
      DELETE: '\x1B[3~'
    };
    
    this.term.write(keys[key] || key);
    await this.wait(100);
  }

  /**
   * Assert condition with description
   */
  assert(condition, description) {
    this.assertions.push({
      passed: condition,
      description,
      timestamp: Date.now() - this.startTime
    });
    
    if (!condition) {
      this.testPassed = false;
      this.errors.push(`Assertion failed: ${description}`);
    }
  }

  /**
   * Assert text appears in output
   */
  assertContains(text, description) {
    const contains = this.output.includes(text);
    this.assert(contains, description || `Output contains "${text}"`);
    return contains;
  }

  /**
   * Assert text does not appear in output
   */
  assertNotContains(text, description) {
    const notContains = !this.output.includes(text);
    this.assert(notContains, description || `Output does not contain "${text}"`);
    return notContains;
  }

  /**
   * Count occurrences of text in output
   */
  countOccurrences(text) {
    const regex = new RegExp(text, 'g');
    const matches = this.output.match(regex);
    return matches ? matches.length : 0;
  }

  /**
   * Assert exact occurrence count
   */
  assertOccurrenceCount(text, expectedCount, description) {
    const count = this.countOccurrences(text);
    this.assert(
      count === expectedCount,
      description || `"${text}" appears exactly ${expectedCount} time(s) (found ${count})`
    );
  }

  /**
   * Get current frame content (last stable output)
   */
  getCurrentFrame() {
    return stripAnsi(this.output);
  }

  /**
   * Detect flicker in output
   */
  detectFlicker() {
    if (this.frameHistory.length < 3) return;
    
    const recent = this.frameHistory.slice(-10);
    let flickerCount = 0;
    
    for (let i = 2; i < recent.length; i++) {
      const current = recent[i].content;
      const previous = recent[i - 1].content;
      const beforePrevious = recent[i - 2].content;
      
      // Check if content oscillates
      if (current === beforePrevious && current !== previous) {
        flickerCount++;
      }
    }
    
    if (flickerCount > this.config.flickerThreshold) {
      this.errors.push(`Flicker detected: ${flickerCount} oscillations`);
    }
  }

  /**
   * Measure operation performance
   */
  async measurePerformance(operation, name) {
    const startTime = Date.now();
    await operation();
    const duration = Date.now() - startTime;
    
    this.performanceMetrics.push({ name, duration });
    
    if (duration > this.config.performanceThreshold) {
      this.errors.push(`Performance issue: ${name} took ${duration}ms`);
    }
    
    return duration;
  }

  /**
   * Capture current state for debugging
   */
  captureState(label) {
    const statePath = join(testResultsDir, `${this.testName}-${label}.txt`);
    fs.writeFileSync(statePath, this.output);
  }

  /**
   * Wait helper
   */
  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Clean up and generate report
   */
  async cleanup() {
    if (this.term) {
      this.term.kill();
    }
    
    // Generate test report
    const report = {
      testName: this.testName,
      passed: this.testPassed,
      duration: Date.now() - this.startTime,
      assertions: this.assertions,
      errors: this.errors,
      performanceMetrics: this.performanceMetrics,
      frameCount: this.frameHistory.length
    };
    
    const reportPath = join(testResultsDir, `${this.testName}-report.json`);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    return report;
  }
}

/**
 * Test Suites
 */

// Test 1: Setup Wizard Flow
async function testSetupWizardFlow() {
  console.log(chalk.blue('\n📋 Testing Setup Wizard Flow...'));
  
  const test = new AutomatedTestRunner('setup-wizard-flow', {
    setupConfig: null // Start fresh
  });
  
  try {
    await test.start();
    
    // Test Welcome Screen
    await test.waitForText('Welcome to Cyber-AutoAgent');
    test.assertContains('CYBER', 'ASCII art displays');
    test.assertOccurrenceCount('CYBER', 1, 'ASCII art appears only once');
    test.assertContains('Full Spectrum Cyber Operations', 'Tagline displays');
    test.assertContains('Press ENTER to begin', 'Instructions display');
    
    // Navigate to deployment selection
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Test Deployment Selection
    test.assertContains('Select Deployment Mode', 'Deployment selection screen appears');
    test.assertContains('Local CLI', 'Local CLI option available');
    test.assertContains('Agent Container', 'Container option available');
    test.assertContains('Enterprise Stack', 'Enterprise option available');
    
    // Select Local CLI
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Test Setup Progress
    test.assertContains('Setting up', 'Setup progress displays');
    await test.waitForText('setup completed', 10000);
    
    console.log(chalk.green('✓ Setup Wizard Flow passed'));
  } catch (error) {
    console.log(chalk.red('✗ Setup Wizard Flow failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 2: Configuration Editor
async function testConfigurationEditor() {
  console.log(chalk.blue('\n📋 Testing Configuration Editor...'));
  
  const test = new AutomatedTestRunner('config-editor', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true,
      deploymentMode: 'local-cli',
      modelProvider: 'bedrock',
      iterations: 100
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Open config editor
    await test.input('/config');
    await test.sendKey('ENTER');
    await test.waitForText('Configuration Editor');
    
    // Test section navigation
    test.assertContains('Models & Credentials', 'Models section visible');
    test.assertContains('Operations', 'Operations section visible');
    test.assertContains('Memory', 'Memory section visible');
    test.assertContains('Observability', 'Observability section visible');
    
    // Navigate sections with arrow keys
    await test.sendKey('DOWN');
    await test.wait(200);
    await test.sendKey('DOWN');
    await test.wait(200);
    
    // Expand a section
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Test field editing
    await test.sendKey('TAB');
    await test.input('150');
    await test.wait(200);
    
    // Save changes
    await test.sendKey('CTRL_S');
    await test.waitForStability();
    
    // Test ESC closes modal
    await test.sendKey('ESC');
    await test.waitForStability();
    test.assertNotContains('Configuration Editor', 'Config editor closed');
    
    console.log(chalk.green('✓ Configuration Editor passed'));
  } catch (error) {
    console.log(chalk.red('✗ Configuration Editor failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 3: Tool Execution Display
async function testToolExecutionDisplay() {
  console.log(chalk.blue('\n📋 Testing Tool Execution Display...'));
  
  const test = new AutomatedTestRunner('tool-execution', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true,
      deploymentMode: 'local-cli',
      modelProvider: 'bedrock',
      autoApprove: true
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Set target
    await test.input('target testphp.vulnweb.com');
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Set objective
    await test.input('objective Quick security scan');
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Start assessment
    await test.input('run');
    await test.sendKey('ENTER');
    
    // Wait for safety warning
    await test.waitForText('Authorization Required', 5000);
    test.assertContains('authorized to test', 'Safety warning displays');
    
    // Confirm safety
    await test.sendKey('SPACE'); // Check box
    await test.sendKey('TAB');
    await test.sendKey('ENTER'); // Confirm
    
    // Wait for tool execution
    await test.waitForText('tool:', 10000);
    
    // Validate tool display format
    const output = test.getCurrentFrame();
    const toolLines = output.split('\n').filter(line => line.includes('tool:'));
    
    if (toolLines.length > 0) {
      test.assert(true, 'Tool execution detected');
      
      // Check for parameter tree format
      test.assertContains('├─', 'Tree branch character present');
      test.assertContains('└─', 'Tree end character present');
    }
    
    // Test animation indicator
    await test.measurePerformance(async () => {
      await test.waitForText('Executing', 5000);
    }, 'Tool animation appearance');
    
    console.log(chalk.green('✓ Tool Execution Display passed'));
  } catch (error) {
    console.log(chalk.red('✗ Tool Execution Display failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 4: Keyboard Navigation and Shortcuts
async function testKeyboardNavigation() {
  console.log(chalk.blue('\n📋 Testing Keyboard Navigation...'));
  
  const test = new AutomatedTestRunner('keyboard-navigation', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Test slash commands
    await test.input('/help');
    await test.sendKey('ENTER');
    await test.waitForText('Available Commands');
    test.assertContains('/config', 'Config command listed');
    test.assertContains('/clear', 'Clear command listed');
    
    // Test Ctrl+L clear
    await test.sendKey('CTRL_L');
    await test.waitForStability();
    test.assert(test.getCurrentFrame().length < 1000, 'Screen cleared');
    
    // Test ESC behavior
    await test.input('/config');
    await test.sendKey('ENTER');
    await test.waitForText('Configuration Editor');
    await test.sendKey('ESC');
    await test.waitForStability();
    test.assertNotContains('Configuration Editor', 'ESC closes modal');
    
    console.log(chalk.green('✓ Keyboard Navigation passed'));
  } catch (error) {
    console.log(chalk.red('✗ Keyboard Navigation failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 5: Error Handling and Recovery
async function testErrorHandling() {
  console.log(chalk.blue('\n📋 Testing Error Handling...'));
  
  const test = new AutomatedTestRunner('error-handling', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Test invalid target
    await test.input('target');
    await test.sendKey('ENTER');
    await test.waitForStability();
    test.assertContains('Usage:', 'Usage hint displays for incomplete command');
    
    // Test invalid URL format
    await test.input('target not-a-valid-url');
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Test unknown command
    await test.input('/unknown');
    await test.sendKey('ENTER');
    await test.waitForStability();
    test.assertContains('Unknown command', 'Unknown command error displays');
    
    // Test recovery
    await test.input('/help');
    await test.sendKey('ENTER');
    await test.waitForText('Available Commands');
    test.assert(true, 'Recovers from error state');
    
    console.log(chalk.green('✓ Error Handling passed'));
  } catch (error) {
    console.log(chalk.red('✗ Error Handling failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 6: Performance and Flicker Detection
async function testPerformanceAndFlicker() {
  console.log(chalk.blue('\n📋 Testing Performance and Flicker...'));
  
  const test = new AutomatedTestRunner('performance-flicker', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true
    },
    flickerThreshold: 2
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Rapid navigation to detect flicker
    for (let i = 0; i < 5; i++) {
      await test.input('/help');
      await test.sendKey('ENTER');
      await test.wait(200);
      await test.sendKey('ESC');
      await test.wait(200);
    }
    
    // Check for flicker
    test.assert(test.errors.filter(e => e.includes('Flicker')).length === 0, 'No flicker detected');
    
    // Performance test - config modal
    const configOpenTime = await test.measurePerformance(async () => {
      await test.input('/config');
      await test.sendKey('ENTER');
      await test.waitForText('Configuration Editor');
    }, 'Config modal open');
    
    test.assert(configOpenTime < 1000, `Config opens quickly (${configOpenTime}ms)`);
    
    console.log(chalk.green('✓ Performance and Flicker passed'));
  } catch (error) {
    console.log(chalk.red('✗ Performance and Flicker failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 7: Safety Mechanisms
async function testSafetyMechanisms() {
  console.log(chalk.blue('\n📋 Testing Safety Mechanisms...'));
  
  const test = new AutomatedTestRunner('safety-mechanisms', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true,
      autoApprove: false
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Setup assessment
    await test.input('target example.com');
    await test.sendKey('ENTER');
    await test.input('objective Test safety');
    await test.sendKey('ENTER');
    await test.input('run');
    await test.sendKey('ENTER');
    
    // Safety modal should appear
    await test.waitForText('Authorization Required');
    
    // Try to bypass with ESC
    await test.sendKey('ESC');
    await test.wait(500);
    test.assertContains('Authorization Required', 'Cannot bypass safety with ESC');
    
    // Try to confirm without checking box
    await test.sendKey('TAB');
    await test.sendKey('TAB');
    await test.sendKey('ENTER');
    await test.wait(500);
    test.assertContains('Authorization Required', 'Cannot confirm without checkbox');
    
    // Properly authorize
    await test.sendKey('SPACE'); // Check box
    await test.sendKey('TAB');
    await test.sendKey('ENTER');
    await test.waitForText('Starting assessment', 5000);
    
    console.log(chalk.green('✓ Safety Mechanisms passed'));
  } catch (error) {
    console.log(chalk.red('✗ Safety Mechanisms failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

// Test 8: Memory and State Management
async function testMemoryAndState() {
  console.log(chalk.blue('\n📋 Testing Memory and State Management...'));
  
  const test = new AutomatedTestRunner('memory-state', {
    setupConfig: {
      isConfigured: true,
      hasSeenWelcome: true,
      memoryMode: 'auto'
    }
  });
  
  try {
    await test.start();
    await test.waitForStability();
    
    // Set initial state
    await test.input('target test1.com');
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Clear and check state persistence
    await test.sendKey('CTRL_L');
    await test.wait(500);
    
    // Input should remember target
    await test.input('show');
    await test.sendKey('ENTER');
    await test.waitForStability();
    test.assertContains('test1.com', 'Target persists after clear');
    
    // Change target
    await test.input('target test2.com');
    await test.sendKey('ENTER');
    await test.waitForStability();
    
    // Verify update
    await test.input('show');
    await test.sendKey('ENTER');
    await test.waitForStability();
    test.assertContains('test2.com', 'Target updates correctly');
    test.assertNotContains('test1.com', 'Old target cleared');
    
    console.log(chalk.green('✓ Memory and State Management passed'));
  } catch (error) {
    console.log(chalk.red('✗ Memory and State Management failed:', error.message));
    test.captureState('failure');
  }
  
  return await test.cleanup();
}

/**
 * Main Test Runner
 */
async function runAllTests() {
  console.log(chalk.bold.cyan('\n🚀 Cyber-AutoAgent Automated Test Suite\n'));
  console.log(chalk.gray('━'.repeat(50)));
  
  const results = [];
  const startTime = Date.now();
  
  // Run all test suites
  const testSuites = [
    testSetupWizardFlow,
    testConfigurationEditor,
    testToolExecutionDisplay,
    testKeyboardNavigation,
    testErrorHandling,
    testPerformanceAndFlicker,
    testSafetyMechanisms,
    testMemoryAndState
  ];
  
  for (const testSuite of testSuites) {
    try {
      const result = await testSuite();
      results.push(result);
    } catch (error) {
      console.error(chalk.red(`Test suite error: ${error.message}`));
      results.push({
        testName: testSuite.name,
        passed: false,
        errors: [error.message]
      });
    }
  }
  
  // Generate summary report
  console.log(chalk.gray('\n' + '━'.repeat(50)));
  console.log(chalk.bold.cyan('\n📊 Test Results Summary\n'));
  
  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const totalAssertions = results.reduce((sum, r) => sum + (r.assertions?.length || 0), 0);
  const passedAssertions = results.reduce((sum, r) => 
    sum + (r.assertions?.filter(a => a.passed).length || 0), 0);
  
  console.log(chalk.green(`✓ Passed: ${passed}`));
  console.log(chalk.red(`✗ Failed: ${failed}`));
  console.log(chalk.gray(`Total Assertions: ${passedAssertions}/${totalAssertions}`));
  console.log(chalk.gray(`Total Duration: ${((Date.now() - startTime) / 1000).toFixed(2)}s`));
  
  // List failures
  if (failed > 0) {
    console.log(chalk.red('\n❌ Failed Tests:'));
    results.filter(r => !r.passed).forEach(r => {
      console.log(chalk.red(`  - ${r.testName}`));
      r.errors?.forEach(e => console.log(chalk.gray(`    ${e}`)));
    });
  }
  
  // Performance summary
  console.log(chalk.cyan('\n⚡ Performance Metrics:'));
  results.forEach(r => {
    if (r.performanceMetrics?.length > 0) {
      r.performanceMetrics.forEach(m => {
        const color = m.duration < 1000 ? chalk.green : 
                     m.duration < 2000 ? chalk.yellow : chalk.red;
        console.log(color(`  ${m.name}: ${m.duration}ms`));
      });
    }
  });
  
  // Save full report
  const fullReport = {
    timestamp: new Date().toISOString(),
    summary: {
      passed,
      failed,
      totalAssertions,
      passedAssertions,
      duration: Date.now() - startTime
    },
    results
  };
  
  const reportPath = join(testResultsDir, 'test-summary.json');
  fs.writeFileSync(reportPath, JSON.stringify(fullReport, null, 2));
  
  console.log(chalk.gray(`\n📁 Full report saved to: ${reportPath}`));
  
  // Exit with appropriate code
  process.exit(failed > 0 ? 1 : 0);
}

// Run tests if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests().catch(error => {
    console.error(chalk.red('Fatal error:', error));
    process.exit(1);
  });
}

export { AutomatedTestRunner, runAllTests };