/**
 * Ensure overflowReducer is used for oversized items
 */
import { describe, it, expect } from '@jest/globals';
import { ByteBudgetRingBuffer } from '../../../src/utils/ByteBudgetRingBuffer.js';

type Ev = { type: string; content?: string };

describe('ByteBudgetRingBuffer overflowReducer', () => {
  it('reduces oversized item via overflowReducer to fit budget', () => {
    const limit = 1024; // 1 KiB budget
    const buf = new ByteBudgetRingBuffer<Ev>(limit, {
      estimator: (e) => (e.content ? e.content.length : 16),
      overflowReducer: (e) => {
        if (e.type === 'output' && e.content && e.content.length > 2000) {
          return { type: 'output', content: e.content.slice(0, 600) + '\n... (content trimmed due to memory budget)\n' + e.content.slice(-300) };
        }
        return e;
      }
    });

    // Create a single item that is larger than the budget
    const big = { type: 'output', content: 'X'.repeat(5000) };
    buf.push(big);

    const arr = buf.toArray();
    expect(arr.length).toBe(1);
    expect(arr[0].content).toContain('content trimmed due to memory budget');
    // Ensure it now fits the budget
    const totalBytes = arr.reduce((acc, e) => acc + (e.content ? e.content.length : 16), 0);
    expect(totalBytes).toBeLessThanOrEqual(limit);
  });
});
