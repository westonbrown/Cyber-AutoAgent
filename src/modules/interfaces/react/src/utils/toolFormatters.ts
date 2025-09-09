/**
 * Tool formatters - Extract tool-specific formatting logic
 * Reduces tech debt by centralizing tool display logic
 */

import { DISPLAY_LIMITS } from '../constants/config.js';
import { isNonEmptyString, isObject, toSafeString, truncate } from './typeUtils.js';

/**
 * Format duration in milliseconds or seconds to human-readable string
 * @param value - Duration in milliseconds (if > 1000) or seconds, or a Date object
 * @param isMilliseconds - Whether the input is in milliseconds (default: auto-detect)
 */
export function formatDuration(value: number | Date, isMilliseconds?: boolean): string {
  let seconds: number;
  
  if (value instanceof Date) {
    // Calculate elapsed time from Date
    seconds = Math.floor((Date.now() - value.getTime()) / 1000);
  } else {
    // Handle numeric input
    if (isMilliseconds === undefined) {
      // Auto-detect: if value > 1000, assume milliseconds
      seconds = value > 1000 ? Math.floor(value / 1000) : value;
    } else {
      seconds = isMilliseconds ? Math.floor(value / 1000) : value;
    }
  }
  
  if (seconds < 60) {
    return `${seconds}s`;
  }
  
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  
  if (remainingMinutes > 0) {
    return `${hours}h ${remainingMinutes}m`;
  }
  
  return `${hours}h`;
}

// Tool input formatter type
type ToolFormatter = (toolInput: any) => string;

// Generic object formatter for unknown tools
export const formatGenericToolInput = (toolInput: any): string => {
  if (!toolInput && toolInput !== 0 && toolInput !== false) return '';
  
  // If input is a JSON-looking string, try to parse it for better previews
  if (isNonEmptyString(toolInput)) {
    const str = String(toolInput).trim();
    if ((str.startsWith('{') && str.endsWith('}')) || (str.startsWith('[') && str.endsWith(']'))) {
      try {
        const parsed = JSON.parse(str);
        // Recurse with parsed structure
        return formatGenericToolInput(parsed);
      } catch {
        // Fall through to truncated string preview
      }
    }
    return truncate(toolInput, DISPLAY_LIMITS.TRUNCATE_LONG);
  }
  
  // Arrays: show count and a short preview of first few items
  if (Array.isArray(toolInput)) {
    const arr = toolInput as any[];
    const n = arr.length;
    if (n === 0) return '[0 items]';
    const sampleCount = Math.min(n, 3);
    const sample = arr.slice(0, sampleCount).map((v) => {
      if (isNonEmptyString(v)) return truncate(String(v), DISPLAY_LIMITS.TRUNCATE_SHORT);
      if (Array.isArray(v)) return `[${v.length} items]`;
      if (isObject(v)) {
        const keys = Object.keys(v);
        return `{${keys.slice(0, 3).join(', ')}${keys.length > 3 ? '…' : ''}}`;
      }
      return toSafeString(v);
    });
    const more = n > sampleCount ? ` (+${n - sampleCount} more)` : '';
    return `items: ${sample.join(', ')}${more}`;
  }
  
  // Plain objects
  if (isObject(toolInput)) {
    const keys = Object.keys(toolInput);
    if (keys.length === 0) return '{}';
    
    // For single key, show key: value with type-aware preview
    if (keys.length === 1) {
      const key = keys[0];
      const value = (toolInput as any)[key];
      let displayValue: string;
      if (Array.isArray(value)) {
        displayValue = `[${value.length} items]`;
      } else if (isObject(value)) {
        const k = Object.keys(value);
        displayValue = `{${k.slice(0, 3).join(', ')}${k.length > 3 ? '…' : ''}}`;
      } else if (isNonEmptyString(value)) {
        displayValue = truncate(value, DISPLAY_LIMITS.TRUNCATE_MEDIUM);
      } else {
        displayValue = toSafeString(value);
      }
      return `${key}: ${displayValue}`;
    }
    
    // For a few keys, render compact k: v previews
    if (keys.length <= DISPLAY_LIMITS.TOOL_INPUT_MAX_KEYS) {
      return keys.map(k => {
        const value = (toolInput as any)[k];
        let displayValue: string;
        if (Array.isArray(value)) {
          displayValue = `[${value.length} items]`;
        } else if (isObject(value)) {
          const k2 = Object.keys(value);
          displayValue = `{${k2.slice(0, 2).join(', ')}${k2.length > 2 ? '…' : ''}}`;
        } else if (isNonEmptyString(value)) {
          displayValue = truncate(value, DISPLAY_LIMITS.TRUNCATE_SHORT);
        } else {
          displayValue = toSafeString(value);
        }
        return `${k}: ${displayValue}`;
      }).join(' | ');
    }
    
    // Larger objects: list a few top-level keys and counts
    const importantKeys = keys.slice(0, DISPLAY_LIMITS.TOOL_INPUT_PREVIEW_KEYS);
    const remainingCount = keys.length - DISPLAY_LIMITS.TOOL_INPUT_PREVIEW_KEYS;
    return `${importantKeys.join(', ')}${remainingCount > 0 ? ` (+${remainingCount} more)` : ''}`;
  }
  
  // Fallback primitive
  return toSafeString(toolInput);
};

