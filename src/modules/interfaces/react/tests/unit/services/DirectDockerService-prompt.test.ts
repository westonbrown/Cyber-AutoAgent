/**
 * DirectDockerService prompt detection tests
 */
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { DirectDockerService } from '../../../src/services/DirectDockerService.js';

import { jest } from '@jest/globals';

describe('DirectDockerService prompt detection', () => {
  let svc: DirectDockerService;
  beforeEach(() => {
    jest.useFakeTimers();
    svc = new DirectDockerService();
    (svc as any).isExecutionActive = true;
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('detects execute prompt and writes execute to stdin (after delay)', () => {
    const writes: string[] = [];
    (svc as any).containerStream = { write: (s: string) => { writes.push(s); } };
    // Load buffer with prompt variant
    (svc as any).streamEventBuffer = 'Some text...\n◆ general > Press Enter or type "execute" to start assessment\n';
    // Trigger prompt handling directly
    (svc as any).handleInteractivePrompts();

    // Advance timers to fire the delayed write
    jest.advanceTimersByTime(600);

    expect(writes[0]).toBe('execute\r\n');
  });
});
