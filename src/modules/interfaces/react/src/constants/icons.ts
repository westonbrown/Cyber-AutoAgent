/**
 * Icon constants for React Ink terminal UI
 * 
 * Unicode symbols for cross-platform terminal compatibility.
 */

export const Icons = {
  // Status indicators
  success: '[OK]',      // Check mark
  error: '[ERR]',        // Multiplication X
  warning: '[WARN]',      // Warning sign
  info: '[INFO]',         // Information
  pending: '[WAIT]',      // Empty circle
  active: '[ACTIVE]',       // Filled circle
  
  // Navigation
  chevronRight: '>', // Right-pointing triangle
  chevronDown: 'v',  // Down-pointing triangle
  arrow: '>',        // Filled right arrow
  bullet: '-',       // Bullet point
  
  // Special indicators
  diamond: '[*]',      // Filled diamond
  diamondEmpty: '[ ]', // Empty diamond
  square: '[#]',       // Filled square
  squareEmpty: '[ ]',  // Empty square
  
  // Target types
  all: '[TARGET]',          // Circle with center dot
  host: '>>',         // Filled right arrow
  web: '[WEB]',          // Right triangle
  ip: '[IP]',           // Filled square
  local: '[LOCAL]',        // Hexagon
  test: '[TEST]',         // Diamond with cross
  null: '[WAIT]',         // Empty circle
  
  // Memory specific
  memory: '[MEM]',       // Diamond for memory operations
  search: '[SEARCH]',       // Circle with dot for search
  results: '>>',      // Arrow for results
  target: '[TGT]',       // Triangle for targets
  
  // Progress indicators
  spinner: ['|', '/', '-', '\\'],
  dots: ['.', '..', '...', '....'],
  
  // Box drawing
  cornerTopLeft: '+',
  cornerTopRight: '+',
  cornerBottomLeft: '+',
  cornerBottomRight: '+',
  horizontal: '-',
  vertical: '|',
  
  // Professional prefixes
  prefix: {
    error: '[ERR] ',
    warning: '[WARN] ',
    info: '[INFO] ',
    success: '[OK] ',
    memory: '[MEM] ',
    target: '[TGT] ',
    result: '> ',
    all: '[ALL] ',
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