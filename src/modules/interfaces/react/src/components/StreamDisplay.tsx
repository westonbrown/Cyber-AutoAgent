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

// Extended event types for UI-specific events not covered by the core SDK events
// These events are used for UI state management and display formatting
export type AdditionalStreamEvent = 
  | { type: 'step_header'; step: number | string; maxSteps: number; operation: string; duration: string; [key: string]: any }
  | { type: 'reasoning'; content: string; [key: string]: any }
  | { type: 'thinking'; context?: 'reasoning' | 'tool_preparation' | 'tool_execution' | 'waiting' | 'startup'; startTime?: number; [key: string]: any }
  | { type: 'thinking_end'; [key: string]: any }
  | { type: 'delayed_thinking_start'; context?: string; startTime?: number; delay?: number; [key: string]: any }
  | { type: 'tool_start'; tool_name: string; tool_input: any; [key: string]: any }
  | { type: 'tool_input_update'; tool_id: string; tool_input: any; [key: string]: any }
  | { type: 'command'; content: string; [key: string]: any }
  | { type: 'output'; content: string; exitCode?: number; duration?: number; [key: string]: any }
  | { type: 'error'; content: string; [key: string]: any }
  | { type: 'metadata'; content: Record<string, string>; [key: string]: any }
  | { type: 'divider'; [key: string]: any }
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
  | { type: 'batch'; id?: string; events: DisplayStreamEvent[]; [key: string]: any }
  | { type: 'tool_output'; tool: string; status?: string; output?: any; [key: string]: any }
  | { type: 'operation_init'; operation_id?: string; target?: string; objective?: string; memory?: any; [key: string]: any };

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
}

// Tool execution state tracking
interface ToolState {
  status: 'executing' | 'completed' | 'failed';
  startTime: number;
}

const DIVIDER = '─'.repeat(process.stdout.columns || 80);

