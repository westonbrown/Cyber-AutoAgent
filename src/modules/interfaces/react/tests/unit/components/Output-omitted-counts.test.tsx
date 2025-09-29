/**
 * Tests to verify that collapse markers include omitted line counts
 */
import { describe, it, expect } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';
import { EventLine } from '../../../src/components/StreamDisplay.js';

const makeLines = (n: number) => Array.from({ length: n }, (_, i) => `line ${i}`).join('\n');

describe('EventLine omitted counts', () => {
  it('shows omitted line count for tool outputs in collapse marker', () => {
    const content = makeLines(1000);
    const evt: any = {
      type: 'output',
      content,
      metadata: { fromToolBuffer: true, tool: 'shell' },
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    // TOOL_OUTPUT_PREVIEW_LINES + TOOL_OUTPUT_TAIL_LINES = 200 + 50 = 250; 1000 - 250 = 750
    expect(frame).toMatch(/\(content continues;\s*750\s+lines omitted\)/);
  });

  it('shows omitted line count for default collapsed outputs', () => {
    const content = makeLines(200);
    const evt: any = {
      type: 'output',
      content,
      // no tool metadata, uses DEFAULT_COLLAPSE_LINES logic
    };
    const { lastFrame } = render(<EventLine event={evt} animationsEnabled={false} />);
    const frame = lastFrame();
    // Default branch uses 5 head + 3 tail = 8 lines shown; 200 - 8 = 192
    expect(frame).toMatch(/\(content continues;\s*192\s+lines omitted\)/);
  });
});
