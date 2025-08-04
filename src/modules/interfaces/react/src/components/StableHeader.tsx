/**
 * Stable Header Component
 * 
 * A wrapper that prevents header duplication during re-renders
 * by using React.memo and careful prop comparison
 */

import React from 'react';
import { Box } from 'ink';
import { Header } from './Header.js';

interface StableHeaderProps {
  version: string;
  terminalWidth: number;
  nightly?: boolean;
}

// Use React.memo to prevent unnecessary re-renders
export const StableHeader = React.memo<StableHeaderProps>(({ 
  version, 
  terminalWidth, 
  nightly = false 
}) => {
  // Clear any residual output before rendering
  React.useEffect(() => {
    // Only clear on mount, not on every render
    if (process.stdout.isTTY) {
      process.stdout.write('\x1b[H'); // Move cursor to home position
    }
  }, []); // Empty deps = only on mount

  return (
    <Box flexDirection="column" width="100%">
      <Header 
        version={version} 
        terminalWidth={terminalWidth}
        nightly={nightly}
      />
    </Box>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function - only re-render if these specific props change
  return (
    prevProps.version === nextProps.version &&
    prevProps.terminalWidth === nextProps.terminalWidth &&
    prevProps.nightly === nextProps.nightly
  );
});

StableHeader.displayName = 'StableHeader';