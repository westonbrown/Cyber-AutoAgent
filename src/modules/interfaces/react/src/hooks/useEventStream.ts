/**
 * Custom hook for managing event streams
 * Simplifies event processing and state management
 */

import React from 'react';
import { DisplayStreamEvent } from '../components/StreamDisplay.js';
import { EVENT_TYPES } from '../constants/config.js';

interface EventStreamState {
  events: DisplayStreamEvent[];
  isThinking: boolean;
  currentStep: number;
  maxSteps: number;
  reasoningBuffer: string[];
  lastToolName: string | null;
}

interface EventStreamActions {
  addEvent: (event: DisplayStreamEvent) => void;
  clearEvents: () => void;
  processEvent: (event: DisplayStreamEvent) => void;
  flushReasoningBuffer: () => void;
}

export const useEventStream = (
  initialMaxSteps: number = 100
): [EventStreamState, EventStreamActions] => {
  const [state, setState] = React.useState<EventStreamState>({
    events: [],
    isThinking: false,
    currentStep: 0,
    maxSteps: initialMaxSteps,
    reasoningBuffer: [],
    lastToolName: null,
  });

  const actions = React.useMemo<EventStreamActions>(() => ({
    addEvent: (event: DisplayStreamEvent) => {
      setState(prev => ({
        ...prev,
        events: [...prev.events, event],
      }));
    },

    clearEvents: () => {
      setState(prev => ({
        ...prev,
        events: [],
        currentStep: 0,
        reasoningBuffer: [],
        lastToolName: null,
      }));
    },

    processEvent: (event: DisplayStreamEvent) => {
      setState(prev => {
        const newState = { ...prev };

        switch (event.type) {
          case EVENT_TYPES.STEP_HEADER:
            if ('step' in event && typeof event.step === 'number') {
              newState.currentStep = event.step;
            }
            if ('maxSteps' in event && typeof event.maxSteps === 'number') {
              newState.maxSteps = event.maxSteps;
            }
            break;

          case EVENT_TYPES.THINKING:
            newState.isThinking = true;
            break;

          case EVENT_TYPES.THINKING_END:
            newState.isThinking = false;
            break;

          case EVENT_TYPES.TOOL_START:
            if ('tool_name' in event && typeof event.tool_name === 'string') {
              newState.lastToolName = event.tool_name;
            }
            break;

          case EVENT_TYPES.REASONING:
            if ('content' in event && typeof event.content === 'string') {
              newState.reasoningBuffer.push(event.content);
            }
            break;
        }

        // Add event to list
        newState.events = [...prev.events, event];
        return newState;
      });
    },

    flushReasoningBuffer: () => {
      setState(prev => {
        if (prev.reasoningBuffer.length === 0) return prev;

        const reasoningEvent: DisplayStreamEvent = {
          type: EVENT_TYPES.REASONING,
          content: prev.reasoningBuffer.join(''),
        };

        return {
          ...prev,
          events: [...prev.events, reasoningEvent],
          reasoningBuffer: [],
        };
      });
    },
  }), []);

  return [state, actions];
};

/**
 * Hook for grouping events for optimized rendering
 */
export const useEventGroups = (events: DisplayStreamEvent[]) => {
  return React.useMemo(() => {
    const groups: Array<{
      type: 'reasoning_group' | 'single';
      events: DisplayStreamEvent[];
      startIdx: number;
    }> = [];

    let currentReasoningGroup: DisplayStreamEvent[] = [];
    let groupStartIdx = 0;

    events.forEach((event, idx) => {
      if (event.type === EVENT_TYPES.REASONING) {
        if (currentReasoningGroup.length === 0) {
          groupStartIdx = idx;
        }
        currentReasoningGroup.push(event);
      } else {
        // End current reasoning group if exists
        if (currentReasoningGroup.length > 0) {
          groups.push({
            type: 'reasoning_group',
            events: currentReasoningGroup,
            startIdx: groupStartIdx,
          });
          currentReasoningGroup = [];
        }

        // Add non-reasoning event as single
        groups.push({
          type: 'single',
          events: [event],
          startIdx: idx,
        });
      }
    });

    // Handle any remaining reasoning group
    if (currentReasoningGroup.length > 0) {
      groups.push({
        type: 'reasoning_group',
        events: currentReasoningGroup,
        startIdx: groupStartIdx,
      });
    }

    return groups;
  }, [events]);
};

/**
 * Hook for tracking swarm operations
 */
export interface SwarmOperation {
  id: string;
  agents: string[];
  currentAgent: string | null;
  handoffCount: number;
  startTime: number;
  endTime?: number;
  status: 'running' | 'completed' | 'failed';
}

export const useSwarmTracking = () => {
  const [swarmOperations, setSwarmOperations] = React.useState<Map<string, SwarmOperation>>(
    new Map()
  );
  const [activeSwarmId, setActiveSwarmId] = React.useState<string | null>(null);

  const startSwarm = React.useCallback((id: string, agents: string[]) => {
    const operation: SwarmOperation = {
      id,
      agents,
      currentAgent: agents[0] || null,
      handoffCount: 0,
      startTime: Date.now(),
      status: 'running',
    };

    setSwarmOperations(prev => new Map(prev).set(id, operation));
    setActiveSwarmId(id);
  }, []);

  const handoffAgent = React.useCallback((fromAgent: string, toAgent: string) => {
    if (!activeSwarmId) return;

    setSwarmOperations(prev => {
      const newMap = new Map(prev);
      const operation = newMap.get(activeSwarmId);
      if (operation) {
        operation.currentAgent = toAgent;
        operation.handoffCount++;
      }
      return newMap;
    });
  }, [activeSwarmId]);

  const completeSwarm = React.useCallback((id: string, status: 'completed' | 'failed' = 'completed') => {
    setSwarmOperations(prev => {
      const newMap = new Map(prev);
      const operation = newMap.get(id);
      if (operation) {
        operation.status = status;
        operation.endTime = Date.now();
      }
      return newMap;
    });
    
    if (activeSwarmId === id) {
      setActiveSwarmId(null);
    }
  }, [activeSwarmId]);

  const getActiveSwarm = React.useCallback(() => {
    return activeSwarmId ? swarmOperations.get(activeSwarmId) : null;
  }, [activeSwarmId, swarmOperations]);

  return {
    swarmOperations,
    activeSwarmId,
    startSwarm,
    handoffAgent,
    completeSwarm,
    getActiveSwarm,
  };
};