// Export EventLine for potential reuse in other components
export const EventLine: React.FC<{ 
  event: DisplayStreamEvent; 
  toolStates?: Map<string, ToolState>;
  toolInputs?: Map<string, any>;
  animationsEnabled?: boolean;
}> = React.memo(({ event, toolStates, toolInputs, animationsEnabled = true }) => {
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
        stepDisplay = "📋 [FINAL REPORT]";
      } else if (swarmAgent && swarmSubStep) {
        // For swarm operations, show agent name with their step count and swarm-wide progress
        // Use replaceAll to handle multi-word agent names correctly
        const agentName = String(swarmAgent).toUpperCase().replaceAll('_', ' ');
        // Show both agent's step count and swarm-wide iteration progress
        const swarmTotalIterations = (event as any)['swarm_total_iterations'] || swarmSubStep;
        const maxIterations = swarmMaxIterations || 30;
        // Display format: agent step count + swarm-wide progress to show actual SDK enforcement
        stepDisplay = `[SWARM: ${agentName} • STEP ${swarmSubStep} | SWARM TOTAL ${swarmTotalIterations}/${maxIterations}]`;
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
      const swarmAgentLabel = ('swarm_agent' in event && event.swarm_agent) 
        ? ` (${event.swarm_agent})` 
        : '';
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text> </Text>
          <Text color="cyan" bold>reasoning{swarmAgentLabel}</Text>
          <Box paddingLeft={0}>
            <Text color="cyan">{event.content}</Text>
          </Box>
          <Text> </Text>
        </Box>
      );
      
    case 'tool_start': {
      // Get the latest tool input (may have been updated via tool_input_update)
      const latestInput = ('tool_id' in event && event.tool_id && toolInputs?.get(event.tool_id)) || event.tool_input || {};
      
      // Always show tool header even if args are not yet available.
      // Individual tool renderers will gracefully handle missing fields.
      // Otherwise handle specific tool formatting
      switch (event.tool_name) {
        case 'swarm':
          // Simplified swarm tool header to avoid duplication
          const agentCount = latestInput?.agents?.length || 0;
          const agentNames = latestInput?.agents?.map((a: any) => 
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
        case 'mem0_memory': {
          const action = latestInput?.action || 'list';
          const content = latestInput?.content || latestInput?.query || '';
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
        }
          
        case 'shell': {
          // Show tool header with command(s) if available
          const agentContext = ('swarm_agent' in event && event.swarm_agent) 
            ? ` (${event.swarm_agent})` : '';
          
          // Get the raw command input
          let commandInput = latestInput?.command || latestInput?.cmd || '';
          
          // Handle both JSON strings AND already-parsed arrays from backend
          // The backend now parses JSON before sending, so we get:
          // 1. Already parsed arrays of objects: [{"command": "cmd", "timeout": 300}, ...]
          // 2. Already parsed arrays of strings: ["cmd1", "cmd2"]
          // 3. JSON strings (legacy): "[{\"command\": \"cmd\", \"timeout\": 300}, ...]"
          // 4. Single strings: "single command"
          
          // Handle already-parsed arrays (NEW - backend now sends these)
          if (Array.isArray(commandInput)) {
            // Extract command strings from array of objects or strings
            commandInput = commandInput.map((item: any) => {
              if (typeof item === 'string') return item;
              if (typeof item === 'object' && item && item.command) return item.command;
              if (typeof item === 'object' && item && item.cmd) return item.cmd;
              return String(item); // Convert to string as fallback
            }).filter(Boolean);
          }
          // Handle JSON strings (LEGACY - for backwards compatibility)
          else if (typeof commandInput === 'string' && commandInput.trim().startsWith('[')) {
            try {
              // Parse the JSON string - it has real newlines, not \n escapes
              const parsed = JSON.parse(commandInput);
              if (Array.isArray(parsed)) {
                // Extract command strings from whatever format we get
                commandInput = parsed.map((item: any) => {
                  if (typeof item === 'string') return item;
                  if (typeof item === 'object' && item && item.command) return item.command;
                  if (typeof item === 'object' && item && item.cmd) return item.cmd;
                  return '';
                }).filter(Boolean);
              }
            } catch (e) {
              // Fallback: try to extract commands using regex
              const matches = commandInput.match(/"command"\s*:\s*"([^"]+)"/g);
              if (matches) {
                commandInput = matches.map(m => {
                  const match = m.match(/"command"\s*:\s*"([^"]+)"/);
                  return match ? match[1] : '';
                }).filter(Boolean);
              } else {
                // Last resort: try to find any quoted strings
                const quotedStrings = commandInput.match(/"([^"]+)"/g);
                if (quotedStrings && quotedStrings.length > 0) {
                  // Filter out JSON keys and keep only command-like strings
                  commandInput = quotedStrings
                    .map(s => s.slice(1, -1))
                    .filter(s => !s.match(/^(command|timeout|parallel)$/))
                    .filter(s => s.includes(' ') || s.includes('/'));
                }
              }
            }
          }
          
          // Simplified command parser - commandInput is already pre-processed above
          const parseCommands = (cmd: any): string[] => {
            if (!cmd) return [];
            
            // If it's already an array (from pre-processing), ensure all items are strings
            if (Array.isArray(cmd)) {
              return cmd.map((item: any) => {
                // Convert everything to string
                if (typeof item === 'string') return item;
                if (typeof item === 'object' && item && item.command) return String(item.command);
                if (typeof item === 'object' && item && item.cmd) return String(item.cmd);
                return String(item);
              }).filter(Boolean);
            }
            
            // Handle string that wasn't caught by pre-processing
            if (typeof cmd === 'string') {
              return [cmd];
            }
            
            // Handle single command object
            if (typeof cmd === 'object' && cmd) {
              if (cmd.command) return [String(cmd.command)];
              if (cmd.cmd) return [String(cmd.cmd)];
            }
            
            return [];
          };
          
          const commands = parseCommands(commandInput);
          
          // Display commands with timeout info if available
          const hasTimeout = latestInput?.timeout;
          const hasParallel = latestInput?.parallel;
          const extraParams = [];
          if (hasTimeout) extraParams.push(`timeout: ${latestInput.timeout}s`);
          if (hasParallel) extraParams.push('parallel execution');
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: shell{agentContext}</Text>
              {commands.length > 0 ? (
                commands.map((cmd, index) => {
                  // Commands should already be strings from parseCommands
                  // But add a safety check just in case
                  const cmdStr = typeof cmd === 'string' ? cmd : String(cmd);
                  return (
                    <Box key={index} marginLeft={2}>
                      <Text dimColor>⎿ {cmdStr}</Text>
                    </Box>
                  );
                })
              ) : (
                <Box marginLeft={2}>
                  <Text dimColor>⎿ (no command)</Text>
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
          const editorContent = latestInput.content || '';
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
          const code = latestInput.code || '';
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
          
        case 'handoff_to_user': {
          // Message will be shown in the special user handoff display
          const userMessage = latestInput.message || '';
          
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
          const targetAgent = latestInput.agent || latestInput.target_agent || 'unknown';
          const handoffMsg = latestInput.message || '';
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
          const toolName = latestInput.tool_name || latestInput.tool || 'unknown';
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
          const stopReason = latestInput.reason || 'Manual stop requested';
          
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

      // Backend now sends clean content without ANSI codes
      const plain = normalized;

      // Skip placeholder tokens
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
      const fromToolBuffer = (event as any).metadata && (event as any).metadata.fromToolBuffer;
      
      const collapseThreshold = isReport ? DISPLAY_LIMITS.REPORT_MAX_LINES : 
                               (isOperationSummary ? DISPLAY_LIMITS.OPERATION_SUMMARY_LINES : 
                                (fromToolBuffer ? DISPLAY_LIMITS.TOOL_OUTPUT_COLLAPSE_LINES : 
                                 DISPLAY_LIMITS.DEFAULT_COLLAPSE_LINES));
      const shouldCollapse = dedupedLines.length > collapseThreshold;
      
      let displayLines;
      if (shouldCollapse && !isReport && !isOperationSummary && !fromToolBuffer) {
        // For normal output only (not tool output), show first 5 and last 3 lines
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

      // Show tool output with special formatting
      if (fromToolBuffer) {
        return (
          <Box flexDirection="column" marginTop={1}>
            <Box>
              <Text color="yellow">output</Text>
              {dedupedLines.length > 10 && <Text dimColor> [{dedupedLines.length} lines]</Text>}
              {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            </Box>
            <Box marginLeft={2} flexDirection="column">
              {displayLines.map((line, index) => (
                <Text key={index} dimColor>{line}</Text>
              ))}
            </Box>
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
      
    case 'report_content':
      // Display the full security assessment report
      if (!event.content) return null;
      
      return (
        <Box flexDirection="column" marginTop={1} marginBottom={1}>
          <Box borderStyle="double" borderColor="cyan" paddingX={1}>
            <Text color="cyan" bold>SECURITY ASSESSMENT REPORT</Text>
          </Box>
          <Box flexDirection="column" marginTop={1} paddingX={1}>
            <Text>{event.content}</Text>
          </Box>
        </Box>
      );
      
    case 'error':
      // Simplified error display - just show the content
      return (
        <Box flexDirection="column" marginTop={1}>
          <Text color="red">{event.content}</Text>
        </Box>
      );
      
    case 'metadata':
      // Render metadata events normally
      // Generic tools no longer emit duplicate metadata
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
              toolStates={toolStates}
              animationsEnabled={animationsEnabled}
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
          {('tools_available' in event && event.tools_available) ? (
            <Text dimColor>  Available Tools: {event.tools_available}</Text>
          ) : null}
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
  
  // Track tool inputs (for handling tool_input_update events from swarm agents)
  const [toolInputs, setToolInputs] = React.useState<Map<string, any>>(new Map());
  
  React.useEffect(() => {
    const newToolStates = new Map<string, ToolState>();
    const newToolInputs = new Map<string, any>();
    
    events.forEach(event => {
      if (event.type === 'tool_start') {
        newToolStates.set(event.tool_name, {
          status: 'executing',
          startTime: Date.now()
        });
        // Store initial tool input (may be empty for swarm agents)
        if ('tool_id' in event && event.tool_id) {
          newToolInputs.set(event.tool_id, event.tool_input || {});
        }
      } else if (event.type === 'tool_input_update') {
        // Update tool input with complete data
        if ('tool_id' in event && event.tool_id && 'tool_input' in event) {
          newToolInputs.set(event.tool_id, event.tool_input);
        }
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
          // Display reasoning group with single label - memoize content combination
          const combinedContent = group.events.reduce((acc, e) => {
            if ('content' in e && e.content) {
              return acc + e.content;
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
              key={event.id || `ev-${idx}-${i}`}  // Use event ID if available
              event={event} 
              toolStates={toolStates}
              toolInputs={toolInputs} 
              animationsEnabled={animationsEnabled} 
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
}> = React.memo(({ events }) => {
  const groups = React.useMemo(() => computeDisplayGroups(events), [events]);

  // Flatten groups into discrete render items with stable keys
  type Item = { key: string; render: () => React.ReactNode };
  const items: Item[] = React.useMemo(() => {
    const out: Item[] = [];
    groups.forEach((group, gIdx) => {
      if (group.type === 'reasoning_group') {
        // Use reduce for better performance with large arrays
        const combinedContent = group.events.reduce((acc, e) => {
          if ('content' in e && (e as any).content) {
            return acc + (e as any).content;
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
});