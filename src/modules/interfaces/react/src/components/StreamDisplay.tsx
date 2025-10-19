/**
 * StreamDisplay - SDK-integrated event streaming for cyber operations
 * Designed for infinite scroll with SDK native events and backward compatibility
 */

import React from 'react';
import { Box, Text } from 'ink';
import { ThinkingIndicator } from './ThinkingIndicator.js';
import { StreamEvent } from '../types/events.js';
import { SwarmDisplay, SwarmState, SwarmAgent } from './SwarmDisplay.js';
import { formatToolInput, getToonPlanPreview } from '../utils/toolFormatters.js';
import { DISPLAY_LIMITS } from '../constants/config.js';
// Removed toolCategories import - using clean tool display without emojis
import * as fs from 'fs/promises';
import * as fsSync from 'fs';
import * as path from 'path';
import stripAnsi from 'strip-ansi';
import { useConfig } from '../contexts/ConfigContext.js';
import type { Config } from '../contexts/ConfigContext.js';

const PROJECT_MARKERS = ['pyproject.toml', path.join('docker', 'docker-compose.yml'), '.git'];
let cachedProjectRoot: string | null | undefined;

const resolveProjectRoot = (): string | null => {
  if (cachedProjectRoot !== undefined) {
    return cachedProjectRoot;
  }
  let currentDir = process.cwd();
  for (let depth = 0; depth < 10; depth += 1) {
    const hasMarker = PROJECT_MARKERS.some(marker => {
      try {
        return fsSync.existsSync(path.join(currentDir, marker));
      } catch {
        return false;
      }
    });
    if (hasMarker) {
      cachedProjectRoot = currentDir;
      return currentDir;
    }
    const parent = path.dirname(currentDir);
    if (parent === currentDir) {
      break;
    }
    currentDir = parent;
  }
  cachedProjectRoot = null;
  return null;
};

// Extended event types for UI-specific events not covered by the core SDK events
// These events are used for UI state management and display formatting
export type AdditionalStreamEvent = 
  | { type: 'step_header'; step: number | string; maxSteps?: number; totalTools?: number; operation?: string; duration?: string; [key: string]: any }
  | { type: 'reasoning'; content: string; [key: string]: any }
  | { type: 'thinking'; context?: 'reasoning' | 'tool_preparation' | 'tool_execution' | 'waiting' | 'startup'; startTime?: number; urgent?: boolean; [key: string]: any }
  | { type: 'thinking_end'; [key: string]: any }
  | { type: 'delayed_thinking_start'; context?: string; startTime?: number; delay?: number; [key: string]: any }
  | { type: 'tool_start'; tool_name: string; tool_input: any; [key: string]: any }
  | { type: 'tool_input_update'; tool_id: string; tool_input: any; [key: string]: any }
  | { type: 'tool_input_corrected'; tool_id: string; tool_input: any; [key: string]: any }
  | { type: 'command'; content: string; [key: string]: any }
  | { type: 'output'; content: string; exitCode?: number; duration?: number; [key: string]: any }
  | { type: 'error'; content: string; [key: string]: any }
  | { type: 'metadata'; content: Record<string, string>; [key: string]: any }
  | { type: 'divider'; [key: string]: any }
  | { type: 'separator'; content?: string; [key: string]: any }
  | { type: 'user_handoff'; message: string; breakout: boolean; [key: string]: any }
  | { type: 'metrics_update'; metrics: any; [key: string]: any }
  | { type: 'model_invocation_start'; modelId?: string; [key: string]: any }
  | { type: 'model_stream_delta'; delta?: string; [key: string]: any }
  | { type: 'reasoning_delta'; delta?: string; [key: string]: any }
  | { type: 'tool_invocation_start'; toolName?: string; toolInput?: any; [key: string]: any }
  | { type: 'tool_invocation_end'; duration?: number; success?: boolean; [key: string]: any }
  | { type: 'event_loop_cycle_start'; cycleNumber?: number; [key: string]: any }
  | { type: 'content_block_delta'; delta?: string; isReasoning?: boolean; [key: string]: any }
  | { type: 'swarm_start'; agent_names?: any[]; agent_details?: any[]; task?: string; [key: string]: any }
  | { type: 'swarm_handoff'; from_agent?: string; to_agent?: string; message?: string; [key: string]: any }
  | { type: 'swarm_complete'; final_agent?: string; execution_count?: number; [key: string]: any }
  | { type: 'specialist_start'; specialist?: string; task?: string; finding?: string; artifactPaths?: string[]; [key: string]: any }
  | { type: 'specialist_progress'; specialist?: string; gate?: number; totalGates?: number; tool?: string; status?: string; [key: string]: any }
  | { type: 'specialist_end'; specialist?: string; result?: any; [key: string]: any }
  | { type: 'batch'; id?: string; events: DisplayStreamEvent[]; [key: string]: any }
  | { type: 'tool_output'; tool: string; status?: string; output?: any; [key: string]: any }
  | { type: 'operation_init'; operation_id?: string; target?: string; objective?: string; memory?: any; [key: string]: any }
  | { type: 'report_paths'; operation_id?: string; target?: string; outputDir?: string; reportPath?: string; logPath?: string; memoryPath?: string; [key: string]: any }
  | { type: 'hitl_pause_requested'; tool_name?: string; tool_id?: string; parameters?: any; reason?: string; confidence?: number; [key: string]: any }
  | { type: 'hitl_feedback_submitted'; feedback_type?: string; content?: string; tool_id?: string; [key: string]: any }
  | { type: 'hitl_agent_interpretation'; tool_id?: string; interpretation?: string; modified_parameters?: any; awaiting_approval?: boolean; [key: string]: any }
  | { type: 'hitl_resume'; tool_id?: string; modified_parameters?: any; approved?: boolean; [key: string]: any };

// Combined event type supporting both SDK-aligned and additional events
export type DisplayStreamEvent = StreamEvent | AdditionalStreamEvent;

// Re-export StreamEvent type for backward compatibility
export type { StreamEvent };

interface StreamDisplayProps {
  events: DisplayStreamEvent[];
  // Configuration for SDK features
  showSDKMetrics?: boolean;
  showPerformanceInfo?: boolean;
  enableCostTracking?: boolean;
  animationsEnabled?: boolean;
  // Terminal dimensions for layout calculations
  terminalWidth?: number;
  availableHeight?: number;
}

// Compute divider dynamically to avoid stale or zero-width when terminal resizes
const getDivider = (): string => {
  try {
    const cols = (process.stdout && (process.stdout as any).columns) ? (process.stdout as any).columns : 80;
    // Ensure a sensible minimum so the line is visible even in constrained environments
    const width = Math.max(60, Number(cols) || 80);
    return '─'.repeat(width);
  } catch {
    return '─'.repeat(80);
  }
};

// Operation context used to locate artifacts like the final report
type OperationContext = {
  operationId?: string | null;
  target?: string | null;
  reportPath?: string | null;
};

// Utility: sanitize target into safe path segment (mirrors Python logic)
const sanitizeTargetForPath = (target: string): string => {
  try {
    let clean = target.replace(/^https?:\/\//, '');
    clean = clean.replace(/\.\./g, '').replace(/\.\//g, '');
    clean = clean.replace(/[^a-zA-Z0-9._-]/g, '_');
    clean = clean.replace(/_+/g, '_');
    clean = clean.slice(0, 100).replace(/^[_\.]+|[_\.]+$/g, '');
    return clean || 'unknown_target';
  } catch {
    return 'unknown_target';
  }
};

// Helper: map container-relative report paths (e.g., /app/outputs/...) to host outputDir
// This is exported for unit tests and to keep behavior consistent anywhere we
// need to interpret backend report paths.
export const mapContainerReportPath = (
  raw: string,
  outputBaseDir?: string | null
): string => {
  try {
    let normalized = raw;
    if (normalized.startsWith('/app/outputs') && outputBaseDir) {
      const suffix = normalized.replace('/app/outputs', '');
      normalized = path.join(outputBaseDir, suffix.replace(/^\/+/, ''));
    }
    return normalized;
  } catch {
    return raw;
  }
};

export const getReportPathCandidates = (
  ctx: OperationContext,
  reportPath: string | null | undefined,
  projectRoot: string | null | undefined,
  outputBaseDir?: string | null | undefined
): string[] => {
  const candidates: string[] = [];

  const addCandidate = (candidate?: string | null) => {
    if (!candidate) return;
    const normalized = path.normalize(candidate);
    if (!candidates.includes(normalized)) {
      candidates.push(normalized);
    }
  };

  // Determine a sensible base directory for relative paths
  const baseDir = (() => {
    try {
      if (outputBaseDir && typeof outputBaseDir === 'string') {
        return outputBaseDir;
      }
      if (projectRoot) {
        return projectRoot;
      }
      return process.cwd();
    } catch {
      return process.cwd();
    }
  })();

  if (reportPath) {
    try {
      if (path.isAbsolute(reportPath)) {
        addCandidate(reportPath);
      } else {
        addCandidate(path.resolve(baseDir, reportPath));
        if (projectRoot && baseDir !== projectRoot) {
          addCandidate(path.resolve(projectRoot, reportPath));
        }
      }
    } catch {
      // Ignore path resolution errors; we'll fall back to inferred paths below
    }
  }

  // Fallback: infer standard unified output path when we know operationId+target
  if (ctx.operationId && ctx.target) {
    const safeTarget = sanitizeTargetForPath(String(ctx.target));
    const relativePath = path.join(
      safeTarget,
      String(ctx.operationId),
      'security_assessment_report.md'
    );

    try {
      addCandidate(path.resolve(baseDir, relativePath));
      if (projectRoot && baseDir !== projectRoot) {
        addCandidate(path.resolve(projectRoot, path.join('outputs', relativePath)));
      }
      // Historical fallback: repo-root/outputs/<target>/<op>/...
      addCandidate(path.resolve(process.cwd(), path.join('outputs', relativePath)));
    } catch {
      // Best-effort only
    }
  }

  return candidates;
};

// Inline viewer to load and render the generated markdown report from disk
const InlineReportViewer: React.FC<{
  ctx: OperationContext;
  reportPath?: string | null;
  fallbackContent?: string | null;
  projectRoot?: string | null;
}>= ({ ctx, reportPath, fallbackContent, projectRoot }) => {
  const [content, setContent] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [resolvedPath, setResolvedPath] = React.useState<string | null>(null);

  // Resolve output base directory locally so this component works in isolation
  const { config } = useConfig();
  const outputBaseDir = React.useMemo(() => {
    try {
      const raw = config.outputDir || './outputs';
      if (path.isAbsolute(raw)) {
        return raw;
      }
      const base = resolveProjectRoot() ?? process.cwd();
      return path.resolve(base, raw);
    } catch {
      return path.resolve(process.cwd(), 'outputs');
    }
  }, [config.outputDir]);

  const candidatePaths = React.useMemo(
    () => getReportPathCandidates(ctx, reportPath ?? null, projectRoot ?? null, outputBaseDir ?? null),
    [ctx.operationId, ctx.target, reportPath, projectRoot, outputBaseDir]
  );

  React.useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        setResolvedPath(null);
        const candidates = candidatePaths;

        if (candidates.length === 0) {
          if (fallbackContent) {
            setContent(fallbackContent);
            return;
          }
          setError('Report context unavailable');
          return;
        }

        let loaded: string | null = null;
        let usedPath: string | null = null;
        for (const candidate of candidates) {
          try {
            if (!fsSync.existsSync(candidate)) {
              continue;
            }
            const data = await fs.readFile(candidate, 'utf-8');
            loaded = data;
            usedPath = candidate;
            break;
          } catch {}
        }
        if (!loaded) {
          if (fallbackContent) {
            setContent(fallbackContent);
            // Fall back to configured reportPath if present
            if (reportPath && path.isAbsolute(reportPath)) {
              setResolvedPath(reportPath);
            }
            return;
          }
          setError('Report file not found');
          if (reportPath && path.isAbsolute(reportPath)) {
            setResolvedPath(reportPath);
          }
          return;
        }
        setContent(loaded);
        if (usedPath) {
          setResolvedPath(usedPath);
        } else if (reportPath && path.isAbsolute(reportPath)) {
          setResolvedPath(reportPath);
        }
      } catch (e: any) {
        setError('Failed to load report');
        if (reportPath && path.isAbsolute(reportPath)) {
          setResolvedPath(reportPath);
        }
      }
    };
    load();
  }, [candidatePaths, fallbackContent, reportPath]);

  if (error) {
    return (
      <Box flexDirection="column" marginTop={1}>
        <Text color="yellow">{error}</Text>
        {(resolvedPath || reportPath) && (
          <Box marginTop={1}>
            <Text dimColor>
              Report saved to: {resolvedPath || reportPath}
            </Text>
          </Box>
        )}
      </Box>
    );
  }
  if (!content) {
    return (
      <Box marginTop={1}>
        <Text dimColor>Loading final report…</Text>
        {(resolvedPath || reportPath) && (
          <Box marginTop={1}>
            <Text dimColor>
              Report saved to: {resolvedPath || reportPath}
            </Text>
          </Box>
        )}
      </Box>
    );
  }

  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const displayLines: string[] =
    lines.length > DISPLAY_LIMITS.REPORT_PREVIEW_LINES + DISPLAY_LIMITS.REPORT_TAIL_LINES
      ? [
          ...lines.slice(0, DISPLAY_LIMITS.REPORT_PREVIEW_LINES),
          '',
          '... (content continues)',
          '',
          ...lines.slice(-DISPLAY_LIMITS.REPORT_TAIL_LINES),
        ]
      : lines;

  const MAX_PREVIEW_LINE_LENGTH = 320;
  const MAX_INLINE_LINES = 160;
  const MAX_INLINE_CHARS = 12000;

  const previewLines = displayLines.slice(0, MAX_INLINE_LINES).map(line => {
    if (line.length > MAX_PREVIEW_LINE_LENGTH) {
      return `${line.slice(0, MAX_PREVIEW_LINE_LENGTH)}…`;
    }
    return line;
  });

  const totalChars = previewLines.reduce((acc, line) => acc + line.length, 0);

  if (totalChars > MAX_INLINE_CHARS) {
    while (previewLines.length > 0 && previewLines.reduce((acc, line) => acc + line.length, 0) > MAX_INLINE_CHARS) {
      previewLines.splice(previewLines.length - 1, 1);
    }
  }

  const truncatedNotice = displayLines.length > previewLines.length || lines.length > DISPLAY_LIMITS.REPORT_PREVIEW_LINES + DISPLAY_LIMITS.REPORT_TAIL_LINES;

  if (previewLines.length === 0) {
    return (
      <Box flexDirection="column" marginTop={1} marginBottom={1}>
        <Box borderStyle="round" borderColor="yellow" paddingX={1}>
          <Text color="yellow" bold>Report preview truncated</Text>
        </Box>
        <Box flexDirection="column" marginTop={1} paddingX={1}>
          <Text dimColor>
            Inline preview suppressed to avoid overwhelming the terminal renderer. Open the saved
            markdown report for the full content.
          </Text>
          {reportPath ? (
            <Text dimColor>Report path: {reportPath}</Text>
          ) : candidatePaths.length > 0 ? (
            <Text dimColor>Report path: {candidatePaths[0]}</Text>
          ) : null}
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" marginTop={1} marginBottom={1}>
      <Box borderStyle="double" borderColor="cyan" paddingX={1}>
        <Text color="cyan" bold>SECURITY ASSESSMENT REPORT</Text>
      </Box>
      <Box flexDirection="column" marginTop={1} paddingX={1}>
        {previewLines.map((line, i) => (
          <Text key={i}>{line}</Text>
        ))}
        {truncatedNotice && (
          <Box marginTop={1}>
            <Text dimColor>
              Preview truncated for brevity. Open the saved markdown report for full content.
            </Text>
          </Box>
        )}
        {(resolvedPath || reportPath) && (
          <Box marginTop={1}>
            <Text dimColor>
              Report saved to: {resolvedPath || reportPath}
            </Text>
          </Box>
        )}
      </Box>
    </Box>
  );
};

