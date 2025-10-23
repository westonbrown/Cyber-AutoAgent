/**
 * Shared formatting utilities for StreamDisplay
 *
 * Provides consistent truncation, tree rendering, and parameter
 * formatting across all event renderers.
 */

/**
 * Truncate long strings with ellipsis
 */
export function truncateString(str: string, maxLength: number = 100): string {
  if (!str || str.length <= maxLength) return str;
  return str.slice(0, maxLength) + '...';
}

/**
 * Truncate multi-line content intelligently
 */
export function truncateLines(
  content: string,
  maxLines: number = 10,
  maxCharsPerLine: number = 120
): { lines: string[]; truncated: boolean } {
  const allLines = content.split('\n');
  const truncated = allLines.length > maxLines;

  const displayLines = allLines.slice(0, maxLines).map(line =>
    line.length > maxCharsPerLine ? line.slice(0, maxCharsPerLine) + '...' : line
  );

  return {
    lines: displayLines,
    truncated
  };
}

/**
 * Format object as tree structure for display
 */
export function formatAsTree(obj: any, indent: number = 0, maxDepth: number = 3): string[] {
  if (indent >= maxDepth) return ['  ...'];

  const lines: string[] = [];
  const prefix = '  '.repeat(indent);

  if (obj === null || obj === undefined) {
    return [`${prefix}${String(obj)}`];
  }

  if (typeof obj !== 'object') {
    return [`${prefix}${String(obj)}`];
  }

  if (Array.isArray(obj)) {
    if (obj.length === 0) return [`${prefix}[]`];
    obj.forEach((item, idx) => {
      lines.push(`${prefix}[${idx}]:`);
      lines.push(...formatAsTree(item, indent + 1, maxDepth));
    });
    return lines;
  }

  const entries = Object.entries(obj);
  if (entries.length === 0) return [`${prefix}{}`];

  entries.forEach(([key, value]) => {
    if (typeof value === 'object' && value !== null) {
      lines.push(`${prefix}${key}:`);
      lines.push(...formatAsTree(value, indent + 1, maxDepth));
    } else {
      const valueStr = String(value);
      const displayValue = valueStr.length > 60 ? valueStr.slice(0, 60) + '...' : valueStr;
      lines.push(`${prefix}${key}: ${displayValue}`);
    }
  });

  return lines;
}

/**
 * Format tool parameters for compact display
 */
export function formatToolParameters(params: any): string {
  if (!params) return '';

  if (typeof params === 'string') {
    return truncateString(params, 100);
  }

  if (typeof params !== 'object') {
    return String(params);
  }

  const entries = Object.entries(params);
  if (entries.length === 0) return '{}';

  if (entries.length === 1) {
    const [key, value] = entries[0];
    return `${key}: ${truncateString(String(value), 80)}`;
  }

  // Multiple params - show count and first few
  const first = entries.slice(0, 2).map(([k, v]) => `${k}: ${truncateString(String(v), 40)}`);
  const remaining = entries.length - 2;
  return remaining > 0 ? `${first.join(', ')} (+${remaining} more)` : first.join(', ');
}

/**
 * Format duration in human-readable form
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
}

/**
 * Format byte size in human-readable form
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)}GB`;
}

/**
 * Format token count with K suffix
 */
export function formatTokens(tokens: number): string {
  if (tokens < 1000) return String(tokens);
  return `${(tokens / 1000).toFixed(1)}K`;
}

/**
 * Format cost in USD
 */
export function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  if (cost < 1) return `$${cost.toFixed(3)}`;
  return `$${cost.toFixed(2)}`;
}

/**
 * Sanitize and normalize content for safe display
 */
export function sanitizeContent(content: any): string {
  if (content === null || content === undefined) return '';
  if (typeof content === 'string') return content;
  if (typeof content === 'object') {
    try {
      return JSON.stringify(content, null, 2);
    } catch {
      return String(content);
    }
  }
  return String(content);
}

/**
 * Extract and format error message from various error shapes
 */
export function extractErrorMessage(error: any): string {
  if (typeof error === 'string') return error;
  if (error?.message) return String(error.message);
  if (error?.error) return String(error.error);
  if (error?.content) return String(error.content);
  return 'Unknown error';
}

/**
 * Determine if content should be truncated based on terminal width
 */
export function shouldTruncate(content: string, terminalWidth: number = 80): boolean {
  const lines = content.split('\n');
  if (lines.length > 20) return true;
  return lines.some(line => line.length > terminalWidth * 0.9);
}

/**
 * Smart truncation that preserves structure
 */
export function smartTruncate(
  content: string,
  terminalWidth: number = 80,
  maxLines: number = 20
): { content: string; wasTruncated: boolean } {
  const lines = content.split('\n');

  if (lines.length <= maxLines && !lines.some(l => l.length > terminalWidth)) {
    return { content, wasTruncated: false };
  }

  const truncatedLines = lines
    .slice(0, maxLines)
    .map(line => (line.length > terminalWidth ? line.slice(0, terminalWidth - 3) + '...' : line));

  const wasTruncated = lines.length > maxLines || lines.some(l => l.length > terminalWidth);

  return {
    content: truncatedLines.join('\n'),
    wasTruncated
  };
}
