#!/usr/bin/env node

/**
 * Swarm Deduplication Integration Test
 *
 * Uses TestExecutionService (mock execution) with a custom JSONL event file to simulate
 * a swarm operation where the same reasoning block is emitted multiple times across
 * step/context changes for the same agent. Asserts:
 *  - The reasoning text appears only once in the terminal output (deduped)
 *  - A proper tool header is rendered before the tool output for swarm agents
 */

import { spawn } from 'node-pty';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import os from 'os';
import path from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

function resolveAppTarget() {
  const dist = join(__dirname, '..', '..', 'dist', 'index.js');
  if (fs.existsSync(dist)) {
    return { runner: 'node', appPath: dist, cwd: dirname(dist) };
  }
  // Fallback to dev runner using tsx without building the whole project
  const src = join(__dirname, '..', '..', 'src', 'index.tsx');
  const reactDir = join(__dirname, '..', '..');
  return { runner: 'npx', appPath: src, cwd: reactDir };
}

function writeSwarmEventsFile() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cyber-swarm-'));
  const file = path.join(tmpDir, 'events.jsonl');
  const lines = [];

  // Start a swarm with two agents
  lines.push(JSON.stringify({
    type: 'swarm_start',
    agent_names: ['auth_specialist', 'injection_specialist'],
    agent_count: 2,
    task: 'Simulated swarm run',
    max_handoffs: 10,
    max_iterations: 10
  }));

  // Step header for auth_specialist
  lines.push(JSON.stringify({
    type: 'step_header',
    is_swarm_operation: true,
    swarm_agent: 'auth_specialist',
    swarm_sub_step: 1,
    swarm_total_iterations: 1,
    swarm_max_iterations: 10,
    operation: 'OP_TEST_SWARM',
    duration: '1s'
  }));

  // Tool start for agent
  lines.push(JSON.stringify({
    type: 'tool_start',
    tool_name: 'http_request',
    tool_id: 't-http-1',
    tool_input: { method: 'GET', url: 'http://example.com' },
    swarm_agent: 'auth_specialist'
  }));

  // Tool output
  lines.push(JSON.stringify({
    type: 'output',
    content: 'HTTP/1.1 200 OK',
    metadata: { fromToolBuffer: true, tool: 'http_request' },
    tool_id: 't-http-1',
    swarm_agent: 'auth_specialist'
  }));

  // Tool end
  lines.push(JSON.stringify({
    type: 'tool_invocation_end',
    success: true,
    tool_name: 'http_request',
    tool_id: 't-http-1',
    swarm_agent: 'auth_specialist'
  }));

  // Reasoning for auth_specialist (first emission)
  const rtext = 'I will test authentication flow using test/test credentials.';
  lines.push(JSON.stringify({ type: 'reasoning', content: rtext, swarm_agent: 'auth_specialist', is_swarm_operation: true }));

  // Next swarm step header (context changes)
  lines.push(JSON.stringify({
    type: 'step_header',
    is_swarm_operation: true,
    swarm_agent: 'auth_specialist',
    swarm_sub_step: 2,
    swarm_total_iterations: 2,
    swarm_max_iterations: 10,
    operation: 'OP_TEST_SWARM',
    duration: '2s'
  }));

  // Repeat identical reasoning for same agent (should be deduped)
  lines.push(JSON.stringify({ type: 'reasoning', content: rtext, swarm_agent: 'auth_specialist', is_swarm_operation: true }));

  fs.writeFileSync(file, lines.join('\n'), 'utf-8');
  return file;
}

function ensureTestConfig() {
  const configDir = path.join(os.homedir(), '.cyber-autoagent');
  try { fs.mkdirSync(configDir, { recursive: true }); } catch {}
  const configPath = path.join(configDir, 'config.json');
  const config = {
    modelProvider: 'bedrock',
    modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
    awsRegion: 'us-east-1',
    iterations: 5,
    confirmations: false,
    outputDir: './outputs',
    isConfigured: true,
    deploymentMode: 'local-cli'
  };
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

async function wait(ms) { return new Promise((r) => setTimeout(r, ms)); }

(async () => {
  const { runner, appPath, cwd } = resolveAppTarget();
  ensureTestConfig();
  const eventsPath = writeSwarmEventsFile();

  const env = {
    ...process.env,
    NO_COLOR: '1',
    CI: 'true',
    NODE_ENV: 'test',
    CYBER_TEST_MODE: 'true',
    CYBER_TEST_EXECUTION: 'mock',
    CYBER_TEST_EVENTS_PATH: eventsPath,
  };

  const args = runner === 'node'
    ? [appPath, '--headless', '--deployment-mode', 'local-cli']
    : ['-y', 'tsx', appPath, '--headless', '--deployment-mode', 'local-cli'];
  const term = spawn(runner, args, {
    cols: 100, rows: 30, cwd, env
  });

  let output = '';
  term.onData(d => output += d);

  try {
    // Let the app bootstrap and stream events
    await wait(3500);

    const clean = output.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '');

    // Assertions
    const hasToolHeader = /tool:\s*http_request/i.test(clean);
    const hasToolOutput = /HTTP\/1\.1\s+200\s+OK/i.test(clean);

    const onceMarks = (clean.match(/\[TEST_ONCE_REASONING\]/g) || []).length;

    if (!hasToolHeader) {
      console.error('Expected tool header for http_request not found');
      console.error(clean.substring(0, 800));
      process.exit(1);
    }
    if (!hasToolOutput) {
      console.error('Expected tool output not found');
      console.error(clean.substring(0, 800));
      process.exit(1);
    }
    if (onceMarks !== 1) {
      console.error(`Expected exactly one accepted reasoning marker, but found ${onceMarks}`);
      console.error(clean.substring(0, 1200));
      process.exit(1);
    }

    console.log('Swarm dedup integration test passed');
    term.kill();
    process.exit(0);
  } catch (e) {
    console.error('Swarm dedup integration test errored:', e?.message || String(e));
    term.kill();
    process.exit(1);
  }
})();
