/**
 * Clean typography system for terminal UI without emojis
 */

export const Icons = {
  // Status indicators
  pending: 'o',
  running: '*',
  success: '+',
  error: 'x',
  warning: '!',
  
  // Tool indicators
  shell: '$',
  shellOutput: '|',
  tool: '>',
  toolComplete: '+',
  toolError: 'x',
  
  // Flow indicators
  arrow: '->',
  arrowRight: '>',
  arrowLeft: '<',
  arrowUp: '^',
  arrowDown: 'v',
  
  // Special indicators
  bullet: '-',
  dot: '.',
  star: '*',
  plus: '+',
  minus: '-',
  check: '[+]',
  cross: '[x]',
  
  // Progress indicators
  progressEmpty: '[ ]',
  progressFull: '[=]',
  progressPartial: '[~]',
  
  // Brackets and separators
  openBracket: '[',
  closeBracket: ']',
  pipe: '|',
  colon: ':',
  dash: '-',
  
  // Agent/System indicators
  agent: '@',
  system: '#',
  user: '>',
  memory: 'M',
  think: 'T',
  
  // Network indicators
  upload: '^',
  download: 'v',
  connection: '<>',
  disconnection: '><',
} as const;

export const Colors = {
  // Modern CLI color scheme based on reference analysis
  primary: 'blue',      // #4796E4 - actions, links (like gemini-cli)
  accent: 'magenta',    // #8B5CF6 - loading, variables (like opencode)
  success: 'green',     // #3CA84B - completion, success
  error: 'red',         // #DD4C4C - errors, failures  
  warning: 'yellow',    // #D5A40A - warnings, attention
  
  // Neutral colors
  text: 'white',
  muted: 'gray',        // #6C7086 - secondary text, comments
  dim: 'gray',
  
  // Tool-specific colors - clean and semantic
  shell: 'blue',        // Shell commands
  tool: 'cyan',         // Tool execution
  agent: 'magenta',     // Agent actions
  system: 'blue',       // System status
  memory: 'cyan',       // Memory operations
  think: 'magenta',     // Reasoning/thinking
  http: 'yellow',       // HTTP requests
  python: 'green',      // Python REPL
  editor: 'blue',       // File editing
} as const;

export const Styles = {
  // Text styles
  bold: { bold: true },
  dim: { dimColor: true },
  italic: { italic: true },
  underline: { underline: true },
  strikethrough: { strikethrough: true },
  inverse: { inverse: true },
  
  // Combined styles
  header: { bold: true, underline: true },
  subheader: { bold: true },
  muted: { dimColor: true },
  error: { color: 'red', bold: true },
  success: { color: 'green' },
  warning: { color: 'yellow' },
  info: { color: 'blue' },
} as const;

export const Layout = {
  // Spacing
  indent: '  ',
  doubleIndent: '    ',
  
  // Separators
  line: '-'.repeat(60),
  doubleLine: '='.repeat(60),
  dotLine: '.'.repeat(60),
  
  // Box drawing
  boxTop: '+' + '-'.repeat(58) + '+',
  boxBottom: '+' + '-'.repeat(58) + '+',
  boxSide: '|',
  
  // Headers
  sectionHeader: (title: string) => `\n[${title}]\n${'-'.repeat(title.length + 2)}`,
  toolHeader: (tool: string) => `> ${tool}`,
  resultHeader: (status: string) => `[${status}]`,
} as const;

export type IconKey = keyof typeof Icons;
export type ColorKey = keyof typeof Colors;

export function formatToolStatus(tool: string, status: 'start' | 'end' | 'error'): string {
  const icon = status === 'start' ? Icons.tool : status === 'end' ? Icons.success : Icons.error;
  return `${icon} ${tool}`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${(seconds * 1000).toFixed(0)}ms`;
  } else if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  } else {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  }
}

export function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  
  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength - 3) + '...';
}
