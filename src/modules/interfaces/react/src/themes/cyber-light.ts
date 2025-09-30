/**
 * Cyber Light Theme - Light theme for Cyber-AutoAgent
 *
 * Light theme with darker colors for better visibility on light terminals.
 * Optimized for terminals with white/light backgrounds.
 */

import { CyberTheme } from './types.js';

export const CyberLightTheme: CyberTheme = {
  type: 'light',
  name: 'Cyber Light',
  background: '#FFFFFF',     // White background
  foreground: '#1E1E1E',     // Dark foreground for readability
  primary: '#0066CC',        // Darker blue accent (visible on light)
  secondary: '#7B3FF2',      // Darker purple accent
  accent: '#0066CC',         // Same as primary
  subtle: '#6C6C6C',         // Medium gray
  success: '#00AA00',        // Dark green (visible on light)
  danger: '#CC0000',         // Dark red
  info: '#0088AA',           // Dark cyan
  warning: '#CC6600',        // Dark orange/yellow
  muted: '#666666',          // Dark gray for secondary text
  comment: '#666666',        // Comment color
  selection: '#E6E6E6',      // Light gray for selection
  gradientColors: ['#0066CC', '#7B3FF2', '#CC0066']  // Darker gradient colors
};