/**
 * Spinner Placement Tests
 *
 * Validates that thinking spinners appear in the correct locations
 * to eliminate UI gaps during agent operations.
 *
 * Edge cases covered:
 * 1. Operation startup (after operation_init)
 * 2. Post-reasoning (after reasoning ends, before tool selection)
 * 3. Post-step-header (after step header, before tool announcement)
 * 4. Tool execution (during tool invocation, before output)
 * 5. Post-tool-completion (after output, before next reasoning/step)
 */

import { describe, it, expect } from '@jest/globals';

type EventType = 'operation_init' | 'reasoning' | 'step_header' | 'tool_start' | 'output' | 'tool_end' | 'tool_invocation_end' | 'thinking';

interface TestEvent {
  type: EventType;
  content?: string;
  tool_name?: string;
  step?: number;
  context?: string;
  urgent?: boolean;
}

/**
 * Simplified version of Terminal's event processing logic
 * focused on spinner placement validation
 */
function processEventsForSpinners(events: TestEvent[], animationsEnabled = true): TestEvent[] {
  const results: TestEvent[] = [];
  let activeThinking = false;
  let activeReasoning = false;

  for (const event of events) {
    switch (event.type) {
      case 'operation_init':
        results.push(event);
        // Should add thinking spinner after operation init
        if (animationsEnabled && !activeThinking) {
          activeThinking = true;
          results.push({
            type: 'thinking',
            context: 'startup',
            urgent: true
          });
        }
        break;

      case 'step_header':
        results.push(event);
        // Should add thinking spinner after step header
        if (animationsEnabled && !activeThinking) {
          activeThinking = true;
          results.push({
            type: 'thinking',
            context: 'tool_preparation',
            urgent: true
          });
        }
        break;

      case 'reasoning':
        // Clear thinking when reasoning arrives
        if (activeThinking) {
          activeThinking = false;
        }
        activeReasoning = true;
        results.push(event);
        break;

      case 'tool_start':
        // Keep spinner showing during tool execution
        if (!activeThinking && animationsEnabled) {
          activeThinking = true;
          results.push({
            type: 'thinking',
            context: 'tool_execution',
            urgent: true
          });
        }
        results.push(event);
        break;

      case 'output':
        // Clear thinking when output arrives
        if (activeThinking) {
          activeThinking = false;
        }
        activeReasoning = false;
        results.push(event);
        break;

      case 'tool_end':
      case 'tool_invocation_end':
        // Clear thinking first
        if (activeThinking) {
          activeThinking = false;
        }
        results.push(event);
        // Add thinking spinner after tool completion
        if (animationsEnabled && !activeReasoning) {
          activeThinking = true;
          results.push({
            type: 'thinking',
            context: 'waiting',
            urgent: true
          });
        }
        break;

      default:
        results.push(event);
    }
  }

  return results;
}

