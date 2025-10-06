/**
 * Professional Log Container Component
 * 
 * Provides a structured, scrollable log display with proper formatting,
 * status indicators, and overflow management.
 */

import React, { useRef, useEffect } from 'react';
import { Box, Text } from 'ink';
import stripAnsi from 'strip-ansi';
import { themeManager } from '../themes/theme-manager.js';
import { LogLevelIcon } from './icons.js';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'debug';
  message: string;
  details?: string;
}

interface LogContainerProps {
  logs: LogEntry[];
  maxHeight?: number;
  title?: string;
  showTimestamps?: boolean;
  autoScroll?: boolean;
  bordered?: boolean;
}

export const LogContainer: React.FC<LogContainerProps> = ({
  logs,
  maxHeight = 12,
  title = 'Logs',
  showTimestamps = true,
  autoScroll = true,
  bordered = true
}) => {
  const theme = themeManager.getCurrentTheme();
  
  // In React Ink, we don't have DOM scrolling - instead we show the latest logs
  // by slicing the array to show only the most recent entries
  // Calculate which logs to show based on maxHeight
  const visibleLogs = autoScroll ? logs.slice(-maxHeight) : logs.slice(0, maxHeight);
  
  return (
    <Box flexDirection="column" flexGrow={1}>
      {/* Title Bar */}
      {title && (
        <Box 
          borderStyle={bordered ? "single" : undefined}
          borderTop={bordered}
          borderLeft={bordered}
          borderRight={bordered}
          borderBottom={false}
          borderColor={theme.accent}
          paddingX={1}
        >
          <Text color={theme.accent} bold>▎{title}</Text>
          <Text color={theme.muted}> ({logs.length} entries)</Text>
        </Box>
      )}
      
      {/* Log Content */}
      <Box
        borderStyle={bordered ? "single" : undefined}
        borderTop={false}
        borderColor={theme.muted}
        paddingX={1}
        paddingY={bordered ? 1 : 0}
        height={maxHeight + (bordered ? 2 : 0)}
        flexDirection="column"
        overflow="hidden"
      >
        {logs.length === 0 ? (
          <Text color={theme.muted}>No logs yet...</Text>
        ) : (
          <>
            {visibleLogs.map((log) => (
              <LogEntry
                key={log.id}
                log={log}
                showTimestamp={showTimestamps}
              />
            ))}
          </>
        )}
        
        {/* Show overflow indicator if there are more logs */}
        {logs.length > maxHeight && (
          <Box marginTop={1}>
            <Text color={theme.muted} dimColor>
              ... {logs.length - maxHeight} more {autoScroll ? 'entries above' : 'entries below'}
            </Text>
          </Box>
        )}
      </Box>
    </Box>
  );
};

/**
 * Individual log entry component
 */
const LogEntry: React.FC<{ log: LogEntry; showTimestamp: boolean }> = ({ log, showTimestamp }) => {
  const theme = themeManager.getCurrentTheme();
  
  const levelColors = {
    info: theme.foreground,
    success: theme.success,
    warning: theme.warning,
    error: theme.danger,
    debug: theme.muted
  };
  
  return (
    <Box marginBottom={0} flexDirection="column">
      <Box>
        {showTimestamp && (
          <Text color={theme.muted}>[{log.timestamp}] </Text>
        )}
        <LogLevelIcon level={log.level} />
        <Text color={levelColors[log.level]}>{stripAnsi(log.message)}</Text>
      </Box>
      {log.details && (
        <Box marginLeft={showTimestamp ? 11 : 2}>
          <Text color={theme.muted} dimColor>{stripAnsi(log.details)}</Text>
        </Box>
      )}
    </Box>
  );
};

/**
 * Compact log display for space-constrained areas
 */
export const CompactLogDisplay: React.FC<{ 
  logs: LogEntry[]; 
  maxItems?: number;
  showIcon?: boolean;
}> = ({ logs, maxItems = 3, showIcon = true }) => {
  const theme = themeManager.getCurrentTheme();
  const recentLogs = logs.slice(-maxItems);
  
  return (
    <Box flexDirection="column">
      {recentLogs.map((log) => (
        <Box key={log.id}>
          {showIcon && <LogLevelIcon level={log.level} />}
          <Text 
            color={log.level === 'error' ? theme.danger : theme.foreground}
            wrap="truncate-end"
          >
            {log.message}
          </Text>
        </Box>
      ))}
    </Box>
  );
};