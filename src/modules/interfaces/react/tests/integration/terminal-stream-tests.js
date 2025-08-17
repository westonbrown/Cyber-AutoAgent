#!/usr/bin/env node

/**
 * Terminal Stream Logic Tests
 * 
 * Comprehensive test suite for validating terminal stream processing,
 * event formatting, and display logic in the React interface.
 * 
 * Tests cover:
 * - Event aggregation and deduplication
 * - Swarm event processing and display
 * - Step header formatting with agent context
 * - Tool output streaming and formatting
 * - Handoff event transformation
 * 
 * This test suite uses PTY (pseudo-terminal) to capture real terminal
 * output and validate the rendering behavior.
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import chalk from 'chalk';
import stripAnsi from 'strip-ansi';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Terminal Stream Test Runner
 * 
 * Validates the complete event processing pipeline from backend
 * emission to frontend display.
 */
class TerminalStreamTestRunner {
  constructor() {
    this.results = [];
    this.currentTest = null;
    this.verbose = process.argv.includes('--verbose');
  }

  /**
   * Test: Swarm Start Event Display
   * 
   * Validates that swarm_start events are properly displayed with:
   * - Tool header showing agent count and task
   * - Rich SwarmDisplay component rendering
   * - Agent details with tools and roles
   */
  async testSwarmStartDisplay() {
    console.log(chalk.blue('\n🔧 Testing Swarm Start Event Display...'));
    
    const testEvent = {
      type: 'swarm_start',
      agent_names: ['recon_specialist', 'injection_hunter', 'xss_specialist'],
      agent_count: 3,
      agent_details: [
        {
          name: 'recon_specialist',
          system_prompt: 'Elite reconnaissance specialist for attack surface mapping',
          tools: ['shell', 'http_request', 'mem0_memory']
        },
        {
          name: 'injection_hunter',
          system_prompt: 'SQL injection and code injection specialist',
          tools: ['shell', 'sqli_validator', 'python_repl']
        },
        {
          name: 'xss_specialist',
          system_prompt: 'Cross-site scripting vulnerability expert',
          tools: ['http_request', 'advanced_payload_coordinator']
        }
      ],
      task: 'Comprehensive security assessment of target application',
      max_handoffs: 25,
      timeout: 1200
    };

    const output = await this.simulateEventDisplay(testEvent);
    
    // Validate expected output elements
    const checks = [
      {
        name: 'Tool header displayed',
        check: output.includes('tool: swarm')
      },
      {
        name: 'Agent count shown',
        check: output.includes('3 specialized agents') || output.includes('agents: 3')
      },
      {
        name: 'Task description shown',
        check: output.includes('Comprehensive security assessment')
      },
      {
        name: 'SwarmDisplay component rendered',
        check: output.includes('[SWARM] Multi-Agent Operation')
      },
      {
        name: 'Agent details displayed',
        check: output.includes('recon_specialist') && 
               output.includes('injection_hunter') &&
               output.includes('xss_specialist')
      },
      {
        name: 'Tools listed for agents',
        check: output.includes('shell') && 
               output.includes('sqli_validator') &&
               output.includes('http_request')
      }
    ];

    const passed = checks.every(c => c.check);
    
    if (this.verbose) {
      console.log(chalk.gray('\nOutput Sample:'));
      console.log(chalk.gray(output.substring(0, 500)));
      console.log(chalk.gray('\nCheck Results:'));
      checks.forEach(c => {
        console.log(c.check ? chalk.green(`  ✓ ${c.name}`) : chalk.red(`  ✗ ${c.name}`));
      });
    }

    this.results.push({
      name: 'Swarm Start Display',
      passed,
      checks,
      output: output.substring(0, 1000)
    });

    return passed;
  }

  /**
   * Test: Step Header with Swarm Agent Context
   * 
   * Validates that step headers properly display:
   * - Agent name in swarm operations
   * - Sub-step numbering for agents
   * - Proper formatting: [SWARM: AGENT_NAME • STEP X/Y]
   */
  async testSwarmStepHeaders() {
    console.log(chalk.blue('\n🔧 Testing Swarm Step Headers...'));
    
    const testEvent = {
      type: 'step_header',
      step: 3,
      maxSteps: 100,
      operation: 'OP_TEST_123',
      duration: '15s',
      is_swarm_operation: true,
      swarm_agent: 'recon_specialist',
      swarm_sub_step: 2,
      swarm_max_sub_steps: 5
    };

    const output = await this.simulateEventDisplay(testEvent);
    
    const checks = [
      {
        name: 'Swarm prefix shown',
        check: output.includes('[SWARM:') || output.includes('[SWARM ')
      },
      {
        name: 'Agent name displayed',
        check: output.includes('RECON_SPECIALIST') || output.includes('recon_specialist')
      },
      {
        name: 'Sub-step numbering',
        check: output.includes('STEP 2/5') || output.includes('2/5')
      },
      {
        name: 'Divider line shown',
        check: output.includes('────') || output.includes('━━━')
      }
    ];

    const passed = checks.every(c => c.check);
    
    if (this.verbose) {
      console.log(chalk.gray('\nExpected format: [SWARM: RECON_SPECIALIST • STEP 2/5]'));
      console.log(chalk.gray('Actual output:'));
      console.log(chalk.gray(output.substring(0, 200)));
    }

    this.results.push({
      name: 'Swarm Step Headers',
      passed,
      checks,
      output: output.substring(0, 500)
    });

    return passed;
  }

