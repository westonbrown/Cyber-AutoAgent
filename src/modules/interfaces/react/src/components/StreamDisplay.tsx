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
import { 
  getToolCategory, 
  formatToolWithIcon, 
  isHighPriorityTool,
  getExecutionStatus 
} from '../utils/toolCategories.js';

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
}> = React.memo(({ event, toolStates }) => {
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
      // Detect if this is a swarm step and extract agent info from context
      let agentInfo = '';
      const stepNumber = event.step;
      
      // Show specific swarm agent name if available
      if (event.swarm_agent) {
        // Capitalize agent name for better visibility
        const agentName = String(event.swarm_agent);
        agentInfo = ` • SUB-AGENT ${agentName}`;
      } else if (event.swarm_context) {
        // If we have swarm context but no specific agent, show operation type
        agentInfo = ` • SUB-AGENT ${event.swarm_context}`;
      } else if (event.is_swarm_operation) { 
        // Show swarm operation indicator
        agentInfo = ' • SWARM OPERATION';
      }
      
      return (
        <Box flexDirection="column" marginTop={1} marginBottom={0}>
          <Box flexDirection="row" alignItems="center">
            <Text color="#89B4FA" bold>
              {event.step === "FINAL REPORT" ? "[FINAL REPORT]" : `[STEP ${event.step}/${event.maxSteps}]`}
            </Text>
            {agentInfo && (
              <Text color="#CBA6F7" bold>{agentInfo}</Text>
            )}
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
      // If the first event has empty input, skip rendering to avoid duplicate tool name lines.
      const hasEmptyInput = !event.tool_input || Object.keys(event.tool_input).length === 0;
      if (hasEmptyInput) {
        return null;
      }
      
      // Otherwise handle specific tool formatting
      switch (event.tool_name) {
        case 'swarm':
          // Suppress detailed rendering here to avoid duplication with 'swarm_start'.
          // Legacy backends without 'swarm_start' will still show rich output via SwarmDisplay when parsed from outputs.
          return null;
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
            </Box>
          );
          break;
          
        case 'shell':
          // Shell commands will be shown via separate 'command' events
          // Just show the tool name here
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: shell</Text>
            </Box>
          );
          break;
          
        case 'http_request':
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
          break;
          
        case 'file_write':
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
          break;
          
        case 'editor':
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
          break;
          
        
        case 'think':
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
          break;
          
        case 'python_repl':
          const code = event.tool_input.code || '';
          const codeLines = code.split('\n');
          const previewLines = 8; // Increased from 5 to show more context
          
          let displayLines;
          let isTruncated = false;
          if (codeLines.length <= previewLines) {
            displayLines = codeLines;
          } else {
            // Show first 6 lines and last 2 lines for better context
            displayLines = [
              ...codeLines.slice(0, 6),
              '',
              `... (${codeLines.length - 8} more lines)`,
              '',
              ...codeLines.slice(-2)
            ];
            isTruncated = true;
          }
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: python_repl</Text>
              <Box marginLeft={2} flexDirection="column">
                <Text dimColor>└─ code:</Text>
                <Box marginLeft={5} flexDirection="column">
                  {displayLines.map((line, i) => {
                    // Don't show tree characters for code content
                    if (line.startsWith('...')) {
                      return <Text key={i} dimColor italic>    {line}</Text>;
                    }
                    return <Text key={i} dimColor>    {line || ' '}</Text>;
                  })}
                </Box>
              </Box>
            </Box>
          );
          break;
          
        case 'report_generator':
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
          break;
          
        case 'handoff_to_user':
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
          break;
          
        case 'handoff_to_agent':
          const toAgent = event.tool_input.agent || event.tool_input.target_agent || 'unknown';
          const handoffMsg = event.tool_input.message || '';
          const msgPreview = handoffMsg.length > 80 ? handoffMsg.substring(0, 80) + '...' : handoffMsg;
          
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: handoff_to_agent</Text>
              <Box marginLeft={2}>
                <Text dimColor>├─ target: {toAgent}</Text>
              </Box>
              {msgPreview && (
                <Box marginLeft={2}>
                  <Text dimColor>└─ message: {msgPreview}</Text>
                </Box>
              )}
            </Box>
          );
          break;
          
        case 'load_tool':
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
          break;
          
        case 'stop':
          const stopReason = event.tool_input.reason || 'Manual stop requested';
          
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text color="green" bold>tool: stop</Text>
              <Box marginLeft={2}>
                <Text dimColor>└─ reason: {stopReason}</Text>
              </Box>
            </Box>
          );
          break;
          
        default:
          // For unknown tools, show just the tool name - parameters will come via metadata events
          return (
            <Box flexDirection="column">
              <Text color="green" bold>tool: {event.tool_name}</Text>
            </Box>
          );
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
      
    case 'output':
      // Skip empty output events completely
      if (!event.content || event.content.trim() === '') {
        return null;
      }
      
      // Skip raw "output" or "reasoning" text that shouldn't be displayed
      if (event.content.trim() === 'output' || event.content.trim() === 'reasoning') {
        return null;
      }
      
      const metadata = [];
      if (event.exitCode !== undefined) metadata.push(`exit: ${event.exitCode}`);
      if (event.duration) metadata.push(`duration: ${event.duration}`);
      
      // Enhanced startup/system messages with better theming and compact structure
      if (event.content && (
        event.content.includes('▶') || 
        event.content.includes('◆') || 
        event.content.includes('✓') ||
        event.content.includes('○') ||
        event.content.startsWith('[Observability]')
      )) {
        // Parse different message types for better styling with minimal spacing
        if (event.content.startsWith('▶')) {
          // Initializing messages - use primary color with emphasis
          return (
            <Text color="#89B4FA" bold>{event.content}</Text>
          );
        } else if (event.content.startsWith('◆')) {
          // System status messages - use info color
          const isComplete = event.content.includes('ready') || event.content.includes('complete');
          return (
            <Text color={isComplete ? "#A6E3A1" : "#89DCEB"}>{event.content}</Text>
          );
        } else if (event.content.includes('✓')) {
          // Success indicators - use success color with minimal spacing
          return (
            <Box marginLeft={1}>
              <Text color="#A6E3A1">{event.content}</Text>
            </Box>
          );
        } else if (event.content.includes('○')) {
          // Warning/unavailable indicators - use warning color
          return (
            <Box marginLeft={1}>
              <Text color="#F9E2AF">{event.content}</Text>
            </Box>
          );
        } else if (event.content.startsWith('[Observability]')) {
          // Observability messages - use accent color with minimal spacing
          return (
            <Text color="#CBA6F7">{event.content}</Text>
          );
        }
        
        // Default system message styling
        return (
          <Text color="#89DCEB">{event.content}</Text>
        );
      }
      
      // For command output, show with consistent spacing
      const lines = event.content.split('\n');
      
      // Check if this is a security report or important system output
      const isReport = event.content.includes('# SECURITY ASSESSMENT REPORT') || 
                      event.content.includes('EXECUTIVE SUMMARY') ||
                      event.content.includes('KEY FINDINGS') ||
                      event.content.includes('REMEDIATION ROADMAP');
      
      // Check if this contains file paths or operation completion info
      const isOperationSummary = event.content.includes('Outputs stored in:') ||
                                 event.content.includes('Memory stored in:') ||
                                 event.content.includes('Report saved to:') ||
                                 event.content.includes('Operation ID:');
      
      // Use constants for display limits
      const collapseThreshold = isReport ? DISPLAY_LIMITS.REPORT_MAX_LINES : 
                               (isOperationSummary ? DISPLAY_LIMITS.OPERATION_SUMMARY_LINES : 
                                DISPLAY_LIMITS.DEFAULT_COLLAPSE_LINES);
      const shouldCollapse = lines.length > collapseThreshold;
      
      let displayLines;
      if (shouldCollapse && !isReport && !isOperationSummary) {
        // For normal output, show first 5 and last 3 lines
        displayLines = [...lines.slice(0, 5), '...', ...lines.slice(-3)];
      } else if (shouldCollapse && (isReport || isOperationSummary)) {
        // For reports and summaries, show much more content
        if (isReport) {
          // For reports, show configured preview and tail lines
          displayLines = [
            ...lines.slice(0, DISPLAY_LIMITS.REPORT_PREVIEW_LINES), 
            '', 
            '... (content continues)', 
            '', 
            ...lines.slice(-DISPLAY_LIMITS.REPORT_TAIL_LINES)
          ];
        } else {
          // For operation summaries, show all content up to limit
          displayLines = lines.slice(0, DISPLAY_LIMITS.OPERATION_SUMMARY_LINES);
        }
      } else {
        // Show all lines if under threshold
        displayLines = lines;
      }
      
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box>
            <Text color="yellow">output</Text>
            {metadata.length > 0 && <Text dimColor> ({metadata.join(', ')})</Text>}
            {shouldCollapse && <Text dimColor> [{lines.length} lines]</Text>}
          </Box>
          <Box marginLeft={2} flexDirection="column">
            {displayLines.map((line, i) => (
              <Text key={i} dimColor>{line}</Text>
            ))}
          </Box>
        </Box>
      );
      
    case 'error':
      return (
        <Box flexDirection="column" marginTop={1}>
          <Box paddingX={1} borderStyle="round" borderColor="#F38BA8">
            <Box flexDirection="column">
              <Text color="#F38BA8" bold>⚠️  ERROR</Text>
              <Box marginLeft={1}>
                <Text color="#F38BA8">{event.content}</Text>
              </Box>
            </Box>
          </Box>
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
          <Text color="yellow">Please provide your response in the input below:</Text>
          <Text> </Text>
        </>
      );
      
    case 'swarm_start':
      // Display swarm operation start with agent details
      const swarmAgents = 'agent_names' in event ? (event.agent_names as any[] || []) : [];
      const swarmDetails = 'agent_details' in event ? (event.agent_details as any[] || []) : [];
      const swarmTask = 'task' in event ? String(event.task || '') : '';
      
      // Don't display empty/invalid swarm events
      if (swarmAgents.length === 0 && !swarmTask) {
        return null;
      }
      
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text color="green" bold>[SWARM] Multi-Agent Operation Starting</Text>
          <Box marginLeft={2}>
            <Text color="blue" bold>Agents ({swarmAgents.length}):</Text>
          </Box>
          {swarmAgents.length > 0 && swarmAgents.map((agent, i) => {
            // Handle agent as either string or object
            let agentName = '';
            if (typeof agent === 'string') {
              agentName = agent;
            } else if (agent && typeof agent === 'object') {
              // Extract name from agent object
              agentName = agent.name || agent.role || 'Agent ' + (i + 1);
            }
            return agentName ? (
              <Box key={i} marginLeft={4}>
                <Text color="cyan">• {agentName}</Text>
              </Box>
            ) : null;
          })}
          {swarmDetails.length > 0 && swarmDetails.map((detail, i) => {
            // Handle detail as either string or object with agent info
            let detailText = '';
            if (typeof detail === 'string') {
              detailText = detail;
            } else if (detail && typeof detail === 'object') {
              // Extract meaningful info from agent object
              detailText = detail.name || detail.role || JSON.stringify(detail).substring(0, 50) + '...';
            }
            return detailText ? (
              <Box key={i} marginLeft={4}>
                <Text color="cyan">• {detailText}</Text>
              </Box>
            ) : null;
          })}
          {swarmTask && (
            <Box marginLeft={2}>
              <Text color="yellow" bold>Task: </Text>
              <Text>{swarmTask}</Text>
            </Box>
          )}
          <Text> </Text>
        </Box>
      );
      
    case 'swarm_handoff':
      // Display agent handoff in swarm
      const fromAgent = 'from_agent' in event ? String(event.from_agent || 'unknown') : 'unknown';
      const toAgent = 'to_agent' in event ? String(event.to_agent || 'unknown') : 'unknown';
      const handoffMessage = 'message' in event ? String(event.message || '') : '';
      
      return (
        <Box flexDirection="column">
          <Text color="magenta" bold>[HANDOFF] Agent Handoff</Text>
          <Box marginLeft={2}>
            <Text color="cyan">{fromAgent} → {toAgent}</Text>
          </Box>
          {handoffMessage && (
            <Box marginLeft={2}>
              <Text dimColor>Message: {handoffMessage}</Text>
            </Box>
          )}
        </Box>
      );
      
    case 'swarm_complete':
      // Display swarm completion
      const finalAgent = 'final_agent' in event ? String(event.final_agent || 'unknown') : 'unknown';
      const executionCount = 'execution_count' in event ? Number(event.execution_count || 0) : 0;
      
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text color="green" bold>[SWARM] Operation Complete</Text>
          <Box marginLeft={2}>
            <Text>Final Agent: {finalAgent}</Text>
            <Text>Total Handoffs: {executionCount}</Text>
          </Box>
          <Text> </Text>
        </Box>
      );
      
    default:
      return null;
  }
});

