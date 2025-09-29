export type EmittedEvent = any;

export class EventStreamEmulator {
  private handlers: Record<string, ((e: EmittedEvent) => void)[]> = {};

  on(event: 'event' | 'complete' | 'stopped', handler: (e?: any) => void) {
    (this.handlers[event] ||= []).push(handler);
  }
  off(event: 'event' | 'complete' | 'stopped', handler: (e?: any) => void) {
    this.handlers[event] = (this.handlers[event] || []).filter(h => h !== handler);
  }
  emit(event: 'event' | 'complete' | 'stopped', payload?: any) {
    for (const h of this.handlers[event] || []) h(payload);
  }

  // Convenience helpers to emit common sequences
  operationInit(op: Partial<EmittedEvent> = {}) {
    this.emit('event', { type: 'operation_init', ...op });
  }
  stepHeader(step: number, extra: Partial<EmittedEvent> = {}) {
    this.emit('event', { type: 'step_header', step, ...extra });
  }
  toolStart(tool_name: string, args: any = {}, extra: Partial<EmittedEvent> = {}) {
    const ts = Date.now();
    this.emit('event', { type: 'tool_start', tool_name, tool_input: args, timestamp: new Date(ts).toISOString(), ...extra });
  }
  output(content: string, meta: any = {}) {
    this.emit('event', { type: 'output', content, metadata: meta });
  }
  toolEnd(tool_name: string, extra: Partial<EmittedEvent> = {}) {
    this.emit('event', { type: 'tool_end', toolName: tool_name, ...extra });
  }
  operationComplete(extra: Partial<EmittedEvent> = {}) {
    this.emit('event', { type: 'operation_complete', ...extra });
  }
}
