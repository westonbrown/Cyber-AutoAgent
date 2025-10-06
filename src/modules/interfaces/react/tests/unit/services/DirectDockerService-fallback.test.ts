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

  it('sends execute when interactive prompt detected in buffer', () => {
    const svc = new DirectDockerService();
    (svc as any).isExecutionActive = true;
    const writes: string[] = [];
    (svc as any).containerStream = { write: (s: string) => { writes.push(s); } };

    // Simulate receiving execute prompt in buffer
    const promptText = "Press Enter or type 'execute' to start assessment";
    (svc as any).streamEventBuffer = promptText;

    // Call handleInteractivePrompts which should detect the prompt
    (svc as any).handleInteractivePrompts();

    // Advance timers to trigger the delayed write
    jest.advanceTimersByTime(1000);

    // Should have sent 'execute\r\n'
    expect(writes.some(w => w.includes('execute\r\n'))).toBe(true);
  });
});