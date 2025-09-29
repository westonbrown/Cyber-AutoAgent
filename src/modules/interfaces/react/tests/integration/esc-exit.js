#!/usr/bin/env node
/*
 Quick integration test: start the CLI and press ESC to verify immediate exit at main screen.
 Exits with code 0 on success, 1 on failure.
*/
const { spawn } = require('node:child_process');

const ESC = Buffer.from([0x1b]);

const child = spawn(process.execPath, ['dist/index.js'], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: {
    ...process.env,
    // Ensure we don't auto-start tests or operations
    CYBER_TEST_MODE: '',
    CYBER_TEST_EXECUTION: '',
  },
});

let stdout = '';
let stderr = '';
let exited = false;

child.stdout.on('data', (d) => { stdout += d.toString(); });
child.stderr.on('data', (d) => { stderr += d.toString(); });

const timeoutMs = 8000;
const earlyKeyDelay = 900; // allow screen to render prompt

const timer = setTimeout(() => {
  if (!exited) {
    try { child.kill('SIGKILL'); } catch {}
  }
  console.error('[ESC-EXIT-TEST] Timeout waiting for process to exit.');
  console.error('--- STDOUT ---');
  console.error(stdout);
  console.error('--- STDERR ---');
  console.error(stderr);
  process.exit(1);
}, timeoutMs);

child.on('exit', (code, signal) => {
  exited = true;
  clearTimeout(timer);
  if (code === 0 || signal === 'SIGTERM' || signal === 'SIGKILL') {
    console.log('[ESC-EXIT-TEST] Process exited (code:', code, 'signal:', signal, ').');
    process.exit(0);
  } else {
    console.error('[ESC-EXIT-TEST] Process exited with failure (code:', code, 'signal:', signal, ').');
    console.error('--- STDOUT ---');
    console.error(stdout);
    console.error('--- STDERR ---');
    console.error(stderr);
    process.exit(1);
  }
});

setTimeout(() => {
  try {
    child.stdin.write(ESC);
  } catch (e) {
    console.error('[ESC-EXIT-TEST] Failed to write ESC to stdin:', e);
  }
}, earlyKeyDelay);

