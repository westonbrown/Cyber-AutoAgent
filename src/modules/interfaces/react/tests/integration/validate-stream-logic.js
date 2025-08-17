#!/usr/bin/env node

/**
 * Stream Logic Validation Tests
 * 
 * Direct validation of terminal stream event processing logic.
 * Tests the EventAggregator and event transformation functions
 * without requiring full React rendering.
 * 
 * This provides fast, focused testing of the core logic that
 * processes events from the Python backend.
 */

import chalk from 'chalk';
import { EventAggregator } from '../../dist/utils/eventAggregator.js';

/**
 * Stream Logic Validator
 * 
 * Tests core event processing without UI rendering
 */
class StreamLogicValidator {
  constructor() {
    this.results = [];
    this.verbose = process.argv.includes('--verbose');
  }

  /**
   * Test: EventAggregator processes swarm events correctly
   */
  testSwarmEventProcessing() {
    console.log(chalk.blue('\n🔍 Testing Swarm Event Processing...'));
    
    const aggregator = new EventAggregator();
    const tests = [];

    // Test 1: swarm_start event activates swarm mode
    const swarmStartEvent = {
      type: 'swarm_start',
      agent_names: ['recon_specialist', 'injection_hunter'],
      agent_details: [
        { name: 'recon_specialist', tools: ['shell', 'http_request'] },
        { name: 'injection_hunter', tools: ['sqli_validator'] }
      ],
      task: 'Security assessment'
    };

    const startResults = aggregator.processEvent(swarmStartEvent);
    tests.push({
      name: 'Swarm start event passed through',
      passed: startResults.length === 1 && startResults[0].type === 'swarm_start'
    });

    // Test 2: Step header during swarm includes agent context
    const stepEvent = {
      type: 'step_header',
      step: 3,
      maxSteps: 100,
      is_swarm_operation: true,
      swarm_agent: 'recon_specialist',
      swarm_sub_step: 2,
      swarm_max_sub_steps: 5
    };

    const stepResults = aggregator.processEvent(stepEvent);
    tests.push({
      name: 'Step header includes swarm context',
      passed: stepResults[0].swarm_agent === 'recon_specialist' &&
              stepResults[0].swarm_sub_step === 2
    });

    // Test 3: handoff_to_agent creates swarm_handoff event
    const handoffToolEvent = {
      type: 'tool_start',
      tool_name: 'handoff_to_agent',
      tool_input: {
        agent_name: 'injection_hunter',
        message: 'Found SQL injection vectors',
        context: { vulnerable_endpoints: ['/search.php'] }
      }
    };

    const handoffResults = aggregator.processEvent(handoffToolEvent);
    const hasSwarmHandoff = handoffResults.some(e => e.type === 'swarm_handoff');
    const handoffEvent = handoffResults.find(e => e.type === 'swarm_handoff');
    
    tests.push({
      name: 'Handoff tool creates swarm_handoff event',
      passed: hasSwarmHandoff && 
              handoffEvent?.to_agent === 'injection_hunter' &&
              handoffEvent?.message.includes('SQL injection')
    });

    // Test 4: Empty swarm_handoff events are filtered
    const emptyHandoffEvent = {
      type: 'swarm_handoff',
      from_agent: 'recon_specialist',
      to_agent: '',
      message: ''
    };

    const emptyResults = aggregator.processEvent(emptyHandoffEvent);
    tests.push({
      name: 'Empty handoff events filtered',
      passed: emptyResults.length === 0
    });

    // Test 5: swarm_end resets swarm state
    const swarmEndEvent = {
      type: 'swarm_end'
    };

    const endResults = aggregator.processEvent(swarmEndEvent);
    tests.push({
      name: 'Swarm end event processed',
      passed: endResults.length === 1 && endResults[0].type === 'swarm_end'
    });

    // After swarm_end, handoff_to_agent should not create swarm_handoff
    const postSwarmHandoff = aggregator.processEvent(handoffToolEvent);
    const hasPostSwarmHandoff = postSwarmHandoff.some(e => e.type === 'swarm_handoff');
    tests.push({
      name: 'Handoff after swarm_end does not create swarm_handoff',
      passed: !hasPostSwarmHandoff
    });

    // Report results
    const passed = tests.every(t => t.passed);
    this.reportTestResults('Swarm Event Processing', tests, passed);
    return passed;
  }

