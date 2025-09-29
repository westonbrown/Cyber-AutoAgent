import { jest, describe, test, expect, beforeAll, afterAll, beforeEach, afterEach } from '@jest/globals';

/**
 * Jest Test Setup
 * Configure test environment for React components
 */

// Mock console.error to reduce noise from React warnings in tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: Invalid hook call') ||
       args[0].includes('Warning: Cannot update a component'))
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

// Set up global test environment (only in jsdom)
if (typeof (global as any).window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: jest.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(), // deprecated
      removeListener: jest.fn(), // deprecated
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });

  // Mock process.stdout for Ink components (avoid interfering with node-pty tests)
  Object.defineProperty(process, 'stdout', {
    value: {
      columns: 80,
      rows: 24,
      isTTY: true,
      write: jest.fn(),
    },
  });
}

// Global test timeout
jest.setTimeout(10000);