/**
 * Cyber Dark Theme - Default theme for Cyber-AutoAgent
 * 
 * Dark theme with blue and cyan color accents for terminal consistency.
 */

import { CyberTheme } from './types.js';

export const CyberDarkTheme: CyberTheme = {
  type: 'dark',
  name: 'Cyber Dark',
  background: '#1E1E2E',     // Gemini dark background
  foreground: '#CDD6F4',     // Gemini foreground
  primary: '#89B4FA',        // Gemini AccentBlue
  secondary: '#CBA6F7',      // Gemini AccentPurple
  accent: '#89B4FA',         // Same as primary
  subtle: '#45475A',         // Even more muted than muted
  success: '#A6E3A1',        // Gemini AccentGreen
  danger: '#F38BA8',         // Gemini AccentRed
  info: '#89DCEB',           // Gemini AccentCyan
  warning: '#F9E2AF',        // Gemini AccentYellow
  muted: '#6C7086',          // Gemini Gray/Comment
  comment: '#6C7086',        // Gemini Comment
  selection: '#313244',      // Slightly lighter than background for selection
  gradientColors: ['#4796E4', '#847ACE', '#C3677F']  // Gemini gradient
};