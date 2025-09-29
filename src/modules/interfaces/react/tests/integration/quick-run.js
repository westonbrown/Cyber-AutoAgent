#!/usr/bin/env node

/**
 * Test runner to execute multiple integration tests quickly
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function run(script) {
  return new Promise((resolve) => {
    const term = spawn('node', [join(__dirname, script)], { cols: 100, rows: 30 });
    term.onExit(() => resolve());
  });
}

(async () => {
  await run('headless-auto-run.js');
})();