  /**
   * Test: Output deduplication
   */
  testOutputDeduplication() {
    console.log(chalk.blue('\n🔍 Testing Output Deduplication...'));
    
    const aggregator = new EventAggregator();
    const tests = [];

    // Test rapid duplicate outputs
    const output1 = { type: 'output', content: 'Duplicate content' };
    const output2 = { type: 'output', content: 'Duplicate content' };
    
    const result1 = aggregator.processEvent(output1);
    tests.push({
      name: 'First output passes through',
      passed: result1.length === 1 && result1[0].content === 'Duplicate content'
    });

    // Immediate duplicate should be filtered
    const result2 = aggregator.processEvent(output2);
    tests.push({
      name: 'Duplicate output filtered',
      passed: result2.length === 0
    });

    // Different output should pass
    const output3 = { type: 'output', content: 'Different content' };
    const result3 = aggregator.processEvent(output3);
    tests.push({
      name: 'Different output passes through',
      passed: result3.length === 1 && result3[0].content === 'Different content'
    });

    const passed = tests.every(t => t.passed);
    this.reportTestResults('Output Deduplication', tests, passed);
    return passed;
  }

  /**
   * Test: Tool event processing
   */
  testToolEventProcessing() {
    console.log(chalk.blue('\n🔍 Testing Tool Event Processing...'));
    
    const aggregator = new EventAggregator();
    const tests = [];

    // Test tool_start event
    const toolStart = {
      type: 'tool_start',
      tool_name: 'shell',
      tool_input: { command: 'nmap -sV target.com' }
    };

    const startResult = aggregator.processEvent(toolStart);
    tests.push({
      name: 'Tool start event processed',
      passed: startResult.length === 1 && 
              startResult[0].tool_name === 'shell'
    });

    // Test shell_command event
    const shellCommand = {
      type: 'shell_command',
      command: 'nmap -sV target.com'
    };

    const commandResult = aggregator.processEvent(shellCommand);
    tests.push({
      name: 'Shell command event processed',
      passed: commandResult.some(e => e.type === 'shell_command')
    });

    // Test tool output
    const toolOutput = {
      type: 'output',
      content: 'Port 80/tcp open http'
    };

    const outputResult = aggregator.processEvent(toolOutput);
    tests.push({
      name: 'Tool output processed',
      passed: outputResult.length === 1 && 
              outputResult[0].content.includes('Port 80')
    });

    // Test tool_end event
    const toolEnd = {
      type: 'tool_end',
      toolName: 'shell'
    };

    const endResult = aggregator.processEvent(toolEnd);
    tests.push({
      name: 'Tool end event processed',
      passed: endResult.length === 1 && endResult[0].type === 'tool_end'
    });

    const passed = tests.every(t => t.passed);
    this.reportTestResults('Tool Event Processing', tests, passed);
    return passed;
  }

