/**
 * Terminal - Full terminal buffer streaming display
 * 
 * Uses React Ink's Static component for smooth output without height limits.
 * 
 * This component allows the full agent output to flow naturally without
 * artificial height constraints, preventing text overlap and cutoff issues.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Box, Text } from 'ink';
import { StreamDisplay, StaticStreamDisplay, DisplayStreamEvent } from './StreamDisplay.js';
import { ExecutionService } from '../services/ExecutionService.js';
import { themeManager } from '../themes/theme-manager.js';
import { loggingService } from '../services/LoggingService.js';
import { useEventBatcher } from '../utils/useBatchedState.js';
import { normalizeEvent } from '../services/events/normalize.js';

interface TerminalProps {
  executionService: ExecutionService | null;
  sessionId: string;
  terminalWidth?: number;
  collapsed?: boolean;
  onEvent?: (event: any) => void;
  onMetricsUpdate?: (metrics: { tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number }) => void;
  animationsEnabled?: boolean;
}

export const Terminal: React.FC<TerminalProps> = React.memo(({
  executionService,
  sessionId,
  terminalWidth = 80,
  collapsed = false,
  onEvent,
  onMetricsUpdate,
  animationsEnabled = true
}) => {
  // Direct event rendering without Static component
  // No buffer limit - events are already persisted to disk in log files
  const [completedEvents, setCompletedEvents] = useState<DisplayStreamEvent[]>([]);
  const [activeEvents, setActiveEvents] = useState<DisplayStreamEvent[]>([]);
  const [metrics, setMetrics] = useState({
    tokens: 0,
    cost: 0,
    duration: '0s',
    memoryOps: 0,
    evidence: 0
  });
  
  // Throttle state for metrics emissions to parent
  const lastEmitRef = useRef<number>(0);
  const pendingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingMetricsRef = useRef<{ tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number } | null>(null);
  const EMIT_INTERVAL_MS = 300;
  
  // State for event processing - replacing EventAggregator with React patterns
  const [activeThinking, setActiveThinking] = useState(false);
  // Keep a ref in sync with activeThinking to avoid setState race conditions
  const activeThinkingRef = useRef(false);
  useEffect(() => { activeThinkingRef.current = activeThinking; }, [activeThinking]);
  const [activeReasoning, setActiveReasoning] = useState(false);
  const [currentToolId, setCurrentToolId] = useState<string | undefined>(undefined);
  const [lastOutputContent, setLastOutputContent] = useState('');
  const [lastOutputTime, setLastOutputTime] = useState(0);
  
  // Swarm operation tracking for proper event enhancement
  const [swarmActive, setSwarmActive] = useState(false);
  const [currentSwarmAgent, setCurrentSwarmAgent] = useState<string | null>(null);
  const swarmHandoffSequenceRef = useRef(0);
  const delayedThinkingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const seenThinkingThisPhaseRef = useRef<boolean>(false);
  const suppressTerminationBannerRef = useRef<boolean>(false);
  // Duplicate emission resolved in ReactBridgeHandler
  // Throttle for active tail updates when animations are disabled
  const activeUpdateTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingActiveUpdaterRef = useRef<((prev: DisplayStreamEvent[]) => DisplayStreamEvent[]) | null>(null);
  const ACTIVE_EMIT_INTERVAL_MS = 80;

  const setActiveThrottled = (
    updater: React.SetStateAction<DisplayStreamEvent[]>
  ) => {
    if (animationsEnabled) {
      setActiveEvents(updater);
      return;
    }

    const fn: (prev: DisplayStreamEvent[]) => DisplayStreamEvent[] =
      typeof updater === 'function' ? (updater as (prev: DisplayStreamEvent[]) => DisplayStreamEvent[]) : (() => updater as DisplayStreamEvent[]);
    pendingActiveUpdaterRef.current = fn;
    if (activeUpdateTimerRef.current) {
      clearTimeout(activeUpdateTimerRef.current);
    }
    activeUpdateTimerRef.current = setTimeout(() => {
      const u = pendingActiveUpdaterRef.current;
      pendingActiveUpdaterRef.current = null;
      activeUpdateTimerRef.current = null;
      if (u) {
        setActiveEvents(prev => u(prev));
      }
    }, ACTIVE_EMIT_INTERVAL_MS);
  };
  
  // Constants for event processing
  const COMMAND_BUFFER_MS = 100;
  const OUTPUT_DEDUPE_TIME_MS = 500;
  const theme = themeManager.getCurrentTheme();
  
  // Event processing function - replaces EventAggregator.processEvent
  const processEvent = (event: any): DisplayStreamEvent[] => {
    const results: DisplayStreamEvent[] = [];

    // Test markers for integration tests
    const testMode = process.env.CYBER_TEST_MODE === 'true';
    const emitTestMarker = (summary: string) => {
      if (testMode) {
        try { loggingService.info(`[TEST_EVENT] ${summary}`); } catch {}
        try { console.log(`[TEST_EVENT] ${summary}`); } catch {}
      }
    };
    
    switch (event.type) {
      case 'step_header':
        emitTestMarker(`step_header step=${event.step} max=${event.maxSteps}`);
        // End any active reasoning session
        setActiveReasoning(false);
        // Reset output suppression for next operation phase
        suppressTerminationBannerRef.current = false;
        
        // Track swarm agent from step header
        if (event.is_swarm_operation && event.swarm_agent) {
          setCurrentSwarmAgent(event.swarm_agent);
        }
        
        results.push({
          type: 'step_header',
          step: event.step,
          maxSteps: event.maxSteps,
          operation: event.operation,
          duration: event.duration,
          // Include swarm-related properties if present
          is_swarm_operation: event.is_swarm_operation,
          swarm_agent: event.swarm_agent || currentSwarmAgent,
          swarm_sub_step: event.swarm_sub_step,
          swarm_max_sub_steps: event.swarm_max_sub_steps,
          swarm_agent_max: event.swarm_agent_max,  // Per-agent max steps
          swarm_total_iterations: event.swarm_total_iterations,  // Pass through for x/y display
          swarm_max_iterations: event.swarm_max_iterations,      // Pass through for x/y display
          agent_count: event.agent_count,  // Number of agents in swarm
          swarm_context: event.swarm_context || (swarmActive ? 'Multi-Agent Operation' : undefined)
        } as DisplayStreamEvent);
        break;
        
      case 'reasoning':
        emitTestMarker('reasoning');
        // Python backend sends complete reasoning blocks
        if (event.content && event.content.trim()) {
          // Clear any active thinking animations when reasoning is shown
          if (activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            setActiveThinking(false);
          }
          // Cancel any pending delayed thinking and mark seen
          if (delayedThinkingTimerRef.current) {
            clearTimeout(delayedThinkingTimerRef.current);
            delayedThinkingTimerRef.current = null;
          }
          seenThinkingThisPhaseRef.current = true;
          
          // Update swarm agent if present in event
          if (event.swarm_agent && swarmActive) {
            setCurrentSwarmAgent(event.swarm_agent);
          }
          
          // Start reasoning session
          setActiveReasoning(true);
          
          // Emit the complete reasoning block directly
          results.push({
            type: 'reasoning',
            content: event.content.trim()
          } as DisplayStreamEvent);
        }
        break;
        
      case 'thinking':
        // Handle thinking start without conflicting with reasoning
        if (!activeReasoning && !activeThinkingRef.current) {
          // If a delayed thinking timer is pending, cancel it to avoid duplicate spinner
          if (delayedThinkingTimerRef.current) {
            clearTimeout(delayedThinkingTimerRef.current);
            delayedThinkingTimerRef.current = null;
          }
          // Cancel any pending delayed thinking
          if (delayedThinkingTimerRef.current) {
            clearTimeout(delayedThinkingTimerRef.current);
            delayedThinkingTimerRef.current = null;
          }
          seenThinkingThisPhaseRef.current = true;
          // Ensure no duplicate thinking events remain active
          setActiveThrottled(prev => prev.filter(e => e.type !== 'thinking'));
          setActiveThinking(true);
          results.push({
            type: 'thinking',
            context: event.context,
            startTime: event.startTime,
            metadata: event.metadata
          } as DisplayStreamEvent);
        }
        break;
        
      case 'thinking_end':
        if (activeThinking) {
          setActiveThinking(false);
          results.push({
            type: 'thinking_end'
          } as DisplayStreamEvent);
        }
        break;
        
      case 'delayed_thinking_start':
        // Suppress delayed thinking spacers when animations are disabled
        if (!animationsEnabled) {
          break;
        }
        // Handle delayed thinking start - pass through and mark as active
        if (!activeThinking && !activeReasoning) {
          setActiveThinking(true);
          results.push(event as DisplayStreamEvent);
        }
        break;
        
      case 'tool_start':
        emitTestMarker(`tool_start tool=${event.toolName || event.tool_name}`);
        // Get the tool ID from the event (support both camel/snake)
        let toolId: string | undefined = event.toolId || event.tool_id;
        // Some tools (e.g., orchestrators) don't emit IDs; use a stable fallback so headers render.
        if (!toolId) {
          const bucket = Math.floor((event.timestamp ? Date.parse(event.timestamp) : Date.now()) / 1000); // 1s buckets
          const name = event.toolName || event.tool_name || 'tool';
          toolId = `${name}-${bucket}`;
        }
        
        // Update swarm agent if present in event
        if (event.swarm_agent && swarmActive) {
          setCurrentSwarmAgent(event.swarm_agent);
        }
        
        // Check if this is a handoff_to_agent tool and update swarm agent
        const toolName = event.toolName || event.tool_name || '';
        if (toolName === 'handoff_to_agent' && swarmActive) {
          // Extract target agent from tool_input
          const toolInput = event.args || event.tool_input || {};
          // Check both 'agent' and 'agent_name' fields (backend uses agent_name)
          const targetAgent = toolInput.agent || toolInput.agent_name;
          if (targetAgent) {
            setCurrentSwarmAgent(targetAgent);
          }
        }
        
        // Always render the tool header now that we have a deterministic id
        
        // Reset phase flags
        seenThinkingThisPhaseRef.current = false;
        setCurrentToolId(toolId);
        // Entering a tool phase should end any active reasoning session
        if (activeReasoning) {
          setActiveReasoning(false);
        }
        
        // Note: Do NOT synthesize swarm_handoff here; backend already emits swarm_handoff events
        // Always emit the tool event
        results.push({
          type: 'tool_start',
          tool_name: toolName,
          tool_input: event.args || event.tool_input || {},
          toolId: toolId,
          toolName: event.toolName,
          tool_id: toolId  // Include tool_id for compatibility
        } as DisplayStreamEvent);

        // Show single unified thinking animation
        if (!activeReasoning && !activeThinkingRef.current) {
          if (delayedThinkingTimerRef.current) {
            clearTimeout(delayedThinkingTimerRef.current);
            delayedThinkingTimerRef.current = null;
          }
          
          setActiveThinking(true);
          seenThinkingThisPhaseRef.current = true;
          results.push({
            type: 'thinking',
            context: 'tool_execution',
            startTime: Date.now()
          } as DisplayStreamEvent);
        }
        break;
        
      case 'tool_input_update':
        // Handle tool input updates from swarm agents
        // Pass through the event with tool_id and updated input
        results.push({
          type: 'tool_input_update',
          tool_id: event.tool_id || event.toolId,
          tool_input: event.tool_input || event.args || {}
        } as DisplayStreamEvent);
        break;
        
      case 'tool_input_corrected':
        // Handle corrected tool input from backend (e.g., parsed shell commands)
        // This fixes the [object Object] display issue for shell commands
        results.push({
          type: 'tool_input_update',
          tool_id: event.tool_id || event.toolId,
          tool_input: event.tool_input || {}
        } as DisplayStreamEvent);
        break;

      case 'tool_invocation_start':
        // Skip this event - the backend emits both tool_start and tool_invocation_start
        // We only need to process tool_start which has more complete information
        // This prevents duplicate tool displays in the UI
        break;
        
      case 'tool_invocation_end':
        // Some backends emit tool_invocation_end without a corresponding tool_end.
        // Ensure we stop any active thinking spinner and reset tool state to avoid "still running" UI.
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        if (delayedThinkingTimerRef.current) {
          clearTimeout(delayedThinkingTimerRef.current);
          delayedThinkingTimerRef.current = null;
        }
        seenThinkingThisPhaseRef.current = false;
        setCurrentToolId(undefined);
        // Optionally, we do not emit a separate tool_end display item here to avoid duplicates
        break;
        
      case 'shell_command':
        results.push({
          type: 'shell_command',
          command: event.command,
          toolId: currentToolId,
          id: `shell_${Date.now()}`,
          timestamp: new Date().toISOString(),
          sessionId: 'current'
        } as DisplayStreamEvent);
        // Don't add separate animations for shell commands - handled by parent tool
        break;

      case 'command':
        // Generic command event - don't add separate animations
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'output':
        emitTestMarker('output');
        // Handle tool output or general output with deduplication
        if (event.content) {
          // Update swarm agent if present in event
          if (event.swarm_agent && swarmActive) {
            setCurrentSwarmAgent(event.swarm_agent);
          }
          
          // Suppress verbose termination block lines after ESC
          if (suppressTerminationBannerRef.current) {
            const line = String(event.content).trim();
            const isDivider = /^([\u2500-\u257F\u2501\u2509\u250A\u250B\u250C\u250D\u250E\u250F\u2510\u2511\u2512\u2513\u2574\u2576\u2501\u2500\-\=\_\~\s]){10,}$/.test(line) || /\u2501|\u2500|\u2502|\u2503|\u2505|\u2507|\u2509/.test(line);
            const terminationPhrases = [
              'ESC Kill Switch activated',
              'Assessment stopped by user',
              'OPERATION TERMINATED BY USER',
              'Assessment was stopped before completion',
              'You can start a new assessment or review partial results'
            ];
            const isTerminationLine = terminationPhrases.some(p => line.includes(p));
            if (!line || isDivider || isTerminationLine) {
              break; // skip noisy termination lines
            }
          }
          // Enhanced deduplication - check for similar content
          const currentTime = Date.now();
          const contentStr = String(event.content);
          
          // Check if this is a duplicate or subset of the last output
          if (lastOutputContent && currentTime - lastOutputTime < OUTPUT_DEDUPE_TIME_MS) {
            // Exact match
            if (contentStr === lastOutputContent) {
              break; // Skip duplicate
            }
            
            // Check if one contains the other (common with Execution Summary vs raw output)
            if (contentStr.includes(lastOutputContent) || lastOutputContent.includes(contentStr)) {
              // Keep the longer/more complete version
              if (contentStr.length <= lastOutputContent.length) {
                break; // Skip this shorter/subset version
              }
            }
          }
          setLastOutputContent(contentStr);
          setLastOutputTime(currentTime);
          
          // Clear any active thinking when output appears
          if (activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            setActiveThinking(false);
          }
          
          results.push({
            type: 'output',
            content: event.content,
            toolId: currentToolId
          } as DisplayStreamEvent);
        }
        break;
        
      case 'tool_end':
        // Update swarm agent if present in event
        if (event.swarm_agent && swarmActive) {
          setCurrentSwarmAgent(event.swarm_agent);
        }
        
        // Clear any active thinking when tool ends
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        // Reset flags and cancel pending delayed thinking
        if (delayedThinkingTimerRef.current) {
          clearTimeout(delayedThinkingTimerRef.current);
          delayedThinkingTimerRef.current = null;
        }
        seenThinkingThisPhaseRef.current = false;
        
        results.push({
          type: 'tool_end',
          toolId: event.toolId,
          tool: event.toolName || 'unknown',
          id: `tool_end_${Date.now()}`,
          timestamp: new Date().toISOString(),
          sessionId: 'current'
        } as DisplayStreamEvent);
        setCurrentToolId(undefined);
        break;

      case 'operation_complete':
        // Clear any active states
        setActiveThinking(false);
        setActiveReasoning(false);
        
        results.push({
          type: 'metrics_update',
          metrics: event.metrics || {},
          duration: event.duration
        } as DisplayStreamEvent);
        break;
        
      case 'swarm_start':
        // Mark swarm as active and reset tracking
        setSwarmActive(true);
        swarmHandoffSequenceRef.current = 0;
        
        // Extract first agent if available
        if (event.agent_names && Array.isArray(event.agent_names) && event.agent_names.length > 0) {
          setCurrentSwarmAgent(event.agent_names[0]);
        }
        
        // Pass through swarm_start event with all details
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'swarm_handoff':
        // This event type doesn't exist in actual SDK - keeping for backwards compatibility
        // Actual handoffs use handoff_to_agent tool
        if (event.to_agent) {
          setCurrentSwarmAgent(event.to_agent);
        }
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'swarm_end':
      case 'swarm_complete':
        // Reset swarm tracking
        setSwarmActive(false);
        setCurrentSwarmAgent(null);
        swarmHandoffSequenceRef.current = 0;
        
        // Pass through swarm end event
        results.push(event as DisplayStreamEvent);
        break;
        
      default:
        // Pass through other events as-is
        results.push(event as DisplayStreamEvent);
        break;
    }
    
    return results;
  };

  useEffect(() => {
    
    // Listen for events from Docker service
    const handleEvent = (rawEvent: any) => {
      const event = normalizeEvent(rawEvent);
      // Debug logging disabled for production use
      // console.error(`[DEBUG] UnconstrainedTerminal received event:`, {
      //   type: event.type,
      //   hasContent: !!event.content,
      //   hasMetrics: !!event.metrics,
      //   timestamp: new Date().toISOString()
      // });
      
      // Handle metrics updates - backend sends cumulative totals, not deltas
      if (event.type === 'metrics_update' && event.metrics) {
        const newMetrics = {
          // Backend sends cumulative totals, use them directly
          tokens: event.metrics.tokens !== undefined ? event.metrics.tokens : metrics.tokens,
          cost: event.metrics.cost !== undefined ? event.metrics.cost : metrics.cost,
          // Duration and counts can be replaced
          duration: event.metrics.duration || metrics.duration,
          memoryOps: event.metrics.memoryOps !== undefined ? event.metrics.memoryOps : metrics.memoryOps,
          evidence: event.metrics.evidence !== undefined ? event.metrics.evidence : metrics.evidence
        };
        // Emit a test marker for metrics updates to aid PTY-based assertions
        try {
          if (process.env.CYBER_TEST_MODE === 'true') {
            const marker = `[TEST_EVENT] metrics_update tokens=${newMetrics.tokens ?? ''} cost=${newMetrics.cost ?? ''} duration=${newMetrics.duration} memoryOps=${newMetrics.memoryOps} evidence=${newMetrics.evidence}`;
            loggingService.info(marker);
            console.log(marker);
          }
        } catch {}
        setMetrics(newMetrics);
        if (onMetricsUpdate) {
          const now = Date.now();
          const emitNow = now - lastEmitRef.current >= EMIT_INTERVAL_MS;
          if (emitNow) {
            lastEmitRef.current = now;
            // Clear any pending timer since we're emitting now
            if (pendingTimerRef.current) {
              clearTimeout(pendingTimerRef.current);
              pendingTimerRef.current = null;
            }
            onMetricsUpdate({
              tokens: newMetrics.tokens,
              cost: newMetrics.cost,
              duration: newMetrics.duration,
              memoryOps: newMetrics.memoryOps,
              evidence: newMetrics.evidence
            });
          } else {
            // Queue latest metrics and schedule trailing emit
            pendingMetricsRef.current = {
              tokens: newMetrics.tokens,
              cost: newMetrics.cost,
              duration: newMetrics.duration,
              memoryOps: newMetrics.memoryOps,
              evidence: newMetrics.evidence
            };
            if (!pendingTimerRef.current) {
              const delay = EMIT_INTERVAL_MS - (now - lastEmitRef.current);
              pendingTimerRef.current = setTimeout(() => {
                lastEmitRef.current = Date.now();
                const m = pendingMetricsRef.current;
                pendingMetricsRef.current = null;
                pendingTimerRef.current = null;
                if (m) {
                  onMetricsUpdate(m);
                }
              }, Math.max(0, delay));
            }
          }
        }
        if (onEvent) onEvent(event);
        return;
      }
      
      // Process event using direct React state management
      const processedEvents = processEvent(event);
      if (processedEvents.length > 0) {
        const regularEvents: DisplayStreamEvent[] = [];

        for (const processedEvent of processedEvents) {
          if (processedEvent.type === 'delayed_thinking_start') {
            // Skip entirely when animations are disabled
            if (!animationsEnabled) {
              continue;
            }
            // Clear any existing delayed thinking timer
            if (delayedThinkingTimerRef.current) {
              clearTimeout(delayedThinkingTimerRef.current);
            }
            // Set timer to start thinking animation after delay
            const delay = (processedEvent as any).delay || 100;
            delayedThinkingTimerRef.current = setTimeout(() => {
              // If a thinking spinner is already active, do not schedule another
              if (activeThinkingRef.current) {
                delayedThinkingTimerRef.current = null;
                return;
              }
              // Optional spacing before thinking animation to visually separate
              if (animationsEnabled) {
                setCompletedEvents(prev => [
                  ...prev,
                  { type: 'output', content: '' } as DisplayStreamEvent,
                  { type: 'output', content: '' } as DisplayStreamEvent
                ]);
              }
              const thinkingEvent: DisplayStreamEvent = {
                type: 'thinking',
                context: (processedEvent as any).context || 'tool_execution',
                startTime: (processedEvent as any).startTime || Date.now(),
                toolName: (processedEvent as any).toolName,
                toolCategory: (processedEvent as any).toolCategory
              } as DisplayStreamEvent;
              // Mark spinner active so backend 'thinking' doesn't duplicate it
              setActiveThinking(true);
              seenThinkingThisPhaseRef.current = true;
              // Remove any existing thinking before adding a new one (belt-and-braces)
              setActiveEvents(prev => [...prev.filter(e => e.type !== 'thinking'), thinkingEvent]);
              delayedThinkingTimerRef.current = null;
            }, delay);
            continue;
          }

          if (processedEvent.type === 'thinking_end') {
            // Move thinking events to static when done
            setActiveThrottled(prev => prev.filter(e => e.type !== 'thinking'));
            continue;
          }

          regularEvents.push(processedEvent);
        }

        if (regularEvents.length > 0) {
          // Move non-thinking items to completed
          const newCompletedEvents = regularEvents.filter(e => e.type !== 'thinking');
          if (newCompletedEvents.length > 0) {
            setCompletedEvents(prev => [...prev, ...newCompletedEvents]);
          }

          // Keep current thinking (if any) in active tail without duplication
          const thinkingEvents = regularEvents.filter(e => e.type === 'thinking');
          if (thinkingEvents.length > 0) {
            setActiveThrottled(prev => [
              ...prev.filter(e => e.type !== 'thinking'),
              ...thinkingEvents
            ]);
          }
        }
      }
      
      // Forward original event to parent
      if (onEvent) {
        onEvent(event);
      }
    };

    // Early return if no execution service
    if (!executionService) {
      return;
    }

    // Subscribe to events
    executionService.on('event', handleEvent);
    
    // Event flushing no longer needed - events are processed directly
    
    // Handle completion to reset state
    const handleComplete = () => {
      // Clear any delayed thinking timers
      if (delayedThinkingTimerRef.current) {
        clearTimeout(delayedThinkingTimerRef.current);
      }
      
      // No need to flush events - they are processed immediately
      
      // Clear any active events
      setActiveThrottled(() => []);
    };
    
    executionService.on('complete', handleComplete);
    // Use a stable function reference so we can remove it in cleanup
    const handleStopped = () => {
      // Mark that we should suppress verbose termination block lines
      suppressTerminationBannerRef.current = true;
      // Emit a concise stop summary event
      setCompletedEvents(prev => [
        ...prev,
        { type: 'stop_summary', timestamp: new Date().toISOString() } as unknown as DisplayStreamEvent
      ]);
      handleComplete();
    };
    executionService.on('stopped', handleStopped);

    // Cleanup
    return () => {
      // Clean up any delayed thinking timers
      if (delayedThinkingTimerRef.current) {
        clearTimeout(delayedThinkingTimerRef.current);
      }
      if (pendingTimerRef.current) {
        clearTimeout(pendingTimerRef.current);
        pendingTimerRef.current = null;
      }
      if (activeUpdateTimerRef.current) {
        clearTimeout(activeUpdateTimerRef.current);
        activeUpdateTimerRef.current = null;
      }
      executionService.off('event', handleEvent);
      executionService.off('complete', handleComplete);
      executionService.off('stopped', handleStopped);
    };
  }, [executionService, onEvent, metrics, onMetricsUpdate, sessionId]);

  if (collapsed) {
    return null;
  }

  return (
    <Box flexDirection="column" width="100%">
      {/* Completed stream (immutable, deduped): render via StaticStreamDisplay to avoid re-renders and keep normalization */}
      {completedEvents.length > 0 && (
        <StaticStreamDisplay events={completedEvents} />
      )}

      {/* Active tail: small, dynamic section only for in-flight events */}
      {activeEvents.length > 0 && (
        <StreamDisplay events={activeEvents} animationsEnabled={animationsEnabled} />
      )}
 
      {/* Trailing spacer to avoid footer crowding */}
      <Box>
        <Text> </Text>
      </Box>
    </Box>
  );
});