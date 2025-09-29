/**
 * PythonExecutionService single-line chunking (no newline) tests
 */
import { describe, it, expect } from '@jest/globals';
import { PythonExecutionService } from '../../../src/services/PythonExecutionService.js';

function wrapEvent(obj: any): string {
  return `__CYBER_EVENT__${JSON.stringify(obj)}__CYBER_EVENT_END__`;
}

describe('PythonExecutionService single-line chunking', () => {
  it('splits very long single line into 64KiB chunks', () => {
    const svc = new PythonExecutionService();
    const emitted: any[] = [];
    (svc as any).on('event', (e: any) => emitted.push(e));

    (svc as any).processOutputStream(wrapEvent({ type: 'tool_start', tool_name: 'shell', timestamp: Date.now() }));

    const total = 300 * 1024; // 300 KiB
    const big = 'Z'.repeat(total); // no newline
    (svc as any).processOutputStream(big);
    (svc as any).processOutputStream(wrapEvent({ type: 'tool_end', tool_name: 'shell', timestamp: Date.now() }));

    const chunks = emitted.filter(e => e?.type === 'output' && e?.metadata?.fromToolBuffer);
    expect(chunks.length).toBeGreaterThan(0);

    const CHUNK_SIZE = 64 * 1024;
    let totalLen = 0;
    for (const c of chunks) {
      const content: string = typeof c.content === 'string' ? c.content : String(c.content ?? '');
      expect(content.length).toBeLessThanOrEqual(CHUNK_SIZE);
      totalLen += content.length;
    }
    expect(totalLen).toBe(total);
  });
});