// Export EventLine for potential reuse in other components
interface EventLineProps {
  event: DisplayStreamEvent;
  toolInputs?: Map<string, any>;
  animationsEnabled?: boolean;
  operationContext?: OperationContext;
  reportPath?: string | null;
  reportFallbackContent?: string | null;
  projectRoot?: string | null;
  configOverride?: Config;
}

export const EventLine: React.FC<EventLineProps> = React.memo(({
  event,
  toolInputs,
  animationsEnabled = true,
  operationContext,
  reportPath,
  reportFallbackContent,
  projectRoot,
  configOverride,
}) => {
  const { config } = useConfig();
  const effectiveConfig = configOverride ?? config;

  switch (event.type) {
    // =======================================================================
    // SDK NATIVE EVENT HANDLERS - Integrated with SDK context
    // =======================================================================
    case 'model_invocation_start':
      return (
        <>
          <Text color="blue" bold>model invocation started</Text>
          {'modelId' in event && event.modelId ? (
            <Text dimColor>Model: {event.modelId}</Text>
          ) : null}
          <Text> </Text>
        </>
      );
      
    case 'model_stream_delta':
      return (
        <>
          {'delta' in event && event.delta ? (
            <Text>{event.delta}</Text>
          ) : null}
        </>
      );
      
    case 'reasoning_delta':
      // Don't display reasoning_delta directly - let the aggregator handle it
      return null;
      
    case 'tool_invocation_start':
      // Skip rendering here - we handle tool display in 'tool_start' event
      // This prevents duplicate tool displays
      return null;
      
    case 'tool_invocation_end':
      // Don't show "tool completed" - just let the output speak for itself
      return null;
      
    case 'event_loop_cycle_start':
      return (
        <>
          <Text color="blue" bold>
            [CYCLE {'cycleNumber' in event ? event.cycleNumber : '?'}] Event loop cycle started
          </Text>
          <Text> </Text>
        </>
      );
      
    case 'metrics_update':
      // Do not render metrics inline; Footer displays tokens/cost/duration.
      return null;
      
    case 'content_block_delta':
      return (
        <>
          {'delta' in event && event.delta ? (
            <Text>{'isReasoning' in event && event.isReasoning ? 
              <Text color="cyan">{event.delta}</Text> : 
              <Text>{event.delta}</Text>
            }</Text>
          ) : null}
        </>
      );
      
    // =======================================================================
    // LEGACY EVENT HANDLERS - Backward compatibility
    // =======================================================================
    case 'step_header':
      // Detect if this is a swarm step and format appropriately
      let stepDisplay = '';
      
      // Access properties through bracket notation to bypass TypeScript checks
      const swarmAgent = (event as any)['swarm_agent'];
      const swarmSubStep = (event as any)['swarm_sub_step'];
      const swarmTotalIterations = (event as any)['swarm_total_iterations'];
      const swarmMaxIterations = (event as any)['swarm_max_iterations'];
      const isSwarmOperation = (event as any)['is_swarm_operation'];
      
      if (event.step === "FINAL REPORT") {
        stepDisplay = "[FINAL REPORT]";
      } else if (typeof event.step === 'string' && String(event.step).toUpperCase() === 'TERMINATED') {
        // Clean termination header without confusing step counters
        stepDisplay = "[TERMINATED]";
      } else if (swarmAgent && swarmSubStep) {
        // For swarm operations, show agent name with their step count and swarm-wide progress
        // Use replaceAll to handle multi-word agent names correctly
        const agentName = String(swarmAgent).toUpperCase().replaceAll('_', ' ');
        // Show agent's step count and swarm-wide iteration progress (no max cap shown)
        const swarmTotal = (event as any)['swarm_total_iterations'] ?? swarmSubStep;
        stepDisplay = `[SWARM: ${agentName} • STEP ${swarmSubStep} | SWARM TOTAL ${swarmTotal}]`;
      } else if (isSwarmOperation) {
        // Generic swarm operation without specific agent
        stepDisplay = `[SWARM • STEP ${event.step}/${event.maxSteps}]`;
      } else {
        // Regular step header with tool count for budget transparency
        const toolCount = (event as any)['totalTools'];
        if (toolCount && toolCount > 0) {
          stepDisplay = `[STEP ${event.step}/${event.maxSteps} | ${toolCount} tools]`;
        } else {
          stepDisplay = `[STEP ${event.step}/${event.maxSteps}]`;
        }
      }
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box flexDirection="row" alignItems="center">
            <Text color="#89B4FA" bold>
              {stepDisplay}
            </Text>
          </Box>
          <Text color="#45475A">{getDivider()}</Text>
          {/* If this is the FINAL REPORT and we have operation context, render the report inline */}
          {event.step === 'FINAL REPORT' && operationContext && (
            <InlineReportViewer
              ctx={{
                ...operationContext,
                reportPath: reportPath ?? operationContext.reportPath ?? null,
              }}
              reportPath={reportPath ?? operationContext.reportPath ?? null}
              fallbackContent={reportFallbackContent ?? null}
              projectRoot={projectRoot ?? null}
            />
          )}
        </Box>
      );
      
    case 'thinking':
      return (
        <ThinkingIndicator
          context={event.context}
          startTime={event.startTime}
          enabled={animationsEnabled}
        />
      );
      
    case 'thinking_end':
      // Don't render anything - this just signals to stop showing thinking indicator
      return null;
      
    case 'delayed_thinking_start':
      // Don't render anything - this is handled by the terminal component
      return null;
      
    case 'termination_reason': {
      // Suppress iteration-limit notifications entirely; SDK governs swarm limits
      const reason = (event as any).reason as string | undefined;
      const msg = (event as any).message as string | undefined;
      if ((typeof reason === 'string' && reason.toLowerCase().includes('swarm')) ||
          (typeof msg === 'string' && msg.toLowerCase().includes('swarm iteration limit'))) {
        return null;
      }
      // Display a simple termination notification (no emojis)
      let reasonLabel = 'TERMINATED';
      switch (reason) {
        case 'stop_tool':
          reasonLabel = 'STOP TOOL';
          break;
        case 'step_limit':
          reasonLabel = 'STEP LIMIT';
          break;
        case 'user_abort':
          reasonLabel = 'TERMINATED';
          break;
        case 'network_timeout':
        case 'network_error':
        case 'timeout':
          reasonLabel = 'NETWORK TIMEOUT';
          break;
        case 'max_tokens':
          reasonLabel = 'TOKEN LIMIT';
          break;
        case 'rate_limited':
          reasonLabel = 'RATE LIMITED';
          break;
        case 'model_error':
          reasonLabel = 'MODEL ERROR';
          break;
        default:
          reasonLabel = 'TERMINATED';
      }
      const normalizedReason = (reason || '').toLowerCase();
      const sanitizedMessage =
        typeof msg === 'string'
          ? (msg.replace(/\s*Switching to final report\.?/gi, '').trim() || 'Provider/network timeout detected.')
          : msg;
      const likelyNetworkIssue = ['network_timeout', 'network_error', 'timeout'].includes(normalizedReason);
      const providerLabel = (() => {
        const providerId = effectiveConfig?.modelProvider;
        if (!providerId) return 'model provider';
        const labelMap: Record<'bedrock' | 'ollama' | 'litellm', string> = {
          bedrock: 'AWS Bedrock',
          ollama: 'Ollama',
          litellm: 'LiteLLM'
        };
        return labelMap[providerId] ?? providerId.replace(/_/g, ' ');
      })();
      const helpHints: string[] = [];
      if (likelyNetworkIssue) {
        if (effectiveConfig?.modelProvider) {
          helpHints.push(`Provider configured as "${providerLabel}".`);
        } else {
          helpHints.push('No model provider configured. Open Settings → Provider to configure credentials.');
        }
        if (effectiveConfig?.awsRegion) {
          helpHints.push(`Region set to "${effectiveConfig.awsRegion}". Verify this matches your ${providerLabel} deployment.`);
        }
        if (effectiveConfig?.ollamaHost && effectiveConfig.modelProvider === 'ollama') {
          helpHints.push(`Attempted to reach Ollama at ${effectiveConfig.ollamaHost}. Ensure the host is reachable.`);
        }
        helpHints.push('Confirm credentials/network access, then retry the assessment.');
      }
      return (
        <Box flexDirection="column" marginTop={1} marginBottom={1}>
          <Box borderStyle="round" borderColor="yellow" paddingX={1}>
            <Text color="yellow" bold>{reasonLabel}: {sanitizedMessage}</Text>
          </Box>
          {helpHints.length > 0 && (
            <Box marginLeft={2} marginTop={1} flexDirection="column">
              {helpHints.map((hint, idx) => (
                <Text key={idx} color="yellow">• {hint}</Text>
              ))}
            </Box>
          )}
        </Box>
      );
    }
      
    case 'reasoning':
      // This case should not be reached anymore as reasoning is handled in StreamDisplay
      // But keep it as fallback
      const swarmAgentLabel = ('swarm_agent' in event && event.swarm_agent)
        ? ` (${event.swarm_agent})`
        : '';
      return (
        <Box flexDirection="column">
          <Text color="cyan" bold>reasoning{swarmAgentLabel}</Text>
          <Box paddingLeft={0}>
            <Text color="cyan">{event.content}</Text>
          </Box>
          <Text> </Text>
        </Box>
      );
      
    case 'tool_start': {
      // Get the latest tool input (may have been updated via tool_input_update)
      // First check if we have updated input in the toolInputs Map, otherwise use the event's tool_input
      const toolId = (event as any).toolId ?? (event as any).tool_id;
      // Prefer the richer input from the current event; fall back to stored map only if event input is absent/empty
      const eventInput = (("tool_input" in event) ? (event as any).tool_input : undefined) as any;
      const hasEventInput = (() => {
        if (eventInput == null) return false;
        if (typeof eventInput === 'string') return eventInput.trim().length > 0;
        if (Array.isArray(eventInput)) return eventInput.length > 0;
        if (typeof eventInput === 'object') return Object.keys(eventInput).length > 0;
        return !!eventInput;
      })();
      const mapInput = (toolId && toolInputs?.get(toolId)) as any;
      const hasMapInput = (() => {
        if (mapInput == null) return false;
        if (typeof mapInput === 'string') return mapInput.trim().length > 0;
        if (Array.isArray(mapInput)) return mapInput.length > 0;
        if (typeof mapInput === 'object') return Object.keys(mapInput).length > 0;
        return !!mapInput;
      })();
      // Choose the input that actually contains the fields needed for rendering.
      // In particular, python_repl often arrives with a trimmed eventInput (code omitted by normalizer),
      // while a subsequent tool_input_update holds the full code. Prefer the map input in that case.
      const getPyCode = (inp: any): string => {
        if (!inp) return '';
        const v = inp.code ?? inp.source ?? inp.input ?? inp.code_preview;
        return typeof v === 'string' ? v : (v != null ? (() => { try { return JSON.stringify(v); } catch { return String(v); } })() : '');
      };
      let latestInput: any = eventInput;
      if (event.tool_name === 'python_repl') {
        const evCode = getPyCode(eventInput);
        const mapCode = getPyCode(mapInput);
        if ((!evCode || evCode.trim().length === 0) && (mapCode && mapCode.trim().length > 0)) {
          latestInput = mapInput;
        } else if (!hasEventInput && hasMapInput) {
          latestInput = mapInput;
        }
      } else {
        latestInput = hasEventInput ? eventInput : (hasMapInput ? mapInput : {});
      }
      
      // Always show tool header even if args are not yet available.
      // Individual tool renderers will gracefully handle missing fields.
      // Otherwise handle specific tool formatting
      switch (event.tool_name) {
        case 'swarm':
          // Simplified swarm tool header to avoid duplication
          // Ensure agents is an array before processing
          const agents = Array.isArray(latestInput?.agents) ? latestInput.agents : [];
          const agentCount = agents.length || 0;
          const agentNames = agents.map((a: any) =>
            typeof a === 'string' ? a : (a?.name || 'agent')
          ).filter(Boolean).slice(0, 4).join(', ') || 'agents';

          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="yellow" bold>tool: swarm</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ deploying {agentCount} agents: {agentNames}</Text>
              </Box>
            </Box>
          );
        case 'mem0_memory': {
          const action = latestInput?.action || 'list';
          const rawContent = latestInput?.content || latestInput?.query || '';
          // Ensure content is always a string (handle plan objects, etc.)
          let content: string;
          if (typeof rawContent === 'string') {
            content = rawContent;
          } else if (rawContent && typeof rawContent === 'object') {
            try {
              content = JSON.stringify(rawContent);
            } catch {
              content = String(rawContent);
            }
          } else {
            content = String(rawContent);
          }
          const planPreview = getToonPlanPreview(content);
          const preview = planPreview ?? (content.length > 60 ? content.substring(0, 60) + '...' : content);
          const labelKey =
            planPreview || action === 'store_plan'
              ? 'plan'
              : action === 'store'
                ? 'content'
                : 'query';

          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: mem0_memory</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ action: {action === 'store_plan' ? 'store_plan' : action === 'store' ? 'storing' : action === 'retrieve' ? 'retrieving' : action}</Text>
              </Box>
              {preview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ {labelKey}: {preview}</Text>
                </Box>
              )}
              {!preview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ </Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'shell': {
          // Show tool header with command(s) if available
          const agentContext = ('swarm_agent' in event && event.swarm_agent) 
            ? ` (${event.swarm_agent})` : '';

          // Pull raw commands from the most permissive set of fields
          const rawInput: any = (latestInput as any) || {};
          let raw = rawInput.commands ?? rawInput.command ?? rawInput.cmd ?? rawInput.input ?? '';

          // Helper to stringify any command entry into a single shell line
          const stringifyCommandEntry = (entry: any): string => {
            if (entry === null || entry === undefined) return '';
            if (typeof entry === 'string') return entry;
            if (Array.isArray(entry)) {
              // Join parts (args arrays)
              const parts = entry.map((p) => stringifyCommandEntry(p)).filter(Boolean);
              return parts.join(' ');
            }
            if (typeof entry === 'object') {
              // Prefer well-known keys in order
              if ('command' in entry) return stringifyCommandEntry((entry as any).command);
              if ('cmd' in entry) return stringifyCommandEntry((entry as any).cmd);
              if ('value' in entry) return stringifyCommandEntry((entry as any).value);
              if ('args' in entry) return stringifyCommandEntry((entry as any).args);
              // Last resort - structured but unknown: JSON.stringify to avoid [object Object]
              try {
                return JSON.stringify(entry);
              } catch {
                return String(entry);
              }
            }
            return String(entry);
          };

          // Normalize raw into a string[] of commands
          let commands: any[] = [];
          try {
            if (Array.isArray(raw)) {
              commands = raw.map((e: any) => stringifyCommandEntry(e)).filter(Boolean);
            } else if (typeof raw === 'string') {
              const trimmed = raw.trim();
              if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
                // JSON-looking string: try to parse
                try {
                  const parsed = JSON.parse(trimmed);
                  if (Array.isArray(parsed)) {
                    commands = parsed.map((e: any) => stringifyCommandEntry(e)).filter(Boolean);
                  } else {
                    const s = stringifyCommandEntry(parsed);
                    if (s) commands = [s];
                  }
                } catch {
                  // Fallback: keep as single command line
                  if (trimmed) commands = [trimmed];
                }
              } else {
                if (trimmed) commands = [trimmed];
              }
            } else if (typeof raw === 'object' && raw) {
              const s = stringifyCommandEntry(raw);
              if (s) commands = [s];
            }
          } catch {
            // If anything fails, ensure commands is at least empty array
            commands = Array.isArray(raw) ? raw.map((e: any) => String(e)).filter(Boolean) : [];
          }

          // Final safety: ensure all commands are strings to avoid "[object Object]"
          const toDisplayString = (x: any): string => {
            if (typeof x === 'string') return x;
            try { return JSON.stringify(x); } catch { return String(x); }
          };
          const displayCommands: string[] = commands.map(toDisplayString).filter(Boolean);

          // Display commands with timeout/parallel info if available
          const hasTimeout = rawInput?.timeout;
          const hasParallel = rawInput?.parallel;
          const extraParams = [] as string[];
          if (hasTimeout) extraParams.push(`timeout: ${rawInput.timeout}s`);
          if (hasParallel) extraParams.push('parallel execution');

          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: shell{agentContext}</Text>
              {displayCommands.length > 0 ? (
                displayCommands.map((cmd, index) => {
                  const isLastCommand = index === displayCommands.length - 1 && extraParams.length === 0;
                  const prefix = isLastCommand ? '└─' : '├─';
                  return (
                    <Box key={index} marginLeft={2}>
                      <Text dimColor>{prefix} {cmd}</Text>
                    </Box>
                  );
                })
              ) : (
                <Box marginLeft={2}>
<Text dimColor>└─ (awaiting args …)</Text>
                </Box>
              )}
              {extraParams.length > 0 && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ {extraParams.join(' | ')}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'http_request': {
const method = latestInput.method || 'GET';
          const url = latestInput.url || '';
          const urlDisplay = url && url.trim().length > 0 ? url : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: http_request</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ method: {method}</Text>
              </Box>
              <Box marginLeft={2}>
<Text dimColor>└─ url: {urlDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_goto_url': {
          const url = latestInput.url || '';
          const urlDisplay = url && url.trim().length > 0 ? url : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_goto_url</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ url: {urlDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_perform_action': {
          const action = latestInput.action || '';
          const actionDisplay = action && action.trim().length > 0 ? action : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_perform_action</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ action: {actionDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_observe_page': {
          const instruction = latestInput.instruction || '';
          const instructionDisplay = instruction && instruction.trim().length > 0 ? instruction : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_observe_page</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ instruction: {instructionDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_evaluate_js': {
          const expression = latestInput.expression || '';
          const expressionDisplay = expression && expression.trim().length > 0 ? expression : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_evaluate_js</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ instruction: {expressionDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_get_cookies': {
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_get_cookies</Text>
            </Box>
          );
        }

        case 'browser_get_page_html': {
          // This tool operates on the browser's current page and has no input arguments.
          // Still, show a short description so the user understands what is happening.
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_get_page_html</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ capture HTML of the current page and save as an artifact</Text>
              </Box>
            </Box>
          );
        }

        case 'browser_set_headers': {
          const headers = latestInput.headers || {};
          const headersDisplay = Object.keys(headers).length > 0 ? JSON.stringify(headers) : '(awaiting args …)';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: browser_set_headers</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ headers: {headersDisplay}</Text>
              </Box>
            </Box>
          );
        }

        case 'file_write': {
          const filePath = latestInput.path || 'unknown';
          const fileContent = latestInput.content || '';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: file_write</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ path: {filePath}</Text>
              </Box>
              {fileContent && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ size: {fileContent.length} chars</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'editor': {
          const editorCmd = latestInput.command || 'edit';
          const editorPath = latestInput.path || '';
          // Support multiple possible input fields for content
          const editorContent = latestInput.content ?? latestInput.file_text ?? latestInput.text ?? '';
          // Compute size in lines if we have text content
          const contentStr = typeof editorContent === 'string' ? editorContent : (() => { try { return JSON.stringify(editorContent, null, 2); } catch { return String(editorContent ?? ''); } })();
          const lineCount = contentStr ? (contentStr.split('\n').length) : 0;
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: editor</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ command: {editorCmd}</Text>
              </Box>
              <Box marginLeft={2}>
                <Text dimColor>{(contentStr && contentStr.length > 0) ? '├─' : '└─'} path: {editorPath}</Text>
              </Box>
              {(contentStr && contentStr.length > 0) && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ size: {lineCount} {lineCount === 1 ? 'line' : 'lines'}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        
        case 'think': {
          // think output goes to reasoning, but still show tool invocation
          const thought = latestInput.thought || latestInput.content || '';
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: think</Text>
              {thought && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ {thought.length > 100 ? thought.substring(0, 100) + '...' : thought}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'python_repl': {
          const code = (latestInput && (latestInput.code ?? latestInput.source ?? latestInput.input ?? latestInput.code_preview)) || '';
          const codeStr = typeof code === 'string' ? code : (() => { try { return JSON.stringify(code, null, 2); } catch { return String(code ?? ''); } })();
          const codeLines = codeStr.split('\n');
          const previewLines = 8; // Increased from 5 to show more context
          let codeDisplayLines: string[];
          if (!codeStr || codeStr.trim().length === 0) {
            codeDisplayLines = [];
          } else if (codeLines.length <= previewLines) {
            codeDisplayLines = codeLines;
          } else {
            // Show first 6 lines and last 2 lines for better context
            codeDisplayLines = [
              ...codeLines.slice(0, 6),
              '',
              `... (${codeLines.length - 8} more lines)`,
              '',
              ...codeLines.slice(-2)
            ];
          }
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: python_repl</Text>
              <Box marginLeft={2} flexDirection="column">
                <Text dimColor>└─ code:</Text>
                {codeDisplayLines.length === 0 ? (
                  <Box marginLeft={5}><Text dimColor>(waiting for code input)</Text></Box>
                ) : (
                  <Box marginLeft={5} flexDirection="column">
                    {codeDisplayLines.map((line, index) => {
                      // Don't show tree characters for code content
                      if (line.startsWith('...')) {
                        return <Text key={index} dimColor italic>    {line}</Text>;
                      }
                      return <Text key={index} dimColor>    {line || ' '}</Text>;
                    })}
                  </Box>
                )}
              </Box>
            </Box>
          );
        }
          
        case 'report_generator': {
          const target = latestInput.target || 'unknown';
          const reportType = latestInput.report_type || latestInput.type || 'general';
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: report_generator</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ target: {target}</Text>
              </Box>
              <Box marginLeft={2}>
                <Text dimColor>└─ type: {reportType}</Text>
              </Box>
            </Box>
          );
        }
          
        case 'handoff_to_agent': {
          // Prefer explicit agent_name (set by backend), then handoff_to, then other fallbacks
          const handoffTo = latestInput.agent_name || latestInput.handoff_to || latestInput.agent || latestInput.target_agent || 'unknown';
          const handoffMsg = latestInput.message || '';
          const msgPreview = handoffMsg.length > 80 ? handoffMsg.substring(0, 80) + '...' : handoffMsg;
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: handoff_to_agent</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ handoff_to: {handoffTo}</Text>
              </Box>
              {msgPreview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ message: {msgPreview}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'load_tool': {
          const toolName = latestInput.tool_name || latestInput.tool || latestInput.name || 'unknown';
          const toolPath = latestInput.path || '';
          const toolDescription = latestInput.description || '';
          const hasPath = !!toolPath;
          const hasDesc = !!toolDescription;
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: load_tool</Text>
              <Box marginLeft={2}>
                <Text dimColor>{hasPath || hasDesc ? '├─' : '└─'} loading: {toolName}</Text>
              </Box>
              {toolPath && (
                <Box marginLeft={2}>
                  <Text dimColor>{hasDesc ? '├─' : '└─'} path: {toolPath}</Text>
                </Box>
              )}
              {toolDescription && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ description: {toolDescription}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'stop': {
          // Show clean stop tool header with reason
          const stopReason = (latestInput && (latestInput.reason || latestInput.message)) || 'Manual stop requested';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: stop</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ reason: {stopReason}</Text>
              </Box>
            </Box>
          );
        }

        default: {
          // Enhanced tool display with swarm agent context and structured parameters
          const agentContext = ('swarm_agent' in event && event.swarm_agent) 
            ? ` (${event.swarm_agent})` : '';
          
          // Check if tool_input is an object with multiple properties for structured display
          const toolInput = latestInput;
          const isStructuredInput = toolInput && typeof toolInput === 'object' && !Array.isArray(toolInput);
          
          if (isStructuredInput && Object.keys(toolInput).length > 0) {
            // Display structured parameters with tree format
            const params = Object.entries(toolInput);
            const paramCount = params.length;
            
            return (
              <Box flexDirection="column" marginTop={1}>
                <Text color="green" bold>tool: {event.tool_name}{agentContext}</Text>
                {params.map(([key, value], index) => {
                  const isLast = index === paramCount - 1;
                  const prefix = isLast ? '└─' : '├─';
                  
                  // Format value based on type
                  let displayValue: string;
                  if (value === null || value === undefined) {
                    displayValue = 'null';
                  } else if (typeof value === 'string') {
                    // Truncate long strings
                    displayValue = value.length > 100 ? value.substring(0, 100) + '...' : value;
                  } else if (Array.isArray(value)) {
                    displayValue = `[${value.length} items]`;
                  } else if (typeof value === 'object') {
                    displayValue = '{...}';
                  } else {
                    displayValue = String(value);
                  }
                  
                  return (
                    <Box key={key} marginLeft={2}>
                      <Text dimColor>{prefix} {key}: {displayValue}</Text>
                    </Box>
                  );
                })}
              </Box>
            );
          }
          
          // Fallback to single-line preview for non-structured inputs
          const preview = formatToolInput(event.tool_name as any, toolInput);
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: {event.tool_name}{agentContext}</Text>
              {preview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ {preview}</Text>
                </Box>
              )}
            </Box>
          );
        }
      }
    }

    case 'command':
          // Robustly derive a displayable command string from event.content
          let commandText: string = '';
          try {
            if (typeof event.content === 'string') {
              const raw = event.content.trim();
              if (raw.startsWith('{')) {
                try {
                  const parsed = JSON.parse(raw);
                  commandText = parsed && parsed.command ? String(parsed.command) : raw;
                } catch {
                  commandText = raw; // Keep as-is if JSON parse fails
                }
              } else {
                commandText = raw;
              }
            } else if (event.content && typeof event.content === 'object') {
              // Avoid [object Object] by JSON stringifying unknown structures
              try {
                commandText = JSON.stringify(event.content);
              } catch {
                commandText = String(event.content);
              }
            } else {
              commandText = String(event.content ?? '');
            }
          } catch {
            commandText = String((event as any).content ?? '');
          }
          
          return (
            <Box flexDirection="column" marginLeft={2}>
              <Text><Text dimColor>├─</Text> {commandText}</Text>
            </Box>
          );

    case 'report_content': {
      // Render the final report content directly from the event
      // This handles massive reports (1000+ lines) that can overwhelm terminal rendering
      try {
        const content = typeof (event as any).content === 'string' ? (event as any).content : JSON.stringify((event as any).content, null, 2);
        const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');

        // Safety limits to prevent terminal overload
        const maxHead = DISPLAY_LIMITS.REPORT_CONTENT_PREVIEW_LINES || 100;
        const maxTail = DISPLAY_LIMITS.REPORT_CONTENT_TAIL_LINES || 30;
        const maxLineLength = DISPLAY_LIMITS.REPORT_CONTENT_MAX_LINE_LENGTH || 320;
        const maxTotalChars = DISPLAY_LIMITS.REPORT_CONTENT_MAX_TOTAL_CHARS || 30000;
        const maxLines = DISPLAY_LIMITS.REPORT_CONTENT_MAX_LINES || 150;

        // Calculate total character count for safety check
        const totalChars = content.length;

        // If content is extremely large, show minimal preview with clear message
        if (totalChars > maxTotalChars || lines.length > maxLines) {
          // Extract report path from content if backend prepended it
          const pathMatch = content.match(/^\[REPORT_PATH: ([^\]]+)\]/);
          const reportPathHint = pathMatch
            ? pathMatch[1]
            : operationContext?.reportPath || 'Check operation output directory for security_assessment_report.md';

          // Remove path marker from display if present
          const displayContent = pathMatch ? content.replace(/^\[REPORT_PATH: [^\]]+\]\n\n/, '') : content;
          const displayLines = displayContent.split('\n');

          return (
            <Box flexDirection="column" marginTop={1} marginBottom={1}>
              <Box borderStyle="double" borderColor="yellow" paddingX={1}>
                <Text color="yellow" bold>SECURITY ASSESSMENT REPORT (Preview Truncated)</Text>
              </Box>
              <Box flexDirection="column" marginTop={1} paddingX={1}>
                <Text color="yellow" bold>Report size: {lines.length.toLocaleString()} lines ({Math.round(totalChars / 1024)}KB)</Text>
                <Text dimColor>Inline preview suppressed to prevent terminal overload.</Text>
                <Text> </Text>
                <Text color="cyan" bold>Full report saved to disk:</Text>
                <Text color="cyan">{reportPathHint}</Text>
                <Text> </Text>
                <Text dimColor>First {Math.min(20, displayLines.length)} lines:</Text>
                {displayLines.slice(0, Math.min(20, displayLines.length)).map((line, i) => {
                  const truncated = line.length > maxLineLength
                    ? line.slice(0, maxLineLength) + '…'
                    : line;
                  return <Text key={i} dimColor>{truncated}</Text>;
                })}
                <Text> </Text>
                <Text dimColor>... ({displayLines.length - 20} more lines in saved file)</Text>
              </Box>
            </Box>
          );
        }

        // For reasonable-sized reports, show truncated inline version
        const displayLines = lines.length > (maxHead + maxTail)
          ? [...lines.slice(0, maxHead), '', '... (content continues)', '', ...lines.slice(-maxTail)]
          : lines;

        // Truncate individual lines to prevent terminal width issues
        const truncatedLines = displayLines.map(line =>
          line.length > maxLineLength ? line.slice(0, maxLineLength) + '…' : line
        );

        return (
          <Box flexDirection="column" marginTop={1} marginBottom={1}>
            <Box borderStyle="double" borderColor="cyan" paddingX={1}>
              <Text color="cyan" bold>SECURITY ASSESSMENT REPORT</Text>
            </Box>
            <Box flexDirection="column" marginTop={1} paddingX={1}>
              {truncatedLines.map((line, i) => (
                <Text key={i}>{line}</Text>
              ))}
              {lines.length > (maxHead + maxTail) && (
                <Box marginTop={1}>
                  <Text dimColor>Full report saved to disk - check operation output directory</Text>
                </Box>
              )}
            </Box>
          </Box>
        );
      } catch (error) {
        // Fallback if rendering fails - at least show something to the user
        return (
          <Box flexDirection="column" marginTop={1} marginBottom={1}>
            <Box borderStyle="double" borderColor="red" paddingX={1}>
              <Text color="red" bold>REPORT GENERATION ERROR</Text>
            </Box>
            <Box flexDirection="column" marginTop={1} paddingX={1}>
              <Text color="red">Failed to render report content</Text>
              <Text dimColor>Report was generated but could not be displayed inline</Text>
              <Text> </Text>
              <Text color="cyan">Full report saved to:</Text>
              <Text color="cyan">./outputs/[target]/[operation_id]/security_assessment_report.md</Text>
            </Box>
          </Box>
        );
      }
    }

    case 'report_paths': {
      const opId = (event as any).operation_id || '';
      const target = (event as any).target || '';
      const outputDir = (event as any).outputDir || '';
      const reportPath = (event as any).reportPath || '';
      const logPath = (event as any).logPath || '';
      const memoryPath = (event as any).memoryPath || '';
      return (
        <Box flexDirection="column" marginTop={1} marginBottom={1}>
          <Box borderStyle="round" borderColor="green" paddingX={1}>
            <Text color="green" bold>ARTIFACTS AND LOGS</Text>
          </Box>
          <Box flexDirection="column" marginTop={1} paddingX={1}>
            {opId ? (<Text>Operation ID: {opId}</Text>) : null}
            {target ? (<Text>Target: {target}</Text>) : null}
            {outputDir ? (<Text>Operation Path: {outputDir}</Text>) : null}
            {reportPath ? (<Text>Report: {reportPath}</Text>) : null}
            {logPath ? (<Text>Log: {logPath}</Text>) : null}
            {memoryPath ? (<Text>Memory: {memoryPath}</Text>) : null}
          </Box>
        </Box>
      );
    }

    case 'output': {
      // Render even when content is empty to preserve intentional spacing.
      if ((event as any).content == null) {
        return null;
      }

      let contentStr: string;
      if (typeof (event as any).content === 'string') {
        contentStr = (event as any).content as string;
      } else {
        try {
          contentStr = JSON.stringify((event as any).content, null, 2);
        } catch {
          contentStr = String((event as any).content);
        }
      }

      // Normalize line endings and fix occasionally inlined tokens
      const normalized = contentStr
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        // If "Command:" was concatenated onto a previous line without a newline, insert one.
        .replace(/(\S)Command:/g, '$1\nCommand:');

      // Strip ANSI escape codes from tool output to prevent terminal formatting issues
      const plain = stripAnsi(normalized);

      // Skip only placeholder tokens if the entire content is just a token
      const plainTrimmed = plain.trim();
      if (/^(output|reasoning)(\s*\[[^\]]+\])?$/i.test(plainTrimmed)) {
        return null;
      }
      
      // Intelligent detection: If content looks like structured data (JSON array/object),
      // it's likely tool output that should be displayed even without metadata
      const looksLikeToolOutput = plainTrimmed.startsWith('[') || plainTrimmed.startsWith('{');
      
      // Check if this output is from a tool buffer (either explicit metadata or inferred)
      const eventMetadata = (event as any).metadata || {};
      const fromToolBuffer = eventMetadata.fromToolBuffer || looksLikeToolOutput;

      // Suppress React application operational logs (timestamps + app status lines)
      const appLogPatterns: RegExp[] = [
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sStarting\s.+\sassessment\son\s/i,
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sOperation ID:/i,
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sExecution Mode:/i,
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sSelecting execution service/i,
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sSelected execution mode:/i,
        /^\s*\[[0-9]{1,2}:[0-9]{2}:[0-9]{2}\s[AP]M\]\sLaunching\s.+\sassessment\sexecution/i,
      ];
      // We'll apply per-line filtering below to catch bundled events too

      // Apply per-line filtering to handle events containing multiple lines
      // But preserve JSON content for tool outputs
      const filteredLinesPre = plain.split('\n').filter(line => {
        const l = line.trim();
        if (l.length === 0) return true; // keep blank spacers
        // Suppress duplicate stop-cycle noise (reason is shown via metadata/termination panel)
        if (l.startsWith('Event loop cycle stop requested')) return false;
        // Remove python_repl success banner lines
        if (/^Code executed successfully\.?$/i.test(l)) return false;
        // Drop placeholder lines, including forms like "output [11 lines]"
        if (/^(output|reasoning)(\s*\[[^\]]+\])?$/i.test(l)) return false;
        // Drop empty Error: labels
        if (/^Error:\s*$/.test(l)) return false;
        // For tool outputs (JSON), keep all content
        if (fromToolBuffer) {
          // Only drop CYBER_EVENT and timestamp logs for tool outputs
          if (l.startsWith('__CYBER_EVENT__') || l.endsWith('__CYBER_EVENT_END__')) return false;
          if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+-\s+(INFO|DEBUG|WARNING|ERROR)\s+-\s+/.test(l)) return false;
          // Suppress noisy parser errors that could appear during large report emission
          if (/^Error parsing event:/i.test(l)) return false;
          return true;
        }
        // For non-tool outputs, apply normal filtering
        // Drop raw CYBER_EVENT payload lines
        if (l.startsWith('__CYBER_EVENT__') || l.endsWith('__CYBER_EVENT_END__')) return false;
        // Drop ISO timestamped app logs: 2025-08-16 16:59:17 - INFO - ...
        if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+-\s+(INFO|DEBUG|WARNING|ERROR)\s+-\s+/.test(l)) return false;
        // Drop [3:19:46 PM]-style app logs
        if (appLogPatterns.some(p => p.test(l))) return false;
        // Suppress noisy parser errors globally as well
        if (/^Error parsing event:/i.test(l)) return false;
        return true;
      });
      if (filteredLinesPre.length === 0) {
        return null;
      }
      const filtered = filteredLinesPre.join('\n');

      // Do not suppress lifecycle ticks anymore; show them in the stream for user visibility.

      // Extract metadata if present in the event (e.g., source, duration)
      const metadata: string[] = [];
      if ('timestamp' in (event as any) && (event as any).timestamp) {
        // Optionally display timestamps in debug mode (kept minimal here)
      }

      // Startup/system messages: format lifecycle/status lines using original symbols (✓/○)
      // IMPORTANT: Do NOT apply this styling to tool outputs
      if (!fromToolBuffer && filtered && (
        filtered.startsWith('▶') ||
        filtered.startsWith('◆') ||
        filtered.trim().startsWith('✓') ||
        filtered.trim().startsWith('○') ||
        filtered.startsWith('[Observability]')
      )) {
        if (filtered.startsWith('▶')) {
          // Initializing messages
          return (
            <Text color="#89B4FA" bold>{filtered}</Text>
          );
        } else if (filtered.startsWith('◆')) {
          // System status messages
          const isComplete = filtered.toLowerCase().includes('ready') || filtered.toLowerCase().includes('complete');
          return (
            <Text color={isComplete ? '#A6E3A1' : '#89DCEB'}>{filtered}</Text>
          );
        } else if (filtered.trim().startsWith('✓')) {
          // Success indicators
          return (
            <Box marginLeft={1}>
              <Text color="#A6E3A1">{filtered}</Text>
            </Box>
          );
        } else if (filtered.trim().startsWith('○')) {
          // Warning/unavailable indicators
          return (
            <Box marginLeft={1}>
              <Text color="#F9E2AF">{filtered}</Text>
            </Box>
          );
        } else if (filtered.startsWith('[Observability]')) {
          return (
            <Text color="#CBA6F7">{filtered}</Text>
          );
        }
      }
      
      // For command output, show with consistent spacing
      const lines = filtered.split('\n');
      // Collapse consecutive duplicate lines within the same event to avoid visual spam
      const dedupedLines: string[] = [];
      for (const line of lines) {
        if (dedupedLines.length === 0 || dedupedLines[dedupedLines.length - 1] !== line) {
          dedupedLines.push(line);
        }
      }
      
      // Check if this is a security report or important system output
      const isReport = contentStr.includes('# SECURITY ASSESSMENT REPORT') || 
                      contentStr.includes('# CTF Challenge Assessment Report') ||
                      contentStr.includes('EXECUTIVE SUMMARY') ||
                      contentStr.includes('KEY FINDINGS') ||
                      contentStr.includes('REMEDIATION ROADMAP');
      
      // Simple and elegant: Only show operation summary for actual completion messages
      // These messages come from the main agent flow, not from tools
      const isOperationSummary = !fromToolBuffer && (
                                 contentStr.includes('Outputs stored in:') ||
                                 contentStr.includes('Memory stored in:') ||
                                 contentStr.includes('Report saved to:') ||
                                 contentStr.includes('Operation ID:') ||
                                 contentStr.includes('REPORT ALSO SAVED TO:') ||
                                 contentStr.includes('OPERATION LOGS:'));
      
      const collapseThreshold = isReport ? DISPLAY_LIMITS.REPORT_MAX_LINES : 
                               (isOperationSummary ? DISPLAY_LIMITS.OPERATION_SUMMARY_LINES : 
                                (fromToolBuffer ? DISPLAY_LIMITS.TOOL_OUTPUT_COLLAPSE_LINES : 
                                 DISPLAY_LIMITS.DEFAULT_COLLAPSE_LINES));
      let shouldCollapse = dedupedLines.length > collapseThreshold;
      
      // Fallback: if content is essentially one giant line (minified or escaped \n) and very large, apply char-based collapse
      if (!shouldCollapse) {
        const totalLen = contentStr.length;
        const newlineCount = (contentStr.match(/\n/g) || []).length;
        const needsCharCollapse = totalLen > (DISPLAY_LIMITS.OUTPUT_PREVIEW_CHARS + DISPLAY_LIMITS.OUTPUT_TAIL_CHARS + 200) && newlineCount < 5;
        if (needsCharCollapse) {
          shouldCollapse = true;
        }
      }
      
      let displayLines: string[];
      if (shouldCollapse && fromToolBuffer) {
        // For tool outputs, show generous head/tail with a continuation marker
        if (dedupedLines.length > DISPLAY_LIMITS.TOOL_OUTPUT_COLLAPSE_LINES) {
          displayLines = [
            ...dedupedLines.slice(0, DISPLAY_LIMITS.TOOL_OUTPUT_PREVIEW_LINES),
            '... (content continues)',
            ...dedupedLines.slice(-DISPLAY_LIMITS.TOOL_OUTPUT_TAIL_LINES)
          ];
        } else {
          // Char-based fallback when lines are not informative
          const s = contentStr;
          const head = s.slice(0, DISPLAY_LIMITS.OUTPUT_PREVIEW_CHARS);
          const tail = s.slice(-DISPLAY_LIMITS.OUTPUT_TAIL_CHARS);
          displayLines = [head, '... (content continues)', tail];
        }
      } else if (shouldCollapse && !isReport && !isOperationSummary) {
        // For normal output, prefer line-based collapse when there are lines; otherwise, use char-based collapse
        if (dedupedLines.length > DISPLAY_LIMITS.DEFAULT_COLLAPSE_LINES) {
          displayLines = [...dedupedLines.slice(0, 5), '... (content continues)', ...dedupedLines.slice(-3)];
        } else {
          const s = contentStr;
          const head = s.slice(0, Math.min(DISPLAY_LIMITS.OUTPUT_PREVIEW_CHARS, Math.floor(s.length * 0.8)));
          const tail = s.slice(-DISPLAY_LIMITS.OUTPUT_TAIL_CHARS);
          displayLines = [head, '... (content continues)', tail];
        }
      } else if (shouldCollapse && (isReport || isOperationSummary)) {
        // For reports and summaries, show much more content
        if (isReport) {
          // For reports, show configured preview and tail lines
          displayLines = [
            ...dedupedLines.slice(0, DISPLAY_LIMITS.REPORT_PREVIEW_LINES), 
            '', 
            '... (content continues)', 
            '', 
            ...dedupedLines.slice(-DISPLAY_LIMITS.REPORT_TAIL_LINES)
          ];
        } else {
          // For operation summaries, show all content up to limit
          displayLines = dedupedLines.slice(0, DISPLAY_LIMITS.OPERATION_SUMMARY_LINES);
        }
      } else {
        // Show all lines if under threshold or expanded
        displayLines = dedupedLines;
      }
      
      // Enhanced styling for final reports and operation summaries
      if (isReport) {
        return (
          <Box flexDirection="column" marginTop={1}>
            <Box>
              <Text color="green" bold>📋 FINAL REPORT</Text>
              {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            </Box>
            <Box marginLeft={2} flexDirection="column">
              {displayLines.map((line: string, index: number) => (
                <Text key={index}>{line}</Text>
              ))}
            </Box>
            <Text> </Text>
          </Box>
        );
      }
      
      if (isOperationSummary) {
        return (
          <Box flexDirection="column" marginTop={1}>
            <Box>
              <Text color="green" bold>📁 OPERATION COMPLETE</Text>
              {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            </Box>
            <Box marginLeft={2} flexDirection="column">
              {displayLines.map((line: string, index: number) => {
                // Highlight path lines
                if (line.includes('Outputs stored in:') || line.includes('Memory stored in:') || 
                    line.includes('Host:') || line.includes('Container:')) {
                  return <Text key={index} color="cyan" bold>{line}</Text>;
                }
                return <Text key={index}>{line}</Text>;
              })}
            </Box>
            <Text> </Text>
          </Box>
        );
      }

      // Show tool output with special formatting
      if (fromToolBuffer) {
        const toolNameMeta = (event as any).metadata?.tool as string | undefined;
        const isPy = toolNameMeta === 'python_repl';
        const headerText = isPy ? 'output (python_repl)' : 'output';
        const showCount = isPy ? dedupedLines.length > 0 : dedupedLines.length > 10;
        return (
          <Box flexDirection="column" marginTop={1}>
            <Box>
              <Text color="yellow">{headerText}</Text>
              {showCount && <Text dimColor> [{dedupedLines.length} lines]</Text>}
              {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            </Box>
            <Box marginLeft={2} flexDirection="column">
              {isPy && dedupedLines.length === 0 ? (
                <Text dimColor>(no stdout)</Text>
              ) : (
                displayLines.map((line: string, index: number) => (
                  <Text key={index} dimColor>{line}</Text>
                ))
              )}
            </Box>
            <Text> </Text>
          </Box>
        );
      }
      
      // Regular output (not tool output)
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color="yellow">output</Text>
            {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            {shouldCollapse && <Text dimColor> [{dedupedLines.length} lines, truncated]</Text>}
          </Box>
          <Box marginLeft={2} flexDirection="column">
            {displayLines.map((line, index) => (
              <Text key={index} dimColor>{line}</Text>
            ))}
          </Box>
          <Text> </Text>
        </Box>
      );
    }
    
    case 'tool_output': {
      // Standardized tool output from backend protocol
      if (!('tool' in event) || !('output' in event)) {
        return null;
      }
      
      const toolName = event.tool as string;
      const toolStatus = (event.status as string) || 'success';
      const output = event.output as any;
      
      // Extract text content
      const outputText = output?.text || '';
      
      if (!outputText.trim()) {
        return null;
      }
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color={toolStatus === 'error' ? 'red' : 'green'}>
              {toolName}: {toolStatus}
            </Text>
          </Box>
          <Box marginLeft={2}>
            <Text>{outputText}</Text>
          </Box>
        </Box>
      );
    }
      
      
    case 'error': {
      // Enhanced error display with solution guidance
      const errorMsg = (event as any).error || event.content || 'Unknown error';
      const solution = (event as any).solution;
      const exitCode = (event as any).exitCode;

      return (
        <Box flexDirection="column" marginTop={1} borderStyle="round" borderColor="red" paddingX={1}>
          <Text bold color="red">✗ Error</Text>
          <Text color="red">{errorMsg}</Text>
          {exitCode !== undefined && (
            <Text dimColor color="red">Exit code: {exitCode}</Text>
          )}
          {solution && (
            <Box flexDirection="column" marginTop={1}>
              <Text bold color="yellow">→ Solution:</Text>
              <Text color="yellow">{solution}</Text>
            </Box>
          )}
        </Box>
      );
    }
      
    case 'metadata': {
      // Render metadata events normally, with special-case compact display for stop_tool
      if (!event.content || typeof event.content !== 'object') return null;
      const entries = Object.entries(event.content);
      if (entries.length === 0) return null;

      // Suppress duplicate stop-notification metadata; stop reason is shown in the tool header
      if (entries.length === 1 && entries[0][0] === 'stopping') {
        return null;
      }

      return (
        <Box flexDirection="column" marginLeft={2}>
          {entries.map(([key, value], index) => {
            const isLast = index === entries.length - 1;
            let displayValue: string;
            if (value === null || value === undefined) {
              displayValue = 'null';
            } else if (typeof value === 'object') {
              try {
                const json = JSON.stringify(value);
                displayValue = json.length > 50 ? json.substring(0, 50) + '...' : json;
              } catch {
                displayValue = '[object]';
              }
            } else {
              const s = String(value);
              displayValue = s.length > 50 ? s.substring(0, 50) + '...' : s;
            }
            return (
              <Box key={index}>
                <Text dimColor>{isLast ? '└─' : '├─'} {key}: {displayValue}</Text>
              </Box>
            );
          })}
        </Box>
      );
    }
      
    case 'divider':
      return null;

    case 'separator':
      return null;

    case 'user_handoff':
      return (
        <>
          <Text color="green" bold>AGENT REQUESTING USER INPUT</Text>
          <Box borderStyle="round" borderColor="green" paddingX={1} marginY={1}>
            <Text>{event.message}</Text>
          </Box>
          {event.breakout ? (
            <Text color="red" bold>Agent execution will stop after this handoff</Text>
          ) : null}
          <Box marginTop={1}>
            <Text color="yellow" bold>➤ Type your response below and press Enter to send it to the agent</Text>
          </Box>
          <Text> </Text>
        </>
      );
      
    case 'swarm_start': {
      // Create and display SwarmDisplay component immediately.
      // We treat a swarm_start as the beginning of an active swarm run so that
      // the UI shows agents as running rather than permanently "initializing".
      const swarmEvent = event as any;
      const agents: SwarmAgent[] = (swarmEvent.agent_details || swarmEvent.agents || []).map((agent: any, index: number) => ({
        id: `agent_${agent.name}_${index}`, // Unique id for each agent
        name: agent.name,
        role: agent.role || (agent.system_prompt ? agent.system_prompt.split('.')[0].trim() : ''),
        // Mark the first agent as active to reflect that it will receive the
        // first swarm step; others remain pending.
        status: index === 0 ? 'active' : 'pending',
        tools: agent.tools || [],
        model_id: agent.model_id,
        model_provider: agent.model_provider,
        temperature: agent.temperature,
        recentToolCalls: []
      }));

      const swarmState: SwarmState = {
        id: `swarm_${Date.now()}`,
        task: swarmEvent.task || 'Multi-agent operation',
        status: 'running',
        agents,
        startTime: Date.now(),
        totalTokens: 0,
        maxHandoffs: swarmEvent.max_handoffs,
        maxIterations: swarmEvent.max_iterations,
        nodeTimeout: swarmEvent.node_timeout,
        executionTimeout: swarmEvent.execution_timeout
      };

      // Use the compact summary view; the detailed per-agent view can be very
      // tall and is redundant with the swarm step headers that follow.
      return (
        <Box marginTop={1} marginBottom={1}>
          <SwarmDisplay swarmState={swarmState} collapsed={true} />
        </Box>
      );
    }
      
    case 'swarm_handoff':
      // Enhanced agent handoff display
      const fromAgent = 'from_agent' in event ? String(event.from_agent || 'unknown') : 'unknown';
      const toAgent = 'to_agent' in event ? String(event.to_agent || 'unknown') : 'unknown';
      const handoffMessage = 'message' in event ? String(event.message || '') : '';
      const sharedContext = 'shared_context' in event ? event.shared_context : {};
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color="magenta" bold>[HANDOFF] </Text>
            <Text color="cyan">{fromAgent}</Text>
            <Text color="gray"> → </Text>
            <Text color="green">{toAgent}</Text>
          </Box>
          {handoffMessage && (
            <Box marginLeft={2}>
              <Text dimColor>└─ "{handoffMessage}"</Text>
            </Box>
          )}
          {typeof sharedContext === 'object' && Object.keys(sharedContext).length > 0 && (
            <Box marginLeft={2} flexDirection="column">
              <Text dimColor>   Context transferred:</Text>
              {Object.entries(sharedContext).slice(0, 3).map(([key, value]) => (
                <Box key={key} marginLeft={4}>
                  <Text dimColor>• {key}: {String(value).substring(0, 50)}{String(value).length > 50 ? '...' : ''}</Text>
                </Box>
              ))}
            </Box>
          )}
        </Box>
      );
      
    case 'swarm_complete': {
      // Enhanced swarm completion display
      const finalAgent = 'final_agent' in event ? String(event.final_agent || 'unknown') : 'unknown';
      const executionCount = 'execution_count' in event ? Number(event.execution_count || 0) : 0;
      const handoffCount = 'handoff_count' in event ? Number(event.handoff_count || 0) : executionCount - 1;
      const totalSteps = 'total_steps' in event ? Number(event.total_steps || 0) : 0;
      const totalIterations = 'total_iterations' in event ? Number(event.total_iterations || 0) : 0;
      const duration = 'duration' in event ? String(event.duration || 'unknown') : 'unknown';
      const totalTokens = 'total_tokens' in event ? Number(event.total_tokens || 0) : 0;
      const agentMetrics = 'agent_metrics' in event ? (event.agent_metrics as any[] || []) : [];
      const swarmStatus = 'status' in event ? String(event.status || 'completed') : 'completed';
      const completedAgents = 'completed_agents' in event ? (event.completed_agents as string[] || []) : [];
      const failedAgents = 'failed_agents' in event ? (event.failed_agents as string[] || []) : [];
      
      // Determine if this was a timeout/failure
      const isTimeout = swarmStatus.toLowerCase().includes('failed') || swarmStatus.toLowerCase().includes('timeout');
      const statusColor = isTimeout ? 'red' : 'green';
      const statusText = isTimeout ? 'TIMEOUT' : 'COMPLETE';
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text color={statusColor} bold>[SWARM: {statusText}] {completedAgents.length || agentMetrics.length || 0} agents, {handoffCount} handoffs, {totalIterations > 0 ? totalIterations : totalSteps} iterations</Text>
          {duration !== 'unknown' && (
            <Box marginLeft={2}>
              <Text dimColor>├─ duration: {duration}</Text>
            </Box>
          )}
          {totalTokens > 0 && (
            <Box marginLeft={2}>
              <Text dimColor>├─ tokens: {totalTokens.toLocaleString()}</Text>
            </Box>
          )}
          {isTimeout && (
            <Box marginLeft={2}>
              <Text color="yellow">├─ ⚠️ Swarm execution timed out - continuing with manual fallback</Text>
            </Box>
          )}
          {completedAgents.length > 0 && (
            <Box marginLeft={2}>
              <Text color="green">├─ completed: {completedAgents.join(', ')}</Text>
            </Box>
          )}
          {failedAgents.length > 0 && (
            <Box marginLeft={2}>
              <Text color="red">└─ failed: {failedAgents.join(', ')}</Text>
            </Box>
          )}
          {agentMetrics.length > 0 && agentMetrics.map((metric, idx) => {
            const isLast = idx === agentMetrics.length - 1 && completedAgents.length === 0 && failedAgents.length === 0;
            const prefix = isLast ? '└─' : '├─';
            return (
              <Box key={idx} marginLeft={2}>
                <Text dimColor>{prefix} {metric.name}: {metric.steps} steps, {metric.tools} tools, {metric.tokens} tokens</Text>
              </Box>
            );
          })}
          {agentMetrics.length === 0 && completedAgents.length === 0 && (
            <Box marginLeft={2}>
              <Text dimColor>└─ final_agent: {finalAgent}</Text>
            </Box>
          )}
        </Box>
      );
    }
      
    case 'batch':
      // Handle batched events from backend
      // Recursively render each event in the batch
      if (!('events' in event) || !Array.isArray(event.events)) {
        return null;
      }
      return (
        <>
          {event.events.map((batchedEvent, idx) => (
            <MemoizedEventLine 
              key={batchedEvent.id || `${event.id}_${idx}`}
              event={batchedEvent}
              toolInputs={toolInputs}
              animationsEnabled={animationsEnabled}
              operationContext={operationContext}
              reportPath={reportPath}
              reportFallbackContent={reportFallbackContent}
              projectRoot={projectRoot}
            />
          ))}
        </>
      );
      
    case 'operation_init':
      // Display comprehensive operation initialization info (preflight checks)
      if (!event || typeof event !== 'object') return null;
      
      return (
        <Box flexDirection="column">
          <Text color="#89B4FA" bold>◆ Operation initialization complete</Text>
          
          {/* Operation Details */}
          {('operation_id' in event && event.operation_id) ? (
            <Text dimColor>  Operation ID: {event.operation_id}</Text>
          ) : null}
          {('target' in event && event.target) ? (
            <Text dimColor>  Target: {event.target}</Text>
          ) : null}
          {('objective' in event && event.objective) ? (
            <Text dimColor>  Objective: {event.objective}</Text>
          ) : null}
          {('max_steps' in event && event.max_steps) ? (
            <Text dimColor>  Max Steps: {event.max_steps}</Text>
          ) : null}
          {('model_id' in event && event.model_id) ? (
            <Text dimColor>  Model: {event.model_id}</Text>
          ) : null}
          {('provider' in event && event.provider) ? (
            <Text dimColor>  Provider: {event.provider}</Text>
          ) : null}
          
          {/* Memory Configuration */}
          {('memory' in event && event.memory) ? (
            <>
              <Text dimColor>  Memory backend: {event.memory.backend || 'unknown'}</Text>
              {event.memory.has_existing ? (
                <Text dimColor>  Previous memories detected - will be loaded</Text>
              ) : null}
              {event.memory.total_count ? (
                <Text dimColor>  Existing memories: {event.memory.total_count}</Text>
              ) : null}
              
              {/* Memory Categories */}
              {event.memory.categories && Object.keys(event.memory.categories).length > 0 ? (
                <Text dimColor>  Memory categories: {Object.entries(event.memory.categories).map(([category, count]) => `${category}:${count}`).join(', ')}</Text>
              ) : null}
              
              {/* Recent Findings Summary */}
              {event.memory.recent_findings && Array.isArray(event.memory.recent_findings) && event.memory.recent_findings.length > 0 ? (
                <Text dimColor>  Recent findings: {event.memory.recent_findings.length} items available</Text>
              ) : null}
            </>
          ) : null}
          
          {/* Environment Info */}
          {('ui_mode' in event && event.ui_mode) ? (
            <Text dimColor>  UI Mode: {event.ui_mode}</Text>
          ) : null}
          {('observability' in event) && (
            <Text dimColor>  Observability: {event.observability ? 'enabled' : 'disabled'}</Text>
          )}
          {('hitl_enabled' in event) && event.hitl_enabled && (
            <Text color="#A6E3A1">  HITL: enabled - human feedback available</Text>
          )}
          {('tools_available' in event && event.tools_available) ? (
            <Text dimColor>  Available Tools: {event.tools_available}</Text>
          ) : null}
        </Box>
      );

    case 'specialist_start': {
      const specialist = event.specialist || 'validation';
      const task = event.task || 'Sub-agent analysis';
      const finding = event.finding ? `"${event.finding}"` : null;
      const artifactCount = event.artifactPaths?.length || 0;

      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color="yellow">[SUB-AGENT] </Text>
            <Text>{specialist}_specialist</Text>
          </Box>
          <Box marginLeft={2}>
            <Text dimColor>└─ task: </Text>
            <Text>{task}</Text>
          </Box>
          {finding && (
            <Box marginLeft={2}>
              <Text dimColor>└─ finding: </Text>
              <Text>{finding}</Text>
            </Box>
          )}
          {artifactCount > 0 && (
            <Box marginLeft={2}>
              <Text dimColor>└─ artifacts: </Text>
              <Text color="cyan">{artifactCount} files</Text>
            </Box>
          )}
        </Box>
      );
    }

    case 'hitl_pause_requested': {
      const toolName = 'tool_name' in event ? String(event.tool_name) : 'unknown';
      const reason = 'reason' in event ? String(event.reason) : undefined;
      const confidence = 'confidence' in event && typeof event.confidence === 'number' ? event.confidence : undefined;

      return (
        <Box flexDirection="column" marginTop={1} marginBottom={1}>
          <Text color="yellow" bold>⚠️  HITL: Tool execution paused for review</Text>
          <Box marginLeft={2} marginTop={1}>
            <Text>Tool: <Text bold color="cyan">{toolName}</Text></Text>
          </Box>
          {reason && (
            <Box marginLeft={2}>
              <Text>Reason: <Text color="yellow">{reason}</Text></Text>
            </Box>
          )}
          {confidence !== undefined && (
            <Box marginLeft={2}>
              <Text>Confidence: <Text color={confidence < 50 ? 'red' : confidence < 70 ? 'yellow' : 'green'}>{confidence}%</Text></Text>
            </Box>
          )}
        </Box>
      );
    }

    case 'hitl_feedback_submitted': {
      const feedbackType = 'feedback_type' in event ? String(event.feedback_type) : 'unknown';
      const content = 'content' in event ? String(event.content) : '';
      const preview = content.length > 80 ? content.substring(0, 80) + '...' : content;

      return (
        <Box flexDirection="column" marginTop={1} marginBottom={1}>
          <Text color="cyan" bold>✓ Feedback Submitted to Agent</Text>
          <Box marginLeft={2} marginTop={1}>
            <Text dimColor>Type: </Text>
            <Text color="cyan">{feedbackType}</Text>
          </Box>
          {preview && (
            <Box marginLeft={2} flexDirection="column">
              <Text dimColor>Content:</Text>
              <Text color="cyan">{preview}</Text>
            </Box>
          )}
          <Box marginLeft={2} marginTop={1}>
            <Text dimColor>→ Agent will process in next step</Text>
          </Box>
        </Box>
      );
    }

    case 'hitl_agent_interpretation': {
      const interpretation = 'interpretation' in event ? String(event.interpretation) : '';
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text color="green" bold>✓ Agent Interpretation:</Text>
          <Box marginLeft={2}>
            <Text color="green">{interpretation}</Text>
          </Box>
        </Box>
      );
    }

    case 'specialist_progress': {
      const status = event.status || 'Processing';
      const gate = event.gate;
      const totalGates = event.totalGates;
      const tool = event.tool;

      let progressText = status;
      if (gate && totalGates) {
        progressText = `Gate ${gate}/${totalGates}: ${status}`;
      } else if (tool) {
        progressText = `${tool} - ${status}`;
      }

      return (
        <Box marginLeft={2} marginTop={1}>
          <Text dimColor>⏳ </Text>
          <Text dimColor>{progressText}</Text>
        </Box>
      );
    }

    case 'specialist_end': {
      const specialist = event.specialist || 'validation';
      const result = event.result || {};
      const validationStatus = result.validationStatus || result.validation_status || 'unknown';
      const confidence = result.confidence;
      const severityMax = result.severityMax || result.severity_max;
      const failedGates = result.failedGates || result.failed_gates || [];

      // Determine icon and color based on status
      let statusIcon = '✓';
      let statusColor = 'green';
      if (validationStatus === 'hypothesis' || validationStatus === 'unverified') {
        statusIcon = '⚠';
        statusColor = 'yellow';
      } else if (validationStatus === 'error') {
        statusIcon = '✗';
        statusColor = 'red';
      }

      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color={statusColor}>{statusIcon} </Text>
            <Text>{specialist}_specialist </Text>
            <Text dimColor>→ </Text>
            <Text color={statusColor} bold>{validationStatus}</Text>
            {confidence !== undefined && (
              <>
                <Text dimColor> | confidence: </Text>
                <Text color="cyan">{confidence}%</Text>
              </>
            )}
            {severityMax && (
              <>
                <Text dimColor> | severity: </Text>
                <Text color="yellow">{severityMax}</Text>
              </>
            )}
          </Box>
          {Array.isArray(failedGates) && failedGates.length > 0 && (
            <Box marginLeft={2}>
              <Text color="red">└─ failed gates: </Text>
              <Text dimColor>[{failedGates.join(', ')}]</Text>
            </Box>
          )}
        </Box>
      );
    }

    case 'hitl_resume': {
      const approved = 'approved' in event ? Boolean(event.approved) : false;
      return (
        <Box marginTop={1}>
          <Text color={approved ? 'green' : 'yellow'}>
            {approved ? '✓ Execution resumed' : '⚠️  Interpretation rejected'}
          </Text>
        </Box>
      );
    }

    default:
      return null;
  }
});

