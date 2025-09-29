#!/usr/bin/env node

/**
 * Enhanced Test Runner for Cyber-AutoAgent React Interface
 * 
 * Orchestrates all testing types:
 * - Unit tests (Jest-based component tests)
 * - Interactive component tests (PTY-based)
 * - User journey validation (End-to-end flows)
 * - Visual regression tests
 * - Performance tests
 * - Automated test suite
 */

import { spawn, execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import chalk from 'chalk';

const __dirname = dirname(fileURLToPath(import.meta.url));
const testResultsDir = join(__dirname, 'fixtures', 'test-results');

// Ensure test results directory
fs.mkdirSync(testResultsDir, { recursive: true });

/**
 * Enhanced Test Runner Class
 */
class EnhancedTestRunner {
  constructor() {
    this.results = {
      unit: null,
      interactive: null,
      journey: null,
      automated: null,
      visual: null,
      performance: null
    };
    this.startTime = Date.now();
  }

  /**
   * Run Jest unit tests
   */
  async runUnitTests() {
    console.log(chalk.blue('\n📋 Running Unit Tests (Jest)...'));
    
    try {
      const result = execSync('npm test -- --passWithNoTests --coverage', {
        cwd: join(__dirname, '..'),
        stdio: 'pipe',
        encoding: 'utf8'
      });
      
      this.results.unit = {
        passed: true,
        output: result,
        duration: Date.now() - this.startTime
      };
      
      console.log(chalk.green('✓ Unit tests passed'));
      return true;
    } catch (error) {
      this.results.unit = {
        passed: false,
        error: error.message,
        output: error.stdout || error.stderr,
        duration: Date.now() - this.startTime
      };
      
      console.log(chalk.red('✗ Unit tests failed'));
      return false;
    }
  }

  /**
   * Run interactive component tests
   */
  async runInteractiveTests() {
    console.log(chalk.blue('\n📋 Running Interactive Component Tests...'));
    
    try {
      const result = await this.executeNodeScript(
        join(__dirname, 'integration', 'interactive-component-tests.js')
      );
      
      this.results.interactive = {
        passed: result.exitCode === 0,
        output: result.output,
        duration: result.duration
      };
      
      if (result.exitCode === 0) {
        console.log(chalk.green('✓ Interactive tests passed'));
        return true;
      } else {
        console.log(chalk.red('✗ Interactive tests failed'));
        return false;
      }
    } catch (error) {
      this.results.interactive = {
        passed: false,
        error: error.message
      };
      console.log(chalk.red('✗ Interactive tests error:', error.message));
      return false;
    }
  }

  /**
   * Run journey validation tests
   */
  async runJourneyTests() {
    console.log(chalk.blue('\n📋 Running Journey Validation Tests...'));
    
    try {
      const result = await this.executeNodeScript(
        join(__dirname, 'integration', 'journey-validation-tests.js')
      );
      
      this.results.journey = {
        passed: result.exitCode === 0,
        output: result.output,
        duration: result.duration
      };
      
      if (result.exitCode === 0) {
        console.log(chalk.green('✓ Journey tests passed'));
        return true;
      } else {
        console.log(chalk.red('✗ Journey tests failed'));
        return false;
      }
    } catch (error) {
      this.results.journey = {
        passed: false,
        error: error.message
      };
      console.log(chalk.red('✗ Journey tests error:', error.message));
      return false;
    }
  }

  /**
   * Run automated test suite
   */
  async runAutomatedTests() {
    console.log(chalk.blue('\n📋 Running Automated Test Suite...'));
    
    try {
      const result = await this.executeNodeScript(
        join(__dirname, 'integration', 'automated-test-suite.js')
      );
      
      this.results.automated = {
        passed: result.exitCode === 0,
        output: result.output,
        duration: result.duration
      };
      
      if (result.exitCode === 0) {
        console.log(chalk.green('✓ Automated tests passed'));
        return true;
      } else {
        console.log(chalk.red('✗ Automated tests failed'));
        return false;
      }
    } catch (error) {
      this.results.automated = {
        passed: false,
        error: error.message
      };
      console.log(chalk.red('✗ Automated tests error:', error.message));
      return false;
    }
  }

  /**
   * Run visual regression tests (using existing capture system)
   */
  async runVisualTests() {
    console.log(chalk.blue('\n📋 Running Visual Regression Tests...'));
    
    try {
      // Check if captures exist
      const capturesDir = join(__dirname, 'fixtures', 'captures');
      if (!fs.existsSync(capturesDir)) {
        console.log(chalk.yellow('⚠ No existing captures found, running capture first...'));
        
        // Run comprehensive capture
        const captureResult = await this.executeNodeScript(
          join(__dirname, 'visual', 'comprehensive-capture.js')
        );
        
        if (captureResult.exitCode !== 0) {
          throw new Error('Capture failed');
        }
      }
      
      // Run validation
      const result = await this.executeNodeScript(
        join(__dirname, 'visual', 'validate-captures.js')
      );
      
      this.results.visual = {
        passed: result.exitCode === 0,
        output: result.output,
        duration: result.duration
      };
      
      if (result.exitCode === 0) {
        console.log(chalk.green('✓ Visual regression tests passed'));
        return true;
      } else {
        console.log(chalk.red('✗ Visual regression tests failed'));
        return false;
      }
    } catch (error) {
      this.results.visual = {
        passed: false,
        error: error.message
      };
      console.log(chalk.red('✗ Visual tests error:', error.message));
      return false;
    }
  }

  /**
   * Run performance tests
   */
  async runPerformanceTests() {
    console.log(chalk.blue('\n📋 Running Performance Tests...'));
    
    // Simple performance test - measure startup time and responsiveness
    const performanceMetrics = [];
    
    try {
      for (let i = 0; i < 3; i++) {
        const startTime = Date.now();
        
        const result = await this.executeNodeScript(
          join(__dirname, '..', 'dist', 'index.js'),
          ['--headless'],
          5000 // 5 second timeout
        );
        
        const duration = Date.now() - startTime;
        performanceMetrics.push(duration);
        
        if (result.exitCode !== 0 && result.exitCode !== null) {
          throw new Error(`Performance test failed: ${result.output}`);
        }
      }
      
      const avgStartup = performanceMetrics.reduce((a, b) => a + b, 0) / performanceMetrics.length;
      const maxStartup = Math.max(...performanceMetrics);
      
      // Performance thresholds
      const startupThreshold = 10000; // 10 seconds
      const maxThreshold = 15000; // 15 seconds
      
      const passed = avgStartup < startupThreshold && maxStartup < maxThreshold;
      
      this.results.performance = {
        passed,
        metrics: {
          averageStartup: avgStartup,
          maxStartup: maxStartup,
          runs: performanceMetrics
        },
        thresholds: {
          startup: startupThreshold,
          max: maxThreshold
        }
      };
      
      if (passed) {
        console.log(chalk.green(`✓ Performance tests passed (avg: ${avgStartup}ms)`));
        return true;
      } else {
        console.log(chalk.red(`✗ Performance tests failed (avg: ${avgStartup}ms, max: ${maxStartup}ms)`));
        return false;
      }
    } catch (error) {
      this.results.performance = {
        passed: false,
        error: error.message
      };
      console.log(chalk.red('✗ Performance tests error:', error.message));
      return false;
    }
  }

  /**
   * Execute Node.js script and capture output
   */
  executeNodeScript(scriptPath, args = [], timeout = 30000) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      let output = '';
      
      const child = spawn('node', [scriptPath, ...args], {
        stdio: 'pipe',
        cwd: dirname(scriptPath)
      });
      
      // Set timeout
      const timer = setTimeout(() => {
        child.kill('SIGKILL');
        resolve({
          exitCode: -1,
          output: output + '\n[TIMEOUT]',
          duration: Date.now() - startTime
        });
      }, timeout);
      
      child.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      child.stderr.on('data', (data) => {
        output += data.toString();
      });
      
      child.on('close', (exitCode) => {
        clearTimeout(timer);
        resolve({
          exitCode,
          output,
          duration: Date.now() - startTime
        });
      });
      
      child.on('error', (error) => {
        clearTimeout(timer);
        resolve({
          exitCode: -1,
          output: output + `\n[ERROR] ${error.message}`,
          duration: Date.now() - startTime
        });
      });
    });
  }

  /**
   * Generate comprehensive report
   */
  generateReport() {
    const totalDuration = Date.now() - this.startTime;
    
    console.log(chalk.bold.cyan('\n🎯 Enhanced Test Suite Report\n'));
    console.log(chalk.gray('━'.repeat(60)));

    // Test type results
    const testTypes = [
      { name: 'Unit Tests', key: 'unit' },
      { name: 'Interactive Tests', key: 'interactive' },
      { name: 'Journey Tests', key: 'journey' },
      { name: 'Automated Tests', key: 'automated' },
      { name: 'Visual Regression', key: 'visual' },
      { name: 'Performance', key: 'performance' }
    ];

    let totalPassed = 0;
    let totalFailed = 0;

    testTypes.forEach(({ name, key }) => {
      const result = this.results[key];
      if (result === null) {
        console.log(chalk.gray(`⏭ ${name}: Skipped`));
      } else if (result.passed) {
        console.log(chalk.green(`✓ ${name}: Passed`));
        totalPassed++;
      } else {
        console.log(chalk.red(`✗ ${name}: Failed`));
        totalFailed++;
      }
    });

    console.log(chalk.gray('\n' + '━'.repeat(60)));
    console.log(chalk.green(`Passed: ${totalPassed}`));
    console.log(chalk.red(`Failed: ${totalFailed}`));
    console.log(chalk.gray(`Total Duration: ${(totalDuration / 1000).toFixed(2)}s`));

    // Performance summary
    if (this.results.performance && this.results.performance.metrics) {
      const { averageStartup, maxStartup } = this.results.performance.metrics;
      console.log(chalk.cyan(`\n⚡ Performance Metrics:`));
      console.log(chalk.gray(`  Average Startup: ${averageStartup.toFixed(0)}ms`));
      console.log(chalk.gray(`  Max Startup: ${maxStartup.toFixed(0)}ms`));
    }

    // Detailed failures
    if (totalFailed > 0) {
      console.log(chalk.red('\n❌ Failed Test Details:'));
      testTypes.forEach(({ name, key }) => {
        const result = this.results[key];
        if (result && !result.passed) {
          console.log(chalk.red(`\n${name}:`));
          if (result.error) {
            console.log(chalk.gray(`  Error: ${result.error}`));
          }
          if (result.output && result.output.length > 0) {
            const lines = result.output.split('\n').slice(-5); // Last 5 lines
            lines.forEach(line => {
              if (line.trim()) {
                console.log(chalk.gray(`  ${line.trim()}`));
              }
            });
          }
        }
      });
    }

    // Save comprehensive report
    const report = {
      timestamp: new Date().toISOString(),
      summary: {
        passed: totalPassed,
        failed: totalFailed,
        duration: totalDuration
      },
      results: this.results,
      testValidationSpecAlignment: {
        section2_1_first_launch: this.results.journey?.passed || false,
        section2_2_configuration: this.results.interactive?.passed || false,
        section2_3_assessment: this.results.automated?.passed || false,
        ui_consistency: this.results.visual?.passed || false,
        performance_requirements: this.results.performance?.passed || false
      }
    };

    const reportPath = join(__dirname, 'fixtures', 'test-results', 'enhanced-test-report.json');
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    console.log(chalk.gray(`\n📁 Full report saved to: ${reportPath}`));

    return totalFailed === 0;
  }
}

