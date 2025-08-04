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
import { EventAggregator } from '../utils/eventAggregator.js';
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
  
  const aggregatorRef = useRef(new EventAggregator());
  const delayedThinkingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const theme = themeManager.getCurrentTheme();

  useEffect(() => {
    let flushInterval: NodeJS.Timeout;
    
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
      
      // Process event through aggregator
      const processedEvents = aggregatorRef.current.processEvent(event);
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
    
    // Set up interval to flush pending events
    flushInterval = setInterval(() => {
      if (aggregatorRef.current.hasPendingEvents()) {
        const pendingEvents = aggregatorRef.current.flushPendingEvents();
        if (pendingEvents.length > 0) {
          const newCompletedEvents = pendingEvents
            .filter(e => e.type !== 'thinking' && e.type !== 'thinking_end');
          
          if (newCompletedEvents.length > 0) {
            setCompletedEvents(prev => [...prev, ...newCompletedEvents]);
          }
        }
      }
    }, 100);
    
    // Handle completion to flush buffers
    const handleComplete = () => {
      // Clear interval
      if (flushInterval) {
        clearInterval(flushInterval);
      }
      
      // Flush any remaining pending events
      const pendingEvents = aggregatorRef.current.flushPendingEvents();
      const finalEvents = aggregatorRef.current.flush();
      const allFinalEvents = [...pendingEvents, ...finalEvents];
      
      if (allFinalEvents.length > 0) {
        const newCompletedEvents = allFinalEvents
          .filter(e => e.type !== 'thinking' && e.type !== 'thinking_end');
        
        if (newCompletedEvents.length > 0) {
          setCompletedEvents(prev => [...prev, ...newCompletedEvents]);
        }
      }
      
      // Clear any active events
      setActiveEvents([]);
    };
    
    dockerService.on('complete', handleComplete);
    dockerService.on('stopped', handleComplete);

    // Cleanup
    return () => {
      if (flushInterval) {
        clearInterval(flushInterval);
      }
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