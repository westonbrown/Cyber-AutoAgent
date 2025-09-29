#!/usr/bin/env node

/**
 * Operation Stream Simulation - Integration Test
 *
 * Uses TestExecutionService by setting CYBER_TEST_MODE=true and CYBER_TEST_EXECUTION=mock.
 * Verifies that step headers, reasoning, tool start/output, and overall stability occur.
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import os from 'os';
import path from 'path';

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
    CYBER_TEST_EXECUTION: 'mock',
  };

  const term = spawn('node', [appPath, '--headless', '--deployment-mode', 'local-cli'], {
    cols: 100, rows: 30, cwd: dirname(appPath), env
  });

  // In case React rendering swallows logs, also set DEBUG to force logger output
  try { env.DEBUG = 'true'; } catch {}

  let output = '';
  term.onData(d => output += d);

  try {
    await wait(800);

    // Start a guided flow to mount the terminal: set target and objective via commands
    term.write('target https://testphp.vulnweb.com');
    term.write('\r');
    await wait(400);
    term.write('objective focus on OWASP Top 10');
    term.write('\r');
    term.write('\r'); // Accept suggestion if dropdown captured first Enter
    await wait(500);
    term.write('execute');
    term.write('\r');
    term.write('\r'); // Accept suggestion if dropdown captured first Enter

    // Confirm safety warning (double confirmation)
    await wait(600);
    term.write('y');
    await wait(300);
    term.write('y');
    await wait(500);

    // Allow mock events to flow
    await wait(8000);

    // Assertions: look for expected substrings or test markers
    // Normalize output to strip ANSI and consolidate
    const clean = output.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '');

    const checks = [
      { name: 'Step headers', ok: /\[TEST_EVENT\] step_header|\[STEP\s+1|\[STEP|\[SWARM|operation/i.test(clean) },
      { name: 'Reasoning or output present', ok: /\[TEST_EVENT\]\s+(reasoning|output|tool_start|metrics_update)|Analyzing target|Finalizing|HTTP\/1\.1 200 OK|hello/i.test(clean) },
    ];

    const failed = checks.filter(c => !c.ok);
    if (failed.length > 0) {
      console.error('Operation stream simulation failed:\n', failed.map(f => ` - ${f.name}`).join('\n'));
      console.error('\n--- Captured output (first 1200 chars) ---\n');
      console.error(clean.substring(0, 1200));
      console.error('\n--- End captured output ---\n');
      process.exit(1);
    }

    console.log('Operation stream simulation passed');
    term.kill();
    process.exit(0);
  } catch (e) {
    console.error('Operation stream simulation errored:', e?.message || String(e));
    term.kill();
    process.exit(1);
  }
})();

