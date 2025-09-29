/**
 * Ensure report_content is trimmed to a small preview to avoid OOM
 * We test the pure helper to avoid React renderer/mock limitations.
 */
import { describe, it, expect } from '@jest/globals';
import { buildTrimmedReportContent } from '../../../src/components/Terminal.js';

describe('Terminal report_content trimming', () => {
  it('stores trimmed report content, not the full string', () => {
    const big = Array.from({ length: 10000 }, (_, i) => `line ${i}`).join('\n');
    const trimmed = buildTrimmedReportContent(big);

    expect(trimmed.includes('... (content continues)')).toBe(true);
    // Ensure not all lines are present
    expect(trimmed.includes('line 9999')).toBe(true); // tail present
    expect(trimmed.includes('line 5000')).toBe(false); // middle omitted
    // Ensure trimming actually reduced size
    expect(trimmed.length).toBeLessThan(big.length);
  });
});
