/**
 * Snapshot-like rendering tests for EventLine across common events and widths
 */
import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';

// Helper to (re)import EventLine with a specific terminal width
async function importEventLineWithWidth(width: number) {
  // Patch process.stdout.columns before module import
  try {
    Object.defineProperty(process.stdout, 'columns', { value: width, configurable: true });
  } catch {}
  jest.resetModules();
  const mod: any = await import('../../../src/components/StreamDisplay.tsx');
  return mod.EventLine as React.FC<any>;
}

describe('EventLine snapshot-style rendering', () => {
  const widths = [60, 120];

  afterEach(() => {
    jest.resetModules();
  });

  it.each(widths)('renders shell tool header and command preview (width=%s)', async (w) => {
    const EventLine = await importEventLineWithWidth(w as number);
    const event = {
      type: 'tool_start',
      tool_name: 'shell',
      tool_input: { command: 'echo Hello' },
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/tool:\s+shell/i);
    expect(out).toMatch(/echo Hello/i);
  });

  it.each(widths)('renders http_request tool header with method and url (width=%s)', async (w) => {
    const EventLine = await importEventLineWithWidth(w as number);
    const event = {
      type: 'tool_start',
      tool_name: 'http_request',
      tool_input: { method: 'GET', url: 'http://example.com' },
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/tool:\s+http_request/i);
    expect(out).toMatch(/GET/i);
    expect(out).toMatch(/example\.com/i);
  });

  it.each(widths)('renders reasoning block (width=%s)', async (w) => {
    const EventLine = await importEventLineWithWidth(w as number);
    const event = {
      type: 'reasoning',
      content: 'Analyzing target for vulnerabilities...'
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/reasoning/i);
    expect(out).toMatch(/Analyzing target/i);
  });

  it.each(widths)('renders swarm step header with agent (width=%s)', async (w) => {
    const EventLine = await importEventLineWithWidth(w as number);
    const event = {
      type: 'step_header',
      step: 2,
      maxSteps: 100,
      is_swarm_operation: true,
      swarm_agent: 'recon_specialist',
      swarm_sub_step: 2,
      swarm_total_iterations: 2,
      swarm_max_iterations: 30,
    } as any;
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/\[SWARM:/i);
    expect(out).toMatch(/RECON[ _]SPECIALIST/i);
    expect(out).toMatch(/STEP\s+2/i);
  });
});
