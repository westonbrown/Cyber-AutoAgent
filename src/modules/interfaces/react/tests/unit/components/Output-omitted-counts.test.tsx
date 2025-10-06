/**
 * Tests to verify that collapse markers include omitted line counts
 */
import { describe, it, expect } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';
import { EventLine } from '../../../src/components/StreamDisplay.js';

const makeLines = (n: number) => Array.from({ length: n }, (_, i) => `line ${i}`).join('\n');

describe('EventLine omitted counts', () => {
  it('shows collapse marker for large tool outputs', () => {
    const content = makeLines(1000);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    // Should show collapse marker (content continues)
    expect(frame).toMatch(/\.\.\. \(content continues\)/);
    // Should show total line count
    expect(frame).toMatch(/\[1000 lines\]/);
  });

  it('shows collapse marker for large default outputs', () => {
    const content = makeLines(200);
    const evt: any = {
      type: 'output',
      content,
      // no tool metadata, uses DEFAULT_COLLAPSE_LINES logic
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    // Should show collapse marker
    expect(frame).toMatch(/\.\.\. \(content continues\)/);
    // Should show truncated indicator
    expect(frame).toMatch(/\[200 lines, truncated\]/);
  });
});
