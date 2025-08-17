/**
 * SwarmDisplay - Display for multi-agent swarm operations
 * Shows detailed information about sub-agents, their tasks, tools, and collaboration
 */

import React, { useState, useEffect } from 'react';
import { Box, Text } from 'ink';
import { themeManager } from '../themes/theme-manager.js';
import { formatDuration } from '../utils/toolFormatters.js';

export interface SwarmAgent {
  id: string;
  name: string;
  role?: string;
  task?: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  tools?: string[];
  model_id?: string;
  model_provider?: string;
  temperature?: number;
  toolCalls?: Array<{
    tool: string;
    input?: any;
    output?: any;
    timestamp?: number;
  }>;
  messages?: string[];
  result?: string;
  startTime?: number;
  endTime?: number;
  currentStep?: number;
  maxSteps?: number;
  tokensUsed?: number;
}

export interface SwarmState {
  id: string;
  task: string;
  status: 'initializing' | 'running' | 'completed' | 'failed';
  agents: SwarmAgent[];
  collaborationChain?: string[];
  startTime: number;
  endTime?: number;
  totalTokens?: number;
  result?: string;
  currentAgent?: string;
  totalHandoffs?: number;
  completedAgents?: string[];
  failedAgents?: string[];
  maxHandoffs?: number;
  maxIterations?: number;
}

interface SwarmDisplayProps {
  swarmState: SwarmState;
  collapsed?: boolean;
}

