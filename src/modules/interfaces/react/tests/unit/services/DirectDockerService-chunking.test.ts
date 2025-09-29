/**
 * Validate chunked raw-output emission in DirectDockerService
 */
import { describe, it, expect } from '@jest/globals';
import { DirectDockerService } from '../../../src/services/DirectDockerService.js';

function wrapEvent(obj: any): string {
  return `__CYBER_EVENT__${JSON.stringify(obj)}__CYBER_EVENT_END__`;
}

describe('DirectDockerService chunked raw-output emission', () => {
  it('emits ~64KiB chunks for large raw tool stdout and flushes at tool_end', () => {
    const svc = new DirectDockerService();
    const emitted: any[] = [];
    (svc as any).on('event', (e: any) => emitted.push(e));

    // Begin with a tool_start structured event to enter tool execution phase
    (svc as any).parseEvents(wrapEvent({ type: 'tool_start', tool_name: 'python_repl', timestamp: Date.now() }));

    // Simulate a large raw stdout payload (~256 KiB)
    const bigSize = 256 * 1024;
    const big = 'X'.repeat(bigSize - 1) + '\n';

    // Feed the large raw data as non-structured output
    (svc as any).parseEvents(big);

    // Issue tool_end structured event to flush remainder
    (svc as any).parseEvents(wrapEvent({ type: 'tool_end', tool_name: 'python_repl', timestamp: Date.now() }));

    const chunks = emitted.filter(e => e?.type === 'output' && e?.metadata?.fromToolBuffer);
    expect(chunks.length).toBeGreaterThan(0);

    const CHUNK_SIZE = 64 * 1024;
    let totalLen = 0;
    for (const c of chunks) {
      const content: string = typeof c.content === 'string' ? c.content : String(c.content ?? '');
      expect(content.length).toBeLessThanOrEqual(CHUNK_SIZE);
      expect(c.metadata.chunked).toBe(true);
      totalLen += content.length;
    }

    expect(totalLen).toBe(big.length);
  });
});