// Tool-specific formatters
export const toolFormatters: Record<string, ToolFormatter> = {
  mem0_memory: (input) => {
    const action = input.action || 'unknown';
    if (action === 'unknown') return '';
    
    const content = input.content || input.query || '';
    const preview = truncate(content, 60);
    const actionDisplay = action === 'store' ? 'storing memory' 
      : action === 'retrieve' ? 'retrieving memory' 
      : action;
    const labelDisplay = action === 'store' ? 'preview' : 'query';
    
    return preview ? `${actionDisplay} | ${labelDisplay}: ${preview}` : actionDisplay;
  },
  
  shell: (input) => {
    const commands = input.command || input.commands || input.cmd || input.input || '';
    const parts: string[] = [
      `Commands: ${commands}`
    ];
    const flags: string[] = [];
    if (input.parallel === true) flags.push('parallel');
    if (input.ignore_errors === true) flags.push('ignore_errors');
    if (input.non_interactive === true) flags.push('non_interactive');
    const extras: string[] = [];
    if (typeof input.timeout === 'number') extras.push(`timeout: ${input.timeout}s`);
    const workDir = input.work_dir || input.cwd;
    if (typeof workDir === 'string' && workDir.length > 0) extras.push(`cwd: ${workDir}`);

    const suffix = [flags.join(', '), extras.join(' | ')].filter(Boolean).join(' | ');
    return suffix ? `${parts.join(' | ')} | ${suffix}` : parts.join(' | ');
  },
  
  http_request: (input) => {
    const method = input.method || 'GET';
    const url = input.url || '';
    return `method: ${method} | url: ${url}`;
  },
  
  file_write: (input) => {
    const filePath = input.path || 'unknown';
    const fileContent = input.content || '';
    const contentInfo = fileContent ? ` | ${fileContent.length} chars` : '';
    return `path: ${filePath}${contentInfo}`;
  },
  
  editor: (input) => {
    const cmd = input.command || 'edit';
    const path = input.path || '';
    const content = input.content || '';
    const info = content ? ` | ${content.length} chars` : '';
    return `${cmd}: ${path}${info}`;
  },
  
  python_repl: (input) => {
    const code = input.code || '';
    const codeLines = code.split('\n');
    const previewLines = DISPLAY_LIMITS.CODE_PREVIEW_LINES;
    
    let codePreview;
    if (codeLines.length <= previewLines) {
      codePreview = code;
    } else {
      const truncatedLines = codeLines.slice(0, previewLines);
      codePreview = truncatedLines.join('\n') + '\n...';
    }
    
    return `code:\n${codePreview}`;
  },
  
  report_generator: (input) => {
    const target = input.target || 'unknown';
    const reportType = input.report_type || input.type || 'general';
    return `target: ${target} | type: ${reportType}`;
  },
  
  handoff_to_agent: (input) => {
    const toAgent = input.agent || input.target_agent || 'unknown';
    const message = input.message || '';
    const msgPreview = truncate(message, DISPLAY_LIMITS.TRUNCATE_MEDIUM);
    return `target: ${toAgent} | message: ${msgPreview}`;
  },
  
  load_tool: (input) => {
    const toolName = input.tool_name || input.tool || 'unknown';
    const toolPath = input.path || '';
    const toolDescription = input.description || '';
    const pathInfo = toolPath ? ` | path: ${toolPath}` : '';
    const descInfo = toolDescription ? ` | ${toolDescription}` : '';
    return `loading: ${toolName}${pathInfo}${descInfo}`;
  },
  
  stop: (input) => {
    return input.reason || 'Manual stop requested';
  }
};

// Main formatter function
export const formatToolInput = (toolName: string, toolInput: any): string => {
  const formatter = toolFormatters[toolName];
  return formatter ? formatter(toolInput) : formatGenericToolInput(toolInput);
};