export const SwarmDisplay: React.FC<SwarmDisplayProps> = ({ swarmState, collapsed = false }) => {
  const theme = themeManager.getCurrentTheme();
  const [elapsedTime, setElapsedTime] = useState(0);
  const [expanded, setExpanded] = useState(true); // Start expanded to show details

  // Update elapsed time every second while running
  useEffect(() => {
    if (swarmState.status === 'running') {
      const interval = setInterval(() => {
        setElapsedTime(Date.now() - swarmState.startTime);
      }, 1000);
      return () => clearInterval(interval);
    } else if (swarmState.endTime) {
      setElapsedTime(swarmState.endTime - swarmState.startTime);
    }
  }, [swarmState.status, swarmState.startTime, swarmState.endTime]);


  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
      case 'running':
        return '[ACTIVE]';
      case 'completed':
        return '[DONE]';
      case 'failed':
        return '[FAIL]';
      case 'pending':
      case 'initializing':
        return '';
      default:
        return '';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'running':
        return theme.warning;
      case 'completed':
        return theme.success;
      case 'failed':
        return theme.danger;
      default:
        return theme.muted;
    }
  };

  if (collapsed) {
    // Collapsed view - clickable summary with more details
    const activeAgents = swarmState.agents.filter(a => a.status === 'active').length;
    const completedAgents = swarmState.agents.filter(a => a.status === 'completed').length;
    
    return (
      <Box flexDirection="column">
        <Box>
          <Text color={theme.primary} bold>[SWARM] </Text>
          <Text color={theme.info}>{swarmState.agents.length} agents</Text>
          <Text color={theme.muted}> | </Text>
          <Text color={theme.warning}>{String(activeAgents)} active</Text>
          <Text color={theme.muted}> | </Text>
          <Text color={theme.success}>{String(completedAgents)} completed</Text>
          <Text color={theme.muted}> | </Text>
          <Text color={theme.info}>{formatDuration(elapsedTime, true)}</Text>
        </Box>
        <Box marginLeft={2} marginTop={1}>
          <Text color={theme.muted}>Task: </Text>
          <Text>{swarmState.task}</Text>
        </Box>
        {swarmState.agents.length > 0 && (
          <Box flexDirection="column" marginLeft={2} marginTop={1}>
            <Text color={theme.accent} dimColor>Agents:</Text>
            {swarmState.agents.map((agent, i) => (
              <Box key={agent.id}>
                <Text color={getStatusColor(agent.status)}>
                  {getStatusIcon(agent.status)}
                </Text>
                <Text color={theme.foreground}> {agent.name}</Text>
                {agent.role && (
                  <Text color={theme.muted}> - {agent.role}</Text>
                )}
                {agent.currentStep && agent.maxSteps && (
                  <Text color={theme.info}> [{agent.currentStep}/{agent.maxSteps}]</Text>
                )}
                {agent.tools && agent.tools.length > 0 && (
                  <Text color={theme.muted}> ({agent.tools.join(', ')})</Text>
                )}
              </Box>
            ))}
          </Box>
        )}
      </Box>
    );
  }

  // Full view - detailed agent information
  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Task description - no header needed */}
      <Box marginBottom={1}>
        <Text color={theme.accent} bold>Task: </Text>
        <Text>{swarmState.task}</Text>
      </Box>

      {/* Timing and metrics */}
      <Box marginLeft={2} marginBottom={1}>
        {elapsedTime > 0 && (
          <>
            <Text color={theme.muted}>Duration: </Text>
            <Text color={theme.info}>{formatDuration(elapsedTime, true)}</Text>
          </>
        )}
        {swarmState.maxIterations && (
          <>
            <Text color={theme.muted}>{elapsedTime > 0 ? ' | ' : ''}Max iterations: </Text>
            <Text color={theme.info}>{swarmState.maxIterations}</Text>
          </>
        )}
        {swarmState.maxHandoffs && (
          <>
            <Text color={theme.muted}> | Max handoffs: </Text>
            <Text color={theme.info}>{swarmState.maxHandoffs}</Text>
          </>
        )}
        {swarmState.totalTokens !== undefined && swarmState.totalTokens > 0 && (
          <>
            <Text color={theme.muted}> | Tokens: </Text>
            <Text color={theme.info}>{swarmState.totalTokens}</Text>
          </>
        )}
      </Box>

      {/* Agent details */}
      <Box flexDirection="column" marginLeft={2}>
        <Text color={theme.accent} bold>Agents ({swarmState.agents.length}):</Text>
        
        {swarmState.agents.map((agent, index) => (
          <Box key={agent.id} flexDirection="column" marginLeft={2} {...(index > 0 ? { marginTop: 1 } : {})}>
            {/* Agent header */}
            <Box>
              <Text color={getStatusColor(agent.status)}>
                {getStatusIcon(agent.status)} 
              </Text>
              <Text color={theme.foreground} bold> {agent.name}</Text>
            </Box>

            {/* Agent full role/system prompt */}
            {agent.role && (
              <Box marginLeft={3} marginRight={2}>
                <Text color={theme.muted} wrap="wrap">{agent.role}</Text>
              </Box>
            )}

            {/* Model and Tools */}
            <Box marginLeft={3}>
              {agent.model_id && (
                <Text color={theme.muted}>
                  Model: <Text color={theme.accent}>{agent.model_id.split('/').pop()?.split(':')[0] || agent.model_id}</Text>
                  {agent.temperature !== undefined && (
                    <Text color={theme.muted}> (temp: {agent.temperature})</Text>
                  )}
                </Text>
              )}
            </Box>
            {agent.tools && agent.tools.length > 0 && (
              <Box marginLeft={3}>
                <Text color={theme.muted}>Tools: </Text>
                <Text color={theme.info}>[{agent.tools.join(', ')}]</Text>
              </Box>
            )}

            {/* Recent tool calls */}
            {agent.toolCalls && agent.toolCalls.length > 0 && (
              <Box flexDirection="column" marginLeft={3}>
                {agent.toolCalls.slice(-3).map((call, i) => (
                  <Box key={i}>
                    <Text color={theme.success}>{'> '}{call.tool}</Text>
                    {call.input && (
                      <Text color={theme.muted}> {JSON.stringify(call.input).slice(0, 50)}...</Text>
                    )}
                  </Box>
                ))}
              </Box>
            )}

            {/* Agent result */}
            {agent.result && (
              <Box marginLeft={3}>
                <Text color={theme.success}>{'> '}</Text>
                <Text>{agent.result.slice(0, 100)}{agent.result.length > 100 ? '...' : ''}</Text>
              </Box>
            )}
          </Box>
        ))}
      </Box>

      {/* Collaboration chain */}
      {swarmState.collaborationChain && swarmState.collaborationChain.length > 0 && (
        <Box flexDirection="column" marginTop={1} marginLeft={2}>
          <Text color={theme.accent} bold>Collaboration Flow:</Text>
          <Box marginLeft={2}>
            <Text color={theme.info}>
              {swarmState.collaborationChain.join(' > ')}
            </Text>
          </Box>
        </Box>
      )}

      {/* Final result */}
      {swarmState.result && (
        <Box flexDirection="column" marginTop={1} marginLeft={2}>
          <Text color={theme.accent} bold>Result:</Text>
          <Box marginLeft={2}>
            <Text color={theme.success}>{swarmState.result}</Text>
          </Box>
        </Box>
      )}
    </Box>
  );
};