/**
 * Streaming Optimization Hook
 * 
 * Optimizes the terminal rendering during streaming operations to prevent
 * black screens, reduce flicker, and improve scrolling performance.
 * 
 * Inspired by Gemini CLI and Codex patterns for smooth terminal experiences.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';

interface StreamingOptions {
  // Maximum number of events to render at once
  maxVisibleEvents?: number;
  // Buffer size for smooth scrolling
  scrollBufferSize?: number;
  // Debounce delay for render updates
  renderDebounce?: number;
  // Enable virtual scrolling
  virtualScrolling?: boolean;
}

interface UseStreamingOptimizationResult {
  // Optimized events for display
  visibleEvents: any[];
  
  // Scroll position
  scrollPosition: number;
  
  // Control functions
  scrollUp: (lines?: number) => void;
  scrollDown: (lines?: number) => void;
  scrollToBottom: () => void;
  
  // Rendering helpers
  shouldConstrainHeight: boolean;
  isScrollable: boolean;
  
  // Performance metrics
  renderCount: number;
}

export const useStreamingOptimization = (
  events: any[],
  terminalHeight: number,
  options: StreamingOptions = {}
): UseStreamingOptimizationResult => {
  const {
    maxVisibleEvents = 100,
    scrollBufferSize = 20,
    renderDebounce = 50,
    virtualScrolling = true
  } = options;
  
  const { stdout } = useStdout();
  const [scrollPosition, setScrollPosition] = useState(0);
  const [renderCount, setRenderCount] = useState(0);
  const [shouldConstrainHeight, setShouldConstrainHeight] = useState(true);
  
  // Track if user has scrolled manually
  const hasManuallyScrolled = useRef(false);
  const renderTimer = useRef<NodeJS.Timeout | null>(null);
  const lastEventCount = useRef(events.length);
  
  // Calculate visible window - use full terminal height
  const availableHeight = Math.max(terminalHeight, 10);
  const maxVisibleLines = Math.min(maxVisibleEvents, availableHeight);
  
  // Auto-scroll to bottom when new events arrive (unless manually scrolled)
  useEffect(() => {
    if (events.length > lastEventCount.current && !hasManuallyScrolled.current) {
      scrollToBottom();
    }
    lastEventCount.current = events.length;
  }, [events.length]);
  
  // Debounced render counter
  const incrementRenderCount = useCallback(() => {
    if (renderTimer.current) {
      clearTimeout(renderTimer.current);
    }
    renderTimer.current = setTimeout(() => {
      setRenderCount(prev => prev + 1);
    }, renderDebounce);
  }, [renderDebounce]);
  
  // Scroll controls
  const scrollUp = useCallback((lines: number = 1) => {
    hasManuallyScrolled.current = true;
    setScrollPosition(prev => Math.max(0, prev - lines));
    incrementRenderCount();
  }, [incrementRenderCount]);
  
  const scrollDown = useCallback((lines: number = 1) => {
    hasManuallyScrolled.current = true;
    const maxScroll = Math.max(0, events.length - maxVisibleLines);
    setScrollPosition(prev => Math.min(maxScroll, prev + lines));
    incrementRenderCount();
  }, [events.length, maxVisibleLines, incrementRenderCount]);
  
  const scrollToBottom = useCallback(() => {
    hasManuallyScrolled.current = false;
    const maxScroll = Math.max(0, events.length - maxVisibleLines);
    setScrollPosition(maxScroll);
    incrementRenderCount();
  }, [events.length, maxVisibleLines, incrementRenderCount]);
  
  // Calculate visible events with virtual scrolling
  const visibleEvents = virtualScrolling
    ? events.slice(scrollPosition, scrollPosition + maxVisibleLines + scrollBufferSize)
    : events;
  
  // Determine if content is scrollable
  const isScrollable = events.length > maxVisibleLines;
  
  // Clear terminal artifacts during heavy streaming
  useEffect(() => {
    if (renderCount % 50 === 0 && renderCount > 0) {
      // Periodically clear terminal artifacts
      stdout.write(ansiEscapes.clearScreen);
    }
  }, [renderCount, stdout]);
  
  return {
    visibleEvents,
    scrollPosition,
    scrollUp,
    scrollDown,
    scrollToBottom,
    shouldConstrainHeight,
    isScrollable,
    renderCount
  };
};