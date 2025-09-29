#!/usr/bin/env node

/**
 * Journey Validation Tests
 * 
 * Comprehensive user journey testing aligned with TEST-VALIDATION-SPECIFICATION.md
 * Tests complete user flows from start to finish with automated validation.
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import os from 'os';
import chalk from 'chalk';
import stripAnsi from 'strip-ansi';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appPath = join(__dirname, '..', 'dist', 'index.js');
const testResultsDir = join(__dirname, 'test-results', 'journeys');

// Ensure test results directory exists
fs.mkdirSync(testResultsDir, { recursive: true });

/**
 * Journey Test Base Class
 */
class JourneyTest {
  constructor(name, description) {
    this.name = name;
    this.description = description;
    this.term = null;
    this.output = '';
    this.validations = [];
    this.errors = [];
    this.startTime = Date.now();
  }

  /**
   * Start PTY session
   */
  async start(config = {}) {
    const env = {
      ...process.env,
      NO_COLOR: '1',
      CI: 'true',
      NODE_ENV: 'test',
      CYBER_TEST_MODE: 'true',
      ...config.env
    };

    // Setup test configuration if provided
    if (config.setupConfig) {
      await this.setupTestConfig(config.setupConfig);
    }

    return new Promise((resolve) => {
      this.term = spawn('node', [appPath, '--headless'], {
        name: 'xterm-256color',
        cols: 80,
        rows: 24,
        cwd: dirname(appPath),
        env
      });

      this.term.onData((data) => {
        this.output += data;
      });

      // Wait for initialization
      setTimeout(() => resolve(), 1500);
    });
  }

  async setupTestConfig(config) {
    const configDir = join(os.homedir(), '.cyber-autoagent');
    const configPath = join(configDir, 'config.json');
    
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }
    
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  }

  /**
   * Validation helpers
   */
  validate(condition, description) {
    this.validations.push({
      condition,
      description,
      passed: condition,
      timestamp: Date.now() - this.startTime
    });
    
    if (!condition) {
      this.errors.push(description);
    }
  }

  validateContains(text, description) {
    const contains = this.output.includes(text);
    this.validate(contains, description || `Contains "${text}"`);
    return contains;
  }

  validateNotContains(text, description) {
    const notContains = !this.output.includes(text);
    this.validate(notContains, description || `Does not contain "${text}"`);
    return notContains;
  }

  validateOccurrenceCount(text, expectedCount, description) {
    const regex = new RegExp(text, 'g');
    const matches = this.output.match(regex);
    const count = matches ? matches.length : 0;
    const valid = count === expectedCount;
    this.validate(valid, description || `"${text}" appears exactly ${expectedCount} times (found ${count})`);
    return valid;
  }

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

  async input(text) {
    this.term.write(text);
    await this.wait(100);
  }

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
      CTRL_L: '\x0C'
    };
    
    this.term.write(keys[key] || key);
    await this.wait(100);
  }

  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  cleanup() {
    if (this.term) {
      this.term.kill();
    }

    // Generate journey report
    const report = {
      name: this.name,
      description: this.description,
      duration: Date.now() - this.startTime,
      validations: this.validations,
      errors: this.errors,
      passed: this.errors.length === 0,
      output: this.output.substring(0, 5000) // Truncate for readability
    };

    const reportPath = join(testResultsDir, `${this.name.replace(/\s+/g, '-').toLowerCase()}.json`);
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    return report;
  }
}

/**
 * Journey Test Implementations
 */

// Test 1: First Launch Experience (Section 2.1 of spec)
class FirstLaunchJourney extends JourneyTest {
  constructor() {
    super('First Launch Experience', 'Test complete first-time setup flow');
  }

