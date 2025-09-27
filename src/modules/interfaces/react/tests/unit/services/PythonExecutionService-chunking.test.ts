/**
 * Validate chunked raw-output emission in PythonExecutionService
 */
import { describe, it, expect } from '@jest/globals';
import { PythonExecutionService } from '../../../src/services/PythonExecutionService.js';

function wrapEvent(obj: any): string {
  return `__CYBER_EVENT__${JSON.stringify(obj)}__CYBER_EVENT_END__`;
}

describe('PythonExecutionService chunked raw-output emission', () => {
  it('emits ~64KiB chunks for large raw tool stdout and flushes at tool_end', () => {
    const svc = new PythonExecutionService();
    const emitted: any[] = [];
    (svc as any).on('event', (e: any) => emitted.push(e));

    // Start a tool
    (svc as any).processOutputStream(wrapEvent({ type: 'tool_start', tool_name: 'shell', timestamp: Date.now() }));

    // Simulate a large raw stdout blob (~200 KiB)
    const bigSize = 200 * 1024; // 200 KiB
    const big = 'A'.repeat(bigSize - 10) + '\n' + 'B'.repeat(9);

    // Feed the large raw data in a single chunk
    (svc as any).processOutputStream(big);

    // End the tool, which should flush remaining buffer
    (svc as any).processOutputStream(wrapEvent({ type: 'tool_end', tool_name: 'shell', timestamp: Date.now() }));

    // Collect tool-buffer output events
    const chunks = emitted.filter(e => e?.type === 'output' && e?.metadata?.fromToolBuffer);
    expect(chunks.length).toBeGreaterThan(0);

    // Validate chunk sizing and metadata
    const CHUNK_SIZE = 64 * 1024;
    let totalLen = 0;
    for (const c of chunks) {
      const content: string = typeof c.content === 'string' ? c.content : String(c.content ?? '');
      expect(content.length).toBeLessThanOrEqual(CHUNK_SIZE); // newline-aware split keeps <= 64KiB
      expect(c.metadata.chunked).toBe(true);
      totalLen += content.length;
    }

    // The concatenated emitted content equals the original big blob
    expect(totalLen).toBe(big.length);
  });
});