/**
 * Stream Formatters Tests
 *
 * Tests for shared formatting utilities
 */

import { describe, it, expect } from '@jest/globals';
import {
  truncateString,
  truncateLines,
  formatAsTree,
  formatToolParameters,
  formatDuration,
  formatBytes,
  formatTokens,
  formatCost,
  sanitizeContent,
  extractErrorMessage,
  shouldTruncate,
  smartTruncate
} from '../../../src/utils/streamFormatters.js';

describe('streamFormatters', () => {
  describe('truncateString', () => {
    it('returns string as-is if under limit', () => {
      const str = 'short string';
      expect(truncateString(str, 100)).toBe(str);
    });

    it('truncates long strings with ellipsis', () => {
      const str = 'a'.repeat(150);
      const result = truncateString(str, 100);
      expect(result.length).toBe(103); // 100 + '...'
      expect(result.endsWith('...')).toBe(true);
    });

    it('handles empty strings', () => {
      expect(truncateString('', 100)).toBe('');
    });
  });

  describe('truncateLines', () => {
    it('returns all lines if under limit', () => {
      const content = 'line1\nline2\nline3';
      const result = truncateLines(content, 10);
      expect(result.lines).toEqual(['line1', 'line2', 'line3']);
      expect(result.truncated).toBe(false);
    });

    it('truncates to maxLines', () => {
      const content = Array.from({ length: 20 }, (_, i) => `line${i}`).join('\n');
      const result = truncateLines(content, 5);
      expect(result.lines.length).toBe(5);
      expect(result.truncated).toBe(true);
    });

    it('truncates long lines', () => {
      const content = 'a'.repeat(200);
      const result = truncateLines(content, 10, 100);
      expect(result.lines[0].length).toBeLessThanOrEqual(103); // 100 + '...'
    });
  });

  describe('formatAsTree', () => {
    it('formats simple object as tree', () => {
      const obj = { key1: 'value1', key2: 'value2' };
      const result = formatAsTree(obj);
      expect(result.some(line => line.includes('key1'))).toBe(true);
      expect(result.some(line => line.includes('value1'))).toBe(true);
    });

    it('formats nested objects with indentation', () => {
      const obj = { parent: { child: 'value' } };
      const result = formatAsTree(obj);
      expect(result.length).toBeGreaterThan(1);
    });

    it('handles arrays', () => {
      const arr = [1, 2, 3];
      const result = formatAsTree(arr);
      expect(result.some(line => line.includes('[0]'))).toBe(true);
    });

    it('respects maxDepth', () => {
      const deep = { a: { b: { c: { d: 'deep' } } } };
      const result = formatAsTree(deep, 0, 2);
      expect(result.some(line => line.includes('...'))).toBe(true);
    });
  });

  describe('formatToolParameters', () => {
    it('formats string parameters', () => {
      expect(formatToolParameters('test')).toBe('test');
    });

    it('formats single key-value pair', () => {
      const result = formatToolParameters({ target: '192.168.1.1' });
      expect(result).toContain('target');
      expect(result).toContain('192.168.1.1');
    });

    it('formats multiple parameters with count', () => {
      const params = { key1: 'val1', key2: 'val2', key3: 'val3' };
      const result = formatToolParameters(params);
      expect(result).toContain('+1 more');
    });

    it('handles empty objects', () => {
      expect(formatToolParameters({})).toBe('{}');
    });
  });

  describe('formatDuration', () => {
    it('formats milliseconds', () => {
      expect(formatDuration(500)).toBe('500ms');
    });

    it('formats seconds', () => {
      expect(formatDuration(2500)).toBe('2.5s');
    });

    it('formats minutes and seconds', () => {
      expect(formatDuration(125000)).toBe('2m 5s');
    });
  });

  describe('formatBytes', () => {
    it('formats bytes', () => {
      expect(formatBytes(500)).toBe('500B');
    });

    it('formats kilobytes', () => {
      expect(formatBytes(2048)).toBe('2.0KB');
    });

    it('formats megabytes', () => {
      expect(formatBytes(2 * 1024 * 1024)).toBe('2.0MB');
    });

    it('formats gigabytes', () => {
      expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.0GB');
    });
  });

  describe('formatTokens', () => {
    it('returns number as string if under 1000', () => {
      expect(formatTokens(500)).toBe('500');
    });

    it('formats thousands with K suffix', () => {
      expect(formatTokens(2500)).toBe('2.5K');
    });
  });

  describe('formatCost', () => {
    it('formats small costs with 4 decimals', () => {
      expect(formatCost(0.0012)).toBe('$0.0012');
    });

    it('formats medium costs with 3 decimals', () => {
      expect(formatCost(0.15)).toBe('$0.150');
    });

    it('formats large costs with 2 decimals', () => {
      expect(formatCost(5.67)).toBe('$5.67');
    });
  });

  describe('sanitizeContent', () => {
    it('returns strings as-is', () => {
      expect(sanitizeContent('test')).toBe('test');
    });

    it('stringifies objects', () => {
      const obj = { key: 'value' };
      const result = sanitizeContent(obj);
      expect(result).toContain('key');
      expect(result).toContain('value');
    });

    it('handles null and undefined', () => {
      expect(sanitizeContent(null)).toBe('');
      expect(sanitizeContent(undefined)).toBe('');
    });
  });

  describe('extractErrorMessage', () => {
    it('returns string errors as-is', () => {
      expect(extractErrorMessage('Error message')).toBe('Error message');
    });

    it('extracts message from error object', () => {
      expect(extractErrorMessage({ message: 'Error occurred' })).toBe('Error occurred');
    });

    it('extracts error field', () => {
      expect(extractErrorMessage({ error: 'Something wrong' })).toBe('Something wrong');
    });

    it('extracts content field', () => {
      expect(extractErrorMessage({ content: 'Error content' })).toBe('Error content');
    });

    it('returns unknown error for unrecognized shapes', () => {
      expect(extractErrorMessage({})).toBe('Unknown error');
    });
  });

  describe('shouldTruncate', () => {
    it('returns true for many lines', () => {
      const content = Array.from({ length: 30 }, (_, i) => `line${i}`).join('\n');
      expect(shouldTruncate(content)).toBe(true);
    });

    it('returns true for very long lines', () => {
      const content = 'a'.repeat(200);
      expect(shouldTruncate(content, 80)).toBe(true);
    });

    it('returns false for short content', () => {
      expect(shouldTruncate('short content', 80)).toBe(false);
    });
  });

  describe('smartTruncate', () => {
    it('returns content unchanged if within limits', () => {
      const content = 'short\ncontent';
      const result = smartTruncate(content, 80, 20);
      expect(result.content).toBe(content);
      expect(result.wasTruncated).toBe(false);
    });

    it('truncates long content', () => {
      const content = Array.from({ length: 30 }, (_, i) => `line${i}`).join('\n');
      const result = smartTruncate(content, 80, 10);
      expect(result.content.split('\n').length).toBeLessThanOrEqual(10);
      expect(result.wasTruncated).toBe(true);
    });

    it('truncates long lines', () => {
      const content = 'a'.repeat(200);
      const result = smartTruncate(content, 80, 20);
      expect(result.content.length).toBeLessThan(200);
      expect(result.wasTruncated).toBe(true);
    });
  });
});