/**
 * Main test runner function
 */
async function runEnhancedTests(options = {}) {
  const runner = new EnhancedTestRunner();
  
  console.log(chalk.bold.magenta('\n🧪 Cyber-AutoAgent Enhanced Test Suite\n'));
  console.log(chalk.gray('Comprehensive testing of all frontend functionality'));
  console.log(chalk.gray('Aligned with TEST-VALIDATION-SPECIFICATION.md\n'));
  console.log(chalk.gray('━'.repeat(60)));

  // Check if build exists
  const distPath = join(__dirname, '..', 'dist', 'index.js');
  if (!fs.existsSync(distPath)) {
    console.log(chalk.yellow('\n⚠ Building application...'));
    try {
      execSync('npm run build', { 
        cwd: join(__dirname, '..'),
        stdio: 'pipe'
      });
      console.log(chalk.green('✓ Build completed'));
    } catch (error) {
      console.error(chalk.red('✗ Build failed:', error.message));
      process.exit(1);
    }
  }

  // Run test suites based on options
  if (!options.skip || !options.skip.includes('unit')) {
    await runner.runUnitTests();
  }
  
  if (!options.skip || !options.skip.includes('interactive')) {
    await runner.runInteractiveTests();
  }
  
  if (!options.skip || !options.skip.includes('journey')) {
    await runner.runJourneyTests();
  }
  
  if (!options.skip || !options.skip.includes('automated')) {
    await runner.runAutomatedTests();
  }
  
  if (!options.skip || !options.skip.includes('visual')) {
    await runner.runVisualTests();
  }
  
  if (!options.skip || !options.skip.includes('performance')) {
    await runner.runPerformanceTests();
  }

  const success = runner.generateReport();
  return success;
}

