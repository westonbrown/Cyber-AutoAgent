/**
 * Unit tests for tool formatter utility
 */
import { describe, it, expect } from '@jest/globals';

let toolFormatters;

beforeAll(async () => {
  const mod = await import('../../dist/utils/toolFormatters.js');
  toolFormatters = mod.toolFormatters;
});

describe('toolFormatters.shell', () => {
  it('formats simple string command', () => {
    const out = toolFormatters.shell({ command: 'echo hello' });
    expect(out).toContain('echo hello');
  });

  it('formats array of commands', () => {
    const out = toolFormatters.shell({ command: ['echo 1', 'echo 2'] });
    expect(out).toContain('echo 1');
    expect(out).toContain('echo 2');
  });

  it('formats nested object commands', () => {
    const out = toolFormatters.shell({ command: [{ command: 'ls -la' }, { args: ['-l', '/tmp'] }] });
    expect(out).toMatch(/ls -la|\["-l","\/tmp"\]/);
  });
});

