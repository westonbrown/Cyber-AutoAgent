/**
 * DirectDockerService auto-execute fallback tests
 */
import { describe, it, expect, jest, beforeEach, afterEach } from '@jest/globals';
import { DirectDockerService } from '../../../src/services/DirectDockerService.js';

function wrapEvent(obj: any): string {
  return `__CYBER_EVENT__${JSON.stringify(obj)}__CYBER_EVENT_END__`;
}

describe('DirectDockerService auto-execute fallback', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
  });

  it('sends execute if prompt not detected after operation_init', () => {
    const svc = new DirectDockerService();
    (svc as any).isExecutionActive = true;
    const writes: string[] = [];
    (svc as any).containerStream = { write: (s: string) => { writes.push(s); } };

    // operation_init should schedule fallback soon
    (svc as any).parseEvents(wrapEvent({ type: 'operation_init', operation_id: 'OP1', timestamp: Date.now() }));

    // Advance timers beyond fallback threshold (initial 1000ms + interval)
    jest.advanceTimersByTime(2000);

    // One of the writes should be 'execute\r\n'
    expect(writes.some(w => w.includes('execute\r\n'))).toBe(true);
  });
});