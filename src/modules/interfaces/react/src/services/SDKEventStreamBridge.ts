/**
 * SDK Event Stream Bridge - Connects Strands SDK native events to React interface
 * 
 * This service bridges the gap between the Strands SDK's sophisticated event system
 * and the React Ink interface, providing real-time streaming of SDK-native events
 * while maintaining compatibility with the existing React event architecture.
 * 
 * Key Features:
 * - Leverages SDK's native streaming events and hook system
 * - Provides structured event transformation for React consumption
 * - Maintains backward compatibility with existing event types
 * - Enables real-time metrics and telemetry streaming
 * - Supports SDK's built-in cost tracking and performance monitoring
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.2.0
 * @since 2025-08-02
 */

import { EventEmitter } from 'events';
import { StreamEvent, EventType } from '../types/events.js';

/**
 * SDK Event Types - Native Strands SDK event categories
 * Maps directly to SDK's event loop and streaming architecture
 */
export enum SDKEventType {
  // Model invocation events from SDK
  MODEL_INVOCATION_START = 'model_invocation_start',
  MODEL_INVOCATION_END = 'model_invocation_end',
  MODEL_STREAM_START = 'model_stream_start',
  MODEL_STREAM_DELTA = 'model_stream_delta',
  MODEL_STREAM_END = 'model_stream_end',
  
  // Tool execution events from SDK
  TOOL_INVOCATION_START = 'tool_invocation_start',
  TOOL_INVOCATION_END = 'tool_invocation_end',
  TOOL_STREAM_START = 'tool_stream_start',
  TOOL_STREAM_DELTA = 'tool_stream_delta',
  TOOL_STREAM_END = 'tool_stream_end',
  
  // Event loop cycle events
  EVENT_LOOP_CYCLE_START = 'event_loop_cycle_start',
  EVENT_LOOP_CYCLE_END = 'event_loop_cycle_end',
  
  // Message lifecycle events
  MESSAGE_ADDED = 'message_added',
  MESSAGE_START = 'message_start',
  MESSAGE_STOP = 'message_stop',
  
  // Content streaming events
  CONTENT_BLOCK_START = 'content_block_start',
  CONTENT_BLOCK_DELTA = 'content_block_delta',
  CONTENT_BLOCK_STOP = 'content_block_stop',
  
  // Reasoning events (for thinking models)
  REASONING_START = 'reasoning_start',
  REASONING_DELTA = 'reasoning_delta',
  REASONING_END = 'reasoning_end',
  
  // Metrics and telemetry events
  METRICS_UPDATE = 'metrics_update',
  USAGE_UPDATE = 'usage_update',
  TRACE_START = 'trace_start',
  TRACE_END = 'trace_end',
  
  // Agent lifecycle events
  AGENT_INITIALIZED = 'agent_initialized',
  BEFORE_INVOCATION = 'before_invocation',
  AFTER_INVOCATION = 'after_invocation',
}

/**
 * SDK Native Event Interface - Structured event from Strands SDK
 */
export interface SDKNativeEvent {
  id: string;
  timestamp: string;
  type: SDKEventType;
  sessionId: string;
  
  // Model invocation context
  modelId?: string;
  messages?: any[];
  systemPrompt?: string;
  
  // Tool invocation context
  toolName?: string;
  toolInput?: any;
  toolResult?: any;
  toolUseId?: string;
  
  // Streaming content
  content?: string | any[];
  delta?: string;
  isComplete?: boolean;
  
  // Performance metrics
  metrics?: {
    latencyMs?: number;
    inputTokens?: number;
    outputTokens?: number;
    totalTokens?: number;
    cycleCount?: number;
    toolCallCount?: number;
  };
  
  // Error information
  error?: string;
  stopReason?: string;
  
  // Additional context
  metadata?: Record<string, any>;
}

/**
 * Event Transformation Configuration
 */
