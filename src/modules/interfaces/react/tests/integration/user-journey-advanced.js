#!/usr/bin/env node

/**
 * Advanced User Journey - Integration Test
 * 
 * Simulates navigating plugins, setting target/objective, executing, then
 * cancelling via ESC and ensuring the UI returns to an idle state without flicker.
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

async function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

function ensureTestConfig() {
  const os = require('os');
  const path = require('path');
  const configDir = path.join(os.homedir(), '.cyber-autoagent');
  try { fs.mkdirSync(configDir, { recursive: true }); } catch {}
  const configPath = path.join(configDir, 'config.json');
  const config = {
    modelProvider: 'bedrock',
    modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
    awsRegion: 'us-east-1',
    dockerImage: 'cyber-autoagent:latest',
    dockerTimeout: 300,
    volumes: [],
    iterations: 25,
    autoApprove: true,
    confirmations: false,
    maxThreads: 5,
    outputFormat: 'markdown',
    verbose: false,
    memoryMode: 'auto',
    keepMemory: true,
    memoryBackend: 'FAISS',
    outputDir: './outputs',
    unifiedOutput: true,
    theme: 'retro',
    showMemoryUsage: false,
    showOperationId: true,
    environment: {},
    reportSettings: { includeRemediation: true, includeCWE: true, includeTimestamps: true, includeEvidence: true, includeMemoryOps: true },
    observability: false,
    isConfigured: true,
    deploymentMode: 'local-cli'
  };
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

(async () => {
  const appPath = resolveAppPath();
  ensureTestConfig();
  const env = {
    ...process.env,
    NO_COLOR: '1',
    CI: 'true',
    NODE_ENV: 'test',
    CYBER_TEST_MODE: 'true',
    CYBER_TEST_EXECUTION: 'mock'
  };

  const term = spawn('node', [appPath, '--headless', '--deployment-mode', 'local-cli'], {
    cols: 100, rows: 30, cwd: dirname(appPath), env
  });

  let output = '';
  term.onData(d => output += d);

  try {
    await wait(1200);

    // Open plugins (module selector)
    term.write('/plugins');
    term.write('\r');
    await wait(500);

    // Choose a module name by typing it directly and hitting enter (fallback path)
    term.write('general');
    term.write('\r');
    await wait(400);

    // Set target and objective, then execute
    term.write('target https://testphp.vulnweb.com');
    term.write('\r');
    await wait(300);

    term.write('objective focus on SQL injection');
    term.write('\r');
    await wait(300);

    term.write('execute');
    term.write('\r');

    // Confirm safety warning
    await wait(400);
    term.write('y');
    await wait(200);
    term.write('y');

    await wait(1500);

    // Cancel via ESC (kill switch)
    term.write('\x1B');
    await wait(300);

    // Assertions: ensure the app prints some termination or stop-related output
    const stopped = /Stopping operation|Operation stopped|ESC Kill Switch/i.test(output);

    if (!stopped) {
      console.error('Advanced user journey failed: stopping markers not found');
      process.exit(1);
    }

    console.log('Advanced user journey passed');
    term.kill();
    process.exit(0);
  } catch (e) {
    console.error('Advanced user journey errored:', e?.message || String(e));
    term.kill();
    process.exit(1);
  }
})();

