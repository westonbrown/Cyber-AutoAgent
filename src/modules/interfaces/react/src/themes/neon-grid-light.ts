/**
 * Terminal Pro Light Theme - Apple-inspired professional theme for light backgrounds
 *
 * Clean, minimal design inspired by Xcode light theme with subtle hacker touches.
 * Bright background with deep green accents for visibility and professionalism.
 */

import { CyberTheme } from './types.js';

export const NeonGridLight: CyberTheme = {
  type: 'light',
  name: 'Terminal Pro Light',

  // === CORE COLORS ===
  background: '#FFFFFF',     // Pure white (Apple Xcode style)
  foreground: '#000000',     // True black (maximum contrast)

  // === PRIMARY ACCENTS ===
  primary: '#00A400',        // Deep green (hacker aesthetic, visible on light)
  secondary: '#007AFF',      // Apple system blue (iOS standard)
  accent: '#00A400',         // Deep green (consistent with primary)

  // === SEMANTIC COLORS ===
  success: '#00A400',        // Deep green (success states)
  danger: '#FF3B30',         // Apple red (iOS standard, light mode)
  info: '#007AFF',           // Apple blue (informational)
  warning: '#FF9500',        // Apple orange (iOS standard, light mode)

  // === SUPPORTING COLORS ===
  subtle: '#C7C7CC',         // Light gray (Apple standard)
  muted: '#8E8E93',          // Medium gray (Apple standard)
  comment: '#AEAEB2',        // Dim gray (Apple standard)
  selection: '#E5E5EA',      // Very light gray (selections)

  // === GRADIENT COLORS (Deep green → Teal → Apple blue) ===
  // Light mode variant of the cool-toned spectrum gradient
  gradientColors: [
    '#00A400',  // Deep green (brand color)
    '#009B80',  // Teal green (transition)
    '#0099CC',  // Deep cyan (mid-point)
    '#0088DD',  // Ocean blue (transition)
    '#007AFF'   // Apple blue (brand color)
  ]
};
