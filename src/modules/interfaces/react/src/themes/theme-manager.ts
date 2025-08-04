/**
 * Theme Management System
 * Handles theme loading, switching, and persistence
 */

import { CyberTheme, ThemeConfig } from './types.js';
import { CyberDarkTheme } from './cyber-dark.js';

class ThemeManager {
  private currentTheme: CyberTheme;
  private config: ThemeConfig;

  constructor() {
    this.currentTheme = CyberDarkTheme;
    this.config = {
      theme: this.currentTheme,
      enableGradients: true,
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
}

export const themeManager = new ThemeManager();