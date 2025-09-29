import { describe, it, expect } from '@jest/globals';
import { ByteBudgetRingBuffer } from '../../../src/utils/ByteBudgetRingBuffer.js';

type Ev = { type: string; content?: string };

describe('ByteBudgetRingBuffer', () => {
  it('enforces byte budget by evicting from the head', () => {
    const limit = 1024; // 1 KiB
    const buf = new ByteBudgetRingBuffer<Ev>(limit, (e) => (e.content ? e.content.length : 16));

    // Push 10 items of ~200 bytes => ~2000 bytes total, expect evictions
    for (let i = 0; i < 10; i++) {
      buf.push({ type: 'output', content: 'x'.repeat(200) + `_${i}` });
    }

    const arr = buf.toArray();
    const totalBytes = arr.reduce((acc, e) => acc + (e.content ? e.content.length : 16), 0);
    expect(totalBytes).toBeLessThanOrEqual(limit);
    // Ensure newer items remain; last item should be present
    expect(arr[arr.length - 1].content?.endsWith('_9')).toBe(true);
  });
});