interface TransformConfig {
  enableReasoningStream: boolean;
  enableMetricsStream: boolean;
  enableDebugEvents: boolean;
  bufferDeltas: boolean;
  deltaBufferMs: number;
}

/**
 * SDK Event Stream Bridge - Main bridge service
 */
export class SDKEventStreamBridge extends EventEmitter {
  private readonly config: TransformConfig;
  private readonly deltaBuffer: Map<string, string> = new Map();
  private readonly pendingFlushes: Map<string, NodeJS.Timeout> = new Map();
  private sessionId: string;
  private eventCount: number = 0;
  
  constructor(config: Partial<TransformConfig> = {}) {
    super();
    this.config = {
      enableReasoningStream: true,
      enableMetricsStream: true,
      enableDebugEvents: false,
      bufferDeltas: true,
      deltaBufferMs: 50,
      ...config
    };
    
    this.sessionId = this.generateSessionId();
  }
  
  /**
   * Process SDK native event and transform to React-compatible events
   */
  processSDKEvent(sdkEvent: SDKNativeEvent): StreamEvent[] {
    const transformedEvents: StreamEvent[] = [];
    
    switch (sdkEvent.type) {
      case SDKEventType.MODEL_INVOCATION_START:
        transformedEvents.push(this.transformModelStart(sdkEvent));
        break;
        
      case SDKEventType.MODEL_STREAM_DELTA:
        if (sdkEvent.delta) {
          if (this.config.bufferDeltas) {
            this.bufferDelta(sdkEvent);
          } else {
            transformedEvents.push(this.transformStreamDelta(sdkEvent));
          }
        }
        break;
        
      case SDKEventType.REASONING_DELTA:
        if (this.config.enableReasoningStream && sdkEvent.delta) {
          transformedEvents.push(this.transformReasoningDelta(sdkEvent));
        }
        break;
        
      case SDKEventType.TOOL_INVOCATION_START:
        transformedEvents.push(this.transformToolStart(sdkEvent));
        break;
        
      case SDKEventType.TOOL_INVOCATION_END:
        transformedEvents.push(this.transformToolEnd(sdkEvent));
        break;
        
      case SDKEventType.EVENT_LOOP_CYCLE_START:
        transformedEvents.push(this.transformCycleStart(sdkEvent));
        break;
        
      case SDKEventType.METRICS_UPDATE:
        if (this.config.enableMetricsStream) {
          transformedEvents.push(this.transformMetricsUpdate(sdkEvent));
        }
        break;
        
      case SDKEventType.MESSAGE_STOP:
        transformedEvents.push(this.transformMessageStop(sdkEvent));
        break;
        
      default:
        if (this.config.enableDebugEvents) {
          transformedEvents.push(this.transformGenericEvent(sdkEvent));
        }
    }
    
    // Emit all transformed events
    transformedEvents.forEach(event => {
      this.emit('stream_event', event);
    });
    
    return transformedEvents;
  }
  
