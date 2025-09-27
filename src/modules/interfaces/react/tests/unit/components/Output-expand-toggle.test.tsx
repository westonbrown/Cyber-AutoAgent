/**
 * Validate head/tail collapsing for tool outputs without any hotkey hints
 */
import { describe, it, expect } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';
import { EventLine } from '../../../src/components/StreamDisplay.js';

const makeLines = (n: number) => Array.from({ length: n }, (_, i) => `line ${i}`).join('\n');

describe('EventLine tool output collapsing', () => {
  it('collapses long tool outputs with head/tail and no hint', () => {
    const content = makeLines(1000);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    expect(frame.includes('... (content continues)')).toBe(true);
    expect(frame.includes('line 999')).toBe(true); // tail present
    expect(frame.includes('line 500')).toBe(false); // middle omitted
    expect(frame.toLowerCase()).not.toContain('press ctrl+s');
  });

  it('does not collapse when under threshold', () => {
    const content = makeLines(120);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    expect(frame.includes('... (content continues)')).toBe(false);
    expect(frame.includes('line 0')).toBe(true);
    expect(frame.includes('line 119')).toBe(true);
  });
});