// Memoize EventLine component for performance
const MemoizedEventLine = React.memo(EventLine);

export const StreamDisplay: React.FC<StreamDisplayProps> = React.memo(({ events }) => {
  // Track active swarm operations
  const [swarmStates, setSwarmStates] = React.useState<Map<string, SwarmState>>(new Map());
  const [currentActiveAgent, setCurrentActiveAgent] = React.useState<string | null>(null);
  
  // Process swarm events to build state
  React.useEffect(() => {
    const newSwarmStates = new Map<string, SwarmState>();
    let currentSwarmId: string | null = null;
    
    events.forEach(event => {
      // Handle swarm tool start
      if (event.type === 'tool_start' && event.tool_name === 'swarm') {
        currentSwarmId = Date.now().toString(); // Simple ID generation
        const task = event.tool_input.task || event.tool_input.objective || 'Unknown task';
        const numAgents = event.tool_input.agents || event.tool_input.num_agents || 0;
        
        // Try to extract agent names from swarm input if available
        const agents: SwarmAgent[] = [];
        if (event.tool_input.agent_names && Array.isArray(event.tool_input.agent_names)) {
          event.tool_input.agent_names.forEach((name: string, i: number) => {
            agents.push({
              id: `agent_${i}`,
              name: name,
              status: 'pending',
              tools: []
            });
          });
        } else {
          // Create placeholder agents if names not available
          for (let i = 0; i < numAgents; i++) {
            agents.push({
              id: `agent_${i}`,
              name: `Agent ${i + 1}`,
              status: 'pending',
              tools: []
            });
          }
        }
        
        newSwarmStates.set(currentSwarmId, {
          id: currentSwarmId,
          task,
          status: 'initializing',
          agents,
          startTime: Date.now()
        });
      }
      // Handle swarm output that contains agent details
      else if (event.type === 'output' && currentSwarmId && event.content) {
        const swarmState = newSwarmStates.get(currentSwarmId);
        if (swarmState) {
          // Parse agent information from output
          const content = event.content;
          
          // Check for swarm completion markers
          if (content.includes('Swarm Execution Complete') || content.includes('Final Team Result')) {
            swarmState.status = 'completed';
            swarmState.endTime = Date.now();
          }
          // Parse agent contributions - match the format from swarm.py output
          else if (content.includes('Individual Agent Contributions')) {
            swarmState.status = 'running';
            // Extract agent details from the formatted output using the actual format from swarm tool
            // Format: **AGENT_NAME:** or **Agent Name:**
            const agentMatches = content.matchAll(/\*\*([^*]+):\*\*/g);
            for (const match of agentMatches) {
              const agentName = match[1].trim();
              // Skip section headers
              if (agentName.includes('Individual Agent Contributions') || 
                  agentName.includes('Final Team Result') || 
                  agentName.includes('Team Resource Usage')) {
                continue;
              }
              
              const existingAgent = swarmState.agents.find(a => a.name === agentName);
              if (!existingAgent) {
                swarmState.agents.push({
                  id: agentName.toLowerCase().replace(/\s+/g, '_'),
                  name: agentName,
                  status: 'active',
                  tools: [],
                  toolCalls: []
                });
              }
            }
            
            // Parse tool usage from agent contributions
            const toolMatches = content.matchAll(/(http_request|shell|python_repl|file_write|nmap|sqlmap|nikto)\s*\([^)]*\)/g);
            for (const match of toolMatches) {
              const toolCall = match[0];
              const toolName = match[1];
              
              // Find the agent this tool belongs to by context
              const beforeTool = content.substring(0, match.index);
              const lastAgentMatch = [...beforeTool.matchAll(/• ([^:]+):/g)].pop();
              if (lastAgentMatch) {
                const agentName = lastAgentMatch[1].trim();
                const agent = swarmState.agents.find(a => a.name === agentName);
                if (agent) {
                  if (!agent.tools?.includes(toolName)) {
                    agent.tools = agent.tools || [];
                    agent.tools.push(toolName);
                  }
                  agent.toolCalls = agent.toolCalls || [];
                  agent.toolCalls.push({
                    tool: toolName,
                    input: toolCall,
                    timestamp: Date.now()
                  });
                }
              }
            }
            
            // Parse agent tasks and results
            const sections = content.split(/• ([^:]+):/);
            for (let i = 1; i < sections.length; i += 2) {
              const agentName = sections[i].trim();
              const agentContent = sections[i + 1];
              const agent = swarmState.agents.find(a => a.name === agentName);
              
              if (agent && agentContent) {
                // Extract task description (first few lines)
                const lines = agentContent.trim().split('\n');
                const taskLines = lines.slice(0, 2).join(' ').trim();
                if (taskLines && !agent.task) {
                  agent.task = taskLines.length > 100 ? taskLines.substring(0, 100) + '...' : taskLines;
                }
                
                // Extract results (look for conclusion patterns)
                const resultPatterns = [
                  /found (\d+.*?)$/im,
                  /identified (\d+.*?)$/im,
                  /discovered (.{10,50})$/im,
                  /completed (.{10,50})$/im
                ];
                
                for (const pattern of resultPatterns) {
                  const match = agentContent.match(pattern);
                  if (match && !agent.result) {
                    agent.result = match[1].trim();
                    agent.status = 'completed';
                    break;
                  }
                }
              }
            }
          }
          // Parse collaboration chain
          else if (content.includes('Collaboration Chain:')) {
            const chainMatch = content.match(/Collaboration Chain:\s*(.+)/);
            if (chainMatch) {
              swarmState.collaborationChain = chainMatch[1].split(' → ').map(s => s.trim());
            }
          }
          // Parse team metrics
          else if (content.includes('Team Size:')) {
            const teamMatch = content.match(/Team Size:\s*(\d+)/);
            if (teamMatch) {
              const teamSize = parseInt(teamMatch[1]);
              // Ensure we have placeholder agents if needed
              while (swarmState.agents.length < teamSize) {
                swarmState.agents.push({
                  id: `agent_${swarmState.agents.length + 1}`,
                  name: `Agent ${swarmState.agents.length + 1}`,
                  status: 'pending',
                  tools: []
                });
              }
            }
          }
          // Parse token usage
          else if (content.includes('Total tokens:')) {
            const tokenMatch = content.match(/Total tokens:\s*([\d,]+)/);
            if (tokenMatch) {
              swarmState.totalTokens = parseInt(tokenMatch[1].replace(/,/g, ''));
            }
          }
        }
      }
    });
    
    setSwarmStates(newSwarmStates);
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
  const displayGroups = React.useMemo(() => {
    // First, normalize events to remove duplicate swarm_start emissions
    const normalized: DisplayStreamEvent[] = [];
    let lastSwarmSignature = '';
    events.forEach((ev) => {
      if (ev.type === 'swarm_start') {
        const names = 'agent_names' in ev && Array.isArray(ev.agent_names) ? (ev.agent_names as any[]).map(a => typeof a === 'string' ? a : (a && (a.name || a.role)) || '').join(',') : '';
        const task = 'task' in ev ? String(ev.task || '') : '';
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
      normalized.push(ev);
    });

    const groups: Array<{
      type: 'reasoning_group' | 'single';
      events: DisplayStreamEvent[];
      startIdx: number;
    }> = [];
    
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
  }, [events]);
  
  // Find active swarm for display
  const activeSwarm = Array.from(swarmStates.values()).find(s => 
    s.status === 'running' || s.status === 'initializing'
  ) || Array.from(swarmStates.values()).pop(); // Show last swarm if none active
  
  return (
    <Box flexDirection="column">
      {/* Display active swarm operation if any */}
      {activeSwarm && (
        <Box marginBottom={1}>
          <SwarmDisplay swarmState={activeSwarm} collapsed={false} />
        </Box>
      )}
      
      {displayGroups.map((group) => {
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
                <Text color="cyan">{combinedContent}</Text>
              </Box>
            </Box>
          );
        } else {
          // Display single events normally
          return group.events.map((event, idx) => (
            <MemoizedEventLine key={`${group.startIdx}-${idx}`} event={event} toolStates={toolStates} />
          ));
        }
      })}
    </Box>
  );
});