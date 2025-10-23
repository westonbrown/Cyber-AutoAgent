/**
 * Test fixtures for event burst scenarios
 * Used for testing UI stability under high event throughput
 */

import { DisplayStreamEvent } from '../../src/components/StreamDisplay.js';
import { EventType } from '../../src/types/events.js';

/**
 * Generate a burst of tool execution events
 */
export function generateToolBurst(count: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  for (let i = 0; i < count; i++) {
    events.push({
      type: 'tool_start',
      tool_name: `test_tool_${i}`,
      tool_input: { param: `value_${i}` },
      id: `tool-start-${i}`,
      timestamp
    });

    events.push({
      type: 'tool_output',
      tool: `test_tool_${i}`,
      status: 'success',
      output: `Output from tool ${i}`,
      id: `tool-output-${i}`,
      timestamp
    });
  }

  return events;
}

/**
 * Generate a burst of reasoning events
 */
export function generateReasoningBurst(count: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  for (let i = 0; i < count; i++) {
    events.push({
      type: EventType.REASONING_START,
      id: `reasoning-${i}`,
      sessionId: 'test-session',
      timestamp,
      delta: `Reasoning step ${i}: analyzing the situation...`,
      isReasoning: true
    });
  }

  return events;
}

/**
 * Generate a burst of metrics update events
 */
export function generateMetricsBurst(count: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  for (let i = 0; i < count; i++) {
    events.push({
      type: 'metrics_update',
      metrics: {
        tokens: 100 * (i + 1),
        cost: 0.001 * (i + 1),
        duration: `${i + 1}s`,
        memoryOps: i,
        evidence: i
      },
      id: `metrics-${i}`,
      timestamp
    });
  }

  return events;
}

/**
 * Generate a burst of error events
 */
export function generateErrorBurst(count: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  for (let i = 0; i < count; i++) {
    events.push({
      type: 'error',
      content: `Error ${i}: Something went wrong`,
      error: `Error details for event ${i}`,
      id: `error-${i}`,
      timestamp
    });
  }

  return events;
}

/**
 * Generate a mixed burst of various event types
 */
export function generateMixedBurst(count: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  for (let i = 0; i < count; i++) {
    const eventType = i % 5;

    switch (eventType) {
      case 0:
        events.push({
          type: 'tool_start',
          tool_name: `mixed_tool_${i}`,
          tool_input: { data: `test_${i}` },
          id: `mixed-tool-${i}`,
          timestamp
        });
        break;
      case 1:
        events.push({
          type: 'reasoning',
          content: `Reasoning: step ${i}`,
          id: `mixed-reasoning-${i}`,
          timestamp
        });
        break;
      case 2:
        events.push({
          type: 'output',
          content: `Output from step ${i}`,
          id: `mixed-output-${i}`,
          timestamp
        });
        break;
      case 3:
        events.push({
          type: EventType.METRICS_UPDATE,
          id: `mixed-metrics-${i}`,
          sessionId: 'test-session',
          timestamp,
          usage: {
            inputTokens: 100 * i,
            outputTokens: 50 * i,
            totalTokens: 150 * i
          }
        });
        break;
      case 4:
        events.push({
          type: 'command',
          content: `ls -la /test/${i}`,
          id: `mixed-command-${i}`,
          timestamp
        });
        break;
    }
  }

  return events;
}

/**
 * Generate a swarm coordination burst
 */
export function generateSwarmBurst(agentCount: number, stepsPerAgent: number): DisplayStreamEvent[] {
  const events: DisplayStreamEvent[] = [];
  const timestamp = new Date().toISOString();

  events.push({
    type: 'swarm_start',
    agent_names: Array.from({ length: agentCount }, (_, i) => `Agent_${i}`),
    task: 'Test swarm coordination',
    id: 'swarm-start',
    timestamp
  });

  for (let agent = 0; agent < agentCount; agent++) {
    for (let step = 0; step < stepsPerAgent; step++) {
      events.push({
        type: EventType.SWARM_AGENT,
        id: `swarm-agent-${agent}-${step}`,
        sessionId: 'test-session',
        timestamp,
        agentName: `Agent_${agent}`,
        agentId: `agent-${agent}`
      });
    }

    if (agent < agentCount - 1) {
      events.push({
        type: 'swarm_handoff',
        from_agent: `Agent_${agent}`,
        to_agent: `Agent_${agent + 1}`,
        message: `Handing off to next agent`,
        id: `swarm-handoff-${agent}`,
        timestamp
      });
    }
  }

  events.push({
    type: 'swarm_complete',
    final_agent: `Agent_${agentCount - 1}`,
    execution_count: agentCount * stepsPerAgent,
    id: 'swarm-complete',
    timestamp
  });

  return events;
}

/**
 * Predefined burst scenarios for common test cases
 */
export const burstScenarios = {
  small: {
    tools: generateToolBurst(10),
    reasoning: generateReasoningBurst(10),
    metrics: generateMetricsBurst(10),
    errors: generateErrorBurst(10),
    mixed: generateMixedBurst(10)
  },
  medium: {
    tools: generateToolBurst(100),
    reasoning: generateReasoningBurst(100),
    metrics: generateMetricsBurst(100),
    errors: generateErrorBurst(100),
    mixed: generateMixedBurst(100)
  },
  large: {
    tools: generateToolBurst(1000),
    reasoning: generateReasoningBurst(1000),
    metrics: generateMetricsBurst(1000),
    errors: generateErrorBurst(1000),
    mixed: generateMixedBurst(1000)
  },
  swarm: {
    small: generateSwarmBurst(3, 5),
    medium: generateSwarmBurst(5, 10),
    large: generateSwarmBurst(10, 20)
  }
};
