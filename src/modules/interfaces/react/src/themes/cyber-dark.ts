/**
 * Cyber Dark Theme - Default theme for Cyber-AutoAgent
 * 
 * Dark theme with blue and cyan color accents for terminal consistency.
 */

import { CyberTheme } from './types.js';

export const CyberDarkTheme: CyberTheme = {
  type: 'dark',
  name: 'Cyber Dark',
  background: '#1E1E2E',     // Dark background
  foreground: '#CDD6F4',     // Light foreground
  primary: '#89B4FA',        // Blue accent
  secondary: '#CBA6F7',      // Purple accent
  accent: '#89B4FA',         // Same as primary
  subtle: '#45475A',         // Even more muted than muted
  success: '#A6E3A1',        // Green accent
  danger: '#F38BA8',         // Red accent
  info: '#89DCEB',           // Cyan accent
  warning: '#F9E2AF',        // Yellow accent
  muted: '#6C7086',          // Gray/Comment
  comment: '#6C7086',        // Comment color
  selection: '#313244',      // Slightly lighter than background for selection
  gradientColors: ['#4796E4', '#847ACE', '#C3677F']  // Gradient colors
};