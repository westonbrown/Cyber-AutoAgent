/**
 * Unconstrained Terminal - Full terminal buffer streaming display
 * 
 * Inspired by gemini-cli and codex implementations that use React Ink's
 * Static component for smooth, unconstrained output without height limits.
 * 
 * This component allows the full agent output to flow naturally without
 * artificial height constraints, preventing text overlap and cutoff issues.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Box, Text, Static } from 'ink';
import { StreamDisplay, DisplayStreamEvent } from './StreamDisplay.js';
import { DirectDockerService } from '../services/DirectDockerService.js';
import { themeManager } from '../themes/theme-manager.js';

interface UnconstrainedTerminalProps {
  dockerService: DirectDockerService;
  sessionId: string;
  terminalWidth?: number;
  collapsed?: boolean;
  onEvent?: (event: any) => void;
  onMetricsUpdate?: (metrics: { tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number }) => void;
}

export const UnconstrainedTerminal: React.FC<UnconstrainedTerminalProps> = React.memo(({
  dockerService,
  sessionId,
  terminalWidth = 80,
  collapsed = false,
  onEvent,
  onMetricsUpdate
}) => {
  // Direct event rendering without Static component
  const [completedEvents, setCompletedEvents] = useState<DisplayStreamEvent[]>([]);
  const [activeEvents, setActiveEvents] = useState<DisplayStreamEvent[]>([]);
  const [metrics, setMetrics] = useState({
    tokens: 0,
    cost: 0,
    duration: '0s',
    memoryOps: 0,
    evidence: 0
  });
  
  // State for event processing - replacing EventAggregator with React patterns
  const [activeThinking, setActiveThinking] = useState(false);
  const [activeReasoning, setActiveReasoning] = useState(false);
  const [currentToolId, setCurrentToolId] = useState<string | undefined>(undefined);
  const [lastOutputContent, setLastOutputContent] = useState('');
  const [lastOutputTime, setLastOutputTime] = useState(0);
  const delayedThinkingTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  // Constants for event processing
  const COMMAND_BUFFER_MS = 100;
  const OUTPUT_DEDUPE_TIME_MS = 1000;
  const theme = themeManager.getCurrentTheme();
  
  // Event processing function - replaces EventAggregator.processEvent
  const processEvent = (event: any): DisplayStreamEvent[] => {
    const results: DisplayStreamEvent[] = [];
    
    switch (event.type) {
      case 'step_header':
        // End any active reasoning session
        setActiveReasoning(false);
        
        results.push({
          type: 'step_header',
          step: event.step,
          maxSteps: event.maxSteps,
          operation: event.operation,
          duration: event.duration
        } as DisplayStreamEvent);
        break;
        
      case 'reasoning':
        // Python backend sends complete reasoning blocks
        if (event.content && event.content.trim()) {
          // Clear any active thinking animations when reasoning is shown
          if (activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            setActiveThinking(false);
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
        if (!activeReasoning && !activeThinking) {
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
        // Handle delayed thinking start - pass through and mark as active
        if (!activeThinking && !activeReasoning) {
          setActiveThinking(true);
          results.push(event as DisplayStreamEvent);
        }
        break;
        
      case 'tool_start':
        // Clear any active thinking when tool starts
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        
        setCurrentToolId(event.toolId);
        
        results.push({
          type: 'tool_start',
          tool_name: event.toolName || event.tool_name || '',
          tool_input: event.args || event.tool_input || {},
          toolId: event.toolId,
          toolName: event.toolName
        } as DisplayStreamEvent);
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
        
        // Start thinking animation after commands are shown (use delayed event)
        if (!activeThinking && !activeReasoning) {
          results.push({
            type: 'delayed_thinking_start',
            context: 'tool_execution',
            startTime: Date.now(),
            delay: COMMAND_BUFFER_MS
          } as DisplayStreamEvent);
        }
        break;
        
      case 'output':
        // Handle tool output or general output with deduplication
        if (event.content) {
          // Basic deduplication
          const currentTime = Date.now();
          if (event.content === lastOutputContent && 
              currentTime - lastOutputTime < OUTPUT_DEDUPE_TIME_MS) {
            break; // Skip duplicate
          }
          setLastOutputContent(event.content);
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
        // Clear any active thinking when tool ends
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        
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
        
      default:
        // Pass through other events as-is
        results.push(event as DisplayStreamEvent);
        break;
    }
    
    return results;
  };

  useEffect(() => {
    
    // Listen for events from Docker service
    const handleEvent = (event: any) => {
      // Debug logging disabled for production use
      // console.error(`[DEBUG] UnconstrainedTerminal received event:`, {
      //   type: event.type,
      //   hasContent: !!event.content,
      //   hasMetrics: !!event.metrics,
      //   timestamp: new Date().toISOString()
      // });
      
      // Handle metrics updates separately
      if (event.type === 'metrics_update' && event.metrics) {
        const newMetrics = {
          tokens: event.metrics.tokens || metrics.tokens,
          cost: event.metrics.cost || metrics.cost,
          duration: event.metrics.duration || metrics.duration,
          memoryOps: event.metrics.memoryOps || metrics.memoryOps,
          evidence: event.metrics.evidence || metrics.evidence
        };
        setMetrics(newMetrics);
        if (onMetricsUpdate) {
          onMetricsUpdate({
            tokens: newMetrics.tokens,
            cost: newMetrics.cost,
            duration: newMetrics.duration,
            memoryOps: newMetrics.memoryOps,
            evidence: newMetrics.evidence
          });
        }
        if (onEvent) onEvent(event);
        return;
      }
      
      // Process event using direct React state management
      const processedEvents = processEvent(event);
      if (processedEvents.length > 0) {
        // Handle delayed thinking start events
        const regularEvents: DisplayStreamEvent[] = [];
        
        for (const processedEvent of processedEvents) {
          if (processedEvent.type === 'delayed_thinking_start') {
            // Clear any existing delayed thinking timer
            if (delayedThinkingTimerRef.current) {
              clearTimeout(delayedThinkingTimerRef.current);
            }
            
            // Set timer to start thinking animation after delay
            delayedThinkingTimerRef.current = setTimeout(() => {
              // Add spacing before thinking animation
              setCompletedEvents(prev => [...prev, 
                { type: 'output', content: '' } as DisplayStreamEvent,
                { type: 'output', content: '' } as DisplayStreamEvent
              ]);
              
              const thinkingEvent: DisplayStreamEvent = {
                type: 'thinking',
                context: (processedEvent as any).context || 'tool_execution',
                startTime: (processedEvent as any).startTime || Date.now()
              };
              setActiveEvents(prev => [...prev, thinkingEvent]);
              delayedThinkingTimerRef.current = null;
            }, (processedEvent as any).delay || 100);
          } else {
            // Clear delayed thinking timer if we get output/error events
            if (processedEvent.type === 'output' || processedEvent.type === 'error' || processedEvent.type === 'thinking_end') {
              if (delayedThinkingTimerRef.current) {
                clearTimeout(delayedThinkingTimerRef.current);
                delayedThinkingTimerRef.current = null;
              }
              
              // Move thinking events to static when done
              if (processedEvent.type === 'thinking_end') {
                setActiveEvents(prev => {
                  const nonThinking = prev.filter(e => e.type !== 'thinking');
                  return nonThinking;
                });
              }
            }
            regularEvents.push(processedEvent);
          }
        }
        
        if (regularEvents.length > 0) {
          // Add completed events to completed list
          const newCompletedEvents = regularEvents
            .filter(e => e.type !== 'thinking' && e.type !== 'thinking_end');
          
          if (newCompletedEvents.length > 0) {
            setCompletedEvents(prev => [...prev, ...newCompletedEvents]);
          }
          
          // Keep thinking events in active display
          const thinkingEvents = regularEvents.filter(e => e.type === 'thinking');
          if (thinkingEvents.length > 0) {
            setActiveEvents(prev => [...prev, ...thinkingEvents]);
          }
        }
      }
      
      // Forward original event to parent
      if (onEvent) {
        onEvent(event);
      }
    };

    // Subscribe to events
    dockerService.on('event', handleEvent);
    
    // Event flushing no longer needed - events are processed directly
    
    // Handle completion to reset state
    const handleComplete = () => {
      // Clear any delayed thinking timers
      if (delayedThinkingTimerRef.current) {
        clearTimeout(delayedThinkingTimerRef.current);
      }
      
      // No need to flush events - they are processed immediately
      
      // Clear any active events
      setActiveEvents([]);
    };
    
    dockerService.on('complete', handleComplete);
    dockerService.on('stopped', handleComplete);

    // Cleanup
    return () => {
      // Clean up any delayed thinking timers
      if (delayedThinkingTimerRef.current) {
        clearTimeout(delayedThinkingTimerRef.current);
      }
      dockerService.off('event', handleEvent);
      dockerService.off('complete', handleComplete);
      dockerService.off('stopped', handleComplete);
    };
  }, [dockerService, onEvent, metrics, onMetricsUpdate, sessionId]);

  if (collapsed) {
    return null;
  }

  return (
    <Box flexDirection="column" width="100%" flexGrow={1}>
      {/* Completed events - use Static for proper scrolling */}
      {completedEvents.length > 0 && (
        <Static items={completedEvents}>
          {(event, index) => (
            <Box key={`event-${index}-${event.type}-${Date.now()}`}>
              <StreamDisplay events={[event]} />
            </Box>
          )}
        </Static>
      )}
      
      {/* Add spacing after completed events before footer */}
      {completedEvents.length > 0 && activeEvents.length === 0 && (
        <Box>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
        </Box>
      )}
      
      {/* Active events (like thinking animations) - rendered dynamically */}
      {activeEvents.length > 0 && (
        <Box width="100%">
          <StreamDisplay events={activeEvents} />
          
          {/* Add proper spacing between animation and footer */}
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
          <Text> </Text>
        </Box>
      )}
    </Box>
  );
});