/**
 * Tests for ToolStdoutChunkerEmulator chunking behavior
 */
import { describe, it, expect } from '@jest/globals';
import { chunkStdout } from '../../utils/ToolStdoutChunkerEmulator.js';

describe('ToolStdoutChunkerEmulator', () => {
  it('splits at newline when preferNewline and large enough slice', () => {
    const a = 'a'.repeat(1500);
    const b = 'b'.repeat(100);
    const input = `${a}\n${b}`;
    const chunks = chunkStdout(input, 1600, true);
    expect(chunks.length).toBe(2);
    expect(chunks[0].endsWith('\n')).toBe(true);
    expect(chunks[0].length).toBe(1501); // 1500 a's + newline
    expect(chunks[1]).toBe(b);
  });

  it('does not split at newline when preferNewline=false', () => {
    const a = 'a'.repeat(1500);
    const b = 'b'.repeat(100);
    const input = `${a}\n${b}`;
    const chunks = chunkStdout(input, 1600, false);
    // First chunk should be exactly size-limited (1600)
    expect(chunks[0].length).toBe(1600);
    expect(chunks.join('')).toBe(input);
  });

  it('handles newline-free large input by size', () => {
    const input = 'x'.repeat(7000);
    const chunks = chunkStdout(input, 2048, true);
    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.join('')).toBe(input);
  });
});
