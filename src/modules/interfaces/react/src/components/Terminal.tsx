/**
 * Terminal - Full terminal buffer streaming display
 *
 * Uses React Ink's Static component for smooth output without height limits.
 *
 * This component allows the full agent output to flow naturally without
 * artificial height constraints, preventing text overlap and cutoff issues.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Text } from 'ink';
import { StreamDisplay, StaticStreamDisplay, DisplayStreamEvent } from './StreamDisplay.js';
import { ExecutionService } from '../services/ExecutionService.js';
import { themeManager } from '../themes/theme-manager.js';
import { loggingService } from '../services/LoggingService.js';
import { useEventBatcher } from '../utils/useBatchedState.js';
import { normalizeEvent } from '../services/events/normalize.js';
import { RingBuffer } from '../utils/RingBuffer.js';
import { ByteBudgetRingBuffer } from '../utils/ByteBudgetRingBuffer.js';
import { DISPLAY_LIMITS } from '../constants/config.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { calculateAvailableHeight } from '../utils/layoutConstants.js';

// Exported helper: build a trimmed report preview to avoid storing huge content in memory
export const buildTrimmedReportContent = (raw: string): string => {
  try {
    const normalized = String(raw || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const lines = normalized.split('\n');
    const head = DISPLAY_LIMITS.REPORT_PREVIEW_LINES || 100;
    const tail = DISPLAY_LIMITS.REPORT_TAIL_LINES || 20;
    if (lines.length <= head + tail) return normalized;
    return [
      ...lines.slice(0, head),
      '',
      '... (content continues)',
      '',
      ...lines.slice(-tail)
    ].join('\n');
  } catch {
    return String(raw || '');
  }
};

interface TerminalProps {
  executionService: ExecutionService | null;
  sessionId: string;
  terminalWidth?: number;
  collapsed?: boolean;
  onEvent?: (event: any) => void;
  onMetricsUpdate?: (metrics: { tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number }) => void;
  animationsEnabled?: boolean;
  cleanupRef?: React.MutableRefObject<(() => void) | null>;
}

export const Terminal: React.FC<TerminalProps> = React.memo(({
  executionService,
  sessionId,
  terminalWidth: propsTerminalWidth,
  collapsed = false,
  onEvent,
  onMetricsUpdate,
  animationsEnabled = true,
  cleanupRef
}) => {
  // Use production-grade terminal size hook with resize handling
  const { availableWidth, availableHeight, columns } = useTerminalSize();
  const terminalWidth = propsTerminalWidth || availableWidth;
  // Test marker utility for diagnosing spinner/timer behavior
  const emitTestMarker = (msg: string) => {
    try {
      if (process.env.CYBER_TEST_MODE === 'true') {
        const marker = `[TEST_EVENT] ${msg}`;
        loggingService.info(marker);
        // eslint-disable-next-line no-console
        console.log(marker);
      }
    } catch {}
  };
  // Direct event rendering without Static component
  // Limit event buffer to prevent memory leaks - events are already persisted to disk
const MAX_EVENTS = Number(process.env.CYBER_MAX_EVENTS || 3000); // Keep last N events in memory (default 3000)
  const [completedEvents, setCompletedEvents] = useState<DisplayStreamEvent[]>([]);
  const [activeEvents, setActiveEvents] = useState<DisplayStreamEvent[]>([]);

  // Batch state updates to prevent memory leaks from frequent toArray() calls
  const pendingStateUpdateRef = useRef<NodeJS.Timeout | null>(null);
  const needsStateUpdateRef = useRef(false);
  const COMPLETED_EVENTS_BATCH_MS = 300;

  // Ring buffers to bound memory regardless of session length
  const MAX_EVENT_BYTES = Number(process.env.CYBER_MAX_EVENT_BYTES || 8 * 1024 * 1024); // 8 MiB default
  const completedBufRef = useRef(new ByteBudgetRingBuffer<DisplayStreamEvent>(
    MAX_EVENT_BYTES,
    {
      estimator: (e) => {
        try {
          if (!e) return 0;
          let bytes = 64;
          const any: any = e as any;
          const add = (v: any) => { if (typeof v === 'string') bytes += v.length; };
          add(any.content);
          add(any.command);
          add(any.message);
          // Tool outputs are the largest; budget mostly on content
          return bytes;
        } catch { return 256; }
      },
      overflowReducer: (e) => {
        // Summarize overly large events to preserve memory bounds
        try {
          const any: any = e as any;
          if (any?.type === 'report_content' && typeof any.content === 'string') {
            return { ...any, content: buildTrimmedReportContent(any.content) } as DisplayStreamEvent;
          }
          if (any?.type === 'output' && typeof any.content === 'string') {
            const s = any.content as string;
            const head = s.slice(0, DISPLAY_LIMITS.OUTPUT_PREVIEW_CHARS);
            const tail = s.slice(-DISPLAY_LIMITS.OUTPUT_TAIL_CHARS);
            return {
              ...any,
              content: `${head}\n... (content trimmed due to memory budget)\n${tail}`
            } as DisplayStreamEvent;
          }
          return e;
        } catch {
          return e;
        }
      }
    }
  ));
  const activeBufRef = useRef(new RingBuffer<DisplayStreamEvent>(Math.min(200, Math.floor(MAX_EVENTS / 5))));
  const [metrics, setMetrics] = useState({
    tokens: 0,
    cost: 0,
    duration: '0s',
    memoryOps: 0,
    evidence: 0
  });
  
  // Deduplication state: track seen output fingerprints per tool session and globally
  const perToolOutputSeenRef = useRef<Map<string, Set<string>>>(new Map());
  const globalOutputSeenRef = useRef<Set<string>>(new Set());
  
  // Throttle state for metrics emissions to parent
  const lastEmitRef = useRef<number>(0);
  const pendingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingMetricsRef = useRef<{ tokens?: number; cost?: number; duration: string; memoryOps: number; evidence: number } | null>(null);
  const EMIT_INTERVAL_MS = 300;
  const METRICS_COALESCE_MS = 500;  // Increased from 150ms to reduce WASM memory fragmentation
  const lastMetricsTsRef = useRef<number>(0);
  
  // State for event processing - replacing EventAggregator with React patterns
  const [activeThinking, setActiveThinking] = useState(false);
  // Keep a ref in sync with activeThinking to avoid setState race conditions
  const activeThinkingRef = useRef(false);
  useEffect(() => { activeThinkingRef.current = activeThinking; }, [activeThinking]);
  const [activeReasoning, setActiveReasoning] = useState(false);
  const [currentToolId, setCurrentToolId] = useState<string | undefined>(undefined);
  const [lastOutputContent, setLastOutputContent] = useState('');
  const [lastOutputTime, setLastOutputTime] = useState(0);

  // Per-step aggregated output (to display a single 'output' block per step)
  const stepAggRef = useRef<{ step?: number | null; head: string; tail: string; omitted: number } | null>({ step: null, head: '', tail: '', omitted: 0 });
  const appendToStepAgg = (fragment: string) => {
    try {
      if (!stepAggRef.current) stepAggRef.current = { step: null, head: '', tail: '', omitted: 0 };
      const agg = stepAggRef.current!;
      const s = String(fragment || '');
      if (!s) return;
      const HEAD_MAX = DISPLAY_LIMITS.OUTPUT_PREVIEW_CHARS || 2000;
      const TAIL_MAX = DISPLAY_LIMITS.OUTPUT_TAIL_CHARS || 500;
      // Fill head until full, then accumulate tail and omitted count
      if (agg.head.length < HEAD_MAX) {
        const remaining = HEAD_MAX - agg.head.length;
        agg.head += s.slice(0, remaining);
        const rest = s.slice(remaining);
        if (rest.length > 0) {
          // We have overflow; add to tail with rolling window
          if (rest.length >= TAIL_MAX) {
            agg.tail = rest.slice(-TAIL_MAX);
          } else {
            const combined = (agg.tail + rest);
            agg.tail = combined.length > TAIL_MAX ? combined.slice(-TAIL_MAX) : combined;
          }
          agg.omitted += rest.length;
        }
      } else {
        // Head full; maintain rolling tail window
        if (s.length >= TAIL_MAX) {
          agg.tail = s.slice(-TAIL_MAX);
        } else {
          const combined = (agg.tail + s);
          agg.tail = combined.length > TAIL_MAX ? combined.slice(-TAIL_MAX) : combined;
        }
        agg.omitted += s.length;
      }
    } catch {}
  };
  const buildAggDisplayEvent = (): DisplayStreamEvent | null => {
    try {
      const agg = stepAggRef.current;
      if (!agg) return null;
      const parts: string[] = [];
      if (agg.head) parts.push(agg.head);
      if (agg.omitted > 0) parts.push(`... (content continues; ${agg.omitted} chars omitted)`);
      if (agg.tail) parts.push(agg.tail);
      const content = parts.join('\n');
      if (!content) return null;
      return { type: 'output', content, metadata: { aggregated: true, fromToolBuffer: true } } as any;
    } catch { return null; }
  };
  const flushAggregatedOutput = (): DisplayStreamEvent | null => {
    const agg = buildAggDisplayEvent();
    resetStepAgg();
    return agg;
  };
  const resetStepAgg = () => { stepAggRef.current = { step: null, head: '', tail: '', omitted: 0 }; };
  
  // Swarm operation tracking for proper event enhancement
  const [swarmActive, setSwarmActive] = useState(false);
  const [currentSwarmAgent, setCurrentSwarmAgent] = useState<string | null>(null);
  const swarmHandoffSequenceRef = useRef(0);
  const delayedThinkingTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Timer to detect idle gaps after tool-buffer output when no explicit tool_end is emitted
  const postToolIdleTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Timer to bridge the gap AFTER reasoning completes and BEFORE next step/tool begins
  const postReasoningIdleTimerRef = useRef<NodeJS.Timeout | null>(null);
  const seenThinkingThisPhaseRef = useRef<boolean>(false);
  const suppressTerminationBannerRef = useRef<boolean>(false);
  // Track last reasoning text to prevent duplicate consecutive emissions
  const lastReasoningTextRef = useRef<string | null>(null);
  // Timestamp of the most recent tool-buffered output chunk
  const lastToolOutputTsRef = useRef<number>(0);
  // Duplicate emission resolved in ReactBridgeHandler
  // Throttle for active tail updates when animations are disabled
  const activeUpdateTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingActiveUpdaterRef = useRef<((prev: DisplayStreamEvent[]) => DisplayStreamEvent[]) | null>(null);
  // Increased from 80ms → 200ms → 400ms to reduce Yoga WASM memory fragmentation
  // This batches more events together, reducing total render count significantly
  // Higher value = fewer re-renders = less WASM memory fragmentation
  const ACTIVE_EMIT_INTERVAL_MS = 400;

  const setActiveThrottled = (
    updater: React.SetStateAction<DisplayStreamEvent[]>
  ) => {
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

  // Batch completed events updates to prevent memory leaks
  const scheduleCompletedEventsUpdate = () => {
    if (pendingStateUpdateRef.current) return;
    needsStateUpdateRef.current = true;
    pendingStateUpdateRef.current = setTimeout(() => {
      if (needsStateUpdateRef.current) {
        setCompletedEvents(completedBufRef.current.toArray());
        needsStateUpdateRef.current = false;
      }
      pendingStateUpdateRef.current = null;
    }, COMPLETED_EVENTS_BATCH_MS);
  };

  // Unified helpers for delayed thinking spinner scheduling/cancellation
  const cancelDelayedThinking = () => {
    if (delayedThinkingTimerRef.current) {
      clearTimeout(delayedThinkingTimerRef.current);
      delayedThinkingTimerRef.current = null;
    }
  };

  const cancelPostToolIdleTimer = () => {
    if (postToolIdleTimerRef.current) {
      clearTimeout(postToolIdleTimerRef.current);
      postToolIdleTimerRef.current = null;
    }
  };

  const cancelPostReasoningIdleTimer = () => {
    if (postReasoningIdleTimerRef.current) {
      clearTimeout(postReasoningIdleTimerRef.current);
      postReasoningIdleTimerRef.current = null;
    }
  };

  const scheduleDelayedThinking = (opts?: { delay?: number; context?: string; toolName?: string; toolCategory?: string; addSpacer?: boolean; }) => {
    // Always cancel any existing timer first to avoid overlap
    cancelDelayedThinking();
    if (!animationsEnabled) return;

    const delay = Math.max(0, opts?.delay ?? 100);
    emitTestMarker && emitTestMarker(`scheduleDelayedThinking request ctx=${opts?.context || 'tool_execution'} delay=${delay}`);
    delayedThinkingTimerRef.current = setTimeout(() => {
      // If a thinking spinner is already active AND visible in the active tail, do not schedule another
      const activeHasThinking = (() => {
        try {
          const arr = activeBufRef.current.toArray();
          return arr.some(e => e && (e as any).type === 'thinking');
        } catch {
          return false;
        }
      })();
      if (activeThinkingRef.current && activeHasThinking) {
        emitTestMarker && emitTestMarker('scheduleDelayedThinking skipped (already visible)');
        delayedThinkingTimerRef.current = null;
        return;
      }

      // Optional spacing before thinking animation to visually separate
      if (opts?.addSpacer && animationsEnabled) {
        completedBufRef.current.push({ type: 'output', content: '' } as DisplayStreamEvent);
        completedBufRef.current.push({ type: 'output', content: '' } as DisplayStreamEvent);
        scheduleCompletedEventsUpdate();
      }

      const thinkingEvent: DisplayStreamEvent = {
        type: 'thinking',
        context: opts?.context || 'tool_execution',
        startTime: Date.now(),
        ...(opts?.toolName ? { toolName: opts.toolName } : {}),
        ...(opts?.toolCategory ? { toolCategory: opts.toolCategory } : {})
      } as DisplayStreamEvent;

      // Mark spinner active so backend 'thinking' doesn't duplicate it
      setActiveThinking(true);
      seenThinkingThisPhaseRef.current = true;

      // Remove any existing thinking before adding a new one, but preserve
      // existing active tail content (e.g., aggregated tool output) to avoid flicker.
      // Insert thinking at the FRONT so the spinner is visible above output.
      setActiveThrottled(() => {
        const existing = activeBufRef.current.toArray().filter(e => e.type !== 'thinking');
        activeBufRef.current.clear();
        activeBufRef.current.push(thinkingEvent);
        for (const e of existing) activeBufRef.current.push(e);
        return activeBufRef.current.toArray();
      });

      emitTestMarker && emitTestMarker(`scheduleDelayedThinking fired ctx=${(thinkingEvent as any).context}`);
      delayedThinkingTimerRef.current = null;
    }, delay) as unknown as NodeJS.Timeout;
  };
  
  const resetAllBuffers = useCallback((preserveEvents: DisplayStreamEvent[] = []) => {
    cancelDelayedThinking();
    if (pendingTimerRef.current) {
      clearTimeout(pendingTimerRef.current);
      pendingTimerRef.current = null;
    }
    if (activeUpdateTimerRef.current) {
      clearTimeout(activeUpdateTimerRef.current);
      activeUpdateTimerRef.current = null;
    }

    stepAggRef.current = { step: null, head: '', tail: '', omitted: 0 };
    pendingReasoningsRef.current = [];
    opSummaryBufferRef.current = [];
    swarmAgentStepsRef.current = new Map();
    seenThinkingThisPhaseRef.current = false;
    suppressTerminationBannerRef.current = false;
    lastReasoningTextRef.current = null;
    perToolOutputSeenRef.current.clear();
    globalOutputSeenRef.current.clear();
    setCurrentToolId(undefined);
    setActiveThinking(false);
    setActiveReasoning(false);
    setLastOutputContent('');
    setLastOutputTime(0);
    setSwarmActive(false);
    setCurrentSwarmAgent(null);
    swarmHandoffSequenceRef.current = 0;
    pendingMetricsRef.current = null;
    lastMetricsTsRef.current = 0;
    lastEmitRef.current = 0;
    setMetrics({ tokens: 0, cost: 0, duration: '0s', memoryOps: 0, evidence: 0 });

    completedBufRef.current.clear();
    activeBufRef.current.clear();
    if (preserveEvents.length > 0) {
      completedBufRef.current.pushMany(preserveEvents);
    }
    scheduleCompletedEventsUpdate();
    setActiveEvents(activeBufRef.current.toArray());
  }, [cancelDelayedThinking, setActiveEvents, setCompletedEvents, setActiveThinking, setActiveReasoning, setSwarmActive, setCurrentSwarmAgent]);
  
  // Constants for event processing
  const COMMAND_BUFFER_MS = 100;
  const OUTPUT_DEDUPE_TIME_MS = 500;
  const theme = themeManager.getCurrentTheme();

  // Expose cleanup function via ref for /clear command
  React.useEffect(() => {
    if (cleanupRef) {
      cleanupRef.current = () => {
        // Clear state arrays to release memory
        setCompletedEvents([]);
        setActiveEvents([]);

        // Reset all buffers and refs
        resetAllBuffers();
      };
    }
    return () => {
      if (cleanupRef) {
        cleanupRef.current = null;
      }
    };
  }, [cleanupRef, resetAllBuffers]);

  // Reset buffers when a new session starts to prevent memory growth across runs
  React.useEffect(() => {
    // Aggressively clear state arrays first to release memory
    setCompletedEvents([]);
    setActiveEvents([]);

    // Then reset all buffers and refs
    resetAllBuffers();

    // Force garbage collection hint by clearing large objects
    // This helps prevent heap overflow when starting multiple operations in same session
    if (global.gc) {
      try {
        global.gc();
      } catch (e) {
        // GC not available, that's okay
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Ensure immediate visual feedback at startup: schedule a lightweight spinner
  // right after the execution begins, before any backend events (e.g., operation_init)
  // are received. This avoids a black screen during initial 3–5s setup gaps.
  React.useEffect(() => {
    if (!executionService || !animationsEnabled) return;
    if (collapsed) return;
    // Only schedule if no spinner is active AND no events have rendered yet
    if (!activeThinkingRef.current && !activeReasoning && activeEvents.length === 0 && completedEvents.length === 0) {
      scheduleDelayedThinking({ delay: 150, context: 'startup', addSpacer: false });
    }
    // Cleanup is handled by the main effect's cleanup and cancelDelayedThinking()
    // to avoid duplicate timers and ensure consistent teardown.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionService, sessionId, animationsEnabled, collapsed]);

  // Fingerprint helper for deduplication
  const fingerprintContent = (s: string): string => {
    try {
      const str = String(s);
      const len = str.length;
      if (len === 0) return 'len:0';
      const head = str.slice(0, 512);
      const tail = len > 512 ? str.slice(-512) : '';
      return `len:${len}|h:${head}|t:${tail}`;
    } catch {
      return 'err';
    }
  };
  
  // Step gating state (anchor step headers until first tool signal)
  const pendingStepHeaderRef = useRef<DisplayStreamEvent | null>(null);
  const pendingStepNumberRef = useRef<number | undefined>(undefined);
  const hasToolForPendingStepRef = useRef<boolean>(false);
  const lastEmittedStepNumberRef = useRef<number | undefined>(undefined);

  const flushPendingStepHeader = (collector: DisplayStreamEvent[]) => {
    if (pendingStepHeaderRef.current && !hasToolForPendingStepRef.current) {
      collector.push(pendingStepHeaderRef.current);
      lastEmittedStepNumberRef.current = pendingStepNumberRef.current ?? lastEmittedStepNumberRef.current;
      pendingStepHeaderRef.current = null;
      hasToolForPendingStepRef.current = true;
    }
  };

  // Track max steps and operation id from operation_init for synthetic headers
  const opMaxStepsRef = useRef<number | undefined>(undefined);
  const operationIdRef = useRef<string | undefined>(undefined);
  const targetRef = useRef<string | undefined>(undefined);
  const stepCounterRef = useRef<number>(0);
  const lastPushedTypeRef = useRef<string | null>(null);
  const firstHeaderSeenRef = useRef<boolean>(false);
  // Buffer for operation summary lines (paths) so we can show them after report preview/content
  const opSummaryBufferRef = useRef<DisplayStreamEvent[]>([]);

  // Pending reasoning buffer (queue): hold reasoning events after the first header
  const pendingReasoningsRef = useRef<DisplayStreamEvent[]>([]);
  const pendingReasoningTimerRef = useRef<NodeJS.Timeout | null>(null);
  const REASONING_LOOKAHEAD_MS = 1000; // kept for compatibility (no timer-based flushes currently used)

  const flushPendingReasoning = (collector: DisplayStreamEvent[]) => {
    if (pendingReasoningTimerRef.current) {
      clearTimeout(pendingReasoningTimerRef.current);
      pendingReasoningTimerRef.current = null;
    }
    if (pendingReasoningsRef.current.length > 0) {
      // Merge all pending reasoning into a single block for this step
      const parts: string[] = [];
      let last: any = null;
      for (const r of pendingReasoningsRef.current) {
        if (r && typeof (r as any).content === 'string') {
          const s = String((r as any).content).trim();
          if (s) parts.push(s);
        }
        last = r || last;
      }
      const merged = parts.join('\n\n');
      if (merged) {
        const mergedEvent: any = { type: 'reasoning', content: merged };
        // Preserve swarm context from the last reasoning in the queue if present
        if (last && (last as any).swarm_agent) mergedEvent.swarm_agent = (last as any).swarm_agent;
        collector.push(mergedEvent as DisplayStreamEvent);
      }
      pendingReasoningsRef.current = [];
      // Clear live reasoning preview now that it has been committed
      // Use immediate update (not throttled) to prevent duplicate display
      activeBufRef.current.clear();
      setActiveEvents(activeBufRef.current.toArray());
    }
  };

  // Track swarm sub-steps per agent for synthesized headers
  const swarmAgentStepsRef = useRef<Map<string, number>>(new Map());


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
      case 'operation_init':
        // Reset dedup sets at operation start
        perToolOutputSeenRef.current.clear();
        globalOutputSeenRef.current.clear();
        // Cache operation metadata
        if (typeof event.max_steps === 'number') {
          opMaxStepsRef.current = event.max_steps;
        }
        if (typeof event.operation_id === 'string') {
          operationIdRef.current = event.operation_id;
        }
        if (typeof event.target === 'string') {
      targetRef.current = event.target;
    }
    // Reset counters at operation start
    stepCounterRef.current = 0;
    lastPushedTypeRef.current = null;
    results.push(event as DisplayStreamEvent);

    // Show spinner immediately after operation_init while awaiting first step/reasoning
    // This covers the 10-15 second gap before the agent's first response
    // CRITICAL: Use scheduleDelayedThinking with 0 delay instead of direct manipulation
    // This ensures proper integration with the event loop and prevents race conditions
    if (animationsEnabled) {
      cancelDelayedThinking();
      setActiveThinking(true);
      seenThinkingThisPhaseRef.current = true;

      // Immediately show urgent thinking event to bypass any delays
      const thinkingEvent: DisplayStreamEvent = {
        type: 'thinking',
        context: 'waiting',
        startTime: Date.now(),
        urgent: true
      } as DisplayStreamEvent;

      // Push to results so it gets processed by the event loop
      results.push(thinkingEvent);
    }
    break;

      case 'step_header':
        emitTestMarker(`step_header step=${event.step} max=${event.maxSteps}`);
        cancelDelayedThinking();
        cancelPostReasoningIdleTimer();
        // End any active reasoning session
        setActiveReasoning(false);
        // Reset last reasoning dedupe on new step
        lastReasoningTextRef.current = null;
        // Reset output suppression for next operation phase
        suppressTerminationBannerRef.current = false;
        
        // Track swarm agent from step header
        if (event.is_swarm_operation && event.swarm_agent) {
          setCurrentSwarmAgent(event.swarm_agent);
        }
        
        // Push header immediately (no gating)
        // Before starting a new step, flush any pending reasoning from the previous tool call
        // so it appears at the end of the previous step (below its outputs)
        flushPendingReasoning(results);

        results.push({
          type: 'step_header',
          step: event.step,
          maxSteps: event.maxSteps,
          operation: event.operation,
          duration: event.duration,
          is_swarm_operation: event.is_swarm_operation,
          swarm_agent: event.swarm_agent || currentSwarmAgent,
          swarm_sub_step: event.swarm_sub_step,
          swarm_max_sub_steps: event.swarm_max_sub_steps,
          swarm_agent_max: event.swarm_agent_max,
          swarm_total_iterations: event.swarm_total_iterations,
          swarm_max_iterations: event.swarm_max_iterations,
          agent_count: event.agent_count,
          swarm_context: event.swarm_context || (swarmActive ? 'Multi-Agent Operation' : undefined)
        } as DisplayStreamEvent);

        // Mark that we've seen the first header
        firstHeaderSeenRef.current = true;
        if (typeof event.step === 'number') {
          stepCounterRef.current = event.step;
        }
        lastPushedTypeRef.current = 'step_header';

        // Show thinking spinner while waiting for tool selection after step header
        // Always reset and show spinner regardless of previous thinking state
        if (animationsEnabled) {
          setActiveThinking(true);
          seenThinkingThisPhaseRef.current = true;

          const thinkingEvent: DisplayStreamEvent = {
            type: 'thinking',
            context: 'tool_preparation',
            startTime: Date.now(),
            urgent: true  // Bypass throttle for immediate display
          } as DisplayStreamEvent;

          results.push(thinkingEvent);

          // Update active buffer immediately to show spinner without delay
          activeBufRef.current.clear();
          activeBufRef.current.push(thinkingEvent);
          setActiveEvents(activeBufRef.current.toArray());
        }
        break;
        
        
      case 'reasoning':
        emitTestMarker('reasoning');
        // Any pending post-tool idle spinner is no longer needed
        cancelPostToolIdleTimer();
        // Reset last tool output timestamp on entering reasoning
        lastToolOutputTsRef.current = 0;
        // Clear any pending post-reasoning timer before scheduling a new one
        cancelPostReasoningIdleTimer();
        // Python backend sends complete reasoning blocks
        if (event.content && event.content.trim()) {
          // Clear any active thinking animations when reasoning is shown
          if (activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            setActiveThinking(false);
          }
          // Cancel any pending delayed thinking and mark seen
          cancelDelayedThinking();
          seenThinkingThisPhaseRef.current = true;
          
          // Update swarm agent if present in event
          if (event.swarm_agent && swarmActive) {
            setCurrentSwarmAgent(event.swarm_agent);
          }
          
          // Start reasoning session
          setActiveReasoning(true);

          const reasoningEvent: DisplayStreamEvent = {
            type: 'reasoning',
            content: String(event.content).trim(),
            ...(swarmActive && currentSwarmAgent ? { swarm_agent: currentSwarmAgent } : {})
          } as DisplayStreamEvent;

          // Queue reasoning for final placement under this step
          pendingReasoningsRef.current.push(reasoningEvent);

          // Immediately reflect the merged reasoning in the active tail so the user sees it during this step
          try {
            const parts: string[] = [];
            for (const r of pendingReasoningsRef.current) {
              const s = (r as any).content ? String((r as any).content).trim() : '';
              if (s) parts.push(s);
            }
            const merged = parts.join('\n\n');
            if (merged) {
              setActiveThrottled(prev => {
                activeBufRef.current.clear();
                activeBufRef.current.push({ type: 'reasoning', content: merged } as any);
                return activeBufRef.current.toArray();
              });
              // After rendering reasoning, briefly show a spinner while the agent
              // prepares the next step/tool selection to avoid a blank gap.
              if (animationsEnabled) {
                // Clear any existing timer and schedule a new one with minimal delay
                cancelPostReasoningIdleTimer();
                postReasoningIdleTimerRef.current = setTimeout(() => {
                  // End the visible reasoning session
                  setActiveReasoning(false);
                  if (!activeThinkingRef.current) {
                    setActiveThinking(true);
                    seenThinkingThisPhaseRef.current = true;

                    // Add thinking to active buffer, preserving any existing content
                    const thinkingEvent: DisplayStreamEvent = {
                      type: 'thinking',
                      context: 'reasoning',
                      startTime: Date.now(),
                      urgent: true  // Bypass throttle to avoid post-reasoning gaps
                    } as DisplayStreamEvent;

                    const existing = activeBufRef.current.toArray().filter(e => e.type !== 'thinking' && e.type !== 'reasoning');
                    activeBufRef.current.clear();
                    activeBufRef.current.push(thinkingEvent);
                    for (const e of existing) activeBufRef.current.push(e);
                    setActiveEvents(activeBufRef.current.toArray());  // Immediate update
                  }
                  postReasoningIdleTimerRef.current = null;
                }, 10) as unknown as NodeJS.Timeout;
              }
            }
          } catch {}
        }
        break;
        
      case 'thinking':
        // Handle thinking start without conflicting with reasoning
        if (!activeReasoning) {
          // Cancel any pending delayed spinner to avoid duplicates
          cancelDelayedThinking();
          cancelPostToolIdleTimer();
          cancelPostReasoningIdleTimer();
          seenThinkingThisPhaseRef.current = true;
          // Ensure the internal flag is set (fallback: it may already be true)
          if (!activeThinkingRef.current) {
            setActiveThinking(true);
          }
          // Create thinking event with urgent flag preserved
          const thinkingEvent: DisplayStreamEvent = {
            type: 'thinking',
            context: event.context,
            startTime: event.startTime || Date.now(),
            metadata: event.metadata,
            urgent: (event as any).urgent || false  // Preserve urgent flag for immediate rendering
          } as DisplayStreamEvent;

          // ALWAYS add to results so event loop processes it
          // The urgent flag will trigger immediate rendering in the event loop (line 1516-1518)
          results.push(thinkingEvent);
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
        cancelPostToolIdleTimer();
        cancelPostReasoningIdleTimer();

        // Keep spinner showing during tool execution, just change context
        if (!activeThinking && animationsEnabled) {
          setActiveThinking(true);
          const thinkingEvent: DisplayStreamEvent = {
            type: 'thinking',
            context: 'tool_execution',
            startTime: Date.now(),
            urgent: true
          } as DisplayStreamEvent;

          results.push(thinkingEvent);
          // Event loop will handle immediate rendering via urgent flag
        }

        // Reset last tool output timestamp for new tool
        lastToolOutputTsRef.current = 0;
        // Do not flush pending reasoning here; wait for step_header to ensure correct attribution
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
        
        // Initialize per-tool dedup set
        try { if (toolId) perToolOutputSeenRef.current.set(toolId, new Set()); } catch {}
        
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
        // Edge case fix: show spinner even if reasoning was active, since we just ended it above.
        if (!activeThinkingRef.current) {
          cancelDelayedThinking();
          
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
        cancelPostToolIdleTimer();
        cancelPostReasoningIdleTimer();
        // Mark end of tool streaming
        lastToolOutputTsRef.current = Date.now();
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        cancelDelayedThinking();
        seenThinkingThisPhaseRef.current = false;
        setCurrentToolId(undefined);
        // Immediately show a spinner while the agent processes the tool result and prepares reasoning
        if (animationsEnabled && !activeReasoning) {
          setActiveThinking(true);
          const thinkingEvent: DisplayStreamEvent = {
            type: 'thinking',
            context: 'waiting',
            startTime: Date.now(),
            urgent: true  // Bypass throttle for immediate display
          } as DisplayStreamEvent;

          results.push(thinkingEvent);
          // Event loop will handle immediate rendering via urgent flag (no manual buffer manipulation)
        }
        // Optionally, we do not emit a separate tool_end display item here to avoid duplicates
        break;
        
      case 'shell_command':
        // Do not flush pending reasoning here; wait for step_header to ensure correct attribution
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

      case 'prompt_change':
        emitTestMarker(`prompt_change action=${event.action}`);
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'model_invocation_start':
        // When the model is invoked (post-tool), show a spinner immediately to indicate
        // the agent is preparing reasoning. This covers gaps before the first reasoning block.
        cancelDelayedThinking();
        cancelPostToolIdleTimer();
        cancelPostReasoningIdleTimer();
        if (!activeThinkingRef.current && animationsEnabled) {
          setActiveThinking(true);
          results.push({
            type: 'thinking',
            context: 'reasoning',
            startTime: Date.now()
          } as DisplayStreamEvent);
        }
        // Do not render the model event itself; UI shows spinner instead
        break;

      case 'model_stream_delta':
      case 'reasoning_delta':
        // Streaming deltas are handled by StreamDisplay or aggregated elsewhere; don't render here
        break;

      case 'output':
        emitTestMarker('output');
        // Normalize content to detect empty/whitespace-only lines
        const rawOut = (event as any).content != null ? String((event as any).content) : '';
        const isEmptyOut = rawOut.trim().length === 0;
        // Determine whether this output belongs to a tool buffer regardless of content
        const fromToolBufferFlag = !!(((event as any)?.metadata?.fromToolBuffer) || ((event as any)?.metadata?.tool) || Boolean(currentToolId));

        // Maintain post-tool bridging behavior even for empty outputs
        if (activeThinking && fromToolBufferFlag) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }

        if (fromToolBufferFlag) {
          // Update last tool output timestamp and start idle timer to show spinner after output
          lastToolOutputTsRef.current = Date.now();
          cancelPostToolIdleTimer();
          if (animationsEnabled) {
            postToolIdleTimerRef.current = setTimeout(() => {
              if (!activeThinkingRef.current && !activeReasoning) {
                scheduleDelayedThinking({ delay: 0, context: 'waiting', addSpacer: false });
              }
              // Exit tool phase to avoid misclassifying subsequent non-tool output
              setCurrentToolId(undefined);
              postToolIdleTimerRef.current = null;
            }, 60) as unknown as NodeJS.Timeout;
          }
        } else if (animationsEnabled) {
          // If a non-tool output arrives shortly after tool output, bridge with a spinner
          const sinceLastToolMs = Date.now() - (lastToolOutputTsRef.current || 0);
          if (sinceLastToolMs > 0 && sinceLastToolMs < 1500 && !activeThinkingRef.current && !activeReasoning) {
            setActiveThinking(true);
            results.push({ type: 'thinking', context: 'waiting', startTime: Date.now() } as DisplayStreamEvent);
            // Also exit tool phase since we've transitioned to waiting for reasoning
            setCurrentToolId(undefined);
          }
        }

        // Only cancel post-reasoning spinner if we have meaningful output
        if (!isEmptyOut) {
          cancelPostReasoningIdleTimer();
        }

        // If we are still before operation_init, keep a startup spinner visible even as
        // status/output lines arrive. This avoids a dead UI during initial setup.
        if (!operationIdRef.current && !activeThinkingRef.current && animationsEnabled) {
          scheduleDelayedThinking({ delay: 0, context: 'startup', addSpacer: false });
        }

        // Output should not be held; but ensure we don't have stale pending reasoning lingering
        // If output appears, we do NOT auto-flush pending reasoning; it may belong under the next header
        // Handle tool output or general output with deduplication
        if (event.content) {
          // Update swarm agent if present in event
          if (event.swarm_agent && swarmActive) {
            setCurrentSwarmAgent(event.swarm_agent);
          }
          
          // Suppress verbose termination block lines after ESC
          if (suppressTerminationBannerRef.current) {
            const line = String(event.content).trim();
            const isDivider = /^(\[\u2500-\u257F\u2501\u2509\u250A\u250B\u250C\u250D\u250E\u250F\u2510\u2511\u2512\u2513\u2574\u2576\u2501\u2500\-\=\_\~\s\]){10,}$/.test(line) || /\u2501|\u2500|\u2502|\u2503|\u2505|\u2507|\u2509/.test(line);
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
          // Fingerprint-based dedup across tool session
          try {
            const fp = fingerprintContent(contentStr);
            const set = currentToolId ? (perToolOutputSeenRef.current.get(currentToolId) || null) : null;
            let seen = false;
            if (set) {
              if (set.has(fp)) {
                seen = true;
              } else {
                set.add(fp);
              }
            } else {
              if (globalOutputSeenRef.current.has(fp)) {
                seen = true;
              } else {
                globalOutputSeenRef.current.add(fp);
              }
            }
            if (seen) {
              break; // skip duplicate chunk/content for this tool/session
            }
          } catch {}

          setLastOutputContent(contentStr);
          setLastOutputTime(currentTime);
          
          // above we already handled spinner transitions irrespective of content

          // Reorder operation summary vs report preview/content: buffer op-summary and flush after report
          const fromToolBuffer = fromToolBufferFlag;
          const isReportPreview = contentStr.includes('# SECURITY ASSESSMENT REPORT') || contentStr.includes('# CTF Challenge Assessment Report') || contentStr.includes('EXECUTIVE SUMMARY') || contentStr.includes('KEY FINDINGS') || contentStr.includes('REMEDIATION ROADMAP');
          const isOperationSummary = !fromToolBuffer && (
            contentStr.includes('Outputs stored in:') ||
            contentStr.includes('Memory stored in:') ||
            contentStr.includes('Report saved to:') ||
            contentStr.includes('REPORT ALSO SAVED TO:') ||
            contentStr.includes('OPERATION LOGS:') ||
            contentStr.includes('Operation ID:')
          );

          if (isOperationSummary) {
            // Buffer operation summary to show after report preview/content
            opSummaryBufferRef.current.push({
              type: 'output',
              content: event.content,
              toolId: currentToolId
            } as DisplayStreamEvent);
            break;
          }

          // Clean placeholder tokens sometimes prefixed in combined output blocks
          let cleanedContent = contentStr;
          if (/^(output|reasoning)(\s*\[[^\]]+\])?\s*\n/i.test(cleanedContent)) {
            cleanedContent = cleanedContent.replace(/^(output|reasoning)(\s*\[[^\]]+\])?\s*\n/i, '');
          }
          // If after cleaning this is a pure placeholder, skip it entirely
          const trimmedClean = cleanedContent.trim();
          if (/^(output|reasoning)(\s*\[[^\]]+\])?$/i.test(trimmedClean)) {
            break;
          }

          // Push normal output
          const outEvt: DisplayStreamEvent = {
            type: 'output',
            content: cleanedContent,
            toolId: currentToolId,
            // Preserve metadata so the renderer can identify tool-buffer outputs
            ...(event.metadata ? { metadata: event.metadata } : {})
          } as DisplayStreamEvent;
          results.push(outEvt);

          // If this is a report preview block, immediately flush any buffered operation summary below it
          if (isReportPreview && opSummaryBufferRef.current.length > 0) {
            results.push(...opSummaryBufferRef.current);
            opSummaryBufferRef.current = [];
          }
        } else {
          // For empty/whitespace-only output, we already handled spinner transitions.
          // Skip rendering to avoid blank gaps in the UI.
        }
        break;
        
      case 'tool_end':
        cancelPostToolIdleTimer();
        cancelPostReasoningIdleTimer();
        // Update swarm agent if present in event
        if (event.swarm_agent && swarmActive) {
          setCurrentSwarmAgent(event.swarm_agent);
        }
        
        // Clear any active thinking when tool ends
        if (activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          setActiveThinking(false);
        }
        // Exit tool phase on tool_end
        setCurrentToolId(undefined);
        // Immediately show a short waiting spinner while transitioning to reasoning
        if (animationsEnabled && !activeReasoning) {
          setActiveThinking(true);
          const thinkingEvent: DisplayStreamEvent = {
            type: 'thinking',
            context: 'waiting',
            startTime: Date.now(),
            urgent: true  // Bypass throttle for immediate display
          } as DisplayStreamEvent;

          results.push(thinkingEvent);
          // Event loop will handle immediate rendering via urgent flag
        }
        // Reset flags and cancel pending delayed thinking
        cancelDelayedThinking();
        seenThinkingThisPhaseRef.current = false;

        // Don't flush reasoning here - let it accumulate until step_header
        // This ensures all reasoning within a step appears as one block

        results.push({
          type: 'tool_end',
          toolId: event.toolId,
          tool: event.toolName || 'unknown',
          id: `tool_end_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          timestamp: new Date().toISOString(),
          sessionId: 'current'
        } as DisplayStreamEvent);
        // Clear per-tool dedup set when tool ends
        try { if (event.toolId) perToolOutputSeenRef.current.delete(String(event.toolId)); } catch {}
        setCurrentToolId(undefined);
        // Spinner already shown above (lines 1147-1160) - no need for additional delayed spinner
        break;

      case 'operation_complete':
        // Clear any active states
        setActiveThinking(false);
        // Flush any pending reasoning before we finalize
        flushPendingReasoning(results);
        setActiveReasoning(false);

        // If any op-summary lines are still buffered (no report emitted), flush them now before metrics
        if (opSummaryBufferRef.current.length > 0) {
          results.push(...opSummaryBufferRef.current);
          opSummaryBufferRef.current = [];
        }

        results.push({
          type: 'metrics_update',
          metrics: event.metrics || {},
          duration: event.duration
        } as DisplayStreamEvent);

        // CRITICAL: Aggressive memory cleanup after operation completes
        // Keep only the most recent events to prevent 6GB heap exhaustion
        setTimeout(() => {
          // Keep only last 100 completed events (enough for final report + metrics)
          const MAX_RETAINED_EVENTS = 100;
          const allCompleted = completedBufRef.current.toArray();

          if (allCompleted.length > MAX_RETAINED_EVENTS) {
            const toKeep = allCompleted.slice(-MAX_RETAINED_EVENTS);
            completedBufRef.current.clear();
            for (const evt of toKeep) {
              completedBufRef.current.push(evt);
            }
            setCompletedEvents(toKeep);
          }

          // Move final active events to completed
          const activeSnapshot = activeBufRef.current.toArray();
          for (const evt of activeSnapshot) {
            completedBufRef.current.push(evt);
          }

          // Clear active buffer completely
          activeBufRef.current.clear();
          setActiveEvents([]);

          // Force garbage collection to release memory immediately
          if (global.gc) {
            try {
              global.gc();
            } catch (e) {
              // GC not available
            }
          }
        }, 1000); // Wait 1s for final renders to complete

        break;
        
      case 'tool_output':
        // Standardized tool output: treat as first tool signal for pending step
        flushPendingStepHeader(results);
        // Do not flush pending reasoning here; wait for step_header to ensure correct attribution
        results.push(event as DisplayStreamEvent);
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
        
      case 'report_content':
        // Trim massive report content to prevent OOM and rely on InlineReportViewer for full content.
        flushPendingReasoning(results);
        // Augment event with operation metadata and replace content with a trimmed preview
        const rcEvent: any = { ...event };
        if (typeof rcEvent.content === 'string') {
          rcEvent.content = buildTrimmedReportContent(rcEvent.content);
        } else if (rcEvent.content) {
          try { rcEvent.content = buildTrimmedReportContent(JSON.stringify(rcEvent.content)); } catch { rcEvent.content = ''; }
        }
        if (operationIdRef.current) rcEvent.operation_id = operationIdRef.current;
        if (targetRef.current) rcEvent.target = targetRef.current;
        results.push(rcEvent as DisplayStreamEvent);
        // Synthesize a paths section immediately below the report
        try {
          const opId = operationIdRef.current || '';
          const target = targetRef.current || '';
          const safeTarget = target ? target.replace(/^https?:\/\//, '').replace(/\.{2}|\.\//g, '').replace(/[^a-zA-Z0-9._-]/g, '_').replace(/_+/g, '_').replace(/^[_\.]+|[_\.]+$/g, '') : '';
          const base = safeTarget && opId ? `./outputs/${safeTarget}/${opId}` : '';
          const memory = safeTarget ? `./outputs/${safeTarget}/memory` : '';
          const reportPath = base ? `${base}/security_assessment_report.md` : '';
          const logPath = base ? `${base}/cyber_operations.log` : '';
          results.push({
            type: 'report_paths',
            operation_id: opId,
            target,
            outputDir: base,
            reportPath,
            logPath,
            memoryPath: memory
          } as unknown as DisplayStreamEvent);
        } catch {}
        // Then flush any buffered operation summary (paths) so they appear beneath the report as well
        if (opSummaryBufferRef.current.length > 0) {
          results.push(...opSummaryBufferRef.current);
          opSummaryBufferRef.current = [];
        }
        break;

      default:
        // Pass through other events as-is (no synthetic headers)
        results.push(event as DisplayStreamEvent);
        try { lastPushedTypeRef.current = String((event as any).type || ''); } catch {}
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
      
      // Preserve preflight and discovery output printed before operation_init.
      // Memory is bounded by CYBER_MAX_EVENTS ring buffer rather than clearing mid-run.

      // Handle metrics updates - backend sends cumulative totals, not deltas
      if (event.type === 'metrics_update' && event.metrics) {
        // Coalesce frequent metrics updates within a short window to reduce render churn
        const nowTs = Date.now();
        if (nowTs - (lastMetricsTsRef.current || 0) < METRICS_COALESCE_MS) {
          // Drop this update; a fresher one will arrive soon
          return;
        }
        lastMetricsTsRef.current = nowTs;
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

        let currentAggDisplayEvent: DisplayStreamEvent | null = null;
        for (const processedEvent of processedEvents) {
          if (processedEvent.type === 'delayed_thinking_start') {
            // Skip entirely when animations are disabled
            if (!animationsEnabled) {
              continue;
            }
            // Use unified scheduler for delayed spinner; include spacing for this path
            const delay = (processedEvent as any).delay || 100;
            scheduleDelayedThinking({
              delay,
              context: (processedEvent as any).context || 'tool_execution',
              toolName: (processedEvent as any).toolName,
              toolCategory: (processedEvent as any).toolCategory,
              addSpacer: true,
            });
            continue;
          }

          if (processedEvent.type === 'thinking_end') {
            // End spinner but keep aggregated output visible in active tail
            setActiveThrottled(prev => {
              activeBufRef.current.clear();
              const aggEv = buildAggDisplayEvent();
              if (aggEv) activeBufRef.current.push(aggEv);
              return activeBufRef.current.toArray();
            });
            continue;
          }

          // Aggregate tool buffer output fragments per step, but DO NOT aggregate system/status outputs
          if (processedEvent.type === 'output') {
            try {
              const any: any = processedEvent as any;
              // Consider output as tool-buffered if metadata says so OR we have an active toolId
              const isToolBuffer = Boolean(any?.metadata?.fromToolBuffer || any?.metadata?.tool || Boolean(currentToolId));
              if (isToolBuffer) {
                let contentStr = '';
                if (typeof any.content === 'string') contentStr = any.content;
                else if (any.content) contentStr = JSON.stringify(any.content);
                appendToStepAgg(contentStr);
                currentAggDisplayEvent = buildAggDisplayEvent();
                // Skip pushing this output into completed; we'll show one per step
                continue;
              }
            } catch {}
          }
          
          regularEvents.push(processedEvent);
        }

        // Keep current thinking (if any) and aggregated output in active tail without duplication
        // This runs on EVERY event to preserve thinking across all events
        const thinkingEvents = regularEvents.filter(e => e.type === 'thinking');
        // Preserve existing thinking even if no new events - prevents thinking from disappearing
        const existingThinking = activeBufRef.current.toArray().filter(e => e.type === 'thinking');
        const hasThinkingToDisplay = thinkingEvents.length > 0 || existingThinking.length > 0 || currentAggDisplayEvent;

        if (hasThinkingToDisplay) {
          // Check if any thinking event is marked urgent - needs immediate rendering
          const hasUrgent = thinkingEvents.some(e => (e as any).urgent === true);

          const updateActiveBuf = () => {
            // Preserve existing thinking if no new thinking events in this batch
            const thinkingToKeep = thinkingEvents.length > 0 ? thinkingEvents : existingThinking;
            // Rebuild active tail: keep thinking, then aggregated output if present
            activeBufRef.current.clear();
            // Deduplicate thinking entries by identity (type-only for safety)
            const uniqueThinking: DisplayStreamEvent[] = [];
            for (const t of thinkingToKeep) {
              if (!uniqueThinking.some(u => u.type === t.type)) uniqueThinking.push(t);
            }
            for (const t of uniqueThinking) activeBufRef.current.push(t);
            if (currentAggDisplayEvent) activeBufRef.current.push(currentAggDisplayEvent);
            return activeBufRef.current.toArray();
          };

          // Bypass throttle for urgent events (startup, post-reasoning) to ensure immediate visibility
          if (hasUrgent) {
            const events = updateActiveBuf();
            setActiveEvents(events);
          } else {
            setActiveThrottled(updateActiveBuf);
          }
        }

        if (regularEvents.length > 0) {
          // Before anything else, if a new step header arrived, flush current aggregated output into completed
          const stepHeaders = regularEvents.filter(e => e.type === 'step_header');
          if (stepHeaders.length > 0) {
            const aggEv = buildAggDisplayEvent();
            if (aggEv) {
              completedBufRef.current.push(aggEv as any);
              scheduleCompletedEventsUpdate();
              resetStepAgg();
            }
            // Clear any live tail from previous step (reasoning/output) to prevent leakage
            setActiveThrottled(() => {
              activeBufRef.current.clear();
              return activeBufRef.current.toArray();
            });
            // End any active thinking/reasoning state at step boundary
            if (activeThinkingRef.current) setActiveThinking(false);
            setActiveReasoning(false);
            // Schedule a brief delayed spinner for the new step while waiting for tool/tool args
            cancelDelayedThinking();
            if (animationsEnabled) {
              scheduleDelayedThinking({ delay: 0, context: 'tool_execution', addSpacer: false });
            }
          }

          // Move non-thinking items to completed (excluding output fragments, separators, dividers handled above)
          const newCompletedEvents = regularEvents.filter(e =>
            e.type !== 'thinking' &&
            e.type !== 'output' &&
            e.type !== 'separator' &&
            e.type !== 'divider'
          );
          if (newCompletedEvents.length > 0) {
completedBufRef.current.pushMany(newCompletedEvents);
            scheduleCompletedEventsUpdate();
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
      const preserved: DisplayStreamEvent[] = [];
      const aggEv = flushAggregatedOutput();
      if (aggEv) preserved.push(aggEv as any);
      resetAllBuffers(preserved);
    };
    
    executionService.on('complete', handleComplete);
    // Use a stable function reference so we can remove it in cleanup
    const handleStopped = () => {
      suppressTerminationBannerRef.current = true;
      const preserved: DisplayStreamEvent[] = [];
      const aggEv = flushAggregatedOutput();
      if (aggEv) preserved.push(aggEv as any);
      resetAllBuffers(preserved);
    };
    executionService.on('stopped', handleStopped);

    // Cleanup
    return () => {
      // Clean up any delayed thinking timers
      cancelDelayedThinking();
      cancelPostToolIdleTimer();
      cancelPostReasoningIdleTimer();
      if (pendingTimerRef.current) {
        clearTimeout(pendingTimerRef.current);
        pendingTimerRef.current = null;
      }
      if (activeUpdateTimerRef.current) {
        clearTimeout(activeUpdateTimerRef.current);
        activeUpdateTimerRef.current = null;
      }
      if (pendingStateUpdateRef.current) {
        clearTimeout(pendingStateUpdateRef.current);
        pendingStateUpdateRef.current = null;
      }
      executionService.off('event', handleEvent);
      executionService.off('complete', handleComplete);
      executionService.off('stopped', handleStopped);
    };
  }, [executionService, onEvent, onMetricsUpdate, sessionId, resetAllBuffers]); // Removed 'metrics' - not used in effect, was causing re-runs on every token update

  if (collapsed) {
    return null;
  }


  // Check if we have thinking-only events (spinner without other content)
  const hasOnlyThinkingInActive = activeEvents.length > 0 &&
    activeEvents.every(e => e.type === 'thinking' || e.type === 'thinking_end');

  return (
    <Box flexDirection="column" flexGrow={1}>
      {/* Completed events - rendered normally (Static component broke rendering) */}
      {completedEvents.length > 0 && (
        <StaticStreamDisplay
          events={completedEvents}
          terminalWidth={terminalWidth}
          availableHeight={availableHeight}
        />
      )}

      {/* Thinking-only spinner rendered IMMEDIATELY after completed content for visibility */}
      {hasOnlyThinkingInActive && (
        <StreamDisplay
          events={activeEvents}
          animationsEnabled={animationsEnabled}
          terminalWidth={terminalWidth}
          availableHeight={availableHeight}
        />
      )}

      {/* Active events with content (reasoning, output, etc) */}
      {activeEvents.length > 0 && !hasOnlyThinkingInActive && (
        <StreamDisplay
          events={activeEvents}
          animationsEnabled={animationsEnabled}
          terminalWidth={terminalWidth}
          availableHeight={availableHeight}
        />
      )}
    </Box>
  );
});