// Memoize EventLine component for performance
const MemoizedEventLine = React.memo(EventLine);

// Shared helper to compute normalized, grouped display items from events
type DisplayGroup = {
  type: 'reasoning_group' | 'single';
  events: DisplayStreamEvent[];
  startIdx: number;
};

/**
 * Simplifies event grouping now that backend handles deduplication.
 * Only groups consecutive reasoning events for visual presentation.
 */
export const computeDisplayGroups = (events: DisplayStreamEvent[]): DisplayGroup[] => {
  // Flatten any batch events first
  const flattened: DisplayStreamEvent[] = [];
  
  for (const event of events) {
    if (event.type === 'batch' && 'events' in event && Array.isArray(event.events)) {
      // Expand batch events
      flattened.push(...event.events);
    } else {
      flattened.push(event);
    }
  }
  
  // Group consecutive reasoning events for cleaner display
  const groups: DisplayGroup[] = [];
  let currentReasoningGroup: DisplayStreamEvent[] = [];
  let startIdx = 0;
  
  flattened.forEach((event, idx) => {
    if (event.type === 'reasoning' || event.type === 'reasoning_delta') {
      currentReasoningGroup.push(event);
    } else {
      // Flush any pending reasoning group
      if (currentReasoningGroup.length > 0) {
        groups.push({
          type: 'reasoning_group',
          events: currentReasoningGroup,
          startIdx
        });
        currentReasoningGroup = [];
      }
      
      // Add non-reasoning event as single
      groups.push({
        type: 'single',
        events: [event],
        startIdx: idx
      });
      startIdx = idx + 1;
    }
  });
  
  // Flush final reasoning group if any
  if (currentReasoningGroup.length > 0) {
    groups.push({
      type: 'reasoning_group',
      events: currentReasoningGroup,
      startIdx
    });
  }
  
  return groups;
};


