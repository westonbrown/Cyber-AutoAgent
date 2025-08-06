/**
 * StreamDisplay - SDK-Enhanced event streaming for cyber operations
 * Designed for infinite scroll with SDK native events and backward compatibility
 */

import React from 'react';
import { Box, Text } from 'ink';
import { ThinkingIndicator } from './ThinkingIndicator.js';
import { StreamEvent } from '../types/events.js';
import { SwarmDisplay, SwarmState, SwarmAgent } from './SwarmDisplay.js';

// Legacy simplified event types for backward compatibility
export type LegacyStreamEvent = 
  | { type: 'step_header'; step: number; maxSteps: number; operation: string; duration: string; [key: string]: any }
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
  | { type: 'content_block_delta'; delta?: string; isReasoning?: boolean; [key: string]: any };

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

const DIVIDER = '─'.repeat(process.stdout.columns || 80);

const EventLine: React.FC<{ event: DisplayStreamEvent }> = React.memo(({ event }) => {
  switch (event.type) {
    // =======================================================================
    // SDK NATIVE EVENT HANDLERS - Enhanced with SDK context
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
      return (
        <>
          <Text color="green" bold>tool: {'toolName' in event ? event.toolName : 'unknown'}</Text>
          {'toolInput' in event && event.toolInput && (
            <Text dimColor>{JSON.stringify(event.toolInput, null, 2)}</Text>
          )}
          <Text> </Text>
        </>
      );
      
    case 'tool_invocation_end':
      return (
        <>
          <Text color="green">tool completed</Text>
          {'duration' in event && event.duration && (
            <Text dimColor>Duration: {event.duration}ms</Text>
          )}
          {'success' in event && event.success === false && (
            <Text color="red">Tool execution failed</Text>
          )}
          <Text> </Text>
        </>
      );
      
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
      if ('usage' in event && event.usage) {
        const usage = event.usage as any;
        const cost = ('cost' in event ? event.cost : null) as any;
        return (
          <>
            <Text color="yellow" dimColor>
              Tokens: {usage.inputTokens} in / {usage.outputTokens} out
              {cost && (
                ` | Cost: $${cost.totalCost?.toFixed(4) || '0.0000'}`
              )}
            </Text>
            <Text> </Text>
          </>
        );
      }
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
        const agentName = event.swarm_agent.toUpperCase();
        agentInfo = ` • [SUB-AGENT: ${agentName}]`;
      } else if (event.swarm_context) {
        // If we have swarm context but no specific agent, show operation type
        agentInfo = ` • [SUB-AGENT: ${event.swarm_context}]`;
      } else if (event.is_swarm_operation) { 
        // Show swarm operation indicator
        agentInfo = ' • [SWARM OPERATION]';
      }
      
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text bold color="blue">
            [STEP {event.step}/{event.maxSteps}]{agentInfo} {DIVIDER.slice(0, Math.max(0, DIVIDER.length - 30))}
          </Text>
          <Text> </Text>
        </Box>
      );
      
    case 'thinking':
      return (
        <Box marginY={0}>
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
      // Format tool input based on tool type - professional display without emojis
      let inputDisplay = '';
      
      switch (event.tool_name) {
        case 'mem0_memory':
          const action = event.tool_input.action || 'unknown';
          if (action === 'unknown') {
            // Don't show confusing unknown action, metadata event will provide clean info
            inputDisplay = '';
          } else {
            const content = event.tool_input.content || event.tool_input.query || '';
            const preview = content.length > 60 ? content.substring(0, 60) + '...' : content;
            const actionDisplay = action === 'store' ? 'storing memory' : action === 'retrieve' ? 'retrieving memory' : action;
            const labelDisplay = action === 'store' ? 'preview' : 'query';
            inputDisplay = preview ? `${actionDisplay} | ${labelDisplay}: ${preview}` : actionDisplay;
          }
          break;
          
        case 'shell':
          // For shell, extract commands and try to identify the agent context
          const commands = event.tool_input.command || event.tool_input.commands || 
                          event.tool_input.cmd || event.tool_input.input || '';
          
          // Don't hardcode agent names - they come from swarm tool output
          inputDisplay = `Commands: ${commands}`;
          break;
          
        case 'http_request':
          const method = event.tool_input.method || 'GET';
          const url = event.tool_input.url || '';
          inputDisplay = `method: ${method} | url: ${url}`;
          break;
          
        case 'file_write':
          const filePath = event.tool_input.path || 'unknown';
          const fileContent = event.tool_input.content || '';
          const contentInfo = fileContent ? ` | ${fileContent.length} chars` : '';
          inputDisplay = `path: ${filePath}${contentInfo}`;
          break;
          
        case 'editor':
          const editorCmd = event.tool_input.command || 'edit';
          const editorPath = event.tool_input.path || '';
          const editorContent = event.tool_input.content || '';
          const editorInfo = editorContent ? ` | ${editorContent.length} chars` : '';
          inputDisplay = `${editorCmd}: ${editorPath}${editorInfo}`;
          break;
          
        case 'swarm':
          // Show expanded swarm details instead of truncated preview
          const agents = event.tool_input.agents || event.tool_input.num_agents || 0;
          const task = event.tool_input.task || event.tool_input.objective || '';
          const taskDisplay = task.length > 200 ? task.substring(0, 200) + '...' : task;
          
          return (
            <Box flexDirection="column">
              <Text color="green" bold>[SWARM] Multi-Agent Operation</Text>
              <Box marginLeft={2}>
                <Text color="blue" bold>Agents: </Text>
                <Text color="blue">{agents}</Text>
              </Box>
              <Box marginLeft={2} flexDirection="column">
                <Text color="yellow" bold>Mission:</Text>
                <Text color="white">{taskDisplay}</Text>
              </Box>
            </Box>
          );
          
        case 'python_repl':
          const code = event.tool_input.code || '';
          const codeLines = code.split('\n');
          
          // Show more lines for better context (8 lines instead of 3)
          const previewLines = 8;
          let codePreview;
          
          if (codeLines.length <= previewLines) {
            // Show all code if it's short enough
            codePreview = code;
          } else {
            // Show first lines with smart truncation
            const truncatedLines = codeLines.slice(0, previewLines);
            codePreview = truncatedLines.join('\n') + '\n...';
          }
          
          inputDisplay = `code:\n${codePreview}`;
          break;
          
        case 'report_generator':
          const target = event.tool_input.target || 'unknown';
          const reportType = event.tool_input.report_type || event.tool_input.type || 'general';
          inputDisplay = `target: ${target} | type: ${reportType}`;
          break;
          
        case 'handoff_to_user':
          // Message will be shown in the special user handoff display
          break;
          
        case 'handoff_to_agent':
          const toAgent = event.tool_input.agent || event.tool_input.target_agent || 'unknown';
          const handoffMsg = event.tool_input.message || '';
          const msgPreview = handoffMsg.length > 80 ? handoffMsg.substring(0, 80) + '...' : handoffMsg;
          inputDisplay = `target: ${toAgent} | message: ${msgPreview}`;
          break;
          
        case 'load_tool':
          const toolName = event.tool_input.tool_name || event.tool_input.tool || 'unknown';
          const toolPath = event.tool_input.path || '';
          const toolDescription = event.tool_input.description || '';
          const pathInfo = toolPath ? ` | path: ${toolPath}` : '';
          const descInfo = toolDescription ? ` | ${toolDescription}` : '';
          inputDisplay = `loading: ${toolName}${pathInfo}${descInfo}`;
          break;
          
        case 'stop':
          inputDisplay = event.tool_input.reason || 'Manual stop requested';
          break;
          
        default:
          // For unknown tools, show key parameters in clean format
          if (event.tool_input && typeof event.tool_input === 'object') {
            const keys = Object.keys(event.tool_input);
            if (keys.length === 0) {
              inputDisplay = '';
            } else if (keys.length <= 4) {
              // Show key-value pairs for small objects
              inputDisplay = keys.map(k => {
                const value = event.tool_input[k];
                const displayValue = typeof value === 'string' && value.length > 50 
                  ? value.substring(0, 50) + '...' 
                  : String(value);
                return `${k}: ${displayValue}`;
              }).join(' | ');
            } else {
              // For larger objects, show key summary
              const importantKeys = keys.slice(0, 3);
              const remainingCount = keys.length - 3;
              inputDisplay = `${importantKeys.join(', ')}${remainingCount > 0 ? ` (+${remainingCount} more)` : ''}`;
            }
          }
      }
      
      // NO dividers before tools - they come after step headers
      if (event.tool_name !== 'shell') {
        return (
          <Box flexDirection="column">
            <Text color="green" bold>tool: {event.tool_name}</Text>
            {inputDisplay && <Text dimColor>{inputDisplay}</Text>}
          </Box>
        );
      } else {
        // For shell, don't hardcode agent names - they come from swarm output
        return (
          <Box flexDirection="column">
            <Text color="green" bold>tool: shell</Text>
          </Box>
        );
      }
      
    case 'command':
      return (
        <Box flexDirection="column">
          <Text><Text dimColor>⎿</Text> {event.content}</Text>
        </Box>
      );
      
    case 'output':
      // Skip empty output events completely
      if (!event.content || event.content.trim() === '') {
        return null;
      }
      
      const metadata = [];
      if (event.exitCode !== undefined) metadata.push(`exit: ${event.exitCode}`);
      if (event.duration) metadata.push(`duration: ${event.duration}`);
      
      // For startup/system messages, display cleanly without "output" prefix
      if (event.content && (
        event.content.includes('▶') || 
        event.content.includes('◆') || 
        event.content.includes('✓') ||
        event.content.includes('○')
      )) {
        return (
          <Text color="blue">{event.content}</Text>
        );
      }
      
      // For command output, show with metadata
      return (
        <Box flexDirection="column">
          <Text> </Text>
          <Text> </Text>
          <Text color="yellow" bold>
            output {metadata.length > 0 && <Text dimColor>({metadata.join(', ')})</Text>}
          </Text>
          <Text dimColor>{event.content}</Text>
          <Text> </Text>
        </Box>
      );
      
    case 'error':
      return (
        <>
          <Text color="red" bold>error</Text>
          <Text color="red">{event.content}</Text>
          <Text> </Text>
        </>
      );
      
    case 'metadata':
      if ('content' in event && typeof event.content === 'object') {
        const entries = Object.entries(event.content);
        // Check if this is memory operation metadata for better styling
        const isMemoryOperation = entries.some(([key]) => key === 'action' && 
          (event.content as any).action?.includes('memory'));
        
        return (
          <>
            <Text color={isMemoryOperation ? "cyan" : "gray"} dimColor={!isMemoryOperation}>
              {entries.map(([key, value]) => `${key}: ${value}`).join(' | ')}
            </Text>
            <Text> </Text>
          </>
        );
      }
      return null;
      
    case 'divider':
      return (
        <>
          <Text dimColor>{DIVIDER}</Text>
          <Text> </Text>
        </>
      );
      
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
  
  // Group consecutive reasoning events to prevent multiple labels
  const displayGroups = React.useMemo(() => {
    const groups: Array<{
      type: 'reasoning_group' | 'single';
      events: DisplayStreamEvent[];
      startIdx: number;
    }> = [];
    
    let currentReasoningGroup: DisplayStreamEvent[] = [];
    let groupStartIdx = 0;
    let activeThinking = false;
    let lastThinkingIdx = -1;
    
    events.forEach((event, idx) => {
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
            <Box key={`reasoning-group-${group.startIdx}`} flexDirection="column">
              <Text> </Text>
              <Text> </Text>
              <Text color="cyan" bold>reasoning</Text>
              <Box paddingLeft={0}>
                <Text color="cyan">{combinedContent}</Text>
              </Box>
              <Text> </Text>
            </Box>
          );
        } else {
          // Display single events normally
          return group.events.map((event, idx) => (
            <MemoizedEventLine key={`${group.startIdx}-${idx}`} event={event} />
          ));
        }
      })}
    </Box>
  );
});