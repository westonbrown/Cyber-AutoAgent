/**
 * SessionControls - Session lifecycle management UI
 *
 * Provides controls for reset, archive, and session info display
 */

import React from 'react';
import { Box, Text } from 'ink';
import { formatDuration } from '../utils/streamFormatters.js';

export interface SessionControlsProps {
  /** Current session ID */
  sessionId: string;
  /** Operation ID if available */
  operationId?: string;
  /** Target being assessed */
  target?: string;
  /** Session start time */
  startTime?: Date;
  /** Current event count */
  eventCount?: number;
  /** Whether session is active */
  isActive?: boolean;
  /** Callback for reset action */
  onReset?: () => void;
  /** Callback for archive action */
  onArchive?: () => void;
  /** Whether to show detailed info */
  showInfo?: boolean;
}

/**
 * Calculate elapsed time from start
 */
function getElapsedTime(startTime?: Date): string {
  if (!startTime) return 'N/A';
  const elapsed = Date.now() - startTime.getTime();
  return formatDuration(elapsed);
}

/**
 * Session info panel
 */
export const SessionInfo: React.FC<{
  sessionId: string;
  operationId?: string;
  target?: string;
  elapsed: string;
  eventCount?: number;
  isActive?: boolean;
}> = ({ sessionId, operationId, target, elapsed, eventCount, isActive }) => {
  return (
    <Box flexDirection="column" borderStyle="round" borderColor="cyan" paddingX={1}>
      <Text bold color="cyan">
        📋 Session Info
      </Text>

      <Box paddingLeft={2} flexDirection="column">
        {operationId && (
          <Box>
            <Text dimColor>Operation: </Text>
            <Text>{operationId.slice(0, 12)}...</Text>
          </Box>
        )}

        {target && (
          <Box>
            <Text dimColor>Target: </Text>
            <Text>{target}</Text>
          </Box>
        )}

        <Box>
          <Text dimColor>Session: </Text>
          <Text>{sessionId.slice(0, 8)}...</Text>
        </Box>

        <Box>
          <Text dimColor>Elapsed: </Text>
          <Text>{elapsed}</Text>
        </Box>

        {eventCount !== undefined && (
          <Box>
            <Text dimColor>Events: </Text>
            <Text>{eventCount}</Text>
          </Box>
        )}

        <Box>
          <Text dimColor>Status: </Text>
          <Text color={isActive ? 'green' : 'gray'}>{isActive ? 'Active' : 'Idle'}</Text>
        </Box>
      </Box>
    </Box>
  );
};

/**
 * Session action buttons
 */
export const SessionActions: React.FC<{
  onReset?: () => void;
  onArchive?: () => void;
  isActive?: boolean;
}> = ({ onReset, onArchive, isActive }) => {
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text dimColor italic>
        Session Actions:
      </Text>
      <Box paddingLeft={2} flexDirection="column">
        {onReset && (
          <Box>
            <Text dimColor>• </Text>
            <Text color="yellow">Ctrl+R</Text>
            <Text> - Reset session (clear UI state)</Text>
          </Box>
        )}
        {onArchive && !isActive && (
          <Box>
            <Text dimColor>• </Text>
            <Text color="yellow">Ctrl+A</Text>
            <Text> - Archive session (save transcript)</Text>
          </Box>
        )}
        <Box>
          <Text dimColor>• </Text>
          <Text color="yellow">Ctrl+I</Text>
          <Text> - Toggle session info</Text>
        </Box>
      </Box>
    </Box>
  );
};

/**
 * Main SessionControls component
 */
export const SessionControls: React.FC<SessionControlsProps> = ({
  sessionId,
  operationId,
  target,
  startTime,
  eventCount,
  isActive = false,
  onReset,
  onArchive,
  showInfo = false
}) => {
  const elapsed = getElapsedTime(startTime);

  if (!showInfo) {
    // Compact mode - just show basic status
    return (
      <Box>
        <Text dimColor>
          Session: {sessionId.slice(0, 8)}... • {elapsed} • {eventCount || 0} events •{' '}
        </Text>
        <Text color={isActive ? 'green' : 'gray'}>{isActive ? 'Active' : 'Idle'}</Text>
        <Text dimColor> (Ctrl+I for info)</Text>
      </Box>
    );
  }

  // Expanded mode - show full info and actions
  return (
    <Box flexDirection="column">
      <SessionInfo
        sessionId={sessionId}
        operationId={operationId}
        target={target}
        elapsed={elapsed}
        eventCount={eventCount}
        isActive={isActive}
      />
      <SessionActions onReset={onReset} onArchive={onArchive} isActive={isActive} />
    </Box>
  );
};

/**
 * Archive confirmation banner
 */
export const ArchiveConfirmation: React.FC<{
  sessionId: string;
  archivePath: string;
}> = ({ sessionId, archivePath }) => {
  return (
    <Box borderStyle="round" borderColor="green" paddingX={1}>
      <Text bold color="green">
        ✓ Session Archived
      </Text>
      <Text> - {sessionId.slice(0, 8)}...</Text>
      <Text dimColor> saved to {archivePath}</Text>
    </Box>
  );
};

/**
 * Reset confirmation banner
 */
export const ResetConfirmation: React.FC = () => {
  return (
    <Box borderStyle="round" borderColor="yellow" paddingX={1}>
      <Text bold color="yellow">
        ⟲ Session Reset
      </Text>
      <Text> - UI state cleared, ready for new operation</Text>
    </Box>
  );
};