export const StreamDisplay: React.FC<StreamDisplayProps> = React.memo(({ events, animationsEnabled = true }) => {
  // Track active swarm operations
  const [swarmStates, setSwarmStates] = React.useState<Map<string, SwarmState>>(new Map());
  // Process swarm events to build state with a stable ID to avoid remount flicker
  React.useEffect(() => {
    // Derive a stable signature from the latest swarm_start event
    let latestSignature: string | null = null;
    let latestTask: string | null = null;
    let latestAgents: SwarmAgent[] | null = null;

    events.forEach(event => {
      if (event.type === 'swarm_start') {
        const names = 'agent_names' in event && Array.isArray(event.agent_names)
          ? (event.agent_names as any[]).map(a => typeof a === 'string' ? a : (a && (a.name || a.role)) || '').join(',')
          : '';
        const task = event.task || 'Unknown task';
        const signature = `${names}|${task}`;
        latestSignature = signature;
        latestTask = task;

        const agentDetails = event.agent_details || [];
        const agents: SwarmAgent[] = [];
        if (Array.isArray(agentDetails)) {
          agentDetails.forEach((detail: any, i: number) => {
            const agentName = detail.name || `Agent ${i + 1}`;
            const systemPrompt = detail.system_prompt || '';
            const agentTools = detail.tools || [];
            const role = systemPrompt.split('.')[0].trim() || 'Agent';
            agents.push({
              id: `agent_${i}`,
              name: agentName,
              role,
              task: role,
              status: 'pending',
              tools: Array.isArray(agentTools) ? agentTools : []
            });
          });
        }
        latestAgents = agents;
      }
    });

    // If we have no new swarm info, do nothing
    if (!latestSignature || !latestTask) {
      return;
    }

    // Update swarm state incrementally and only if something changed
    setSwarmStates(prev => {
      const next = new Map(prev);
      const existing = next.get(latestSignature!);
      const now = Date.now();
      const updated: SwarmState = {
        id: latestSignature!,
        task: latestTask!,
        status: existing?.status || 'initializing',
        agents: latestAgents && latestAgents.length > 0 ? latestAgents : (existing?.agents || []),
        startTime: existing?.startTime || now,
        endTime: existing?.endTime,
        totalTokens: existing?.totalTokens,
        result: existing?.result
      };

      // Shallow compare to avoid unnecessary state updates
      const hasChanged = !existing 
        || existing.task !== updated.task
        || existing.status !== updated.status
        || existing.agents.length !== updated.agents.length;

      if (hasChanged) {
        next.set(latestSignature!, updated);
        return next;
      }
      return prev; // no change
    });
  }, [events]);
  
  // Track tool inputs (for handling tool_input_update events from swarm agents)
  const [toolInputs, setToolInputs] = React.useState<Map<string, any>>(new Map());
  
  // Resolve output base directory from config so report resolution matches backend outputDir
  const { config } = useConfig();
  const outputBaseDir = React.useMemo(() => {
    try {
      const raw = config.outputDir || './outputs';
      if (path.isAbsolute(raw)) {
        return raw;
      }
      const base = resolveProjectRoot() ?? process.cwd();
      return path.resolve(base, raw);
    } catch {
      return path.resolve(process.cwd(), 'outputs');
    }
  }, [config.outputDir]);
  
  React.useEffect(() => {
    const newToolInputs = new Map<string, any>();
    
    events.forEach(event => {
      if (event.type === 'tool_start') {
        // Store initial tool input only if it has meaningful content
        if ('tool_id' in event && event.tool_id) {
          const ti: any = (event as any).tool_input;
          const hasMeaningful = (() => {
            if (ti == null) return false;
            if (typeof ti === 'string') return ti.trim().length > 0;
            if (Array.isArray(ti)) return ti.length > 0;
            if (typeof ti === 'object') return Object.keys(ti).length > 0;
            return !!ti;
          })();
          if (hasMeaningful) {
            newToolInputs.set(event.tool_id, ti);
          }
        }
      } else if (event.type === 'tool_input_update' || event.type === 'tool_input_corrected') {
        // Update tool input with complete/corrected data
        if ('tool_id' in event && event.tool_id && 'tool_input' in event) {
          newToolInputs.set(event.tool_id, event.tool_input);
        }
      }
    });
    
    setToolInputs(newToolInputs);
  }, [events]);
  
  // Group consecutive reasoning events to prevent multiple labels
  const displayGroups = React.useMemo(() => computeDisplayGroups(events), [events]);
  
  // Memoize active swarm lookup - expensive operation
  const activeSwarm = React.useMemo(() => {
    return Array.from(swarmStates.values()).find(s => 
      s.status === 'running' || s.status === 'initializing'
    );
  }, [swarmStates]);
  
  // Memoize swarm event check
  const hasSwarmStartEvent = React.useMemo(() => {
    return events.some(e => e.type === 'swarm_start');
  }, [events]);
  
  const projectRoot = React.useMemo(() => resolveProjectRoot(), []);

  const reportDetails = React.useMemo(() => {
    let latestPath: string | null = null;
    let fallback: string | null = null;

    events.forEach(event => {
      if (event.type === 'report_paths') {
        const candidate =
          (event as any).reportPath ??
          (event as any).report_path ??
          (event as any).report ??
          null;
        if (candidate) {
          latestPath = String(candidate);
        }
      } else if ((event as any).type === 'assessment_complete') {
        const raw = (event as any).report_path;
        if (typeof raw === 'string' && raw) {
          latestPath = mapContainerReportPath(raw, outputBaseDir);
        }
      } else if (event.type === 'report_content') {
        if ('content' in event && typeof (event as any).content === 'string') {
          fallback = (event as any).content as string;
        } else if ('content' in event && (event as any).content) {
          try {
            fallback = JSON.stringify((event as any).content);
          } catch {
            fallback = String((event as any).content);
          }
        }
      }
    });
    return { path: latestPath, content: fallback };
  }, [events, outputBaseDir]);

  // Capture operation context (operation_id and target) from events for artifact resolution
  const operationContext = React.useMemo<OperationContext>(() => {
    let opId: string | null = null;
    let target: string | null = null;
    for (const e of events) {
      if (e.type === 'operation_init') {
        if ('operation_id' in e && (e as any).operation_id) opId = String((e as any).operation_id);
        if ('target' in e && (e as any).target) target = String((e as any).target);
      }
    }
    return { operationId: opId, target, reportPath: reportDetails.path };
  }, [events, reportDetails.path]);

  // Soft virtualization: render only the most recent N groups to cap Ink/Yoga node count
  // This dramatically reduces memory pressure after long sessions while preserving recent context.
  const MAX_GROUPS_RENDERED = (() => {
    const env = Number(process.env.CYBER_MAX_GROUPS_RENDERED);
    if (Number.isFinite(env) && env > 50) return Math.floor(env);
    // Default cap chosen to balance usability and stability
    return 500;
  })();
  const totalGroups = displayGroups.length;

  // Ensure that the FINAL REPORT header (if present) is always kept in view
  let startIndex = Math.max(0, totalGroups - MAX_GROUPS_RENDERED);
  let finalReportIndex = -1;
  for (let i = 0; i < totalGroups; i++) {
    const group = displayGroups[i];
    if (group.events.some(e => e.type === 'step_header' && (e as any).step === 'FINAL REPORT')) {
      finalReportIndex = i;
      break;
    }
  }
  if (finalReportIndex >= 0 && finalReportIndex < startIndex) {
    startIndex = finalReportIndex;
  }

  const groupsToRender = displayGroups.slice(startIndex);
  const omittedCount = startIndex;

  return (
    <Box flexDirection="column">
      {/* Only display swarm if we have actual swarm events in this session */}
      {activeSwarm && hasSwarmStartEvent && (
        <Box marginBottom={1}>
          <SwarmDisplay swarmState={activeSwarm} collapsed={false} />
        </Box>
      )}

      {/* Omitted items banner to indicate truncated history in the viewport */}
      {omittedCount > 0 && (
        <Box marginBottom={1}>
          <Text dimColor>… {omittedCount} earlier items omitted (press up or use logs to review)</Text>
        </Box>
      )}
      
      {groupsToRender.map((group, idx) => {
        if (group.type === 'reasoning_group') {
          // Display reasoning group with single label - memoize content combination
          const combinedContent = group.events.reduce((acc, e) => {
            // Prefer full reasoning content when present
            if ('content' in e && (e as any).content) {
              const content = (e as any).content;
              // Add spacing between chunks if accumulator is not empty and doesn't end with whitespace
              if (acc && !acc.endsWith(' ') && !acc.endsWith('\n')) {
                return acc + ' ' + content;
              }
              return acc + content;
            }
            // Also accumulate streaming deltas so we don't lose interim reasoning
            if (e.type === 'reasoning_delta' && 'delta' in (e as any) && (e as any).delta) {
              const delta = (e as any).delta;
              if (acc && !acc.endsWith(' ') && !acc.endsWith('\n')) {
                return acc + ' ' + delta;
              }
              return acc + delta;
            }
            return acc;
          }, '');
          
          // Check if this is swarm agent reasoning
          const swarmAgent = group.events[0] && 'swarm_agent' in group.events[0] 
            ? group.events[0].swarm_agent 
            : null;
          
          // Create reasoning label with agent info if available
          const reasoningLabel = swarmAgent 
            ? `reasoning (${swarmAgent})`
            : 'reasoning';
          
          return (
            <Box key={`reasoning-group-${group.startIdx}`} flexDirection="column" marginTop={1}>
              <Text color="cyan" bold>{reasoningLabel}</Text>
              <Box paddingLeft={0}>
                <Text color="cyan" wrap="wrap">{combinedContent}</Text>
              </Box>
            </Box>
          );
        } else {
          // Display single events normally
          return group.events.map((event, i) => (
              <MemoizedEventLine 
                key={event.id || `ev-${startIndex + idx}-${i}`}  // Use event ID if available
                event={event} 
                toolInputs={toolInputs} 
                animationsEnabled={animationsEnabled} 
                operationContext={operationContext}
                reportPath={reportDetails.path}
                reportFallbackContent={reportDetails.content}
                projectRoot={projectRoot}
              />
          ));
        }
      })}
    </Box>
  );
});

