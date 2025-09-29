/**
 * Event Renderer Test Component
 * 
 * Simple component for testing event rendering in isolation.
 * Uses the actual MemoizedEventLine component from StreamDisplay
 * to ensure tests validate real rendering behavior.
 */

import React from 'react';
import { Box, Text } from 'ink';
import { EventLine as MemoizedEventLine } from '../../src/components/StreamDisplay.tsx';

/**
 * EventRenderer - Test wrapper for event display
 * 
 * @param {Object} props
 * @param {Object} props.event - The event to render
 * @param {Object} props.context - Additional context (swarmActive, currentAgent, etc.)
 */
export const EventRenderer = ({ event, context = {} }) => {
  // Simulate the context that would normally be provided by StreamDisplay
  const toolStates = new Map();
  const animationsEnabled = false; // Disable animations for testing
  
  // Apply context to event if needed
  const processedEvent = { ...event };
  
  // If this is a step_header during swarm, enhance it
  if (event.type === 'step_header' && context.swarmActive) {
    processedEvent.is_swarm_operation = true;
    processedEvent.swarm_agent = processedEvent.swarm_agent || context.currentAgent;
  }
  
  // If this is a handoff_to_agent tool, transform it
  if (event.type === 'tool_start' && event.tool_name === 'handoff_to_agent' && context.swarmActive) {
    // Also emit a swarm_handoff event
    return (
      <Box flexDirection="column">
        {/* Swarm handoff display */}
        <MemoizedEventLine
          event={{
            type: 'swarm_handoff',
            from_agent: context.currentAgent || 'unknown',
            to_agent: event.tool_input?.agent_name || 'unknown',
            message: event.tool_input?.message || '',
            shared_context: event.tool_input?.context || {}
          }}
          toolStates={toolStates}
          animationsEnabled={animationsEnabled}
        />
        {/* Original tool display */}
        <MemoizedEventLine
          event={processedEvent}
          toolStates={toolStates}
          animationsEnabled={animationsEnabled}
        />
      </Box>
    );
  }
  
  // Render the event
  return (
    <Box flexDirection="column">
      <MemoizedEventLine
        event={processedEvent}
        toolStates={toolStates}
        animationsEnabled={animationsEnabled}
      />
    </Box>
  );
};

export default EventRenderer;