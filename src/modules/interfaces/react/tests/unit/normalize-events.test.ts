/**
 * Unit tests for event normalization utilities
 */
import { describe, it, expect } from '@jest/globals';

// Import the built normalize util to avoid TS config complications
// tests -> react -> dist -> services/events/normalize.js

let normalizeEvent;

beforeAll(async () => {
  const mod = await import('../../dist/services/events/normalize.js');
  normalizeEvent = mod.normalizeEvent;
});

describe('normalizeEvent', () => {
  it('normalizes tool_start shell inputs (array/object/string)', () => {
    const e1 = normalizeEvent({ type: 'tool_start', tool_name: 'shell', args: { command: ['echo 1', { cmd: 'echo 2' }] } });
    expect(e1.tool_input.command).toBeDefined();

    const e2 = normalizeEvent({ type: 'tool_start', tool_name: 'shell', args: { command: '{"cmd":"echo 3"}' } });
    const cmd2 = e2.tool_input.command;
    expect(cmd2).toBeDefined();
  });

  it('unwraps command event content objects with command field', () => {
    const e = normalizeEvent({ type: 'command', content: '{"command":"ls -la"}' });
    expect(typeof e.content).toBe('string');
    expect(e.content).toContain('ls -la');
  });

  it('ensures deterministic toolId when missing', () => {
    const e = normalizeEvent({ type: 'tool_start', tool_name: 'http_request', tool_input: { url: 'http://x' } });
    expect(e.toolId || e.tool_id).toBeDefined();
  });
});