  /**
   * Test: Reasoning and thinking events
   */
  testReasoningEvents() {
    console.log(chalk.blue('\n🔍 Testing Reasoning Events...'));
    
    const aggregator = new EventAggregator();
    const tests = [];

    // Test reasoning event
    const reasoning = {
      type: 'reasoning',
      content: 'Analyzing target for vulnerabilities...'
    };

    const reasoningResult = aggregator.processEvent(reasoning);
    tests.push({
      name: 'Reasoning event processed',
      passed: reasoningResult.some(e => e.type === 'reasoning')
    });

    // Test thinking event
    const thinking = {
      type: 'thinking',
      context: 'tool_execution',
      startTime: Date.now()
    };

    const thinkingResult = aggregator.processEvent(thinking);
    tests.push({
      name: 'Thinking event processed',
      passed: thinkingResult.some(e => e.type === 'thinking')
    });

    // Test thinking_end
    const thinkingEnd = {
      type: 'thinking_end'
    };

    const endResult = aggregator.processEvent(thinkingEnd);
    tests.push({
      name: 'Thinking end processed',
      passed: endResult.some(e => e.type === 'thinking_end')
    });

    const passed = tests.every(t => t.passed);
    this.reportTestResults('Reasoning Events', tests, passed);
    return passed;
  }

  /**
   * Report test results for a category
   */
  reportTestResults(category, tests, passed) {
    this.results.push({ category, tests, passed });

    if (this.verbose || !passed) {
      tests.forEach(test => {
        const icon = test.passed ? chalk.green('  ✓') : chalk.red('  ✗');
        const status = test.passed ? '' : chalk.red(' FAILED');
        console.log(`${icon} ${test.name}${status}`);
      });
    }

    const icon = passed ? chalk.green('✓') : chalk.red('✗');
    console.log(`${icon} ${category}: ${passed ? 'PASSED' : 'FAILED'}`);
  }

  /**
   * Run all validation tests
   */
  async runAll() {
    console.log(chalk.bold.cyan('\n═══════════════════════════════════════════'));
    console.log(chalk.bold.cyan('   Stream Logic Validation Suite'));
    console.log(chalk.bold.cyan('═══════════════════════════════════════════'));

    const startTime = Date.now();

    // Run all tests
    const swarmPassed = this.testSwarmEventProcessing();
    const dedupePassed = this.testOutputDeduplication();
    const toolPassed = this.testToolEventProcessing();
    const reasoningPassed = this.testReasoningEvents();

    // Calculate results
    const duration = Date.now() - startTime;
    const totalCategories = this.results.length;
    const passedCategories = this.results.filter(r => r.passed).length;
    const allTests = this.results.flatMap(r => r.tests);
    const totalTests = allTests.length;
    const passedTests = allTests.filter(t => t.passed).length;

    // Display summary
    console.log(chalk.bold.cyan('\n═══════════════════════════════════════════'));
    console.log(chalk.bold.cyan('   Test Results Summary'));
    console.log(chalk.bold.cyan('═══════════════════════════════════════════'));

    console.log(chalk.cyan('\nCategories:'));
    this.results.forEach(result => {
      const icon = result.passed ? chalk.green('✓') : chalk.red('✗');
      const status = result.passed ? chalk.green('PASSED') : chalk.red('FAILED');
      const testCount = result.tests.filter(t => t.passed).length;
      console.log(`  ${icon} ${result.category}: ${status} (${testCount}/${result.tests.length} tests)`);
    });

    console.log(chalk.cyan(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`));
    console.log(chalk.bold(`Categories: ${passedCategories}/${totalCategories} | `) + 
                chalk.bold(`Tests: ${passedTests}/${totalTests}`));
    console.log(chalk.gray(`Duration: ${duration}ms`));
    console.log(chalk.cyan(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`));

    // Exit with appropriate code
    const allPassed = passedCategories === totalCategories;
    if (allPassed) {
      console.log(chalk.green('\n✅ All stream logic validations passed!'));
    } else {
      console.log(chalk.red('\n❌ Some validations failed. Please review.'));
    }

    process.exit(allPassed ? 0 : 1);
  }
}

// Run if executed directly
if (process.argv[1] === new URL(import.meta.url).pathname) {
  const validator = new StreamLogicValidator();
  validator.runAll().catch(error => {
    console.error(chalk.red('Validation error:'), error);
    process.exit(1);
  });
}

export default StreamLogicValidator;