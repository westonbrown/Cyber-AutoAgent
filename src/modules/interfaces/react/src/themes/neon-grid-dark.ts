/**
 * Terminal Pro Dark Theme - Apple-inspired professional hacker theme
 *
 * Clean, minimal design inspired by Apple Terminal.app with classic hacker aesthetics.
 * True black background with matrix green accents for maximum professionalism.
 */

import { CyberTheme } from './types.js';

export const NeonGridDark: CyberTheme = {
  type: 'dark',
  name: 'Terminal Pro',

  // === CORE COLORS ===
  background: '#000000',     // True black (Apple Terminal style)
  foreground: '#FFFFFF',     // Pure white (maximum contrast, clean)

  // === PRIMARY ACCENTS ===
  primary: '#00FF41',        // Matrix green (classic hacker aesthetic)
  secondary: '#0A84FF',      // Apple system blue (professional, familiar)
  accent: '#00FF41',         // Matrix green (consistent with primary)

  // === SEMANTIC COLORS ===
  success: '#00FF41',        // Matrix green (operations successful)
  danger: '#FF453A',         // Apple red (critical alerts, iOS standard)
  info: '#0A84FF',           // Apple blue (informational messages)
  warning: '#FF9F0A',        // Apple orange (warnings, iOS standard)

  // === SUPPORTING COLORS ===
  subtle: '#3D3D3D',         // Dark gray (inactive elements)
  muted: '#98989D',          // Medium gray (secondary text, Apple standard)
  comment: '#6E6E73',        // Dim gray (code comments, Apple standard)
  selection: '#1C1C1E',      // Very dark gray (selections, subtle)

  // === GRADIENT COLORS (Matrix green → Cyan → Apple blue) ===
  // Inspired by Gemini's multi-color gradients, cool-toned spectrum
  gradientColors: [
    '#00FF41',  // Bright matrix green (brand color)
    '#00E5A0',  // Emerald green (transition)
    '#00D9FF',  // Bright cyan (mid-point)
    '#33B8FF',  // Sky blue (transition)
    '#0A84FF'   // Apple blue (brand color)
  ]
};
