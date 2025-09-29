/**
 * Mock for the node-pty module (ESM version).
 * 
 * This mock provides a fake implementation of the `spawn` function,
 * returning an object with methods that can be spied on in tests.
 */
import { jest } from '@jest/globals';

// Export a `spawn` function directly to match `import { spawn } from 'node-pty'`
export const spawn = jest.fn((_file, _args, _opts) => {
  let onDataCallback = null;
  let state = 'WELCOME'; // Initial state

  return {
    onData: jest.fn((callback) => {
      onDataCallback = callback;
      // Simulate initial output
      if (onDataCallback && state === 'WELCOME') {
        onDataCallback('Welcome to the Cyber-AutoAgent CLI!');
      }
    }),
    write: jest.fn((data) => {
      if (!onDataCallback) return;

      // Handle /config command after setup is complete
      if (data === '/config' && state === 'COMPLETED') {
        state = 'CONFIG_EDITOR';
        onDataCallback('Configuration Editor');
        return;
      }

      // Handle Enter key for state transitions
      if (data === '\r') {
        switch (state) {
          case 'WELCOME':
            state = 'DEPLOYMENT_MODE';
            onDataCallback('Select Deployment Mode');
            break;
          case 'DEPLOYMENT_MODE':
            state = 'INSTALLING';
            onDataCallback('Setting up dependencies...');
            // Simulate the completion of the setup process
            setTimeout(() => {
              if (onDataCallback) {
                state = 'COMPLETED';
                onDataCallback('Setup completed!');
              }
            }, 50);
            break;
        }
      }
    }),
    onExit: jest.fn(),
    kill: jest.fn(),
    resize: jest.fn(),
  };
});

// Also provide a default export for `import pty from 'node-pty'`
export default {
  spawn,
};
