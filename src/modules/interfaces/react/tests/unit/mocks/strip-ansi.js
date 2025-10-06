/**
 * Mock for strip-ansi module
 * Used in tests to remove ANSI escape codes from strings
 */

export default function stripAnsi(string) {
  if (typeof string !== 'string') {
    throw new TypeError(`Expected a \`string\`, got \`${typeof string}\``);
  }

  // Remove ANSI escape codes
  return string.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, '');
}

// Also export as named export for compatibility
export { stripAnsi };
