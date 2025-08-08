/**
 * Tool Categories - Visual categorization system for tools
 * Provides icons, colors, and importance levels for different tool types
 */

export interface ToolCategory {
  name: string;
  icon: string;
  color: string;
  importance: 'critical' | 'high' | 'normal' | 'low';
}

// Tool category definitions
export const toolCategories: Record<string, ToolCategory> = {
  // Security scanning tools
  security: {
    name: 'Security',
    icon: '🔒',
    color: 'blue',
    importance: 'high'
  },
  
  // System/shell commands
  system: {
    name: 'System',
    icon: '⚙️',
    color: 'green',
    importance: 'normal'
  },
  
  // Memory/storage operations
  memory: {
    name: 'Memory',
    icon: '💾',
    color: 'cyan',
    importance: 'normal'
  },
  
  // Network operations
  network: {
    name: 'Network',
    icon: '🌐',
    color: 'yellow',
    importance: 'normal'
  },
  
  // Control flow tools
  control: {
    name: 'Control',
    icon: '⚠️',
    color: 'red',
    importance: 'critical'
  },
  
  // Multi-agent operations
  multi: {
    name: 'Multi-Agent',
    icon: '🔄',
    color: 'magenta',
    importance: 'high'
  },
  
  // Code execution
  code: {
    name: 'Code',
    icon: '🔧',
    color: 'blue',
    importance: 'normal'
  },
  
  // File operations
  file: {
    name: 'File',
    icon: '📁',
    color: 'gray',
    importance: 'low'
  },
  
  // Reporting
  report: {
    name: 'Report',
    icon: '📋',
    color: 'green',
    importance: 'high'
  }
};

// Map tools to categories
export const toolCategoryMap: Record<string, keyof typeof toolCategories> = {
  // Security tools
  'nmap': 'security',
  'nikto': 'security',
  'sqlmap': 'security',
  'gobuster': 'security',
  'metasploit': 'security',
  'netcat': 'security',
  'tcpdump': 'security',
  'quick_recon': 'security',
  
  // System tools
  'shell': 'system',
  'bash': 'system',
  'cmd': 'system',
  
  // Memory tools
  'mem0_memory': 'memory',
  'memory': 'memory',
  
  // Network tools
  'http_request': 'network',
  'curl': 'network',
  'wget': 'network',
  
  // Control tools
  'stop': 'control',
  'handoff_to_user': 'control',
  'handoff_to_agent': 'control',
  'complete_swarm_task': 'control',
  
  // Multi-agent tools
  'swarm': 'multi',
  
  // Code tools
  'python_repl': 'code',
  'python': 'code',
  'editor': 'code',
  
  // File tools
  'file_write': 'file',
  'file_read': 'file',
  'load_tool': 'file',
  
  // Report tools
  'generate_security_report': 'report',
  'report_generator': 'report'
};

/**
 * Get the category for a tool
 */
export function getToolCategory(toolName: string): ToolCategory {
  const categoryKey = toolCategoryMap[toolName];
  if (categoryKey) {
    return toolCategories[categoryKey];
  }
  
  // Default category for unknown tools
  return {
    name: 'Tool',
    icon: '🔧',
    color: 'gray',
    importance: 'normal'
  };
}

/**
 * Get display color based on importance
 */
export function getImportanceColor(importance: ToolCategory['importance']): string {
  switch (importance) {
    case 'critical':
      return 'redBright';
    case 'high':
      return 'yellowBright';
    case 'normal':
      return 'green';
    case 'low':
      return 'gray';
    default:
      return 'white';
  }
}

/**
 * Format tool name with category icon
 */
export function formatToolWithIcon(toolName: string): string {
  const category = getToolCategory(toolName);
  return `${category.icon} ${toolName}`;
}

/**
 * Check if tool should have enhanced visibility
 */
export function isHighPriorityTool(toolName: string): boolean {
  const category = getToolCategory(toolName);
  return category.importance === 'critical' || category.importance === 'high';
}

/**
 * Get execution status display
 */
export interface ExecutionStatus {
  symbol: string;
  color: string;
  text: string;
}

export function getExecutionStatus(
  status: 'pending' | 'executing' | 'completed' | 'failed',
  duration?: number
): ExecutionStatus {
  switch (status) {
    case 'pending':
      return {
        symbol: '○',
        color: 'gray',
        text: 'pending'
      };
    case 'executing':
      return {
        symbol: '●',
        color: 'yellow',
        text: duration ? `executing [${duration}s]` : 'executing'
      };
    case 'completed':
      return {
        symbol: '✓',
        color: 'green',
        text: duration ? `completed [${duration}s]` : 'completed'
      };
    case 'failed':
      return {
        symbol: '✗',
        color: 'red',
        text: duration ? `failed [${duration}s]` : 'failed'
      };
    default:
      return {
        symbol: '?',
        color: 'gray',
        text: 'unknown'
      };
  }
}