/**
 * ExtendedTextInput bracketed paste tests
 */
import React from 'react';
import { render } from 'ink-testing-library';
import { describe, it, expect } from '@jest/globals';
import { ExtendedTextInput } from '../../../src/components/ExtendedTextInput.js';

const ESC = '\u001b';

describe.skip('ExtendedTextInput bracketed paste', () => {
  it('coalesces bracketed paste into a single onChange value', () => {
    let latest = '';
    const { stdin } = render(
      <ExtendedTextInput
        value=""
        onChange={(v) => { latest = v; }}
        onSubmit={() => {}}
        focus
      />
    );

    // Start bracketed paste
    stdin.write(`${ESC}[200~`);
    // Send text in several chunks
    stdin.write('hello ');
    stdin.write('world');
    stdin.write('!');
    // End bracketed paste
    stdin.write(`${ESC}[201~`);

    expect(latest).toBe('hello world!');
  });
});