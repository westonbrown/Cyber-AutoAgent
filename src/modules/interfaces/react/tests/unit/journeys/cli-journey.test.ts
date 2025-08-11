/**
 * @jest-environment node
 */
import path from 'path';
import fs from 'fs';
import os from 'os';
import { spawn } from 'node-pty';
import { jest, describe, test, expect, beforeAll } from '@jest/globals';
import { fileURLToPath } from 'url';

// Define __dirname in ES module scope
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

jest.setTimeout(30000);

const capturesDir = path.join(__dirname, '..', '..', 'fixtures', 'captures', 'journeys');
const appDist = path.join(__dirname, '..', '..', '..', 'dist', 'index.js');

function ensureDir(p: string) {
  fs.mkdirSync(p, { recursive: true });
}

function writeCapture(name: string, content: string) {
  ensureDir(capturesDir);
  const filename = path.join(capturesDir, name);
  fs.writeFileSync(filename, content);
}

type PtySession = {
  term: any;
  output: string;
};

function startCli(extraEnv: Record<string,string> = {}): PtySession {
  const env = {
    ...process.env,
    NO_COLOR: '1',
    CI: 'true',
    NODE_ENV: 'test',
    CYBER_TEST_MODE: 'true',
    ...extraEnv,
  } as any;

  const term = spawn('node', [appDist, '--headless'], {
    name: 'xterm-256color',
    cols: 100,
    rows: 30,
    cwd: path.dirname(appDist),
    env,
  });

  let output = '';
  term.onData((d: string) => (output += d));
  return { term, output };
}

async function wait(ms: number) {
  await new Promise((r) => setTimeout(r, ms));
}

const Keys = {
  ENTER: '\r',
  ESC: '\x1B',
  TAB: '\t',
  SPACE: ' ',
  UP: '\x1B[A',
  DOWN: '\x1B[B',
  LEFT: '\x1B[D',
  RIGHT: '\x1B[C',
  CTRL_S: '\x13',
};

function setTestConfig(config: Record<string, any> | null) {
  const configDir = path.join(os.homedir(), '.cyber-autoagent');
  ensureDir(configDir);
  const configPath = path.join(configDir, 'config.json');
  if (config === null) {
    if (fs.existsSync(configPath)) fs.unlinkSync(configPath);
    return;
  }
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

/**
 * First-time setup journey: welcome -> select local cli -> progress -> done
 */
describe('CLI Journey - First-time setup and config editor', () => {
  beforeAll(() => {
    ensureDir(capturesDir);
  });

  test('first launch flow captures screens and completes without crash', async () => {
    setTestConfig(null);
    const { term } = startCli();

    // Start capturing immediately to avoid missing early output
    let cumulative = '';
    term.onData((d: string) => {
      cumulative += d;
    });

    // allow boot render
    await wait(1200);
    let snapshotIndex = 0;
    const snap = async (label: string) => {
      const file = `${String(snapshotIndex).padStart(3, '0')}-${label}.txt`;
      snapshotIndex += 1;
      // take a synchronous dump by requesting cursor position (nudge output)
      term.write('');
      await wait(150);
      // @ts-ignore captured in closure updated by onData
      // eslint-disable-next-line no-undef
      writeCapture(file, (term as any)._decoder ? '' : '');
    };

    // Workaround: read screen using private buffer is not available; keep cumulative output

    const capture = async (label: string) => {
      const file = `${String(snapshotIndex).padStart(3, '0')}-${label}.txt`;
      snapshotIndex += 1;
      writeCapture(file, cumulative);
    };

    // Allow the PTY listener to receive buffered output before first assertion
    await capture('welcome');
    await wait(200);
    expect(cumulative).toContain('Welcome');

    // proceed to mode selection
    term.write(Keys.ENTER);
    await wait(1200);
    await capture('deployment-selection');
    expect(cumulative).toMatch(/Select Deployment Mode|Deployment Mode/i);

    // select Local CLI (default) and continue
    term.write(Keys.ENTER);
    await wait(800);
    await capture('progress');
    expect(cumulative).toMatch(/Setting up|Checking|Installing|Preparing/i);

    // wait for completion message
    const start = Date.now();
    let doneSeen = false;
    while (Date.now() - start < 15000) {
      if (/setup completed|completed successfully|Ready/i.test(cumulative)) { doneSeen = true; break; }
      await wait(300);
    }
    await capture('completed');
    expect(doneSeen).toBe(true);

    // Open config editor from main with /config
    term.write('/config');
    term.write(Keys.ENTER);
    await wait(1500);
    await capture('config-editor-open');
    expect(cumulative).toContain('Configuration Editor');

    // Expand first section, navigate a field, try save
    term.write(Keys.ENTER);
    await wait(200);
    term.write(Keys.TAB);
    await wait(200);
    term.write(Keys.CTRL_S);
    await wait(400);
    await capture('config-editor-after-save');

    // Exit with double ESC
    term.write(Keys.ESC);
    await wait(150);
    term.write(Keys.ESC);
    await wait(300);
    await capture('back-to-main');

    term.kill();
  });
});
