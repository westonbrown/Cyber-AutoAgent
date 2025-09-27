/**
 * Compact Header Component
 * 
 * Minimal design with responsive logo and branding
 */

import React from 'react';
import { Box, Text } from 'ink';
import Gradient from 'ink-gradient';
import { themeManager } from '../themes/theme-manager.js';

interface HeaderProps {
  version?: string;
  terminalWidth?: number;
  nightly?: boolean;
  exitNotice?: boolean;
}

// ASCII art logos for terminal display
const longAsciiLogo = `
 ██████╗██╗   ██╗██████╗ ███████╗██████╗      █████╗ ██╗   ██╗████████╗ ██████╗  █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗    ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝    ███████║██║   ██║   ██║   ██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗    ██╔══██║██║   ██║   ██║   ██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
╚██████╗   ██║   ██████╔╝███████╗██║  ██║    ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
 ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
`;

const compactLogo = `🔐 Cyber-AutoAgent`;
const ultraCompactLogo = `🔐 CAA`;

export const Header: React.FC<HeaderProps> = React.memo(({ 
  version = '0.1.3', 
  terminalWidth = 80,
  nightly = false,
  exitNotice = false
}) => {
  const theme = themeManager.getCurrentTheme();
  const useGradient = themeManager.shouldUseGradient();
  
  // Choose logo based on terminal width - standardized to use only full ASCII or compact text
  const logo = terminalWidth >= 90 ? longAsciiLogo : 
               terminalWidth >= 40 ? compactLogo : 
               ultraCompactLogo;
  
  const isAsciiArt = logo.includes('\n');
  
  return (
    <Box
      alignItems="flex-start"
      flexShrink={0}
      flexDirection="column"
      flexGrow={1}
    >
      {/* Logo - ASCII art or text */}
      {isAsciiArt ? (
        <Box key="ascii-logo">
          {useGradient && theme.gradientColors ? (
            <Gradient colors={theme.gradientColors}>
              <Text>{logo}</Text>
            </Gradient>
          ) : (
            <Text color={theme.primary}>{logo}</Text>
          )}
        </Box>
      ) : (
        <Box
          key="compact-logo"
          flexDirection="row"
          justifyContent="space-between"
          flexGrow={1}
          marginBottom={1}
        >
          <Box key="logo-text">
            {useGradient && theme.gradientColors ? (
              <Gradient colors={theme.gradientColors}>
                <Text>{logo}</Text>
              </Gradient>
            ) : (
              <Text color={theme.primary}>{logo}</Text>
            )}
          </Box>
          
          {/* Version and status for compact mode */}
          <Box key="compact-version">
            <Text color={theme.muted}>v{version}</Text>
            {nightly && (
              <Text color={theme.warning}> | NIGHTLY</Text>
            )}
            <Text color={theme.muted}> | Full Spectrum Cyber Operations</Text>
          </Box>
        </Box>
      )}
      
      {/* Version and subtitle for ASCII art mode */}
      {isAsciiArt && (
        <Box key="ascii-subtitle" flexDirection="row" justifyContent="flex-start" flexGrow={1}>
          <Text color={theme.muted}>Full Spectrum Cyber Operations v{version}</Text>
          {nightly && (
            <Text color={theme.warning}> | NIGHTLY</Text>
          )}
        </Box>
      )}
      
      {/* Optional exit notice under the header */}
      {exitNotice && (
        <Box key="exit-notice" flexGrow={1}>
          <Text color={theme.danger}>🔴 ESC — Exiting Cyber-AutoAgent</Text>
        </Box>
      )}

      {/* Add spacing after header */}
      <Box key="header-spacing" marginBottom={1} />
    </Box>
  );
});

Header.displayName = 'Header';