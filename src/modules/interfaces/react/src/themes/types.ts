/**
 * Professional Theme System for Cyber-AutoAgent
 * Based on Gemini CLI's color palette for consistency
 */

export interface CyberTheme {
  type: 'dark' | 'light' | 'ansi' | 'custom';
  name: string;
  background: string;
  foreground: string;
  primary: string;      // Cyber blue/green
  secondary: string;    // Purple accent
  accent: string;       // Accent color (similar to primary)
  subtle: string;       // Very muted text
  success: string;      // Operation success green
  danger: string;       // Alert red
  info: string;         // Info cyan
  warning: string;      // Warning yellow
  muted: string;        // Gray for secondary text
  comment: string;      // For logs/comments
  selection: string;    // Background for selected items
  gradientColors?: string[];  // For ASCII art gradients
}

export interface ThemeConfig {
  theme: CyberTheme;
  enableGradients: boolean;
  enableAnimations: boolean;
  terminalWidth: number;
}