/**
 * Terminal Background Detection
 *
 * Detects whether the terminal is using a light or dark background
 * to automatically select the appropriate theme.
 */

export type BackgroundType = 'dark' | 'light' | 'unknown';

/**
 * Detect terminal background type using various methods
 *
 * Methods used (in order of preference):
 * 1. COLORFGBG environment variable (most reliable)
 * 2. Terminal program detection (iTerm2, VS Code, etc.)
 * 3. Fallback to dark (safest default)
 */
export function detectTerminalBackground(): BackgroundType {
  // Method 1: COLORFGBG environment variable
  // Format: "foreground;background" where:
  // - 0-7 = dark background
  // - 8-15 = light background
  const colorFgBg = process.env.COLORFGBG;
  if (colorFgBg) {
    const parts = colorFgBg.split(';');
    if (parts.length >= 2) {
      const bg = parseInt(parts[1], 10);
      if (!isNaN(bg)) {
        // 0-7 = dark colors, 8-15 = light colors
        if (bg >= 0 && bg <= 7) {
          return 'dark';
        } else if (bg >= 8 && bg <= 15) {
          return 'light';
        }
      }
    }
  }

  // Method 2: Terminal program specific detection
  const termProgram = process.env.TERM_PROGRAM?.toLowerCase();
  const termProgramVersion = process.env.TERM_PROGRAM_VERSION;

  // iTerm2 - check for light theme indicators
  if (termProgram === 'iterm.app') {
    // iTerm2 doesn't set COLORFGBG reliably, default to dark
    // Users can override with CYBER_THEME env var if needed
    return 'dark';
  }

  // VS Code - check theme
  if (termProgram === 'vscode' || process.env.TERM_PROGRAM === 'vscode') {
    // VS Code doesn't reliably expose theme info, default to dark
    return 'dark';
  }

  // Apple Terminal - default to dark (most common)
  if (termProgram === 'apple_terminal') {
    return 'dark';
  }

  // Method 3: Check for explicit user preference via environment variable
  const cyberTheme = process.env.CYBER_THEME?.toLowerCase();
  if (cyberTheme === 'light') {
    return 'light';
  } else if (cyberTheme === 'dark') {
    return 'dark';
  }

  // Method 4: Check if NO_COLOR is set (implies preference for no styling)
  // In this case, assume dark as safest default
  if (process.env.NO_COLOR) {
    return 'dark';
  }

  // Fallback: Default to dark (safest choice - dark colors work on most terminals)
  return 'dark';
}

/**
 * Check if terminal supports 256 colors or true color
 */
export function supportsRichColors(): boolean {
  const term = process.env.TERM?.toLowerCase() || '';

  // Check for 256 color support
  if (term.includes('256color') || term.includes('24bit') || term.includes('truecolor')) {
    return true;
  }

  // Check COLORTERM for truecolor support
  const colorTerm = process.env.COLORTERM?.toLowerCase() || '';
  if (colorTerm.includes('truecolor') || colorTerm === '24bit') {
    return true;
  }

  // iTerm2, VS Code, and modern terminals support rich colors
  const termProgram = process.env.TERM_PROGRAM?.toLowerCase();
  if (termProgram === 'iterm.app' || termProgram === 'vscode' || termProgram === 'hyper') {
    return true;
  }

  return false;
}

/**
 * Get recommended theme type based on terminal detection
 */
export function getRecommendedThemeType(): 'dark' | 'light' {
  const background = detectTerminalBackground();

  // If we detected light background, recommend light theme
  if (background === 'light') {
    return 'light';
  }

  // Otherwise default to dark (works on both dark terminals and unknown)
  return 'dark';
}