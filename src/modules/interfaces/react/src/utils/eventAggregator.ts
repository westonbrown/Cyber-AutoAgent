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
  private pendingStepHeader?: DisplayStreamEvent;
  // Track step gating to properly attribute early reasoning to the previous step
  private pendingStepNumber?: number;
  private hasToolForPendingStep: boolean = false;
  private lastEmittedStepNumber?: number;
  
  // Command buffering delay constant  
  private readonly COMMAND_BUFFER_MS = 100; // Short delay to collect all commands
  
  // Prevent duplicate outputs
  private lastOutputContent: string = '';
  private outputDedupeTimeMs = 1000; // 1 second window for deduplication
  private lastOutputTime: number = 0;
  
  // Swarm operation tracking for intelligent handoff transformation
  private swarmActive: boolean = false;
  private currentSwarmAgent: string | null = null;
  private swarmHandoffSequence: number = 0;

  // Dedupe: avoid duplicate tool headers from dual emitters (hooks + bridge handler)
  private displayedToolStartIds: Set<string> = new Set();
  // Track dedupe keys by tool id so we can clean them up on tool_end
  private toolStartDedupeKeyById: Map<string, string> = new Map();
  
  // These methods are no longer used since we don't buffer events
  // Kept for potential future use if buffering is needed
  hasPendingEvents(): boolean {
    return false;
  }
  
  flushPendingEvents(): DisplayStreamEvent[] {
    return [];
  }
  
  flush(): DisplayStreamEvent[] {
    return [];
  }
  
  processEvent(event: any): DisplayStreamEvent[] {
    const results: DisplayStreamEvent[] = [];
    
    switch (event.type) {
      case 'step_header':
        // End any active reasoning session
        this.activeReasoningSession = false;
        // Track swarm agent from step header
        if (event.is_swarm_operation && event.swarm_agent) {
          this.currentSwarmAgent = event.swarm_agent;
        }
        // Buffer the step header; flush when the first tool event of this step arrives
        this.pendingStepHeader = {
          type: 'step_header',
          step: event.step,
          maxSteps: event.maxSteps,
          operation: event.operation,
          duration: event.duration,
          is_swarm_operation: (event as any).is_swarm_operation,
          swarm_agent: (event as any).swarm_agent || this.currentSwarmAgent,
          swarm_sub_step: (event as any).swarm_sub_step,
          swarm_max_sub_steps: (event as any).swarm_max_sub_steps,
          swarm_total_iterations: (event as any).swarm_total_iterations,
          swarm_max_iterations: (event as any).swarm_max_iterations,
          swarm_context: (event as any).swarm_context || (this.swarmActive ? 'Multi-Agent Operation' : undefined)
        } as DisplayStreamEvent;
        // Track pending step number and reset tool flag
        this.pendingStepNumber = (typeof event.step === 'number') ? event.step : undefined;
        this.hasToolForPendingStep = false;
        this.activeReasoningSession = false;
        break;
        
      case 'reasoning':
        // Python backend now sends complete reasoning blocks - no buffering needed
        if (event.content && typeof event.content === 'string' && event.content.trim()) {
          // Clear any active thinking animations when reasoning is shown
          if (this.activeThinking) {
            results.push({ type: 'thinking_end' } as DisplayStreamEvent);
            this.activeThinking = false;
          }
          
          // Start reasoning session
          this.activeReasoningSession = true;
          
          // Emit the complete reasoning block directly, preserving swarm context if present
          const reasoningEvent: any = {
            type: 'reasoning',
            content: (event.content as string).trim(),
          };
          // Preserve or infer swarm agent context for consistent UI labeling
          const incomingAgent = ('swarm_agent' in event && event.swarm_agent) ? event.swarm_agent : undefined;
          reasoningEvent.swarm_agent = incomingAgent || this.currentSwarmAgent || undefined;
          if ('is_swarm_operation' in event && event.is_swarm_operation) {
            reasoningEvent.is_swarm_operation = event.is_swarm_operation;
          }
          
          // IMPORTANT: If a new step header is pending and no tool has been seen for that step yet,
          // keep this reasoning attached to the previous step by not flushing the header here.
          // This preserves the intuitive attribution (reasoning summarizing prior step results).
          results.push(reasoningEvent as DisplayStreamEvent);
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

        // If there is a pending step header, emit it now before the tool header
        if (this.pendingStepHeader) {
          results.push(this.pendingStepHeader);
          // Update step gating state
          this.lastEmittedStepNumber = this.pendingStepNumber ?? this.lastEmittedStepNumber;
          this.pendingStepHeader = undefined;
          this.hasToolForPendingStep = true;
        }

        // Dedupe duplicate tool headers by tool id (hooks + bridge may emit both)
        {
          const candidateId = (event as any).toolId ?? (event as any).tool_id ?? undefined;
          const stepKey = (this.pendingStepNumber ?? this.lastEmittedStepNumber ?? 0).toString();
          if (candidateId) {
            const dedupeKey = `${stepKey}:${candidateId}`;
            if (this.displayedToolStartIds.has(dedupeKey)) {
              // Already displayed a header for this tool invocation within this step; ignore duplicates
              break;
            }
            this.displayedToolStartIds.add(dedupeKey);
            this.toolStartDedupeKeyById.set(String(candidateId), dedupeKey);
          }
        }
        
        this.currentToolId = event.toolId;
        
        // Special handling for handoff_to_agent during swarm operations
        if (event.tool_name === 'handoff_to_agent' && this.swarmActive) {
          const toolInput = event.tool_input || {};
          
          // Create a proper swarm_handoff event with rich context
          results.push({
            type: 'swarm_handoff',
            from_agent: this.currentSwarmAgent || 'unknown',
            to_agent: toolInput.agent_name || toolInput.handoff_to || 'unknown',
            message: toolInput.message || '',
            shared_context: toolInput.context || {},
            timestamp: event.timestamp || Date.now(),
            sequence: ++this.swarmHandoffSequence
          } as DisplayStreamEvent);
          
          // Update current agent
          this.currentSwarmAgent = toolInput.agent_name || toolInput.handoff_to || this.currentSwarmAgent;
          
          // Still emit the tool event for completeness but mark it as processed
          results.push({
            type: 'tool_start',
            tool_name: event.toolName || event.tool_name || '',
            tool_input: event.args || event.tool_input || {},
            toolId: event.toolId,
            toolName: event.toolName,
            _handoff_processed: true
          } as DisplayStreamEvent);
        } else {
          // Normal tool start
          results.push({
            type: 'tool_start',
            tool_name: event.toolName || event.tool_name || '',
            tool_input: event.args || event.tool_input || {},
            toolId: event.toolId,
            toolName: event.toolName
          } as DisplayStreamEvent);
        }
        break;
        
      case 'shell_command':
        // Treat shell_command as evidence of a tool starting (in case a start event was missed)
        if (this.pendingStepHeader && !this.hasToolForPendingStep) {
          results.push(this.pendingStepHeader);
          this.lastEmittedStepNumber = this.pendingStepNumber ?? this.lastEmittedStepNumber;
          this.pendingStepHeader = undefined;
          this.hasToolForPendingStep = true;
        }
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
          
          // IMPORTANT: Do NOT flush a pending step header on generic 'output' events.
          // Late output from the previous tool can arrive after a new step_header
          // (e.g., final buffer flush). Flushing here would incorrectly advance
          // the header before prior-step reasoning is rendered.
          // We only flush on explicit tool signals (tool_start/tool_output).
          
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
        
      case 'tool_output':
        // If a step is pending and we receive a standardized tool_output event,
        // flush the step header before displaying output to keep attribution correct.
        if (this.pendingStepHeader && !this.hasToolForPendingStep) {
          results.push(this.pendingStepHeader);
          this.lastEmittedStepNumber = this.pendingStepNumber ?? this.lastEmittedStepNumber;
          this.pendingStepHeader = undefined;
          this.hasToolForPendingStep = true;
        }
        // Pass through the event as-is for StreamDisplay to render
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'tool_end':
        // Clear any active thinking when tool ends
        if (this.activeThinking) {
          results.push({ type: 'thinking_end' } as DisplayStreamEvent);
          this.activeThinking = false;
        }

        // Cleanup dedupe cache for this tool id to avoid unbounded growth
        if ((event as any).toolId) {
          const tid = String((event as any).toolId);
          const key = this.toolStartDedupeKeyById.get(tid);
          if (key) {
            this.displayedToolStartIds.delete(key);
            this.toolStartDedupeKeyById.delete(tid);
          } else {
            // Fallback: remove by raw id if present (legacy cleanup)
            this.displayedToolStartIds.delete(tid);
          }
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
        // Mark swarm as active and reset tracking
        this.swarmActive = true;
        this.swarmHandoffSequence = 0;
        
        // Extract first agent if available
        if (event.agent_names && Array.isArray(event.agent_names) && event.agent_names.length > 0) {
          this.currentSwarmAgent = event.agent_names[0];
        }
        
        // Pass through swarm_start event with all details
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'swarm_handoff':
        // Handle swarm handoff events
        // If the event has empty data, skip it (will be replaced by tool-based handoff)
        if (!event.to_agent || !event.message) {
          break;
        }
        
        // Update current agent
        if (event.to_agent) {
          this.currentSwarmAgent = event.to_agent;
        }
        
        // Pass through the handoff event
        results.push(event as DisplayStreamEvent);
        break;
        
      case 'swarm_end':
      case 'swarm_complete':
        // Reset swarm tracking
        this.swarmActive = false;
        this.currentSwarmAgent = null;
        this.swarmHandoffSequence = 0;
        
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