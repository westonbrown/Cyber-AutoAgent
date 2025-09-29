#!/usr/bin/env node

/**
 * Headless Auto-Run Integration Test
 *
 * Validates that the app can start in headless mode, accept basic commands,
 * open the configuration editor, and exit cleanly.
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));

function resolveAppPath() {
  const candidates = [
    join(__dirname, '..', '..', 'dist', 'index.js'),
    join(__dirname, '..', 'dist', 'index.js'),
  ];
  for (const p of candidates) {
    try { if (fs.existsSync(p)) return p; } catch {}
  }
  return candidates[0];
}

(async () => {
  const appPath = resolveAppPath();
  const term = spawn('node', [appPath, '--headless'], {
    cols: 100,
    rows: 30,
    cwd: dirname(appPath),
    env: { ...process.env, NO_COLOR: '1', CI: 'true', CYBER_TEST_MODE: 'true' }
  });

  let output = '';
  term.onData(d => output += d);

  const wait = (ms) => new Promise(r => setTimeout(r, ms));

  try {
    await wait(1200);

    // Open config
    term.write('/config');
    term.write('\r');
    await wait(1200);

    if (!/Configuration Editor/i.test(output)) {
      console.error('Config editor did not open');
      process.exit(1);
    }

    // Close
    term.write('\x1B');
    await wait(500);

    // Clear screen: send ESC again to exit config if needed
    term.write('\x1B');
    await wait(300);

    // Basic assertion: app remained responsive and no fatal error
    if (/TypeError|ReferenceError|Unhandled/i.test(output)) {
      console.error('Fatal error detected in output');
      process.exit(1);
    }

    console.log('Headless auto-run test passed');
    term.kill();
    process.exit(0);
  } catch (err) {
    console.error('Headless auto-run test failed:', err?.message || String(err));
    term.kill();
    process.exit(1);
  }
})();

