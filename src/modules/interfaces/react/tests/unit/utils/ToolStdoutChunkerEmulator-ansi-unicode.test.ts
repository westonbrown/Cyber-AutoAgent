/**
 * ANSI and Unicode safety tests for ToolStdoutChunkerEmulator
 */
import { describe, it, expect } from '@jest/globals';
import { chunkStdout } from '../../utils/ToolStdoutChunkerEmulator.js';

describe('ToolStdoutChunkerEmulator ANSI/Unicode safety', () => {
  it('does not split inside ANSI SGR escape sequence', () => {
    const input = 'abc' + '\x1b[31m' + 'XYZ' + '\x1b[0m' + 'end';
    // Force a boundary that would land mid-escape if not guarded
    const chunks = chunkStdout(input, 5, false);
    // First chunk should exclude the partial escape and end at 'abc'
    expect(chunks[0]).toBe('abc');
    // Second chunk should start with a full escape sequence
    expect(chunks[1].startsWith('\x1b[31m')).toBe(true);
    expect(chunks.join('')).toBe(input);
  });

  it('does not split surrogate pairs (e.g., emoji)', () => {
    const smile = '😀'; // surrogate pair in UTF-16
    const input = 'A' + smile + 'B';
    const chunks = chunkStdout(input, 2, false);
    // To avoid splitting the surrogate, first chunk should be just 'A'
    expect(chunks[0]).toBe('A');
    // Next chunk should start with the full emoji
    expect(chunks[1].startsWith(smile)).toBe(true);
    expect(chunks.join('')).toBe(input);
  });
});
