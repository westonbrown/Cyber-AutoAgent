/**
 * Event Aggregator - Simplified for new reasoning approach
 * Python backend now handles reasoning accumulation and emits complete blocks
 */

import { DisplayStreamEvent } from '../components/StreamDisplay.js';

export class EventAggregator {
  private outputBuffer: string[] = [];
  private reasoningBuffer: string[] = [];
  private currentToolId?: string;
  private lastEventType?: string;
  private activeThinking: boolean = false;
  private activeReasoningSession: boolean = false;
  
  // Command buffering delay constant  
  private readonly COMMAND_BUFFER_MS = 100; // Short delay to collect all commands
  
  // Prevent duplicate outputs
  private lastOutputContent: string = '';
  private outputDedupeTimeMs = 1000; // 1 second window for deduplication
  private lastOutputTime: number = 0;
  
  // Legacy methods for backward compatibility with DirectTerminal
  hasPendingEvents(): boolean {
    return false; // No longer buffering events
  }
  
  flushPendingEvents(): DisplayStreamEvent[] {
    return []; // No pending events to flush
  }
  
  flush(): DisplayStreamEvent[] {
    return []; // No buffered events to flush
  }
  
  processEvent(event: any): DisplayStreamEvent[] {
    const results: DisplayStreamEvent[] = [];
    
    switch (event.type) {
      case 'step_header':
        // End any active reasoning session
        this.activeReasoningSession = false;
        
        // Backend now emits step headers at the correct time (after reasoning)
        // Just emit step header immediately
        results.push({
          type: 'step_header',
          step: event.step,
          maxSteps: event.maxSteps,
          operation: event.operation,
          duration: event.duration,
          // Include swarm-related properties if present
          is_swarm_operation: event.is_swarm_operation,
          swarm_agent: event.swarm_agent,
          swarm_context: event.swarm_context
        } as DisplayStreamEvent);
        
        // End reasoning session after step header
        this.activeReasoningSession = false;
        break;
        
      case 'reasoning':
        // Python backend now sends complete reasoning blocks - no buffering needed
        if (event.content && event.content.trim()) {
          // Clear any active thinking animations when reasoning is shown
          if (this.activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            this.activeThinking = false;
          }
          
          // Start reasoning session
          this.activeReasoningSession = true;
          
          // Emit the complete reasoning block directly
          results.push({
            type: 'reasoning',
            content: event.content.trim()
          } as DisplayStreamEvent);
        }
        break;
        
      case 'reasoning_delta':
        // Legacy reasoning delta events - no longer used since Python sends complete blocks
        // Ignore these events
        break;
        
      case 'thinking':
        // Handle thinking start without conflicting with reasoning
        if (!this.activeReasoningSession && !this.activeThinking) {
          this.activeThinking = true;
          results.push({
            type: 'thinking',
            context: event.context,
            startTime: event.startTime,
            metadata: event.metadata
          } as DisplayStreamEvent);
        }
        break;
        
      case 'thinking_end':
        if (this.activeThinking) {
          this.activeThinking = false;
          results.push({
            type: 'thinking_end'
          } as DisplayStreamEvent);
        }
        break;
        
      case 'delayed_thinking_start':
        // Handle delayed thinking start - pass through and mark as active
        if (!this.activeThinking && !this.activeReasoningSession) {
          this.activeThinking = true; // Mark as active so it can be stopped later
          results.push(event as DisplayStreamEvent);
        }
        break;
        
      case 'tool_start':
        // Clear any active thinking when tool starts
        if (this.activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          this.activeThinking = false;
        }
        
        this.currentToolId = event.toolId;
        
        results.push({
          type: 'tool_start',
          tool_name: event.toolName || event.tool_name || '',
          tool_input: event.args || event.tool_input || {},
          toolId: event.toolId,
          toolName: event.toolName
        } as DisplayStreamEvent);
        break;
        
      case 'shell_command':
        results.push({
          type: 'shell_command',
          command: event.command,
          toolId: this.currentToolId,
          id: `shell_${Date.now()}`,
          timestamp: new Date().toISOString(),
          sessionId: 'current'
        } as DisplayStreamEvent);
        
        // Start thinking animation after commands are shown (use delayed event)
        if (!this.activeThinking && !this.activeReasoningSession) {
          results.push({
            type: 'delayed_thinking_start',
            context: 'tool_execution',
            startTime: Date.now(),
            delay: this.COMMAND_BUFFER_MS
          } as DisplayStreamEvent);
        }
        break;
        
      case 'output':
        // Handle tool output or general output
        if (event.content) {
          // Basic deduplication
          const currentTime = Date.now();
          if (event.content === this.lastOutputContent && 
              currentTime - this.lastOutputTime < this.outputDedupeTimeMs) {
            break; // Skip duplicate
          }
          this.lastOutputContent = event.content;
          this.lastOutputTime = currentTime;
          
          // Clear any active thinking when output appears
          if (this.activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            this.activeThinking = false;
          }
          
          results.push({
            type: 'output',
            content: event.content,
            toolId: this.currentToolId
          } as DisplayStreamEvent);
        }
        break;
        
      case 'tool_end':
        // Clear any active thinking when tool ends
        if (this.activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          this.activeThinking = false;
        }
        
        results.push({
          type: 'tool_end',
          toolId: event.toolId,
          tool: event.toolName || 'unknown',
          id: `tool_end_${Date.now()}`,
          timestamp: new Date().toISOString(),
          sessionId: 'current'
        } as DisplayStreamEvent);
        this.currentToolId = undefined;
        break;
        
      case 'operation_complete':
        // Clear any active states
        this.activeThinking = false;
        this.activeReasoningSession = false;
        
        results.push({
          type: 'metrics_update',
          metrics: event.metrics || {},
          duration: event.duration
        } as DisplayStreamEvent);
        break;
        
      case 'swarm_start':
        // Pass through swarm_start event
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'swarm_end':
        // Pass through swarm_end event
        results.push(event as DisplayStreamEvent);
        break;
        
      default:
        // Pass through other events as-is
        results.push(event as DisplayStreamEvent);
        break;
    }
    
    this.lastEventType = event.type;
    return results;
  }
}