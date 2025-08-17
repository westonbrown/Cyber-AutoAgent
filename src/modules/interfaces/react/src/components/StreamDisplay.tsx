/**
 * StreamDisplay - SDK-integrated event streaming for cyber operations
 * Designed for infinite scroll with SDK native events and backward compatibility
 */

import React from 'react';
import { Box, Text } from 'ink';
import { ThinkingIndicator } from './ThinkingIndicator.js';
import { StreamEvent } from '../types/events.js';
import { SwarmDisplay, SwarmState, SwarmAgent } from './SwarmDisplay.js';
import { formatToolInput } from '../utils/toolFormatters.js';
import { DISPLAY_LIMITS } from '../constants/config.js';
// Removed toolCategories import - using clean tool display without emojis

// Legacy simplified event types for backward compatibility
export type LegacyStreamEvent = 
  | { type: 'step_header'; step: number | string; maxSteps: number; operation: string; duration: string; [key: string]: any }
  | { type: 'reasoning'; content: string; [key: string]: any }
  | { type: 'thinking'; context?: 'reasoning' | 'tool_preparation' | 'tool_execution' | 'waiting' | 'startup'; startTime?: number; [key: string]: any }
  | { type: 'thinking_end'; [key: string]: any }
  | { type: 'delayed_thinking_start'; context?: string; startTime?: number; delay?: number; [key: string]: any }
  | { type: 'tool_start'; tool_name: string; tool_input: any; [key: string]: any }
  | { type: 'command'; content: string; [key: string]: any }
  | { type: 'output'; content: string; exitCode?: number; duration?: number; [key: string]: any }
  | { type: 'error'; content: string; [key: string]: any }
  | { type: 'metadata'; content: Record<string, string>; [key: string]: any }
  | { type: 'divider'; [key: string]: any }
  | { type: 'user_handoff'; message: string; breakout: boolean; [key: string]: any }
  | { type: 'metrics_update'; metrics: any; [key: string]: any } // Pass-through type
  | { type: 'model_invocation_start'; modelId?: string; [key: string]: any }
  | { type: 'model_stream_delta'; delta?: string; [key: string]: any }
  | { type: 'reasoning_delta'; delta?: string; [key: string]: any }
  | { type: 'tool_invocation_start'; toolName?: string; toolInput?: any; [key: string]: any }
  | { type: 'tool_invocation_end'; duration?: number; success?: boolean; [key: string]: any }
  | { type: 'event_loop_cycle_start'; cycleNumber?: number; [key: string]: any }
  | { type: 'content_block_delta'; delta?: string; isReasoning?: boolean; [key: string]: any }
  | { type: 'swarm_start'; agent_names?: any[]; agent_details?: any[]; task?: string; [key: string]: any }
  | { type: 'swarm_handoff'; from_agent?: string; to_agent?: string; message?: string; [key: string]: any }
  | { type: 'swarm_complete'; final_agent?: string; execution_count?: number; [key: string]: any };

// Combined event type supporting both SDK and legacy events
export type DisplayStreamEvent = StreamEvent | LegacyStreamEvent;

// Re-export StreamEvent type for backward compatibility
export type { StreamEvent };

interface StreamDisplayProps {
  events: DisplayStreamEvent[];
  // Configuration for SDK features
  showSDKMetrics?: boolean;
  showPerformanceInfo?: boolean;
  enableCostTracking?: boolean;
  animationsEnabled?: boolean;
}

// Tool execution state tracking
interface ToolState {
  status: 'executing' | 'completed' | 'failed';
  startTime: number;
}

const DIVIDER = '─'.repeat(process.stdout.columns || 80);