describe('Terminal Spinner Placement', () => {

  it('adds startup spinner immediately after operation_init', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' }
    ];

    const processed = processEventsForSpinners(events);

    expect(processed).toHaveLength(2);
    expect(processed[0].type).toBe('operation_init');
    expect(processed[1].type).toBe('thinking');
    expect(processed[1].context).toBe('startup');
    expect(processed[1].urgent).toBe(true);
  });

  it('adds tool_preparation spinner after step_header', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },
      { type: 'reasoning', content: 'Planning attack...' },
      { type: 'step_header', step: 1 }
    ];

    const processed = processEventsForSpinners(events);

    // Find the step_header
    const stepHeaderIndex = processed.findIndex(e => e.type === 'step_header');
    expect(stepHeaderIndex).toBeGreaterThan(-1);

    // Next event should be thinking spinner
    const nextEvent = processed[stepHeaderIndex + 1];
    expect(nextEvent?.type).toBe('thinking');
    expect(nextEvent?.context).toBe('tool_preparation');
    expect(nextEvent?.urgent).toBe(true);
  });

  it('clears thinking spinner when reasoning arrives', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },
      { type: 'reasoning', content: 'Analyzing...' }
    ];

    const processed = processEventsForSpinners(events);

    // Startup spinner should be added after operation_init
    expect(processed[1].type).toBe('thinking');
    expect(processed[1].context).toBe('startup');

    // Reasoning should follow (spinner implicitly cleared)
    expect(processed[2].type).toBe('reasoning');

    // No thinking events should remain after reasoning
    const thinkingAfterReasoning = processed.slice(3).filter(e => e.type === 'thinking');
    expect(thinkingAfterReasoning).toHaveLength(0);
  });

  it('shows tool_execution spinner during tool invocation', () => {
    const events: TestEvent[] = [
      { type: 'step_header', step: 1 },
      { type: 'tool_start', tool_name: 'shell' }
    ];

    const processed = processEventsForSpinners(events);

    // Find tool_start
    const toolStartIndex = processed.findIndex(e => e.type === 'tool_start');
    expect(toolStartIndex).toBeGreaterThan(-1);

    // Should have thinking spinner before tool_start (after step header)
    const beforeToolStart = processed[toolStartIndex - 1];
    expect(beforeToolStart?.type).toBe('thinking');
    expect(['tool_preparation', 'tool_execution']).toContain(beforeToolStart?.context);
  });

  it('clears spinner when tool output arrives', () => {
    const events: TestEvent[] = [
      { type: 'step_header', step: 1 },
      { type: 'tool_start', tool_name: 'http_request' },
      { type: 'output', content: 'Status: 200 OK' }
    ];

    const processed = processEventsForSpinners(events);

    // Output should be present
    const outputIndex = processed.findIndex(e => e.type === 'output');
    expect(outputIndex).toBeGreaterThan(-1);

    // No thinking events should appear after output (until next event adds one)
    const afterOutput = processed.slice(outputIndex + 1);
    const hasThinking = afterOutput.some(e => e.type === 'thinking');
    expect(hasThinking).toBe(false);
  });

  it('adds waiting spinner after tool_end', () => {
    const events: TestEvent[] = [
      { type: 'step_header', step: 1 },
      { type: 'tool_start', tool_name: 'mem0_memory' },
      { type: 'output', content: '{"results": [...]}' },
      { type: 'tool_end', tool_name: 'mem0_memory' }
    ];

    const processed = processEventsForSpinners(events);

    // Find tool_end
    const toolEndIndex = processed.findIndex(e => e.type === 'tool_end');
    expect(toolEndIndex).toBeGreaterThan(-1);

    // Next event should be thinking spinner
    const nextEvent = processed[toolEndIndex + 1];
    expect(nextEvent?.type).toBe('thinking');
    expect(nextEvent?.context).toBe('waiting');
    expect(nextEvent?.urgent).toBe(true);
  });

  it('handles complete operation flow with no gaps', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },
      { type: 'reasoning', content: 'Planning...' },
      { type: 'step_header', step: 1 },
      { type: 'tool_start', tool_name: 'http_request' },
      { type: 'output', content: 'Response data' },
      { type: 'tool_end', tool_name: 'http_request' },
      { type: 'reasoning', content: 'Analyzing results...' },
      { type: 'step_header', step: 2 },
      { type: 'tool_start', tool_name: 'shell' },
      { type: 'output', content: 'Command output' },
      { type: 'tool_invocation_end' }
    ];

    const processed = processEventsForSpinners(events);

    // Validate each transition has appropriate spinner coverage
    let lastEventType: EventType | null = null;
    let hasSpinnerBetween = false;

    for (let i = 0; i < processed.length; i++) {
      const event = processed[i];

      // Check critical transitions where spinners must appear
      if (lastEventType === 'operation_init' && event.type !== 'thinking') {
        throw new Error('Missing spinner after operation_init');
      }

      if (lastEventType === 'step_header' && event.type !== 'thinking') {
        throw new Error('Missing spinner after step_header');
      }

      if (lastEventType === 'tool_end' && event.type !== 'thinking' && event.type !== 'reasoning') {
        throw new Error('Missing spinner after tool_end');
      }

      if (event.type === 'thinking') {
        hasSpinnerBetween = true;
      }

      lastEventType = event.type;
    }

    expect(hasSpinnerBetween).toBe(true);
  });

  it('respects animationsEnabled=false', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },
      { type: 'step_header', step: 1 },
      { type: 'tool_end', tool_name: 'shell' }
    ];

    const processed = processEventsForSpinners(events, false);

    // Should not contain any thinking events
    const thinkingEvents = processed.filter(e => e.type === 'thinking');
    expect(thinkingEvents).toHaveLength(0);
  });

  it('validates all thinking events have urgent flag for immediate display', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },
      { type: 'reasoning', content: 'test' },
      { type: 'step_header', step: 1 },
      { type: 'tool_start', tool_name: 'test' },
      { type: 'output', content: 'test' },
      { type: 'tool_end', tool_name: 'test' }
    ];

    const processed = processEventsForSpinners(events);

    const thinkingEvents = processed.filter(e => e.type === 'thinking');

    // All automatically-added thinking events should have urgent flag
    for (const event of thinkingEvents) {
      expect(event.urgent).toBe(true);
    }

    // Should have thinking events for all major transitions
    expect(thinkingEvents.length).toBeGreaterThan(0);
  });

  it('validates thinking contexts are appropriate for each location', () => {
    const events: TestEvent[] = [
      { type: 'operation_init' },          // → 'startup'
      { type: 'reasoning', content: 'test' },
      { type: 'step_header', step: 1 },    // → 'tool_preparation' (persists through tool_start)
      { type: 'tool_start', tool_name: 't' }, // (spinner already active, no new one added)
      { type: 'output', content: 'test' },
      { type: 'tool_end', tool_name: 't' } // → 'waiting'
    ];

    const processed = processEventsForSpinners(events);

    const thinkingEvents = processed.filter(e => e.type === 'thinking');

    // Verify contexts are set appropriately
    // Note: tool_preparation spinner persists during tool_start (not replaced)
    expect(thinkingEvents[0].context).toBe('startup');
    expect(thinkingEvents[1].context).toBe('tool_preparation');
    expect(thinkingEvents[2].context).toBe('waiting');

    // Total should be 3 thinking events (startup, tool_preparation, waiting)
    expect(thinkingEvents.length).toBe(3);
  });
});