// Static variant to render an immutable, deduplicated history without re-renders.
// Uses the same normalization/grouping to avoid duplicate headers/banners.
import { Static } from 'ink';

export const StaticStreamDisplay: React.FC<{
  events: DisplayStreamEvent[];
  terminalWidth?: number;
  availableHeight?: number;
}> = React.memo(({ events, terminalWidth, availableHeight }) => {
  const groups = React.useMemo(() => computeDisplayGroups(events), [events]);
  const projectRoot = React.useMemo(() => resolveProjectRoot(), []);
  const reportDetails = React.useMemo(() => {
    let latestPath: string | null = null;
    let fallback: string | null = null;
    events.forEach(event => {
      if (event.type === 'report_paths') {
        const candidate =
          (event as any).reportPath ??
          (event as any).report_path ??
          (event as any).report ??
          null;
        if (candidate) {
          latestPath = String(candidate);
        }
      } else if (event.type === 'report_content') {
        if ('content' in event && typeof (event as any).content === 'string') {
          fallback = (event as any).content as string;
        } else if ('content' in event && (event as any).content) {
          try {
            fallback = JSON.stringify((event as any).content);
          } catch {
            fallback = String((event as any).content);
          }
        }
      }
    });
    return { path: latestPath, content: fallback };
  }, [events]);

  // Flatten groups into discrete render items with stable keys
  type Item = { key: string; render: () => React.ReactNode };
  const items: Item[] = React.useMemo(() => {
    const out: Item[] = [];
    groups.forEach((group, gIdx) => {
      if (group.type === 'reasoning_group') {
        // Use reduce for better performance with large arrays
        const combinedContent = group.events.reduce((acc, e) => {
          // Prefer full reasoning content when present
          if ('content' in e && (e as any).content) {
            const content = (e as any).content;
            // Add spacing between chunks if accumulator is not empty and doesn't end with whitespace
            if (acc && !acc.endsWith(' ') && !acc.endsWith('\n')) {
              return acc + ' ' + content;
            }
            return acc + content;
          }
          // Also accumulate streaming deltas so we don't lose interim reasoning
          if (e.type === 'reasoning_delta' && 'delta' in (e as any) && (e as any).delta) {
            const delta = (e as any).delta;
            if (acc && !acc.endsWith(' ') && !acc.endsWith('\n')) {
              return acc + ' ' + delta;
            }
            return acc + delta;
          }
          return acc;
        }, '');
        
        // Check if this is swarm agent reasoning
        const swarmAgent = group.events[0] && 'swarm_agent' in group.events[0] 
          ? (group.events[0] as any).swarm_agent 
          : null;
        
        // Create reasoning label with agent info if available
        const reasoningLabel = swarmAgent 
          ? `reasoning (${swarmAgent})`
          : 'reasoning';
        
        const key = `rg-${group.startIdx}`;
        out.push({
          key,
          render: () => (
            <Box key={key} flexDirection="column" marginTop={1}>
              <Text color="cyan" bold>{reasoningLabel}</Text>
              <Box paddingLeft={0}>
                <Text color="cyan" wrap="wrap">{combinedContent}</Text>
              </Box>
            </Box>
          )
        });
      } else {
        group.events.forEach((event, i) => {
          const eid = (event as any)?.id ?? (event as any)?.timestamp ?? `${gIdx}-${i}`;
          const key = `ev-${eid}`;
          out.push({
            key,
            render: () => (
              <MemoizedEventLine
                key={key}
                event={event}
                animationsEnabled={false}
                operationContext={undefined}
                reportPath={reportDetails.path}
                reportFallbackContent={reportDetails.content}
                projectRoot={projectRoot}
              />
            )
          });
        });
      }
    });
    return out;
  }, [groups]);

  return (
    <Static items={items}>
      {(item: Item) => item.render()}
    </Static>
  );
});
