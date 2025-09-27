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
import { RingBuffer } from '../utils/RingBuffer.js';
import { ByteBudgetRingBuffer } from '../utils/ByteBudgetRingBuffer.js';
import { DISPLAY_LIMITS } from '../constants/config.js';

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
  // Limit event buffer to prevent memory leaks - events are already persisted to disk
const MAX_EVENTS = Number(process.env.CYBER_MAX_EVENTS || 3000); // Keep last N events in memory (default 3000)
  const [completedEvents, setCompletedEvents] = useState<DisplayStreamEvent[]>([]);
  const [activeEvents, setActiveEvents] = useState<DisplayStreamEvent[]>([]);
  // Ring buffers to bound memory regardless of session length
  const MAX_EVENT_BYTES = Number(process.env.CYBER_MAX_EVENT_BYTES || 8 * 1024 * 1024); // 8 MiB default
  const completedBufRef = useRef(new ByteBudgetRingBuffer<DisplayStreamEvent>(MAX_EVENT_BYTES, (e) => {
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
  }));
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
  const METRICS_COALESCE_MS = 150;
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
  
  // Swarm operation tracking for proper event enhancement
  const [swarmActive, setSwarmActive] = useState(false);
  const [currentSwarmAgent, setCurrentSwarmAgent] = useState<string | null>(null);
  const swarmHandoffSequenceRef = useRef(0);
  const delayedThinkingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const seenThinkingThisPhaseRef = useRef<boolean>(false);
  const suppressTerminationBannerRef = useRef<boolean>(false);
  // Track last reasoning text to prevent duplicate consecutive emissions
  const lastReasoningTextRef = useRef<string | null>(null);
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
        break;

      case 'step_header':
        emitTestMarker(`step_header step=${event.step} max=${event.maxSteps}`);
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

          const reasoningEvent: DisplayStreamEvent = {
            type: 'reasoning',
            content: String(event.content).trim(),
            ...(swarmActive && currentSwarmAgent ? { swarm_agent: currentSwarmAgent } : {})
          } as DisplayStreamEvent;

          // Minimal rule for correctness: always queue reasoning
          // We will flush after tool_end (preferred) or at the next step_header if needed.
          pendingReasoningsRef.current.push(reasoningEvent);
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
        
      case 'output':
        emitTestMarker('output');
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
          
          // Clear any active thinking when output appears
          if (activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            setActiveThinking(false);
          }
          
          // Reorder operation summary vs report preview/content: buffer op-summary and flush after report
          const fromToolBuffer = !!((event as any).metadata && (event as any).metadata.fromToolBuffer);
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

          // Push normal output
          const outEvt: DisplayStreamEvent = {
            type: 'output',
            content: event.content,
            toolId: currentToolId
          } as DisplayStreamEvent;
          results.push(outEvt);

          // If this is a report preview block, immediately flush any buffered operation summary below it
          if (isReportPreview && opSummaryBufferRef.current.length > 0) {
            results.push(...opSummaryBufferRef.current);
            opSummaryBufferRef.current = [];
          }
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
        
        // Flush any pending reasoning so it appears below the outputs of this tool call
        flushPendingReasoning(results);

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
                // Add a tiny spacer into the completed ring buffer without unbounded growth
                completedBufRef.current.push({ type: 'output', content: '' } as DisplayStreamEvent);
                completedBufRef.current.push({ type: 'output', content: '' } as DisplayStreamEvent);
                setCompletedEvents(completedBufRef.current.toArray());
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
activeBufRef.current.clear();
              activeBufRef.current.push(thinkingEvent);
              setActiveEvents(activeBufRef.current.toArray());
              delayedThinkingTimerRef.current = null;
            }, delay);
            continue;
          }

          if (processedEvent.type === 'thinking_end') {
            // Move thinking events to static when done
setActiveThrottled(prev => {
              activeBufRef.current.clear();
              return activeBufRef.current.toArray();
            });
            continue;
          }

          regularEvents.push(processedEvent);
        }

        if (regularEvents.length > 0) {
          // Move non-thinking items to completed
          const newCompletedEvents = regularEvents.filter(e => e.type !== 'thinking');
          if (newCompletedEvents.length > 0) {
completedBufRef.current.pushMany(newCompletedEvents);
            setCompletedEvents(completedBufRef.current.toArray());
          }

          // Keep current thinking (if any) in active tail without duplication
          const thinkingEvents = regularEvents.filter(e => e.type === 'thinking');
          if (thinkingEvents.length > 0) {
setActiveThrottled(prev => {
            // Keep only latest thinking in active tail
            activeBufRef.current.clear();
            for (const t of thinkingEvents) activeBufRef.current.push(t);
            return activeBufRef.current.toArray();
          });
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
completedBufRef.current.push({ type: 'stop_summary', timestamp: new Date().toISOString() } as unknown as DisplayStreamEvent);
      setCompletedEvents(completedBufRef.current.toArray());
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
    <Box flexDirection="column" flexGrow={1}>
      <>
        {completedEvents.length > 0 && (
          <StaticStreamDisplay events={completedEvents} />
        )}
        {activeEvents.length > 0 && (
          <StreamDisplay events={activeEvents} animationsEnabled={animationsEnabled} />
        )}
      </>
      
      {/* Trailing spacer to avoid footer crowding */}
      <Box>
        <Text> </Text>
      </Box>
    </Box>
  );
});