const EventLine: React.FC<{ 
  event: DisplayStreamEvent; 
  toolStates?: Map<string, ToolState>;
  animationsEnabled?: boolean;
}> = React.memo(({ event, toolStates, animationsEnabled = true }) => {
  switch (event.type) {
    // =======================================================================
    // SDK NATIVE EVENT HANDLERS - Integrated with SDK context
    // =======================================================================
    case 'model_invocation_start':
      return (
        <>
          <Text color="blue" bold>model invocation started</Text>
          {'modelId' in event && event.modelId && (
            <Text dimColor>Model: {event.modelId}</Text>
          )}
          <Text> </Text>
        </>
      );
      
    case 'model_stream_delta':
      return (
        <>
          {'delta' in event && event.delta && (
            <Text>{event.delta}</Text>
          )}
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
          {'delta' in event && event.delta && (
            <Text>{'isReasoning' in event && event.isReasoning ? 
              <Text color="cyan">{event.delta}</Text> : 
              <Text>{event.delta}</Text>
            }</Text>
          )}
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
        stepDisplay = "📋 [FINAL REPORT]";
      } else if (swarmAgent && swarmSubStep) {
        // For swarm operations, show agent name and iteration count
        const agentName = String(swarmAgent).toUpperCase().replace('_', ' ');
        if (swarmTotalIterations && swarmMaxIterations) {
          stepDisplay = `[SWARM: ${agentName} • STEP ${swarmTotalIterations}/${swarmMaxIterations}]`;
        } else {
          stepDisplay = `[SWARM: ${agentName} • STEP ${swarmSubStep}]`;
        }
      } else if (isSwarmOperation) {
        // Generic swarm operation without specific agent
        stepDisplay = `[SWARM • STEP ${event.step}/${event.maxSteps}]`;
      } else {
        // Regular step header
        stepDisplay = `[STEP ${event.step}/${event.maxSteps}]`;
      }
      
      return (
        <Box flexDirection="column" marginTop={1} marginBottom={0}>
          <Box flexDirection="row" alignItems="center">
            <Text color="#89B4FA" bold>
              {stepDisplay}
            </Text>
          </Box>
          <Text color="#45475A">{DIVIDER.slice(0, Math.max(0, DIVIDER.length - 20))}</Text>
        </Box>
      );
      
    case 'thinking':
      return (
        <Box marginTop={1}>
          <ThinkingIndicator 
            context={event.context}
            startTime={event.startTime}
            enabled={animationsEnabled}
          />
        </Box>
      );
      
    case 'thinking_end':
      // Don't render anything - this just signals to stop showing thinking indicator
      return null;
      
    case 'delayed_thinking_start':
      // Don't render anything - this is handled by the terminal component
      return null;
      
    case 'reasoning':
      // This case should not be reached anymore as reasoning is handled in StreamDisplay
      // But keep it as fallback
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text> </Text>
          <Text color="cyan" bold>reasoning</Text>
          <Box paddingLeft={0}>
            <Text color="cyan">{event.content}</Text>
          </Box>
          <Text> </Text>
        </Box>
      );
      
    case 'tool_start':
      // Always show tool header even if args are not yet available.
      // Individual tool renderers will gracefully handle missing fields.
      // Otherwise handle specific tool formatting
      switch (event.tool_name) {
        case 'swarm':
          // Simplified swarm tool header to avoid duplication
          const agentCount = event.tool_input?.agents?.length || 0;
          const agentNames = event.tool_input?.agents?.map((a: any) => 
            typeof a === 'string' ? a : a.name
          ).filter(Boolean).slice(0, 4).join(', ') || 'agents';
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="yellow" bold>tool: swarm</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ deploying {agentCount} agents: {agentNames}</Text>
              </Box>
            </Box>
          );
        case 'mem0_memory':
          const action = event.tool_input?.action || 'list';
          const content = event.tool_input?.content || event.tool_input?.query || '';
          const preview = content.length > 60 ? content.substring(0, 60) + '...' : content;
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: mem0_memory</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ action: {action === 'store' ? 'storing' : action === 'retrieve' ? 'retrieving' : action}</Text>
              </Box>
              {preview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ {action === 'store' ? 'content' : 'query'}: {preview}</Text>
                </Box>
              )}
              {!preview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ </Text>
                </Box>
              )}
            </Box>
          );
          break;
          
        case 'shell': {
          // Show tool header with swarm agent context if available
          const agentContext = ('swarm_agent' in event && event.swarm_agent) 
            ? ` (${event.swarm_agent})` : '';
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: shell{agentContext}</Text>
            </Box>
          );
        }
          
        case 'http_request': {
          const method = event.tool_input.method || 'GET';
          const url = event.tool_input.url || '';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: http_request</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ method: {method}</Text>
              </Box>
              <Box marginLeft={2}>
                <Text dimColor>└─ url: {url}</Text>
              </Box>
            </Box>
          );
        }
          
        case 'file_write': {
          const filePath = event.tool_input.path || 'unknown';
          const fileContent = event.tool_input.content || '';
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
          const editorCmd = event.tool_input.command || 'edit';
          const editorPath = event.tool_input.path || '';
          const editorContent = event.tool_input.content || '';
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: editor</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ command: {editorCmd}</Text>
              </Box>
              <Box marginLeft={2}>
                <Text dimColor>{editorContent ? '├─' : '└─'} path: {editorPath}</Text>
              </Box>
              {editorContent && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ size: {editorContent.length} chars</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        
        case 'think': {
          // think output goes to reasoning, but still show tool invocation
          const thought = event.tool_input.thought || event.tool_input.content || '';
          
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
          const code = event.tool_input.code || '';
          const codeLines = code.split('\n');
          const previewLines = 8; // Increased from 5 to show more context
          let codeDisplayLines: string[];
          if (codeLines.length <= previewLines) {
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
                <Box marginLeft={5} flexDirection="column">
                  {codeDisplayLines.map((line, index) => {
                    // Don't show tree characters for code content
                    if (line.startsWith('...')) {
                      return <Text key={index} dimColor italic>    {line}</Text>;
                    }
                    return <Text key={index} dimColor>    {line || ' '}</Text>;
                  })}
                </Box>
              </Box>
            </Box>
          );
        }
          
        case 'report_generator': {
          const target = event.tool_input.target || 'unknown';
          const reportType = event.tool_input.report_type || event.tool_input.type || 'general';
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
          
        case 'handoff_to_user': {
          // Message will be shown in the special user handoff display
          const userMessage = event.tool_input.message || '';
          
          // Still show tool call with tree format even though there's a special display
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: handoff_to_user</Text>
              {userMessage && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ message: {userMessage.length > 80 ? userMessage.substring(0, 80) + '...' : userMessage}</Text>
                </Box>
              )}
            </Box>
          );
        }
          
        case 'handoff_to_agent': {
          const targetAgent = event.tool_input.agent || event.tool_input.target_agent || 'unknown';
          const handoffMsg = event.tool_input.message || '';
          const msgPreview = handoffMsg.length > 80 ? handoffMsg.substring(0, 80) + '...' : handoffMsg;
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: handoff_to_agent</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ target: {targetAgent}</Text>
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
          const toolName = event.tool_input.tool_name || event.tool_input.tool || 'unknown';
          const toolPath = event.tool_input.path || '';
          const toolDescription = event.tool_input.description || '';
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
          const stopReason = event.tool_input.reason || 'Manual stop requested';
          
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
          // Enhanced tool display with swarm agent context
          const agentContext = ('swarm_agent' in event && event.swarm_agent) 
            ? ` (${event.swarm_agent})` : '';
          const preview = formatToolInput(event.tool_name as any, (event as any).tool_input);
          
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
      break;

    case 'command':
          // Parse command if it's a JSON object
          let commandText = event.content;
          if (typeof event.content === 'string' && event.content.startsWith('{')) {
            try {
              const parsed = JSON.parse(event.content);
              if (parsed.command) {
                commandText = parsed.command;
              }
            } catch (e) {
              // If parsing fails, use original content
            }
          }
          
          return (
            <Box flexDirection="column" marginLeft={2}>
              <Text><Text dimColor>⎿</Text> {commandText}</Text>
            </Box>
          );

    case 'output': {
      // Render even when content is empty to preserve intentional spacing.
      if ((event as any).content == null) {
        return null;
      }

      const contentStr = typeof (event as any).content === 'string'
        ? ((event as any).content as string)
        : String((event as any).content);

      // Normalize line endings and fix occasionally inlined tokens
      const normalized = contentStr
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        // If "Command:" was concatenated onto a previous line without a newline, insert one.
        .replace(/(\S)Command:/g, '$1\nCommand:');

      // Strip ANSI color codes for filtering logic
      const stripAnsi = (s: string) => s.replace(/\x1B\[[0-9;]*m/g, '');
      const plain = stripAnsi(normalized);

      // Skip placeholder tokens even if wrapped in ANSI codes
      const plainTrimmed = plain.trim();
      if (plainTrimmed === 'output' || plainTrimmed === 'reasoning') {
        return null;
      }

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
      const filteredLinesPre = plain.split('\n').filter(line => {
        const l = line.trim();
        if (l.length === 0) return true; // keep blank spacers
        // Drop placeholder lines that some backends emit as control tokens
        if (l === 'output' || l === 'reasoning') return false;
        // Drop raw CYBER_EVENT payload lines
        if (l.startsWith('__CYBER_EVENT__') || l.endsWith('__CYBER_EVENT_END__')) return false;
        // Drop ISO timestamped app logs: 2025-08-16 16:59:17 - INFO - ...
        if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+-\s+(INFO|DEBUG|WARNING|ERROR)\s+-\s+/.test(l)) return false;
        // Drop [3:19:46 PM]-style app logs
        if (appLogPatterns.some(p => p.test(l))) return false;
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
      if (filtered && (
        filtered.startsWith('▶') ||
        filtered.startsWith('◆') ||
        filtered.includes('✓') ||
        filtered.includes('○') ||
        filtered.startsWith('[Observability]')
      )) {
        if (filtered.startsWith('▶')) {
          // Initializing messages
          return (
            <Text color="#89B4FA" bold>{filtered}</Text>
          );
        } else if (filtered.startsWith('◆')) {
          // System status messages
          const isComplete = filtered.includes('ready') || filtered.includes('complete');
          return (
            <Text color={isComplete ? '#A6E3A1' : '#89DCEB'}>{filtered}</Text>
          );
        } else if (filtered.includes('✓')) {
          // Success indicators
          return (
            <Box marginLeft={1}>
              <Text color="#A6E3A1">{filtered}</Text>
            </Box>
          );
        } else if (filtered.includes('○')) {
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
        // Default system message styling
        return (
          <Text color="#89DCEB">{filtered}</Text>
        );
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
                      contentStr.includes('EXECUTIVE SUMMARY') ||
                      contentStr.includes('KEY FINDINGS') ||
                      contentStr.includes('REMEDIATION ROADMAP');
      
      // Check if this contains file paths or operation completion info
      const isOperationSummary = contentStr.includes('Outputs stored in:') ||
                                 contentStr.includes('Memory stored in:') ||
                                 contentStr.includes('Report saved to:') ||
                                 contentStr.includes('Operation ID:') ||
                                 contentStr.includes('ASSESSMENT COMPLETE') ||
                                 contentStr.includes('logs stored in:') ||
                                 contentStr.includes('evidence stored in:');
      
      // Use constants for display limits
      const collapseThreshold = isReport ? DISPLAY_LIMITS.REPORT_MAX_LINES : 
                               (isOperationSummary ? DISPLAY_LIMITS.OPERATION_SUMMARY_LINES : 
                                DISPLAY_LIMITS.DEFAULT_COLLAPSE_LINES);
      const fromToolBuffer = (event as any).metadata && (event as any).metadata.fromToolBuffer === true;
      const shouldCollapse = dedupedLines.length > collapseThreshold && !fromToolBuffer;
      
      let displayLines;
      if (shouldCollapse && !isReport && !isOperationSummary) {
        // For normal output, show first 5 and last 3 lines
        displayLines = [...dedupedLines.slice(0, 5), '...', ...dedupedLines.slice(-3)];
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
        // Show all lines if under threshold
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
              {displayLines.map((line, index) => (
                <Text key={index}>{line}</Text>
              ))}
            </Box>
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
              {displayLines.map((line, index) => {
                // Highlight path lines
                if (line.includes('Outputs stored in:') || line.includes('Memory stored in:') || 
                    line.includes('Host:') || line.includes('Container:')) {
                  return <Text key={index} color="cyan" bold>{line}</Text>;
                }
                return <Text key={index}>{line}</Text>;
              })}
            </Box>
          </Box>
        );
      }

      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color="yellow">output</Text>
            {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            {shouldCollapse && <Text dimColor> [{dedupedLines.length} lines]</Text>}
          </Box>
          <Box marginLeft={2} flexDirection="column">
            {displayLines.map((line, index) => (
              <Text key={index} dimColor>{line}</Text>
            ))}
          </Box>
        </Box>
      );
    }
      
    case 'error':
      // Simplified error display - just show the content
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text color="red">{event.content}</Text>
        </Box>
      );
      
    case 'metadata':
      // Display metadata parameters for tools that don't have built-in formatting
      if (event.content && typeof event.content === 'object') {
        const metadataEntries = Object.entries(event.content);
        if (metadataEntries.length > 0) {
          return (
            <Box flexDirection="column" marginLeft={2}>
              {metadataEntries.map(([key, value], index) => {
                const isLast = index === metadataEntries.length - 1;
                const displayValue = typeof value === 'string' && value.length > 50 
                  ? value.substring(0, 50) + '...' 
                  : String(value);
                return (
                  <Box key={index}>
                    <Text dimColor>{isLast ? '└─' : '├─'} {key}: {displayValue}</Text>
                  </Box>
                );
              })}
            </Box>
          );
        }
      }
      return null;
      
    case 'divider':
      return null;
      
    case 'user_handoff':
      return (
        <>
          <Text color="green" bold>AGENT REQUESTING USER INPUT</Text>
          <Box borderStyle="round" borderColor="green" paddingX={1} marginY={1}>
            <Text>{event.message}</Text>
          </Box>
          {event.breakout && (
            <Text color="red" bold>Agent execution will stop after this handoff</Text>
          )}
          <Box marginTop={1}>
            <Text color="yellow" bold>➤ Type your response below and press Enter to send it to the agent</Text>
          </Box>
          <Text> </Text>
        </>
      );
      
    case 'swarm_start': {
      // Create and display SwarmDisplay component immediately
      const swarmEvent = event as any;
      const agents: SwarmAgent[] = (swarmEvent.agent_details || swarmEvent.agents || []).map((agent: any, index: number) => ({
        id: `agent_${agent.name}_${index}`,  // Add unique id for each agent
        name: agent.name,
        role: agent.role || (agent.system_prompt ? agent.system_prompt.split('.')[0].trim() : ''),
        status: 'pending',
        tools: agent.tools || [],
        model_id: agent.model_id,
        model_provider: agent.model_provider,
        temperature: agent.temperature,
        recentToolCalls: []
      }));
      
      const swarmState: SwarmState = {
        id: `swarm_${Date.now()}`,
        task: swarmEvent.task || 'Multi-agent operation',
        status: 'initializing',
        agents: agents,
        startTime: Date.now(),
        totalTokens: 0,
        maxHandoffs: swarmEvent.max_handoffs,
        maxIterations: swarmEvent.max_iterations
      };
      
      return (
        <Box marginTop={1} marginBottom={1}>
          <SwarmDisplay swarmState={swarmState} collapsed={false} />
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
      
    case 'swarm_complete':
      // Enhanced swarm completion display
      const finalAgent = 'final_agent' in event ? String(event.final_agent || 'unknown') : 'unknown';
      const executionCount = 'execution_count' in event ? Number(event.execution_count || 0) : 0;
      const duration = 'duration' in event ? String(event.duration || 'unknown') : 'unknown';
      const totalTokens = 'total_tokens' in event ? Number(event.total_tokens || 0) : 0;
      const agentMetrics = 'agent_metrics' in event ? (event.agent_metrics as any[] || []) : [];
      const status = 'status' in event ? String(event.status || 'completed') : 'completed';
      const completedAgents = 'completed_agents' in event ? (event.completed_agents as string[] || []) : [];
      const failedAgents = 'failed_agents' in event ? (event.failed_agents as string[] || []) : [];
      
      // Determine if this was a timeout/failure
      const isTimeout = status.toLowerCase().includes('failed') || status.toLowerCase().includes('timeout');
      const statusColor = isTimeout ? 'red' : 'green';
      const statusText = isTimeout ? 'TIMEOUT' : 'COMPLETE';
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text color={statusColor} bold>[SWARM: {statusText}] {agentMetrics.length || completedAgents.length || 0} agents, {executionCount} handoffs</Text>
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

export const computeDisplayGroups = (events: DisplayStreamEvent[]): DisplayGroup[] => {
  // First, normalize events to remove duplicate swarm_start emissions
  const normalized: DisplayStreamEvent[] = [];
  let lastSwarmSignature = '';
  // Track if the previous event ended a tool so we can tag the next output
  let lastWasToolEnd = false;
  // Track active tool between start/end to tag outputs during tool execution
  let activeToolName: string | null = null;
  // Helper to normalize output content for duplicate comparison
  const normalizeOutputContent = (ev: any): string => {
    if (!ev || ev.type !== 'output') return '';
    const raw = typeof ev.content === 'string' ? ev.content : String(ev.content ?? '');
    const noCr = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    const stripAnsi = (s: string) => s.replace(/\x1B\[[0-9;]*m/g, '');
    const stripLogAndPrompt = (line: string) => {
      const ansiStripped = stripAnsi(line);
      // remove leading timestamp + level prefixes e.g., 2025-08-16 22:23:59 - INFO -
      const noLog = ansiStripped.replace(/^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?\s*-\s*(?:DEBUG|INFO|WARNING|WARN|ERROR)\s*-\s*/i, '');
      // remove common shell prompts at start of line: user@host:~$, $, #, >, PS ...>
      const noPrompt = noLog.replace(/^\s*(?:[\w_.-]+@[\w.-]+(?:[:~][^\s#\$>]*)?[#\$>]\s*|\$\s*|#\s*|>\s*|PS [^>]+>\s*)/, '');
      return noPrompt;
    };
    const normalizedLines = noCr.split('\n').map(stripLogAndPrompt).map(l => l.trim());
    return normalizedLines.join('\n').trim();
  };
  // Helpers to extract command text and boundary lines for overlap trimming
  const parseCommandText = (ev: any): string => {
    if (!ev || ev.type !== 'command') return '';
    try {
      if (typeof ev.content === 'string' && ev.content.startsWith('{')) {
        const parsed = JSON.parse(ev.content);
        if (parsed && typeof parsed.command === 'string') return parsed.command;
      }
    } catch {}
    return typeof ev.content === 'string' ? ev.content : String(ev.content ?? '');
  };
  const stripAnsi = (s: string) => s.replace(/\x1B\[[0-9;]*m/g, '');
  const stripLogPrefixAndPrompt = (line: string) => {
    const noLog = line.replace(/^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,\.]\d+)?\s*-\s*(?:DEBUG|INFO|WARNING|WARN|ERROR)\s*-\s*/i, '');
    return noLog.replace(/^\s*(?:[\w_.-]+@[\w.-]+(?:[:~][^\s#\$>]*)?[#\$>]\s*|\$\s*|#\s*|>\s*|PS [^>]+>\s*)/, '');
  };
  const firstNonEmpty = (s: string): string => {
    const line = s.split('\n').find(l => stripAnsi(stripLogPrefixAndPrompt(l)).trim().length > 0) ?? '';
    return stripAnsi(stripLogPrefixAndPrompt(line)).trim();
  };
  const lastNonEmpty = (s: string): string => {
    const lines = s.split('\n');
    for (let i = lines.length - 1; i >= 0; i--) {
      const l = stripAnsi(stripLogPrefixAndPrompt(lines[i])).trim();
      if (l.length > 0) return l;
    }
    return '';
  };
  events.forEach((ev) => {
    if (ev.type === 'swarm_start') {
      const names = 'agent_names' in ev && Array.isArray(ev.agent_names)
        ? (ev.agent_names as any[]).map(a => typeof a === 'string' ? a : (a && (a.name || a.role)) || '').join(',')
        : '';
      const task = ev.task || 'Unknown task';
      const signature = `${names}|${task}`;
      if (signature === lastSwarmSignature) {
        // skip duplicate consecutive swarm_start
        return;
      }
      lastSwarmSignature = signature;
    } else if (ev.type !== 'metrics_update') {
      // Reset signature on other meaningful events
      lastSwarmSignature = '';
    }
    // Drop redundant metadata that immediately repeats swarm_start info
    if (
      ev.type === 'metadata' &&
      normalized.length > 0 &&
      normalized[normalized.length - 1].type === 'swarm_start'
    ) {
      const last = normalized[normalized.length - 1] as any;
      const meta = (ev as any).content || {};
      const agentsMatch = typeof meta.agents === 'string' && meta.agents.includes(String(last.agent_count || ''));
      const taskMatch = typeof meta.task === 'string' && meta.task === (last.task || '');
      if (agentsMatch || taskMatch) {
        // Skip this metadata; it's a summary of the swarm_start already shown
        return;
      }
    }

    // Deduplicate consecutive tool_start events for the same tool
    if (ev.type === 'tool_start') {
      const currentTool = (ev as any).tool_name || '';
      const hasMeaningful = (() => {
        const input = (ev as any).tool_input || {};
        if (!input) return false;
        // Consider presence of non-empty string or any numeric/boolean as meaningful
        for (const key of Object.keys(input)) {
          const val = (input as any)[key];
          if (val == null) continue;
          if (typeof val === 'string' && val.trim().length > 0) return true;
          if (typeof val === 'number' || typeof val === 'boolean') return true;
          if (Array.isArray(val) && val.length > 0) return true;
          if (typeof val === 'object' && Object.keys(val).length > 0) return true;
        }
        return false;
      })();

      const lastEv = normalized[normalized.length - 1];
      if (lastEv && lastEv.type === 'tool_start') {
        const lastTool = (lastEv as any).tool_name || '';
        if (lastTool === currentTool) {
          // If previous had no meaningful input and current has, replace previous
          const lastHasMeaningful = (() => {
            const input = (lastEv as any).tool_input || {};
            if (!input) return false;
            for (const key of Object.keys(input)) {
              const val = (input as any)[key];
              if (val == null) continue;
              if (typeof val === 'string' && val.trim().length > 0) return true;
              if (typeof val === 'number' || typeof val === 'boolean') return true;
              if (Array.isArray(val) && val.length > 0) return true;
              if (typeof val === 'object' && Object.keys(val).length > 0) return true;
            }
            return false;
          })();

          if (!lastHasMeaningful && hasMeaningful) {
            normalized.pop();
            normalized.push(ev);
            return;
          }
          if (!lastHasMeaningful && !hasMeaningful) {
            // Keep only one empty-header for back-to-back starts
            return;
          }
        }
      }
    }

    // Track active tool state
    if (ev.type === 'tool_start') {
      activeToolName = (ev as any).tool_name || 'unknown_tool';
    } else if (ev.type === 'tool_invocation_end' || ev.type === 'step_header') {
      // Consider tool ended on these
      lastWasToolEnd = true;
      activeToolName = null;
    }

    // If we're in/after a tool, tag outputs so they don't collapse in the UI
    if ((lastWasToolEnd || activeToolName) && ev.type === 'output') {
      const anyEv: any = ev as any;
      anyEv.metadata = anyEv.metadata || {};
      if (anyEv.metadata.fromToolBuffer !== true) {
        anyEv.metadata.fromToolBuffer = true;
      }
      lastWasToolEnd = false;
    } else if (ev.type !== 'metadata') {
      // Reset on other meaningful events
      lastWasToolEnd = false;
    }

    // Trim echoed command line from immediate output after a command event
    if (ev.type === 'output' && normalized.length > 0 && normalized[normalized.length - 1].type === 'command') {
      const prevCmd = normalized[normalized.length - 1] as any;
      const cmdText = stripAnsi(parseCommandText(prevCmd)).trim();
      if (cmdText) {
        const raw = typeof (ev as any).content === 'string' ? (ev as any).content : String((ev as any).content ?? '');
        const norm = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        const head = firstNonEmpty(norm);
        // Also compare after removing common prompts from head
        const headNoPrompt = stripLogPrefixAndPrompt(head);
        if (head && (head === cmdText || head.startsWith(cmdText) || headNoPrompt === cmdText || headNoPrompt.startsWith(cmdText))) {
          const lines = norm.split('\n');
          let removed = false;
          const newLines: string[] = [];
          for (const line of lines) {
            const candidate = stripAnsi(stripLogPrefixAndPrompt(line)).trim();
            if (!removed && candidate.length > 0) {
              removed = true; // skip echoed head
              continue;
            }
            newLines.push(line);
          }
          const joined = newLines.join('\n');
          // If effectively empty after removal, skip this event entirely
          if (stripAnsi(joined).trim().length === 0) {
            return; // do not push ev
          }
          (ev as any).content = joined;
        }
      }
    }

    // Trim overlap line when consecutive outputs share boundary
    if (ev.type === 'output' && normalized.length > 0 && normalized[normalized.length - 1].type === 'output') {
      const prev = normalized[normalized.length - 1] as any;
      const prevRaw = typeof prev.content === 'string' ? prev.content : String(prev.content ?? '');
      const currRaw = typeof (ev as any).content === 'string' ? (ev as any).content : String((ev as any).content ?? '');
      const prevNorm = prevRaw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
      const currNorm = currRaw.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
      const tail = lastNonEmpty(prevNorm);
      const head = firstNonEmpty(currNorm);
      if (tail && head && tail === head) {
        const lines = currNorm.split('\n');
        let removed = false;
        const newLines: string[] = [];
        for (const line of lines) {
          const candidate = stripAnsi(stripLogPrefixAndPrompt(line)).trim();
          if (!removed && candidate.length > 0) {
            removed = true; // skip overlapping head line
            continue;
          }
          newLines.push(line);
        }
        const joined = newLines.join('\n');
        if (stripAnsi(joined).trim().length === 0) {
          return; // nothing left to show
        }
        (ev as any).content = joined;
      }
    }

    // Deduplicate consecutive output events with identical normalized content
    if (ev.type === 'output' && normalized.length > 0 && normalized[normalized.length - 1].type === 'output') {
      const prev = normalized[normalized.length - 1] as any;
      const prevNorm = normalizeOutputContent(prev);
      const currNorm = normalizeOutputContent(ev as any);
      if (prevNorm.length > 0 && prevNorm === currNorm) {
        // Skip duplicate output event
        return;
      }
    }

    normalized.push(ev);
  });

  const groups: DisplayGroup[] = [];

  let currentReasoningGroup: DisplayStreamEvent[] = [];
  let groupStartIdx = 0;
  let activeThinking = false;
  let lastThinkingIdx = -1;

  normalized.forEach((event, idx) => {
    if (event.type === 'reasoning') {
      if (currentReasoningGroup.length === 0) {
        groupStartIdx = idx;
      }
      currentReasoningGroup.push(event);
    } else if (event.type === 'thinking') {
      // End current reasoning group if exists
      if (currentReasoningGroup.length > 0) {
        groups.push({
          type: 'reasoning_group',
          events: currentReasoningGroup,
          startIdx: groupStartIdx
        });
        currentReasoningGroup = [];
      }

      activeThinking = true;
      lastThinkingIdx = groups.length;

      // Add thinking event
      groups.push({
        type: 'single',
        events: [event],
        startIdx: idx
      });
    } else if (event.type === 'thinking_end') {
      // Mark that thinking has ended
      activeThinking = false;
      // Don't add thinking_end to display
    } else {
      // End current reasoning group if exists
      if (currentReasoningGroup.length > 0) {
        groups.push({
          type: 'reasoning_group',
          events: currentReasoningGroup,
          startIdx: groupStartIdx
        });
        currentReasoningGroup = [];
      }

      // Add non-reasoning event as single
      groups.push({
        type: 'single',
        events: [event],
        startIdx: idx
      });
    }
  });

  // Handle any remaining reasoning group
  if (currentReasoningGroup.length > 0) {
    groups.push({
      type: 'reasoning_group',
      events: currentReasoningGroup,
      startIdx: groupStartIdx
    });
  }

  // If we have an active thinking that should be hidden, filter it out
  if (!activeThinking && lastThinkingIdx >= 0) {
    return groups.filter((_, idx) => idx !== lastThinkingIdx);
  }

  return groups;
};

export const StreamDisplay: React.FC<StreamDisplayProps> = React.memo(({ events, animationsEnabled = true }) => {
  // Track active swarm operations
  const [swarmStates, setSwarmStates] = React.useState<Map<string, SwarmState>>(new Map());
  const [currentActiveAgent, setCurrentActiveAgent] = React.useState<string | null>(null);
  
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
  
  // Track tool execution states
  const [toolStates, setToolStates] = React.useState<Map<string, ToolState>>(new Map());
  
  React.useEffect(() => {
    const newToolStates = new Map<string, ToolState>();
    
    events.forEach(event => {
      if (event.type === 'tool_start') {
        newToolStates.set(event.tool_name, {
          status: 'executing',
          startTime: Date.now()
        });
      } else if (event.type === 'tool_invocation_end') {
        const toolName = ('tool_name' in event && event.tool_name) || 'unknown';
        const success = ('success' in event && event.success !== false);
        newToolStates.set(toolName, {
          status: success ? 'completed' : 'failed',
          startTime: newToolStates.get(toolName)?.startTime || Date.now()
        });
      }
    });
    
    setToolStates(newToolStates);
  }, [events]);
  
  // Group consecutive reasoning events to prevent multiple labels
  const displayGroups = React.useMemo(() => computeDisplayGroups(events), [events]);
  
  // Find active swarm for display - only show if not handled by swarm_start events
  const activeSwarm = Array.from(swarmStates.values()).find(s => 
    s.status === 'running' || s.status === 'initializing'
  );
  
  // Only show swarm display if we have actual swarm_start events in this session
  const hasSwarmStartEvent = events.some(e => e.type === 'swarm_start');
  
  return (
    <Box flexDirection="column">
      {/* Only display swarm if we have actual swarm events in this session */}
      {activeSwarm && hasSwarmStartEvent && (
        <Box marginBottom={1}>
          <SwarmDisplay swarmState={activeSwarm} collapsed={false} />
        </Box>
      )}
      
      {displayGroups.map((group, idx) => {
        if (group.type === 'reasoning_group') {
          // Display reasoning group with single label
          const combinedContent = group.events.map(e => {
            if ('content' in e && e.content) {
              return e.content;
            }
            return '';
          }).join('');
          return (
            <Box key={`reasoning-group-${group.startIdx}`} flexDirection="column" marginTop={1}>
              <Text color="cyan" bold>reasoning</Text>
              <Box paddingLeft={0}>
                <Text color="cyan" wrap="wrap">{combinedContent}</Text>
              </Box>
            </Box>
          );
        } else {
          // Display single events normally
          return group.events.map((event, i) => (
            <MemoizedEventLine key={`ev-${idx}-${i}`} event={event} toolStates={toolStates} animationsEnabled={animationsEnabled} />
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
}> = ({ events }) => {
  const groups = React.useMemo(() => computeDisplayGroups(events), [events]);

  // Flatten groups into discrete render items with stable keys
  type Item = { key: string; render: () => React.ReactNode };
  const items: Item[] = React.useMemo(() => {
    const out: Item[] = [];
    groups.forEach((group, gIdx) => {
      if (group.type === 'reasoning_group') {
        const combinedContent = group.events.map(e => ('content' in e && (e as any).content) ? (e as any).content : '').join('');
        const key = `rg-${group.startIdx}`;
        out.push({
          key,
          render: () => (
            <Box key={key} flexDirection="column" marginTop={1}>
              <Text color="cyan" bold>reasoning</Text>
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
              <MemoizedEventLine key={key} event={event} toolStates={new Map()} animationsEnabled={false} />
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
};