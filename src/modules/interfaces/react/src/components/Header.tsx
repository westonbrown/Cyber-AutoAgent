/**
 * Compact Header Component
 * Minimal Gemini CLI-inspired design with responsive logo
 */

import React from 'react';
import { Box, Text } from 'ink';
import Gradient from 'ink-gradient';
import { themeManager } from '../themes/theme-manager.js';

interface HeaderProps {
  version?: string;
  terminalWidth?: number;
  nightly?: boolean;
}

// ASCII art logos inspired by Gemini CLI
const longAsciiLogo = `
 ██████╗██╗   ██╗██████╗ ███████╗██████╗      █████╗ ██╗   ██╗████████╗ ██████╗  █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗    ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝    ███████║██║   ██║   ██║   ██║   ██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗    ██╔══██║██║   ██║   ██║   ██║   ██║██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
╚██████╗   ██║   ██████╔╝███████╗██║  ██║    ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
 ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
`;

const shortAsciiLogo = `
  ╔═╗╦ ╦╔╗ ╔═╗╦═╗   ╔═╗╦ ╦╔╦╗╔═╗
  ║  ╚╦╝╠╩╗║╣ ╠╦╝───╠═╣║ ║ ║ ║ ║
  ╚═╝ ╩ ╚═╝╚═╝╩╚═   ╩ ╩╚═╝ ╩ ╚═╝
`;

const compactLogo = `🔐 Cyber-AutoAgent`;
const ultraCompactLogo = `🔐 CAA`;

export const Header: React.FC<HeaderProps> = ({ 
  version = '0.1.3', 
  terminalWidth = 80,
  nightly = false
}) => {
  const theme = themeManager.getCurrentTheme();
  const useGradient = themeManager.shouldUseGradient();
  
  // Choose logo based on terminal width
  const logo = terminalWidth >= 90 ? longAsciiLogo : 
               terminalWidth >= 60 ? shortAsciiLogo :
               terminalWidth >= 40 ? compactLogo : 
               ultraCompactLogo;
  
  const isAsciiArt = logo.includes('\n');
  
  return (
    <Box
      alignItems="flex-start"
      flexShrink={0}
      flexDirection="column"
      width="100%"
    >
      {/* Logo - ASCII art or text */}
      {isAsciiArt ? (
        <Box>
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
          flexDirection="row"
          justifyContent="space-between"
          width="100%"
          marginBottom={1}
        >
          <Box>
            {useGradient && theme.gradientColors ? (
              <Gradient colors={theme.gradientColors}>
                <Text>{logo}</Text>
              </Gradient>
            ) : (
              <Text color={theme.primary}>{logo}</Text>
            )}
          </Box>
          
          {/* Version and status for compact mode */}
          <Box>
            <Text color={theme.muted}>v{version}</Text>
            {nightly && (
              <Text color={theme.warning}> • NIGHTLY</Text>
            )}
            <Text color={theme.muted}> • Full Spectrum Cyber Operations</Text>
          </Box>
        </Box>
      )}
      
      {/* Version and subtitle for ASCII art mode */}
      {isAsciiArt && (
        <Box width="100%" flexDirection="row" justifyContent="flex-start">
          <Text color={theme.muted}>Full Spectrum Cyber Operations v{version}</Text>
          {nightly && (
            <Text color={theme.warning}> • NIGHTLY</Text>
          )}
        </Box>
      )}
      
      {/* Add spacing after header */}
      <Box marginBottom={1} />
    </Box>
  );
};