  async run() {
    await this.start({
      setupConfig: null // Fresh setup
    });

    // Section 2.1.1 - Welcome Screen Display
    await this.waitForText('Welcome to Cyber-AutoAgent');
    
    // Validate branding (TEST-VALIDATION-SPECIFICATION line 42-53)
    this.validateContains('CYBER', 'ASCII art banner renders correctly');
    this.validateOccurrenceCount('CYBER', 1, 'ASCII art appears only once');
    this.validateContains('Full Spectrum Cyber Operations', 'Tagline displays correctly');
    this.validateContains('Press ENTER', 'Instructions are clear');
    
    // Check for version information
    this.validate(
      this.output.match(/v?\d+\.\d+\.\d+/) !== null,
      'Version information displays'
    );

    // Section 2.1.2 - Deployment Mode Selection
    await this.sendKey('ENTER');
    await this.waitForText('Select Deployment Mode');
    
    this.validateContains('Local CLI', 'Local CLI option visible');
    this.validateContains('Agent Container', 'Container option visible');
    this.validateContains('Enterprise Stack', 'Enterprise option visible');
    
    // Test keyboard navigation
    await this.sendKey('DOWN');
    await this.wait(200);
    await this.sendKey('UP');
    await this.wait(200);
    
    // Select Local CLI
    await this.sendKey('ENTER');
    
    // Section 2.1.3 - Setup Progress Streaming
    await this.waitForText('Setting up', 10000);
    
    this.validate(
      this.output.includes('Setting up') || this.output.includes('Checking'),
      'Setup progress displays'
    );
    
    // Wait for completion
    await this.waitForText('setup completed', 15000);
    this.validateContains('setup completed', 'Setup completes successfully');

    return this.cleanup();
  }
}

// Test 2: Configuration Management Journey (Section 2.2)
class ConfigurationJourney extends JourneyTest {
  constructor() {
    super('Configuration Management', 'Test configuration editor functionality');
  }

  async run() {
    await this.start({
      setupConfig: {
        isConfigured: true,
        hasSeenWelcome: true,
        deploymentMode: 'local-cli'
      }
    });

    await this.waitForText('Cyber-AutoAgent');
    
    // Open configuration editor
    await this.input('/config');
    await this.sendKey('ENTER');
    await this.waitForText('Configuration Editor');
    
    // Section 2.2.1 - Configuration Modal Display
    this.validateContains('Configuration Editor', 'Modal opens correctly');
    this.validateContains('Models & Credentials', 'Models section visible');
    this.validateContains('Operations', 'Operations section visible');
    this.validateContains('Memory', 'Memory section visible');
    this.validateContains('Observability', 'Observability section visible');
    
    // Test keyboard navigation
    await this.sendKey('DOWN');
    await this.wait(200);
    await this.sendKey('DOWN');
    await this.wait(200);
    
    // Expand section
    await this.sendKey('ENTER');
    await this.wait(500);
    
    // Section 2.2.2 - Provider-aware field display would go here
    // For now, just check basic field editing
    
    // Test field editing
    await this.sendKey('TAB');
    await this.input('150');
    await this.wait(200);
    
    // Section 2.2.3 - Configuration Persistence
    // Test save
    await this.sendKey('CTRL_S');
    await this.wait(500);
    
    // Test ESC closes modal
    await this.sendKey('ESC');
    await this.wait(500);
    this.validateNotContains('Configuration Editor', 'ESC closes modal');

    return this.cleanup();
  }
}

// Test 3: Security Assessment Execution (Section 2.3)
class AssessmentExecutionJourney extends JourneyTest {
  constructor() {
    super('Assessment Execution', 'Test complete assessment workflow');
  }