  /**
   * Test: Handoff Event Transformation
   * 
   * Validates that handoff_to_agent tool events are transformed
   * into rich swarm_handoff events with:
   * - From/to agent names
   * - Handoff message
   * - Shared context display
   */
  async testHandoffTransformation() {
    console.log(chalk.blue('\n🔧 Testing Handoff Event Transformation...'));
    
    const toolEvent = {
      type: 'tool_start',
      tool_name: 'handoff_to_agent',
      tool_input: {
        agent_name: 'injection_hunter',
        message: 'Reconnaissance complete. Found SQL injection vectors at /search.php',
        context: {
          vulnerable_endpoints: ['/search.php', '/login.php'],
          database_type: 'MySQL',
          schema_leaked: true
        }
      }
    };

    const output = await this.simulateEventDisplay(toolEvent, {
      swarmActive: true,
      currentAgent: 'recon_specialist'
    });
    
    const checks = [
      {
        name: 'Handoff header shown',
        check: output.includes('[HANDOFF]')
      },
      {
        name: 'From agent displayed',
        check: output.includes('recon_specialist')
      },
      {
        name: 'To agent displayed',
        check: output.includes('injection_hunter')
      },
      {
        name: 'Handoff message shown',
        check: output.includes('Reconnaissance complete') || 
               output.includes('SQL injection vectors')
      },
      {
        name: 'Context transferred',
        check: output.includes('vulnerable_endpoints') || 
               output.includes('/search.php')
      }
    ];

    const passed = checks.every(c => c.check);
    
    this.results.push({
      name: 'Handoff Transformation',
      passed,
      checks,
      output: output.substring(0, 800)
    });

    return passed;
  }

  /**
   * Test: Tool Output Streaming
   * 
   * Validates proper formatting of tool outputs including:
   * - Shell command execution
   * - HTTP request/response
   * - Memory operations
   * - Output deduplication
   */
  async testToolOutputStream() {
    console.log(chalk.blue('\n🔧 Testing Tool Output Streaming...'));
    
    const events = [
      {
        type: 'tool_start',
        tool_name: 'shell',
        tool_input: {
          command: 'nmap -sV testphp.vulnweb.com'
        }
      },
      {
        type: 'output',
        content: 'Starting Nmap scan...\nPort 80/tcp open http nginx 1.19.0\nPort 443/tcp closed https'
      },
      {
        type: 'tool_end',
        tool_name: 'shell'
      }
    ];

    const output = await this.simulateEventSequence(events);
    
    const checks = [
      {
        name: 'Tool header shown',
        check: output.includes('tool: shell')
      },
      {
        name: 'Command displayed',
        check: output.includes('nmap') && output.includes('testphp.vulnweb.com')
      },
      {
        name: 'Output header shown',
        check: output.includes('output')
      },
      {
        name: 'Scan results displayed',
        check: output.includes('Port 80/tcp') && output.includes('nginx')
      }
    ];

    const passed = checks.every(c => c.check);
    
    this.results.push({
      name: 'Tool Output Streaming',
      passed,
      checks,
      output: output.substring(0, 600)
    });

    return passed;
  }

  /**
   * Test: Event Deduplication
   * 
   * Validates that duplicate events are properly filtered:
   * - Consecutive swarm_start events
   * - Duplicate output events
   * - Empty handoff events
   */
  async testEventDeduplication() {
    console.log(chalk.blue('\n🔧 Testing Event Deduplication...'));
    
    const events = [
      {
        type: 'swarm_start',
        agent_names: ['agent1'],
        task: 'Test task'
      },
      {
        type: 'swarm_start',
        agent_names: ['agent1'],
        task: 'Test task'
      },
      {
        type: 'output',
        content: 'Duplicate output'
      },
      {
        type: 'output',
        content: 'Duplicate output'
      },
      {
        type: 'swarm_handoff',
        from_agent: 'agent1',
        to_agent: '',
        message: ''
      }
    ];

    const output = await this.simulateEventSequence(events);
    
    // Count occurrences
    const swarmStartCount = (output.match(/\[SWARM\] Multi-Agent Operation/g) || []).length;
    const outputCount = (output.match(/Duplicate output/g) || []).length;
    const emptyHandoffCount = (output.match(/\[HANDOFF\].*→\s*$/g) || []).length;
    
    const checks = [
      {
        name: 'Single swarm_start rendered',
        check: swarmStartCount === 1
      },
      {
        name: 'Single output rendered',
        check: outputCount === 1
      },
      {
        name: 'Empty handoff suppressed',
        check: emptyHandoffCount === 0
      }
    ];

    const passed = checks.every(c => c.check);
    
    if (this.verbose) {
      console.log(chalk.gray('\nDeduplication counts:'));
      console.log(chalk.gray(`  Swarm starts: ${swarmStartCount} (expected: 1)`));
      console.log(chalk.gray(`  Duplicate outputs: ${outputCount} (expected: 1)`));
      console.log(chalk.gray(`  Empty handoffs: ${emptyHandoffCount} (expected: 0)`));
    }

    this.results.push({
      name: 'Event Deduplication',
      passed,
      checks,
      metrics: { swarmStartCount, outputCount, emptyHandoffCount }
    });

    return passed;
  }

