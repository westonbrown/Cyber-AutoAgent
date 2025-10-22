/**
 * Unknown tool generic rendering tests (UI-side replication of #63)
 *
 * Verifies that StreamDisplay renders unregistered tool names (e.g., nmap/whatweb)
 * using the default formatter without crashing, so the header/params appear even
 * when backend rejects execution. This reproduces the UI portion of the failure
 * mode and guards against regressions when routing is fixed backend-side.
 */
import { describe, it, expect, jest, afterEach } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';

async function importEventLine() {
  jest.resetModules();
  const mod: any = await import('../../../src/components/StreamDisplay.tsx');
  return mod.EventLine as React.FC<any>;
}

describe('Unknown tool generic display', () => {
  afterEach(() => jest.resetModules());

  it('renders generic header and structured params for tool: nmap', async () => {
    const EventLine = await importEventLine();
    const event = {
      type: 'tool_start',
      tool_name: 'nmap',
      tool_input: {
        target: 'http://20.52.255.203:8084',
        options: '-sC -sV -oN /app/outputs/OP_x/artifacts/nmap_scan.txt'
      }
    };

    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame() || '';

    expect(out).toMatch(/tool:\s+nmap/i);
    expect(out).toMatch(/target:\s+http:\/\/20\.52\.255\.203:8084/i);
    expect(out).toMatch(/options:\s+-sC/i);
  });

  it('renders generic header and url param for tool: whatweb', async () => {
    const EventLine = await importEventLine();
    const event = {
      type: 'tool_start',
      tool_name: 'whatweb',
      tool_input: {
        url: 'http://20.52.255.203:8084/'
      }
    };

    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame() || '';

    expect(out).toMatch(/tool:\s+whatweb/i);
    expect(out).toMatch(/url:\s+http:\/\/20\.52\.255\.203:8084\//i);
  });
});