  async run() {
    await this.start({
      setupConfig: {
        isConfigured: true,
        hasSeenWelcome: true,
        deploymentMode: 'local-cli',
        autoApprove: false
      }
    });

    await this.waitForText('Cyber-AutoAgent');
    
    // Section 2.3.1 - Target Definition and Validation
    await this.input('target testphp.vulnweb.com');
    await this.sendKey('ENTER');
    await this.wait(500);
    
    this.validate(
      this.output.includes('Target set') || this.output.includes('testphp.vulnweb.com'),
      'Valid target accepted'
    );
    
    // Set objective
    await this.input('objective Quick security assessment');
    await this.sendKey('ENTER');
    await this.wait(500);
    
    // Section 2.3.2 - Safety Authorization Flow
    await this.input('run');
    await this.sendKey('ENTER');
    await this.waitForText('Authorization Required', 10000);
    
    this.validateContains('Authorization Required', 'Safety modal appears');
    this.validateContains('authorized to test', 'Legal warning displayed');
    
    // Try to bypass with ESC
    await this.sendKey('ESC');
    await this.wait(500);
    this.validateContains('Authorization Required', 'Cannot bypass with ESC');
    
    // Try to proceed without checkbox
    await this.sendKey('TAB');
    await this.sendKey('ENTER');
    await this.wait(500);
    this.validateContains('Authorization Required', 'Cannot proceed without checkbox');
    
    // Proper authorization
    await this.sendKey('SPACE'); // Check box
    await this.sendKey('TAB');
    await this.sendKey('ENTER');
    
    // Section 2.3.3 - Real-time Assessment Streaming
    await this.waitForText('tool:', 10000);
    
    this.validateContains('tool:', 'Tool execution begins');
    this.validate(
      this.output.includes('├─') || this.output.includes('└─'),
      'Tool parameters use tree format'
    );
    
    // Check for thinking indicator
    this.validate(
      this.output.includes('⠋') || this.output.includes('Executing'),
      'Tool execution animation appears'
    );

    return this.cleanup();
  }
}

// Test 4: Operation Control and Monitoring (Section 2.4)
class OperationControlJourney extends JourneyTest {
  constructor() {
    super('Operation Control', 'Test operation control mechanisms');
  }

  async run() {
    await this.start({
      setupConfig: {
        isConfigured: true,
        hasSeenWelcome: true,
        deploymentMode: 'local-cli'
      }
    });

    await this.waitForText('Cyber-AutoAgent');
    
    // Set up a quick operation
    await this.input('target example.com');
    await this.sendKey('ENTER');
    await this.input('objective Test control');
    await this.sendKey('ENTER');
    await this.input('run');
    await this.sendKey('ENTER');
    
    // Safety approval
    await this.waitForText('Authorization Required');
    await this.sendKey('SPACE');
    await this.sendKey('TAB');
    await this.sendKey('ENTER');
    
    // Wait for operation to start
    await this.waitForText('tool:', 5000);
    
    // Test Ctrl+C pause
    await this.sendKey('CTRL_C');
    await this.wait(1000);
    
    this.validate(
      this.output.includes('Paused') || this.output.includes('Interrupted'),
      'Ctrl+C pauses operation'
    );
    
    // Test ESC kill switch
    await this.sendKey('ESC');
    await this.wait(1000);
    
    this.validate(
      this.output.includes('Kill') || this.output.includes('Stopping') || this.output.includes('Exit'),
      'ESC triggers kill switch'
    );

    return this.cleanup();
  }
}

// Test 5: Error Handling and Recovery
class ErrorHandlingJourney extends JourneyTest {
  constructor() {
    super('Error Handling', 'Test error scenarios and recovery');
  }

  async run() {
    await this.start({
      setupConfig: {
        isConfigured: true,
        hasSeenWelcome: true
      }
    });

    await this.waitForText('Cyber-AutoAgent');
    
    // Test invalid command
    await this.input('/unknown');
    await this.sendKey('ENTER');
    await this.wait(500);
    
    this.validate(
      this.output.includes('Unknown') || this.output.includes('not found'),
      'Invalid command error displayed'
    );
    
    // Test incomplete target
    await this.input('target');
    await this.sendKey('ENTER');
    await this.wait(500);
    
    this.validate(
      this.output.includes('Usage') || this.output.includes('required'),
      'Usage hint for incomplete command'
    );
    
    // Test recovery
    await this.input('/help');
    await this.sendKey('ENTER');
    await this.waitForText('Available Commands');
    
    this.validateContains('Available Commands', 'Recovery from error state');

    return this.cleanup();
  }
}

