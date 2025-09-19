#!/usr/bin/env node

/**
 * Swarm Heavy Deduplication Integration Test
 *
 * Emits many repeated reasoning blocks for the same swarm agent across
 * several step headers. Asserts:
 *  - Only one accepted reasoning marker is emitted ([TEST_ONCE_REASONING])
 *  - Tool header for a normal tool appears in the stream
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
  const src = join(__dirname, '..', '..', 'src', 'index.tsx');
  const reactDir = join(__dirname, '..', '..');
  return { runner: 'npx', appPath: src, cwd: reactDir };
}

function writeHeavyEventsFile() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cyber-swarm-heavy-'));
  const file = path.join(tmpDir, 'events.jsonl');
  const lines = [];

  // Start swarm and step
  lines.push(JSON.stringify({ type: 'swarm_start', agent_names: ['sqli_specialist'], agent_count: 1, task: 'Heavy dedupe test', max_handoffs: 5, max_iterations: 10 }));
  lines.push(JSON.stringify({ type: 'step_header', is_swarm_operation: true, swarm_agent: 'sqli_specialist', swarm_sub_step: 1, swarm_total_iterations: 1, swarm_max_iterations: 10 }));

  const r = 'I will deepen SQLi findings by enumerating schema and testing privilege escalation.';

  // Repeat the exact same reasoning many times with different whitespace variants
  for (let i = 0; i < 3; i++) {
    lines.push(JSON.stringify({ type: 'reasoning', content: r, is_swarm_operation: true, swarm_agent: 'sqli_specialist' }));
  }
  lines.push(JSON.stringify({ type: 'step_header', is_swarm_operation: true, swarm_agent: 'sqli_specialist', swarm_sub_step: 2, swarm_total_iterations: 2, swarm_max_iterations: 10 }));
  for (let i = 0; i < 3; i++) {
    lines.push(JSON.stringify({ type: 'reasoning', content: '  ' + r + '  ', is_swarm_operation: true, swarm_agent: 'sqli_specialist' }));
  }
  lines.push(JSON.stringify({ type: 'step_header', is_swarm_operation: true, swarm_agent: 'sqli_specialist', swarm_sub_step: 3, swarm_total_iterations: 3, swarm_max_iterations: 10 }));
  for (let i = 0; i < 3; i++) {
    lines.push(JSON.stringify({ type: 'reasoning', content: r.replace(/\s+/g, ' '), is_swarm_operation: true, swarm_agent: 'sqli_specialist' }));
  }

  // Include one simple tool to ensure header/output still appear
  lines.push(JSON.stringify({ type: 'tool_start', tool_name: 'http_request', tool_input: { method: 'GET', url: 'http://example.com' }, swarm_agent: 'sqli_specialist' }));
  lines.push(JSON.stringify({ type: 'output', content: 'HTTP/1.1 200 OK', metadata: { fromToolBuffer: true } }));
  lines.push(JSON.stringify({ type: 'tool_invocation_end' }));

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
  const eventsPath = writeHeavyEventsFile();

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

  const term = spawn(runner, args, { cols: 100, rows: 30, cwd, env });
  let output = '';
  term.onData(d => output += d);

  try {
    // Give the app time to boot
    await wait(800);
    // Drive minimal flow like other integration tests
    term.write('target https://testphp.vulnweb.com');
    term.write('\r');
    await wait(300);
    term.write('objective swarm heavy dedupe');
    term.write('\r');
    await wait(300);
    term.write('execute');
    term.write('\r');
    // Confirm safety prompts (double)
    await wait(400);
    term.write('y');
    await wait(200);
    term.write('y');

    await wait(6000);
    const clean = output.replace(/\x1B\[[0-9;]*[A-Za-z]/g, '');

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
      console.error(clean.substring(0, 1400));
      process.exit(1);
    }

    console.log('Swarm heavy dedup integration test passed');
    term.kill();
    process.exit(0);
  } catch (e) {
    console.error('Swarm heavy dedup integration test errored:', e?.message || String(e));
    term.kill();
    process.exit(1);
  }
})();

