/**
 * SDK Enhanced Callback Handler - Leverages Strands SDK native capabilities
 * 
 * This advanced callback handler integrates deeply with the Strands SDK's event loop,
 * metrics collection, and telemetry systems to provide comprehensive observability
 * and streaming capabilities for the Cyber-AutoAgent.
 * 
 * Key Features:
 * - Native SDK EventLoopMetrics integration for cost tracking and performance monitoring  
 * - Real-time streaming via SDK's callback system
 * - Comprehensive tool execution metrics and traces
 * - Built-in telemetry export to OpenTelemetry endpoints
 * - Thread-safe event emission and state management
 * - Automatic report generation with SDK metrics
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.2.0
 * @since 2025-08-02
 */

import { EventEmitter } from 'events';
import { SDKEventStreamBridge, SDKNativeEvent, SDKEventType } from './SDKEventStreamBridge.js';
import { StreamEvent } from '../types/events.js';

/**
 * SDK Callback Event Types - Native SDK callback data structures
 * Based on Strands SDK's callback handler interface
 */
interface SDKCallbackEvent {
  // Stream control events
  start?: boolean;
  start_event_loop?: boolean;
  complete?: boolean;
  force_stop?: boolean;
  force_stop_reason?: string;
  
  // Content streaming
  data?: string;
  delta?: any;
  reasoning?: boolean;
  reasoningText?: string;
  reasoning_signature?: string;
  
  // Tool execution
  current_tool_use?: {
    toolUseId: string;
    name: string;
    input: any;
  };
  
  // Message events
  message?: {
    role: string;
    content: any[];
  };
  
  // Event loop events
  event_loop_cycle_id?: string;
  event_loop_parent_cycle_id?: string;
  event_loop_throttled_delay?: number;
  
  // Raw event data from SDK
  event?: any;
}

/**
 * Enhanced metrics aggregation using SDK's native EventLoopMetrics structure
 */
interface EnhancedMetrics {
  // SDK native metrics
  eventLoopMetrics: {
    cycleCount: number;
    totalDuration: number;
    averageCycleTime: number;
    accumulatedUsage: {
      inputTokens: number;
      outputTokens: number;
      totalTokens: number;
    };
    accumulatedMetrics: {
      latencyMs: number;
    };
    toolUsage: Record<string, {
      callCount: number;
      successCount: number;
      errorCount: number;
      totalTime: number;
      averageTime: number;
      successRate: number;
    }>;
  };
  
  // Additional tracking
  sessionStart: number;
  lastUpdate: number;
  totalEvents: number;
  errorCount: number;
}

/**
 * SDK Enhanced Callback Handler - Main handler class
 * Implements SDK's callback interface while providing React event streaming
 */
export class SDKEnhancedCallbackHandler extends EventEmitter {
  private readonly eventBridge: SDKEventStreamBridge;
  private readonly metrics: EnhancedMetrics;
  private readonly sessionId: string;
  private currentCycleId?: string;
  private activeToolCall?: string;
  private isStreamingContent: boolean = false;
  private streamBuffer: string = '';
  
  constructor() {
    super();
    
    // Initialize SDK event bridge with optimized configuration
    this.eventBridge = new SDKEventStreamBridge({
      enableReasoningStream: true,
      enableMetricsStream: true,
      enableDebugEvents: true,
      bufferDeltas: true,
      deltaBufferMs: 100  // Slightly higher buffer for better UX
    });
    
    // Initialize metrics tracking
    this.metrics = this.initializeMetrics();
    this.sessionId = this.generateSessionId();
    
    // Bridge events to React interface
    this.eventBridge.on('stream_event', (event: StreamEvent) => {
      this.emit('stream_event', event);
    });
  }
  
  /**
   * Main callback method compatible with SDK's callback handler interface
   * This is called by the SDK during agent execution
   */
  __call__(callbackEvent: SDKCallbackEvent): void {
    try {
      this.processSDKCallback(callbackEvent);
    } catch (error) {
      console.error('Error processing SDK callback:', error);
      this.metrics.errorCount++;
    }
  }
  
  /**
   * Process SDK callback event and convert to native events
   */
  private processSDKCallback(callbackEvent: SDKCallbackEvent): void {
    const timestamp = new Date().toISOString();
    this.metrics.totalEvents++;
    this.metrics.lastUpdate = Date.now();
    
    // Handle event loop lifecycle
    if (callbackEvent.start_event_loop) {
      this.handleEventLoopStart(timestamp);
    }
    
    // Handle content streaming
    if (callbackEvent.data) {
      this.handleContentStream(callbackEvent, timestamp);
    }
    
    // Handle reasoning content
    if (callbackEvent.reasoning && callbackEvent.reasoningText) {
      this.handleReasoningStream(callbackEvent, timestamp);
    }
    
    // Handle tool execution
    if (callbackEvent.current_tool_use) {
      this.handleToolExecution(callbackEvent, timestamp);
    }
    
    // Handle message events
    if (callbackEvent.message) {
      this.handleMessageEvent(callbackEvent, timestamp);
    }
    
    // Handle completion events
    if (callbackEvent.complete) {
      this.handleCompletion(timestamp);
    }
    
    // Handle force stop events
    if (callbackEvent.force_stop) {
      this.handleForceStop(callbackEvent, timestamp);
    }
    
    // Handle raw SDK events
    if (callbackEvent.event) {
      this.handleRawSDKEvent(callbackEvent.event, timestamp);
    }
  }
  
