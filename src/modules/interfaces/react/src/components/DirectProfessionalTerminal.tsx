/**
 * Direct Professional Terminal - Optimized for smooth streaming
 * 
 * Features:
 * - Virtual scrolling for large event streams
 * - Flicker-free rendering with proper buffering
 * - Smooth scrolling during active operations
 * - Prevents black screen issues during streaming
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, useInput, Text } from 'ink';
import { StreamDisplay, DisplayStreamEvent } from './StreamDisplay.js';
import { DirectDockerService } from '../services/DirectDockerService.js';
import { EventAggregator } from '../utils/eventAggregator.js';
import { useStreamingOptimization } from '../hooks/useStreamingOptimization.js';
import { themeManager } from '../themes/theme-manager.js';

interface DirectProfessionalTerminalProps {
  dockerService: DirectDockerService;
  sessionId: string;
  terminalWidth?: number;
  terminalHeight?: number;
  collapsed?: boolean;
  onEvent?: (event: any) => void;
  onMetricsUpdate?: (metrics: { tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number }) => void;
}

export const DirectProfessionalTerminal: React.FC<DirectProfessionalTerminalProps> = React.memo(({
  dockerService,
  sessionId,
  terminalWidth = 80,
  terminalHeight = 24,
  collapsed = false,
  onEvent,
  onMetricsUpdate
}) => {
  const [events, setEvents] = useState<DisplayStreamEvent[]>([]);
  const [activeThinking, setActiveThinking] = useState<{context: string; startTime: number} | null>(null);
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
  
  // Use streaming optimization hook
  const {
    visibleEvents,
    scrollPosition,
    scrollUp,
    scrollDown,
    scrollToBottom,
    isScrollable
  } = useStreamingOptimization(events, terminalHeight, {
    maxVisibleEvents: 50,
    virtualScrolling: true,
    renderDebounce: 100
  });
  
  // Handle keyboard input for scrolling
  useInput((input, key) => {
    if (!isScrollable) return;
    
    if (key.upArrow) {
      scrollUp();
    } else if (key.downArrow) {
      scrollDown();
    } else if (key.pageUp) {
      scrollUp(10);
    } else if (key.pageDown) {
      scrollDown(10);
    } else if (input === 'h' && key.ctrl) {
      scrollUp(999999); // Scroll to top (Ctrl+H for Home)
    } else if (input === 'e' && key.ctrl) {
      scrollToBottom(); // Ctrl+E for End
    }
  });

  useEffect(() => {
    let flushInterval: NodeJS.Timeout;
    
    // Listen for events from Docker service
    const handleEvent = (event: any) => {
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
              setEvents(prevEvents => [...prevEvents, {
                type: 'thinking',
                context: (processedEvent as any).context || 'tool_execution',
                startTime: (processedEvent as any).startTime || Date.now()
              }]);
              delayedThinkingTimerRef.current = null;
            }, (processedEvent as any).delay || 100);
          } else {
            // Clear delayed thinking timer if we get output/error events
            if (processedEvent.type === 'output' || processedEvent.type === 'error' || processedEvent.type === 'thinking_end') {
              if (delayedThinkingTimerRef.current) {
                clearTimeout(delayedThinkingTimerRef.current);
                delayedThinkingTimerRef.current = null;
              }
            }
            regularEvents.push(processedEvent);
          }
        }
        
        if (regularEvents.length > 0) {
          setEvents(prev => [...prev, ...regularEvents]);
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
          setEvents(prev => [...prev, ...pendingEvents]);
        }
      }
    }, 100); // Increased to allow better buffering
    
    // Handle completion to flush buffers
    const handleComplete = () => {
      // Clear interval
      if (flushInterval) {
        clearInterval(flushInterval);
      }
      
      // Flush any remaining pending events
      const pendingEvents = aggregatorRef.current.flushPendingEvents();
      if (pendingEvents.length > 0) {
        setEvents(prev => [...prev, ...pendingEvents]);
      }
      
      // Flush any other buffers
      const finalEvents = aggregatorRef.current.flush();
      if (finalEvents.length > 0) {
        setEvents(prev => [...prev, ...finalEvents]);
      }
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
  }, [dockerService, onEvent, metrics, onMetricsUpdate]);

  if (collapsed) {
    return null;
  }

  return (
    <Box flexDirection="column" height="100%">
      {/* Virtual scrolling container - use full height */}
      <Box flexDirection="column" height="100%">
        <StreamDisplay events={visibleEvents} />
      </Box>
      
      {/* Scroll indicator */}
      {isScrollable && (
        <Box flexDirection="row" justifyContent="space-between" marginTop={1}>
          <Text color={theme.muted}>
            {scrollPosition > 0 ? '↑ ' : '  '}
            Line {scrollPosition + 1}-{Math.min(scrollPosition + visibleEvents.length, events.length)} of {events.length}
            {scrollPosition + visibleEvents.length < events.length ? ' ↓' : '  '}
          </Text>
          <Text color={theme.muted}>
            {scrollPosition + visibleEvents.length >= events.length ? '[END]' : '[↓ More]'}
          </Text>
        </Box>
      )}
    </Box>
  );
});