// CLI handling
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const options = {};
  
  // Parse CLI arguments
  if (args.includes('--skip-unit')) options.skip = [...(options.skip || []), 'unit'];
  if (args.includes('--skip-interactive')) options.skip = [...(options.skip || []), 'interactive'];
  if (args.includes('--skip-journey')) options.skip = [...(options.skip || []), 'journey'];
  if (args.includes('--skip-automated')) options.skip = [...(options.skip || []), 'automated'];
  if (args.includes('--skip-visual')) options.skip = [...(options.skip || []), 'visual'];
  if (args.includes('--skip-performance')) options.skip = [...(options.skip || []), 'performance'];
  
  if (args.includes('--help')) {
    console.log(chalk.cyan('Enhanced Test Runner for Cyber-AutoAgent\n'));
    console.log('Usage: run-enhanced-tests.js [options]\n');
    console.log('Options:');
    console.log('  --skip-unit          Skip Jest unit tests');
    console.log('  --skip-interactive   Skip interactive component tests');
    console.log('  --skip-journey       Skip user journey validation');
    console.log('  --skip-automated     Skip automated test suite');
    console.log('  --skip-visual        Skip visual regression tests');
    console.log('  --skip-performance   Skip performance tests');
    console.log('  --help               Show this help message');
    process.exit(0);
  }

  runEnhancedTests(options).then(success => {
    process.exit(success ? 0 : 1);
  }).catch(error => {
    console.error(chalk.red('Enhanced test runner failed:', error));
    process.exit(1);
  });
}

export { runEnhancedTests, EnhancedTestRunner };