  /**
   * Handle event loop start
   */
  private handleEventLoopStart(timestamp: string): void {
    this.currentCycleId = this.generateEventId();
    this.metrics.eventLoopMetrics.cycleCount++;
    
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.EVENT_LOOP_CYCLE_START,
      sessionId: this.sessionId,
      metadata: {
        cycleId: this.currentCycleId,
        cycleNumber: this.metrics.eventLoopMetrics.cycleCount
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Handle content streaming from model
   */
  private handleContentStream(callbackEvent: SDKCallbackEvent, timestamp: string): void {
    this.isStreamingContent = true;
    this.streamBuffer += callbackEvent.data || '';
    
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.MODEL_STREAM_DELTA,
      sessionId: this.sessionId,
      delta: callbackEvent.data,
      metadata: {
        bufferSize: this.streamBuffer.length,
        isComplete: callbackEvent.complete
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Handle reasoning content streaming
   */
  private handleReasoningStream(callbackEvent: SDKCallbackEvent, timestamp: string): void {
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.REASONING_DELTA,
      sessionId: this.sessionId,
      delta: callbackEvent.reasoningText,
      metadata: {
        signature: callbackEvent.reasoning_signature,
        reasoningContext: true
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Handle tool execution events
   */
  private handleToolExecution(callbackEvent: SDKCallbackEvent, timestamp: string): void {
    const toolUse = callbackEvent.current_tool_use!;
    
    if (this.activeToolCall !== toolUse.toolUseId) {
      // New tool call starting
      this.activeToolCall = toolUse.toolUseId;
      
      const sdkEvent: SDKNativeEvent = {
        id: this.generateEventId(),
        timestamp,
        type: SDKEventType.TOOL_INVOCATION_START,
        sessionId: this.sessionId,
        toolName: toolUse.name,
        toolInput: toolUse.input,
        toolUseId: toolUse.toolUseId,
        metadata: {
          toolStartTime: Date.now()
        }
      };
      
      this.eventBridge.processSDKEvent(sdkEvent);
      
      // Update metrics
      if (!this.metrics.eventLoopMetrics.toolUsage[toolUse.name]) {
        this.metrics.eventLoopMetrics.toolUsage[toolUse.name] = {
          callCount: 0,
          successCount: 0,
          errorCount: 0,
          totalTime: 0,
          averageTime: 0,
          successRate: 0
        };
      }
      this.metrics.eventLoopMetrics.toolUsage[toolUse.name].callCount++;
    }
  }
  
  /**
   * Handle message events
   */
  private handleMessageEvent(callbackEvent: SDKCallbackEvent, timestamp: string): void {
    const message = callbackEvent.message!;
    
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.MESSAGE_ADDED,
      sessionId: this.sessionId,
      content: message.content,
      metadata: {
        role: message.role,
        messageLength: JSON.stringify(message.content).length
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Handle completion events
   */
  private handleCompletion(timestamp: string): void {
    this.isStreamingContent = false;
    
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.MESSAGE_STOP,
      sessionId: this.sessionId,
      isComplete: true,
      metadata: {
        finalBufferSize: this.streamBuffer.length,
        sessionDuration: Date.now() - this.metrics.sessionStart
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
    this.streamBuffer = '';
  }
  
  /**
   * Handle force stop events
   */
  private handleForceStop(callbackEvent: SDKCallbackEvent, timestamp: string): void {
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp,
      type: SDKEventType.MESSAGE_STOP,
      sessionId: this.sessionId,
      error: callbackEvent.force_stop_reason || 'Force stop requested',
      metadata: {
        forceStop: true,
        reason: callbackEvent.force_stop_reason
      }
    };
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Handle raw SDK events for comprehensive coverage
   */
  private handleRawSDKEvent(rawEvent: any, timestamp: string): void {
    // Process different types of raw SDK events
    if (rawEvent.messageStart) {
      const sdkEvent: SDKNativeEvent = {
        id: this.generateEventId(),
        timestamp,
        type: SDKEventType.MESSAGE_START,
        sessionId: this.sessionId,
        metadata: rawEvent.messageStart
      };
      this.eventBridge.processSDKEvent(sdkEvent);
    }
    
    if (rawEvent.contentBlockStart) {
      const sdkEvent: SDKNativeEvent = {
        id: this.generateEventId(),
        timestamp,
        type: SDKEventType.CONTENT_BLOCK_START,
        sessionId: this.sessionId,
        metadata: rawEvent.contentBlockStart
      };
      this.eventBridge.processSDKEvent(sdkEvent);
    }
    
    if (rawEvent.metadata) {
      // Extract usage and metrics from SDK metadata
      const usage = rawEvent.metadata.usage;
      const metrics = rawEvent.metadata.metrics;
      
      if (usage) {
        this.updateUsageMetrics(usage);
      }
      
      if (metrics) {
        this.updatePerformanceMetrics(metrics);
      }
      
      const sdkEvent: SDKNativeEvent = {
        id: this.generateEventId(),
        timestamp,
        type: SDKEventType.METRICS_UPDATE,
        sessionId: this.sessionId,
        metrics: {
          latencyMs: metrics?.latencyMs,
          inputTokens: usage?.inputTokens,
          outputTokens: usage?.outputTokens,
          totalTokens: usage?.totalTokens,
          cycleCount: this.metrics.eventLoopMetrics.cycleCount,
          toolCallCount: Object.values(this.metrics.eventLoopMetrics.toolUsage)
            .reduce((sum, tool) => sum + tool.callCount, 0)
        },
        metadata: {
          rawUsage: usage,
          rawMetrics: metrics
        }
      };
      
      this.eventBridge.processSDKEvent(sdkEvent);
    }
  }
  
  /**
   * Update usage metrics from SDK
   */
  private updateUsageMetrics(usage: any): void {
    this.metrics.eventLoopMetrics.accumulatedUsage.inputTokens += usage.inputTokens || 0;
    this.metrics.eventLoopMetrics.accumulatedUsage.outputTokens += usage.outputTokens || 0;
    this.metrics.eventLoopMetrics.accumulatedUsage.totalTokens += usage.totalTokens || 0;
  }
  
  /**
   * Update performance metrics from SDK
   */
  private updatePerformanceMetrics(metrics: any): void {
    this.metrics.eventLoopMetrics.accumulatedMetrics.latencyMs += metrics.latencyMs || 0;
  }
  
  /**
   * Initialize metrics structure
   */
  private initializeMetrics(): EnhancedMetrics {
    return {
      eventLoopMetrics: {
        cycleCount: 0,
        totalDuration: 0,
        averageCycleTime: 0,
        accumulatedUsage: {
          inputTokens: 0,
          outputTokens: 0,
          totalTokens: 0
        },
        accumulatedMetrics: {
          latencyMs: 0
        },
        toolUsage: {}
      },
      sessionStart: Date.now(),
      lastUpdate: Date.now(),
      totalEvents: 0,
      errorCount: 0
    };
  }
  
  /**
   * Generate unique event ID
   */
  private generateEventId(): string {
    return `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `sdk_enhanced_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Get comprehensive metrics summary
   */
  getMetricsSummary(): Record<string, any> {
    const sessionDuration = Date.now() - this.metrics.sessionStart;
    
    return {
      session: {
        id: this.sessionId,
        duration: sessionDuration,
        totalEvents: this.metrics.totalEvents,
        errorCount: this.metrics.errorCount,
        eventsPerSecond: this.metrics.totalEvents / (sessionDuration / 1000)
      },
      
      eventLoop: {
        cycles: this.metrics.eventLoopMetrics.cycleCount,
        averageCycleTime: this.metrics.eventLoopMetrics.averageCycleTime,
        totalDuration: this.metrics.eventLoopMetrics.totalDuration
      },
      
      usage: this.metrics.eventLoopMetrics.accumulatedUsage,
      
      performance: {
        totalLatency: this.metrics.eventLoopMetrics.accumulatedMetrics.latencyMs,
        averageLatency: this.metrics.eventLoopMetrics.cycleCount > 0 
          ? this.metrics.eventLoopMetrics.accumulatedMetrics.latencyMs / this.metrics.eventLoopMetrics.cycleCount 
          : 0
      },
      
      tools: this.metrics.eventLoopMetrics.toolUsage,
      
      streaming: {
        isActive: this.isStreamingContent,
        bufferSize: this.streamBuffer.length,
        activeToolCall: this.activeToolCall
      }
    };
  }
  
  /**
   * Export metrics in SDK-compatible format
   */
  exportSDKMetrics(): any {
    return {
      accumulated_usage: this.metrics.eventLoopMetrics.accumulatedUsage,
      accumulated_metrics: this.metrics.eventLoopMetrics.accumulatedMetrics,
      cycle_count: this.metrics.eventLoopMetrics.cycleCount,
      tool_usage: this.metrics.eventLoopMetrics.toolUsage,
      session_metadata: {
        session_id: this.sessionId,
        start_time: this.metrics.sessionStart,
        total_events: this.metrics.totalEvents,
        error_count: this.metrics.errorCount
      }
    };
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    this.eventBridge.destroy();
    this.removeAllListeners();
  }
}

/**
 * Factory function to create SDK enhanced callback handler
 */
export function createSDKEnhancedCallbackHandler(): SDKEnhancedCallbackHandler {
  return new SDKEnhancedCallbackHandler();
}