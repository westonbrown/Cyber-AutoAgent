/**
 * Icon constants for React Ink terminal UI
 * 
 * Unicode symbols for cross-platform terminal compatibility.
 */

export const Icons = {
  // Status indicators
  success: '✓',      // Check mark
  error: '✕',        // Multiplication X
  warning: '⚠',      // Warning sign
  info: 'ℹ',         // Information
  pending: '○',      // Empty circle
  active: '●',       // Filled circle
  
  // Navigation
  chevronRight: '▸', // Right-pointing triangle
  chevronDown: '▾',  // Down-pointing triangle
  arrow: '▶',        // Filled right arrow
  bullet: '•',       // Bullet point
  
  // Special indicators
  diamond: '◆',      // Filled diamond
  diamondEmpty: '◇', // Empty diamond
  square: '▪',       // Filled square
  squareEmpty: '▫',  // Empty square
  
  // Target types
  all: '◉',          // Circle with center dot
  host: '▶',         // Filled right arrow
  web: '▸',          // Right triangle
  ip: '▪',           // Filled square
  local: '⬡',        // Hexagon
  test: '◈',         // Diamond with cross
  null: '○',         // Empty circle
  
  // Memory specific
  memory: '◆',       // Diamond for memory operations
  search: '◉',       // Circle with dot for search
  results: '▶',      // Arrow for results
  target: '▸',       // Triangle for targets
  
  // Progress indicators
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
  dots: ['⢎ ', '⠎⠁', '⠊⠑', '⠈⠱', ' ⡱', '⢀⡰', '⢄⡠', '⢆⡀'],
  
  // Box drawing
  cornerTopLeft: '┌',
  cornerTopRight: '┐',
  cornerBottomLeft: '└',
  cornerBottomRight: '┘',
  horizontal: '─',
  vertical: '│',
  
  // Professional prefixes
  prefix: {
    error: '✕ ',
    warning: '⚠ ',
    info: 'ℹ ',
    success: '✓ ',
    memory: '◆ ',
    target: '▸ ',
    result: '▶ ',
    all: '◉ ',
  }
};

// Target type mapping
export const getTargetIcon = (targetName: string): string => {
  if (targetName === 'NONE' || targetName === 'none') return Icons.null;
  if (targetName.match(/^\d+\.\d+\.\d+\.\d+$/)) return Icons.ip;
  if (targetName.includes('localhost') || targetName === '127.0.0.1') return Icons.local;
  if (targetName.includes('.com') || targetName.includes('.org') || targetName.includes('.net')) return Icons.web;
  if (targetName.includes('test') || targetName.includes('demo')) return Icons.test;
  return Icons.host;
};