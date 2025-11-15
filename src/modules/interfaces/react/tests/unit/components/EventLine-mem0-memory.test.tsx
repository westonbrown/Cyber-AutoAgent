/**
 * Render mem0_memory store/retrieve headers to verify formatting and content previews
 */
import { describe, it, expect, jest, afterEach } from '@jest/globals';
import React from 'react';
import { render } from 'ink-testing-library';

async function importEventLine() {
  jest.resetModules();
  const mod: any = await import('../../../src/components/StreamDisplay.tsx');
  return mod.EventLine as React.FC<any>;
}

describe('EventLine mem0_memory formatting', () => {
  afterEach(() => jest.resetModules());

  it('shows store action with content preview', async () => {
    const EventLine = await importEventLine();
    const event = {
      type: 'tool_start',
      tool_name: 'mem0_memory',
      tool_input: { action: 'store', content: 'note: sql injection vector at /search' }
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/tool:\s+mem0_memory/i);
    expect(out).toMatch(/action:\s+storing/i);
    expect(out).toMatch(/content|query/i);
    expect(out).toMatch(/sql injection/i);
  });

  it('shows retrieve action with query preview', async () => {
    const EventLine = await importEventLine();
    const event = {
      type: 'tool_start',
      tool_name: 'mem0_memory',
      tool_input: { action: 'retrieve', query: 'find: injection' }
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/tool:\s+mem0_memory/i);
    expect(out).toMatch(/action:\s+retrieving/i);
    expect(out).toMatch(/find: injection/i);
  });

  it('shows compact preview for TOON plans', async () => {
    const EventLine = await importEventLine();
    const plan = `plan_overview[1]{objective,current_phase,total_phases}:
  Harden portal,2,3
plan_phases[3]{id,title,status,criteria}:
  1,Recon,done,map services
  2,Testing,active,validate IDOR paths
  3,Exploit,pending,extract flag`;
    const event = {
      type: 'tool_start',
      tool_name: 'mem0_memory',
      tool_input: { action: 'store_plan', content: plan }
    };
    const { lastFrame } = render(React.createElement(EventLine, { event, animationsEnabled: false }));
    const out = lastFrame();
    expect(out).toMatch(/plan:\s+Harden portal/i);
    expect(out).toMatch(/Phase 2\/3/i);
  });
});
