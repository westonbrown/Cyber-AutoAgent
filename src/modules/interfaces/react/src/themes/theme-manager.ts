/**
 * Theme Management System
 * Handles theme loading, switching, and persistence
 * Automatically detects terminal background and selects appropriate theme
 */

import { CyberTheme, ThemeConfig } from './types.js';
import { NeonGridDark } from './neon-grid-dark.js';
import { NeonGridLight } from './neon-grid-light.js';
import { getRecommendedThemeType, supportsRichColors } from './terminal-detector.js';

class ThemeManager {
  private currentTheme: CyberTheme;
  private config: ThemeConfig;
  private darkTheme: CyberTheme = NeonGridDark;
  private lightTheme: CyberTheme = NeonGridLight;

  constructor() {
    // Auto-detect terminal background and select appropriate theme
    const recommendedType = getRecommendedThemeType();
    this.currentTheme = recommendedType === 'light' ? this.lightTheme : this.darkTheme;

    const supportsColors = supportsRichColors();

    this.config = {
      theme: this.currentTheme,
      enableGradients: true, // Always enable gradients for Neon Grid theme
      enableAnimations: true,
      terminalWidth: process.stdout.columns || 80
    };
  }

  getCurrentTheme(): CyberTheme {
    return this.currentTheme;
  }

  getConfig(): ThemeConfig {
    return this.config;
  }

  setTheme(theme: CyberTheme): void {
    this.currentTheme = theme;
    this.config.theme = theme;
  }

  updateTerminalWidth(width: number): void {
    this.config.terminalWidth = width;
  }

  shouldUseGradient(): boolean {
    return this.config.enableGradients && !!this.currentTheme.gradientColors;
  }

  getLogoSize(): 'short' | 'long' {
    return this.config.terminalWidth >= 80 ? 'long' : 'short';
  }

  /**
   * Check if current theme is dark
   */
  isDarkTheme(): boolean {
    return this.currentTheme.type === 'dark';
  }

  /**
   * Check if current theme is light
   */
  isLightTheme(): boolean {
    return this.currentTheme.type === 'light';
  }

  /**
   * Switch between light and dark themes
   */
  toggleTheme(): void {
    if (this.isDarkTheme()) {
      this.setTheme(this.lightTheme);
    } else {
      this.setTheme(this.darkTheme);
    }
  }

  /**
   * Force set to dark theme
   */
  useDarkTheme(): void {
    this.setTheme(this.darkTheme);
  }

  /**
   * Force set to light theme
   */
  useLightTheme(): void {
    this.setTheme(this.lightTheme);
  }

  /**
   * Get theme-appropriate color for a semantic purpose
   * This helps components use correct colors regardless of theme
   */
  getSemanticColor(purpose: 'tool' | 'reasoning' | 'output' | 'error' | 'warning' | 'step'): string {
    const theme = this.currentTheme;

    switch (purpose) {
      case 'tool':
        return theme.success; // Green for tools
      case 'reasoning':
        return theme.info; // Cyan for reasoning
      case 'output':
        return theme.foreground; // Default foreground
      case 'error':
        return theme.danger; // Red for errors
      case 'warning':
        return theme.warning; // Yellow/Orange for warnings
      case 'step':
        return theme.primary; // Blue for steps
      default:
        return theme.foreground;
    }
  }
}

export const themeManager = new ThemeManager();