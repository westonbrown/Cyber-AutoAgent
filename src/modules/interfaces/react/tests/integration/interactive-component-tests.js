#!/usr/bin/env node

/**
 * Interactive Component Tests for Cyber-AutoAgent
 * 
 * Tests all interactive React components including:
 * - Modal navigation and keyboard handling
 * - Tool animation and display formatting
 * - Configuration persistence
 * - State management
 * - Flicker detection
 */

import React from 'react';
import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import chalk from 'chalk';
import stripAnsi from 'strip-ansi';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Component Test Suite
 */
class ComponentTestRunner {
  constructor() {
    this.results = [];
    this.currentTest = null;
  }

  /**
   * Test Configuration Editor Component
   */
  async testConfigEditor() {
    console.log(chalk.blue('\n📋 Testing Configuration Editor Component...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'config-editor'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    term.onData(data => { output += data; });
    
    // Wait for component to render
    await this.wait(1000);
    
    // Test section navigation
    term.write('\x1B[B'); // Arrow down
    await this.wait(200);
    
    // Test field editing
    term.write('\r'); // Enter to expand
    await this.wait(200);
    term.write('\t'); // Tab to field
    await this.wait(200);
    term.write('test-value');
    await this.wait(200);
    
    // Test save functionality
    term.write('\x13'); // Ctrl+S
    await this.wait(500);
    
    const testPassed = output.includes('Configuration Editor') &&
                      !output.includes('ERROR') &&
                      !output.includes('undefined');
    
    term.kill();
    
    this.results.push({
      name: 'Configuration Editor',
      passed: testPassed,
      output: output.substring(0, 500)
    });
    
    return testPassed;
  }

  /**
   * Test Tool Display Formatting
   */
  async testToolDisplay() {
    console.log(chalk.blue('\n📋 Testing Tool Display Component...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'tool-display'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    let frameChanges = 0;
    let lastFrame = '';
    
    term.onData(data => {
      output += data;
      if (output !== lastFrame) {
        frameChanges++;
        lastFrame = output;
      }
    });
    
    // Wait for rendering
    await this.wait(2000);
    
    // Check tool format
    const hasCorrectFormat = output.includes('tool:') &&
                            output.includes('├─') &&
                            output.includes('└─');
    
    // Check for animation
    const hasAnimation = output.includes('Executing') || 
                        output.includes('⠋') ||
                        output.includes('⠙') ||
                        output.includes('⠹');
    
    // Check no flicker (excessive frame changes)
    const noFlicker = frameChanges < 50; // Reasonable threshold
    
    term.kill();
    
    const testPassed = hasCorrectFormat && hasAnimation && noFlicker;
    
    this.results.push({
      name: 'Tool Display',
      passed: testPassed,
      details: {
        hasCorrectFormat,
        hasAnimation,
        noFlicker,
        frameChanges
      }
    });
    
    return testPassed;
  }

  /**
   * Test Modal Navigation
   */
  async testModalNavigation() {
    console.log(chalk.blue('\n📋 Testing Modal Navigation...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'modal-navigation'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    term.onData(data => { output += data; });
    
    // Test opening modal
    await this.wait(500);
    term.write('/config');
    term.write('\r');
    await this.wait(1000);
    
    const modalOpened = output.includes('Configuration Editor');
    
    // Test ESC closes modal
    term.write('\x1B');
    await this.wait(500);
    
    const modalClosed = !output.includes('Configuration Editor') || 
                       output.lastIndexOf('Configuration Editor') < output.length - 100;
    
    term.kill();
    
    const testPassed = modalOpened && modalClosed;
    
    this.results.push({
      name: 'Modal Navigation',
      passed: testPassed,
      details: {
        modalOpened,
        modalClosed
      }
    });
    
    return testPassed;
  }

  /**
   * Test Safety Warning Modal
   */
  async testSafetyWarning() {
    console.log(chalk.blue('\n📋 Testing Safety Warning Modal...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'safety-warning'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    term.onData(data => { output += data; });
    
    await this.wait(1000);
    
    // Try to bypass with ESC
    term.write('\x1B');
    await this.wait(500);
    
    const cannotBypass = output.includes('Authorization Required');
    
    // Try to confirm without checkbox
    term.write('\t\t\r'); // Tab twice and enter
    await this.wait(500);
    
    const requiresCheckbox = output.includes('Authorization Required');
    
    // Properly check and confirm
    term.write(' '); // Space to check
    term.write('\t\r'); // Tab and enter
    await this.wait(500);
    
    const canConfirm = output.includes('Authorized') || 
                       output.includes('Confirmed');
    
    term.kill();
    
    const testPassed = cannotBypass && requiresCheckbox && canConfirm;
    
    this.results.push({
      name: 'Safety Warning',
      passed: testPassed,
      details: {
        cannotBypass,
        requiresCheckbox,
        canConfirm
      }
    });
    
    return testPassed;
  }

  /**
   * Test Thinking Indicator Animation
   */
  async testThinkingIndicator() {
    console.log(chalk.blue('\n📋 Testing Thinking Indicator...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'thinking-indicator'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    const frames = [];
    
    term.onData(data => {
      output += data;
      frames.push(output);
    });
    
    // Capture animation frames
    await this.wait(3000);
    
    // Check for spinner characters
    const spinnerChars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    let animationDetected = false;
    
    for (const char of spinnerChars) {
      if (output.includes(char)) {
        animationDetected = true;
        break;
      }
    }
    
    // Check for different frames (animation)
    const uniqueFrames = new Set(frames.map(f => stripAnsi(f))).size;
    const hasAnimation = uniqueFrames > 5;
    
    term.kill();
    
    const testPassed = animationDetected && hasAnimation;
    
    this.results.push({
      name: 'Thinking Indicator',
      passed: testPassed,
      details: {
        animationDetected,
        uniqueFrames,
        totalFrames: frames.length
      }
    });
    
    return testPassed;
  }

  /**
   * Test Stream Display Updates
   */
  async testStreamDisplay() {
    console.log(chalk.blue('\n📋 Testing Stream Display...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'stream-display'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    let output = '';
    const events = [];
    
    term.onData(data => {
      output += data;
      // Track events
      if (output.includes('[STEP')) {
        events.push('step');
      }
      if (output.includes('tool:')) {
        events.push('tool');
      }
      if (output.includes('output')) {
        events.push('output');
      }
    });
    
    await this.wait(3000);
    
    // Check event sequence
    const hasStepHeaders = events.includes('step');
    const hasToolEvents = events.includes('tool');
    const hasOutput = events.includes('output');
    
    // Check formatting
    const properFormatting = output.includes('[STEP') &&
                            output.includes('tool:') &&
                            (output.includes('├─') || output.includes('└─'));
    
    term.kill();
    
    const testPassed = hasStepHeaders && hasToolEvents && hasOutput && properFormatting;
    
    this.results.push({
      name: 'Stream Display',
      passed: testPassed,
      details: {
        hasStepHeaders,
        hasToolEvents,
        hasOutput,
        properFormatting,
        eventCount: events.length
      }
    });
    
    return testPassed;
  }

  /**
   * Test State Persistence
   */
  async testStatePersistence() {
    console.log(chalk.blue('\n📋 Testing State Persistence...'));
    
    // Create test config
    const configDir = join(process.env.HOME || process.env.USERPROFILE, '.cyber-autoagent');
    const configPath = join(configDir, 'test-config.json');
    
    const testConfig = {
      isConfigured: true,
      iterations: 150,
      modelProvider: 'bedrock',
      testValue: 'persistence-test'
    };
    
    // Write config
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }
    fs.writeFileSync(configPath, JSON.stringify(testConfig, null, 2));
    
    // Start app and check if config is loaded
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'state-persistence'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname,
      env: {
        ...process.env,
        CYBER_CONFIG_PATH: configPath
      }
    });
    
    let output = '';
    term.onData(data => { output += data; });
    
    await this.wait(2000);
    
    // Check if config values are loaded
    const configLoaded = output.includes('150') || 
                        output.includes('persistence-test');
    
    // Modify config through UI
    term.write('/config\r');
    await this.wait(1000);
    term.write('\x1B[B\r'); // Navigate and expand
    await this.wait(500);
    term.write('\t200'); // Change value
    await this.wait(500);
    term.write('\x13'); // Save
    await this.wait(1000);
    
    term.kill();
    
    // Read config file to verify persistence
    let configPersisted = false;
    if (fs.existsSync(configPath)) {
      const savedConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      configPersisted = savedConfig.iterations === 200 || 
                       savedConfig.testValue === 'persistence-test';
    }
    
    // Cleanup
    if (fs.existsSync(configPath)) {
      fs.unlinkSync(configPath);
    }
    
    const testPassed = configLoaded && configPersisted;
    
    this.results.push({
      name: 'State Persistence',
      passed: testPassed,
      details: {
        configLoaded,
        configPersisted
      }
    });
    
    return testPassed;
  }

  /**
   * Test Flicker Detection
   */
  async testFlickerDetection() {
    console.log(chalk.blue('\n📋 Testing Flicker Detection...'));
    
    const term = spawn('node', [
      join(__dirname, 'test-harness.js'),
      'flicker-test'
    ], {
      cols: 80,
      rows: 24,
      cwd: __dirname
    });
    
    const frames = [];
    let output = '';
    
    term.onData(data => {
      output += data;
      frames.push({
        content: output,
        timestamp: Date.now()
      });
    });
    
    // Perform rapid UI updates
    await this.wait(500);
    for (let i = 0; i < 10; i++) {
      term.write('/help\r');
      await this.wait(100);
      term.write('\x1B'); // ESC
      await this.wait(100);
    }
    
    // Analyze frames for flicker
    let flickerCount = 0;
    for (let i = 2; i < frames.length; i++) {
      const current = stripAnsi(frames[i].content);
      const previous = stripAnsi(frames[i - 1].content);
      const beforePrevious = stripAnsi(frames[i - 2].content);
      
      // Detect oscillation
      if (current === beforePrevious && current !== previous) {
        flickerCount++;
      }
    }
    
    term.kill();
    
    const noFlicker = flickerCount < 3;
    
    this.results.push({
      name: 'Flicker Detection',
      passed: noFlicker,
      details: {
        flickerCount,
        totalFrames: frames.length
      }
    });
    
    return noFlicker;
  }

  /**
   * Helper: Wait for milliseconds
   */
  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Generate test report
   */
  generateReport() {
    console.log(chalk.bold.cyan('\n📊 Component Test Results\n'));
    console.log(chalk.gray('━'.repeat(50)));
    
    let passed = 0;
    let failed = 0;
    
    this.results.forEach(result => {
      if (result.passed) {
        console.log(chalk.green(`✓ ${result.name}`));
        passed++;
      } else {
        console.log(chalk.red(`✗ ${result.name}`));
        failed++;
      }
      
      if (result.details) {
        Object.entries(result.details).forEach(([key, value]) => {
          const color = value === true ? chalk.green : 
                       value === false ? chalk.red : chalk.gray;
          console.log(color(`  ${key}: ${value}`));
        });
      }
    });
    
    console.log(chalk.gray('\n' + '━'.repeat(50)));
    console.log(chalk.green(`Passed: ${passed}`));
    console.log(chalk.red(`Failed: ${failed}`));
    
    // Save detailed report
    const reportPath = join(__dirname, 'test-results', 'component-test-report.json');
    fs.mkdirSync(dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify({
      timestamp: new Date().toISOString(),
      summary: { passed, failed },
      results: this.results
    }, null, 2));
    
    console.log(chalk.gray(`\nDetailed report: ${reportPath}`));
    
    return failed === 0;
  }
}

/**
 * Run all component tests
 */
async function runComponentTests() {
  const runner = new ComponentTestRunner();
  
  await runner.testConfigEditor();
  await runner.testToolDisplay();
  await runner.testModalNavigation();
  await runner.testSafetyWarning();
  await runner.testThinkingIndicator();
  await runner.testStreamDisplay();
  await runner.testStatePersistence();
  await runner.testFlickerDetection();
  
  const success = runner.generateReport();
  process.exit(success ? 0 : 1);
}

// Run tests if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runComponentTests().catch(error => {
    console.error(chalk.red('Test execution failed:', error));
    process.exit(1);
  });
}

export { ComponentTestRunner };