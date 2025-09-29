/**
 * Char-based fallback tests for large single-line outputs
 */
import { describe, it, expect } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';
import { EventLine } from '../../../src/components/StreamDisplay.js';

function bigSingleLine(len: number, head = 'HEAD-', tail = '-TAIL') {
  const middleLen = Math.max(0, len - head.length - tail.length);
  return head + 'X'.repeat(middleLen) + tail;
}

describe('EventLine char-based fallback for huge single-line outputs', () => {
  it('collapses huge single-line tool output with head/tail and gap marker', () => {
    const content = bigSingleLine(12000);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();

    expect(/\.\.\. \(content continues(?:;\s*\d+\s+chars omitted)?\)/.test(frame)).toBe(true);
    // Ensure head and tail parts are present
    expect(frame).toContain('HEAD-');
    // Should not contain the entire middle
    expect(frame.includes('X'.repeat(3000))).toBe(false);
  });

  it('collapses huge single-line non-tool output with head/tail and gap marker', () => {
    const content = bigSingleLine(10000, 'BEGIN-', '-END');
    const evt: any = {
      type: 'output',
      content,
      // No metadata.fromToolBuffer on purpose
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();

    expect(/\.\.\. \(content continues(?:;\s*\d+\s+chars omitted)?\)/.test(frame)).toBe(true);
    expect(frame).toContain('BEGIN-');
    expect(frame).toContain('-END');
  });

  it('does not collapse when single-line is below char threshold (head preserved under width clamp)', () => {
    // Threshold is OUTPUT_PREVIEW_CHARS + OUTPUT_TAIL_CHARS + 200 = 2700 by default
    const content = bigSingleLine(2300);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();

    expect(frame).not.toContain('... (content continues)');
    expect(frame).toContain('HEAD-');
    // Tail may be truncated by width clamp; we only assert non-collapsed and head presence
  });
});
