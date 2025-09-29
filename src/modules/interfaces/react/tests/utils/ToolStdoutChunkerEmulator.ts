function isHighSurrogate(code: number) {
  return code >= 0xd800 && code <= 0xdbff;
}
function isLowSurrogate(code: number) {
  return code >= 0xdc00 && code <= 0xdfff;
}

// Attempt to avoid splitting inside ANSI SGR sequences (e.g., "\x1b[31m")
function adjustEndForAnsi(input: string, start: number, end: number): number {
  // Look back a small window for ESC sequences
  const lookback = Math.min(64, end - start);
  const windowStart = end - lookback;
  const windowStr = input.slice(windowStart, end);
  const escIndex = windowStr.lastIndexOf("\x1b[");
  if (escIndex >= 0) {
    // We found a CSI sequence start within the window. If the sequence end (final byte 0x40-0x7E)
    // does not occur before the boundary, we're mid-sequence. Backtrack to the ESC position.
    const seqStart = windowStart + escIndex;
    const afterSeq = input.slice(seqStart, end);
    // A very loose check: if we haven't encountered a final byte like 'm', 'K', etc., treat as open
    const hasFinal = /[\x40-\x7E]/.test(afterSeq.slice(2)); // skip ESC[
    if (!hasFinal) {
      // Only backtrack if it doesn't collapse the chunk to empty
      if (seqStart > start) {
        return seqStart;
      }
    }
  }
  return end;
}

// Avoid splitting Unicode surrogate pairs at the boundary
function adjustEndForUnicode(input: string, start: number, end: number): number {
  if (end <= start || end >= input.length) return end;
  const prev = input.charCodeAt(end - 1);
  const next = input.charCodeAt(end);
  if (isHighSurrogate(prev) && isLowSurrogate(next)) {
    return end - 1; // back up one to not cut the pair
  }
  return end;
}

export function chunkStdout(input: string, size = 64 * 1024, preferNewline = true): string[] {
  const chunks: string[] = [];
  let i = 0;
  while (i < input.length) {
    let end = Math.min(i + size, input.length);

    if (preferNewline) {
      const slice = input.slice(i, end);
      // Try to backtrack to last newline within the slice for nicer boundaries
      const lastNL = slice.lastIndexOf('\n');
      if (lastNL > 0 && end - i > 1024) {
        end = i + lastNL + 1;
      }
    }

    // Safety adjustments for ANSI sequences and Unicode pairs
    end = adjustEndForAnsi(input, i, end);
    end = adjustEndForUnicode(input, i, end);

    // Ensure forward progress
    if (end <= i) {
      end = Math.min(i + Math.max(1, size), input.length);
    }

    chunks.push(input.slice(i, end));
    i = end;
  }
  return chunks;
}