  /**
   * Simulate event display through the terminal
   */
  async simulateEventDisplay(event, context = {}) {
    return new Promise((resolve) => {
      // Create a test harness that simulates the event flow
      const testScript = `
import React from 'react';
import { render } from 'ink';
import { EventRenderer } from '../../src/components/EventRenderer.js';

const event = ${JSON.stringify(event)};
const context = ${JSON.stringify(context)};

const App = () => {
  return <EventRenderer event={event} context={context} />;
};

render(<App />);

// Auto-exit after render
setTimeout(() => process.exit(0), 500);
      `;

      // Write temporary test file
      const testFile = join(__dirname, 'temp-test.js');
      fs.writeFileSync(testFile, testScript);

      // Run with node and capture output
      const term = spawn('node', [testFile], {
        cols: 120,
        rows: 40,
        cwd: __dirname
      });

      let output = '';
      term.onData(data => { output += data; });
      
      term.onExit(() => {
        // Clean up temp file
        try { fs.unlinkSync(testFile); } catch {}
        resolve(output);
      });

      // Timeout safety
      setTimeout(() => {
        term.kill();
        resolve(output);
      }, 2000);
    });
  }

  /**
   * Simulate a sequence of events
   */
  async simulateEventSequence(events) {
    // For now, concatenate individual simulations
    // In production, this would use a stateful renderer
    let combinedOutput = '';
    for (const event of events) {
      const output = await this.simulateEventDisplay(event);
      combinedOutput += output;
    }
    return combinedOutput;
  }

  /**
   * Wait utility
   */
  wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Run all tests
   */
  async runAll() {
    console.log(chalk.bold.cyan('\n═══════════════════════════════════════════'));
    console.log(chalk.bold.cyan('   Terminal Stream Logic Test Suite'));
    console.log(chalk.bold.cyan('═══════════════════════════════════════════\n'));

    const startTime = Date.now();

    // Run test suite
    await this.testSwarmStartDisplay();
    await this.testSwarmStepHeaders();
    await this.testHandoffTransformation();
    await this.testToolOutputStream();
    await this.testEventDeduplication();

    // Generate report
    const duration = Date.now() - startTime;
    const passed = this.results.filter(r => r.passed).length;
    const failed = this.results.filter(r => !r.passed).length;
    const total = this.results.length;

    console.log(chalk.bold.cyan('\n═══════════════════════════════════════════'));
    console.log(chalk.bold.cyan('   Test Results Summary'));
    console.log(chalk.bold.cyan('═══════════════════════════════════════════\n'));

    // Display results
    this.results.forEach(result => {
      const icon = result.passed ? chalk.green('✓') : chalk.red('✗');
      const status = result.passed ? chalk.green('PASSED') : chalk.red('FAILED');
      console.log(`${icon} ${result.name}: ${status}`);
      
      if (!result.passed && result.checks) {
        result.checks.filter(c => !c.check).forEach(c => {
          console.log(chalk.red(`    ✗ ${c.name}`));
        });
      }
    });

    console.log(chalk.cyan(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`));
    console.log(chalk.bold(`Total: ${total} | `) + 
                chalk.green(`Passed: ${passed} | `) + 
                chalk.red(`Failed: ${failed}`));
    console.log(chalk.gray(`Duration: ${duration}ms`));
    console.log(chalk.cyan(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`));

    // Save detailed report
    const reportPath = join(__dirname, '..', 'fixtures', 'test-results', 
                           `terminal-stream-${Date.now()}.json`);
    fs.writeFileSync(reportPath, JSON.stringify({
      timestamp: new Date().toISOString(),
      duration,
      passed,
      failed,
      total,
      results: this.results
    }, null, 2));

    console.log(chalk.gray(`\nDetailed report saved to: ${reportPath}`));

    // Exit code based on results
    process.exit(failed > 0 ? 1 : 0);
  }
}

// Run tests if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const runner = new TerminalStreamTestRunner();
  runner.runAll().catch(error => {
    console.error(chalk.red('Test runner error:'), error);
    process.exit(1);
  });
}

export default TerminalStreamTestRunner;