  /**
   * Transform model invocation start to thinking event
   */
  private transformModelStart(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'thinking' as any,
      context: 'model_invocation',
      startTime: Date.now()
    };
  }
  
  /**
   * Transform streaming delta to output event
   */
  private transformStreamDelta(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'output' as any,
      content: sdkEvent.delta || '',
      exitCode: 0
    };
  }
  
  /**
   * Transform reasoning delta to reasoning event
   */
  private transformReasoningDelta(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'reasoning' as any,
      content: sdkEvent.delta || ''
    };
  }
  
  /**
   * Transform tool start to tool_start event
   */
  private transformToolStart(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'tool_start' as any,
      tool_name: sdkEvent.toolName || 'unknown',
      tool_input: sdkEvent.toolInput || {}
    };
  }
  
  /**
   * Transform tool end to output event with results
   */
  private transformToolEnd(sdkEvent: SDKNativeEvent): any {
    const result = sdkEvent.toolResult;
    const content = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
    
    return {
      type: 'output',
      content,
      exitCode: sdkEvent.error ? 1 : 0,
      duration: sdkEvent.metrics?.latencyMs ? sdkEvent.metrics.latencyMs / 1000 : undefined
    };
  }
  
  /**
   * Transform event loop cycle start to step header
   */
  private transformCycleStart(sdkEvent: SDKNativeEvent): any {
    this.eventCount++;
    return {
      type: 'step_header',
      step: this.eventCount,
      maxSteps: 100, // Default, can be configured
      operation: `cycle_${this.eventCount}`,
      duration: '0s'
    };
  }
  
  /**
   * Transform metrics update to metrics event
   */
  private transformMetricsUpdate(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'metrics_update',
      metrics: {
        tokens: {
          input: sdkEvent.metrics?.inputTokens || 0,
          output: sdkEvent.metrics?.outputTokens || 0,
          total: sdkEvent.metrics?.totalTokens || 0
        },
        latency: sdkEvent.metrics?.latencyMs || 0,
        cycles: sdkEvent.metrics?.cycleCount || 0,
        toolCalls: sdkEvent.metrics?.toolCallCount || 0,
        timestamp: sdkEvent.timestamp
      }
    };
  }
  
  /**
   * Transform message stop to thinking_end
   */
  private transformMessageStop(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'thinking_end'
    };
  }
  
  /**
   * Transform generic SDK event for debugging
   */
  private transformGenericEvent(sdkEvent: SDKNativeEvent): any {
    return {
      type: 'metadata',
      content: {
        sdk_event_type: sdkEvent.type,
        timestamp: sdkEvent.timestamp,
        ...sdkEvent.metadata
      }
    };
  }
  
  /**
   * Buffer delta content to reduce event frequency
   */
  private bufferDelta(sdkEvent: SDKNativeEvent): void {
    const bufferId = sdkEvent.toolUseId || 'default';
    const currentBuffer = this.deltaBuffer.get(bufferId) || '';
    this.deltaBuffer.set(bufferId, currentBuffer + (sdkEvent.delta || ''));
    
    // Clear existing flush timer
    const existingTimer = this.pendingFlushes.get(bufferId);
    if (existingTimer) {
      clearTimeout(existingTimer);
    }
    
    // Set new flush timer
    const timer = setTimeout(() => {
      const bufferedContent = this.deltaBuffer.get(bufferId) || '';
      if (bufferedContent) {
        const flushEvent: any = {
          type: 'output',
          content: bufferedContent,
          exitCode: 0
        };
        this.emit('stream_event', flushEvent);
        this.deltaBuffer.delete(bufferId);
        this.pendingFlushes.delete(bufferId);
      }
    }, this.config.deltaBufferMs);
    
    this.pendingFlushes.set(bufferId, timer);
  }
  
  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `sdk_session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Get current session metrics
   */
  getSessionMetrics(): Record<string, any> {
    return {
      sessionId: this.sessionId,
      eventCount: this.eventCount,
      activeBuffers: this.deltaBuffer.size,
      pendingFlushes: this.pendingFlushes.size
    };
  }
  
  /**
   * Flush all pending buffers immediately
   */
  flushAll(): void {
    for (const [bufferId, content] of this.deltaBuffer.entries()) {
      if (content) {
        const flushEvent: any = {
          type: 'output',
          content,
          exitCode: 0
        };
        this.emit('stream_event', flushEvent);
      }
    }
    
    // Clear all buffers and timers
    this.deltaBuffer.clear();
    this.pendingFlushes.forEach(timer => clearTimeout(timer));
    this.pendingFlushes.clear();
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    this.flushAll();
    this.removeAllListeners();
  }
}

/**
 * Create and configure SDK event bridge with sensible defaults
 */
export function createSDKEventBridge(config?: Partial<TransformConfig>): SDKEventStreamBridge {
  return new SDKEventStreamBridge(config);
}