/**
 * Journey Test Runner
 */
async function runJourneyTests() {
  console.log(chalk.bold.cyan('\n🚀 Journey Validation Tests\n'));
  console.log(chalk.gray('Testing complete user workflows per TEST-VALIDATION-SPECIFICATION\n'));
  console.log(chalk.gray('━'.repeat(60)));

  const journeys = [
    new FirstLaunchJourney(),
    new ConfigurationJourney(),
    new AssessmentExecutionJourney(),
    new OperationControlJourney(),
    new ErrorHandlingJourney()
  ];

  const results = [];
  const startTime = Date.now();

  for (const journey of journeys) {
    console.log(chalk.blue(`\n🔍 Running: ${journey.name}`));
    console.log(chalk.gray(`   ${journey.description}`));
    
    try {
      const result = await journey.run();
      results.push(result);
      
      if (result.passed) {
        console.log(chalk.green(`   ✓ Passed (${result.validations.length} validations)`));
      } else {
        console.log(chalk.red(`   ✗ Failed (${result.errors.length} errors)`));
      }
    } catch (error) {
      console.log(chalk.red(`   ✗ Error: ${error.message}`));
      results.push({
        name: journey.name,
        passed: false,
        errors: [error.message],
        validations: []
      });
    }
  }

  // Generate summary
  console.log(chalk.gray('\n' + '━'.repeat(60)));
  console.log(chalk.bold.cyan('\n📊 Journey Test Summary\n'));

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const totalValidations = results.reduce((sum, r) => sum + (r.validations?.length || 0), 0);
  const passedValidations = results.reduce((sum, r) => 
    sum + (r.validations?.filter(v => v.passed).length || 0), 0);

  console.log(chalk.green(`✓ Journeys Passed: ${passed}`));
  console.log(chalk.red(`✗ Journeys Failed: ${failed}`));
  console.log(chalk.gray(`Total Validations: ${passedValidations}/${totalValidations}`));
  console.log(chalk.gray(`Total Duration: ${((Date.now() - startTime) / 1000).toFixed(2)}s`));

  // List failures
  if (failed > 0) {
    console.log(chalk.red('\n❌ Failed Journeys:'));
    results.filter(r => !r.passed).forEach(r => {
      console.log(chalk.red(`  - ${r.name}`));
      r.errors?.slice(0, 3).forEach(e => console.log(chalk.gray(`    ${e}`)));
      if (r.errors?.length > 3) {
        console.log(chalk.gray(`    ... and ${r.errors.length - 3} more errors`));
      }
    });
  }

  // Save comprehensive report
  const fullReport = {
    timestamp: new Date().toISOString(),
    summary: {
      passed,
      failed,
      totalValidations,
      passedValidations,
      duration: Date.now() - startTime
    },
    results,
    specAlignment: {
      section_2_1_first_launch: results.find(r => r.name === 'First Launch Experience')?.passed || false,
      section_2_2_configuration: results.find(r => r.name === 'Configuration Management')?.passed || false,
      section_2_3_assessment: results.find(r => r.name === 'Assessment Execution')?.passed || false,
      section_2_4_control: results.find(r => r.name === 'Operation Control')?.passed || false,
      error_handling: results.find(r => r.name === 'Error Handling')?.passed || false
    }
  };

  const reportPath = join(testResultsDir, 'journey-validation-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(fullReport, null, 2));

  console.log(chalk.gray(`\n📁 Detailed report: ${reportPath}`));

  return failed === 0;
}

// Export for use in other test runners
export { JourneyTest, runJourneyTests };

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runJourneyTests().then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error(chalk.red('Journey test execution failed:', error));
    process.exit(1);
  });
}