/**
 * SDK Hook Integration - Comprehensive event capture via Strands SDK hook system
 * 
 * This module provides deep integration with the Strands SDK's hook system to capture
 * all agent lifecycle events, model invocations, tool executions, and message handling.
 * It leverages the SDK's native BeforeXEvent and AfterXEvent patterns for comprehensive
 * observability and real-time streaming to the React interface.
 * 
 * Key Features:
 * - Native integration with SDK's hook registry and event system
 * - Comprehensive event capture across all agent lifecycle stages
 * - Real-time performance monitoring and cost tracking
 * - Thread-safe event emission and state management
 * - Automatic trace correlation and context preservation
 * - Support for both experimental and stable SDK hook events
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.2.0 
 * @since 2025-08-02
 */

import { EventEmitter } from 'events';
import { SDKEventStreamBridge, SDKNativeEvent, SDKEventType } from './SDKEventStreamBridge.js';

/**
 * SDK Hook Event Types - Maps to native Strands SDK hook events
 * Based on strands.hooks and strands.experimental.hooks modules
 */
export enum SDKHookEventType {
  // Agent lifecycle hooks
  AGENT_INITIALIZED = 'agent_initialized',
  BEFORE_INVOCATION = 'before_invocation', 
  AFTER_INVOCATION = 'after_invocation',
  
  // Model invocation hooks
  BEFORE_MODEL_INVOCATION = 'before_model_invocation',
  AFTER_MODEL_INVOCATION = 'after_model_invocation',
  
  // Tool invocation hooks
  BEFORE_TOOL_INVOCATION = 'before_tool_invocation',
  AFTER_TOOL_INVOCATION = 'after_tool_invocation',
  
  // Message lifecycle hooks
  MESSAGE_ADDED = 'message_added',
  
  // Custom hook events
  CUSTOM_HOOK = 'custom_hook'
}

/**
 * Hook Event Context - Rich context from SDK hook events
 */
interface HookEventContext {
  // Common context
  hookType: SDKHookEventType;
  timestamp: string;
  agentId?: string;
  sessionId?: string;
  traceId?: string;
  
  // Agent context
  agent?: any;
  
  // Model invocation context
  modelId?: string;
  messages?: any[];
  systemPrompt?: string;
  stopResponse?: {
    message: any;
    stopReason: string;
  };
  
  // Tool invocation context
  selectedTool?: any;
  toolUse?: {
    toolUseId: string;
    name: string;
    input: any;
  };
  invocationState?: Record<string, any>;
  toolResult?: any;
  
  // Message context
  message?: any;
  
  // Error context
  exception?: Error;
  
  // Performance metrics
  startTime?: number;
  endTime?: number;
  duration?: number;
  
  // Additional metadata
  metadata?: Record<string, any>;
}

/**
 * Hook Registration Configuration
 */
interface HookConfig {
  enableModelHooks: boolean;
  enableToolHooks: boolean;
  enableMessageHooks: boolean;
  enableAgentHooks: boolean;
  enablePerformanceTracking: boolean;
  enableErrorCapture: boolean;
  maxContextSize: number;
}

/**
 * SDK Hook Integration Service
 */
export class SDKHookIntegration extends EventEmitter {
  private readonly eventBridge: SDKEventStreamBridge;
  private readonly config: HookConfig;
  private readonly sessionId: string;
  private readonly activeContexts: Map<string, HookEventContext> = new Map();
  private readonly performanceTracking: Map<string, number> = new Map();
  private eventCount: number = 0;
  
  constructor(config: Partial<HookConfig> = {}) {
    super();
    
    this.config = {
      enableModelHooks: true,
      enableToolHooks: true,
      enableMessageHooks: true,
      enableAgentHooks: true,
      enablePerformanceTracking: true,
      enableErrorCapture: true,
      maxContextSize: 1000000, // 1MB max context
      ...config
    };
    
    this.eventBridge = new SDKEventStreamBridge({
      enableReasoningStream: true,
      enableMetricsStream: true,
      enableDebugEvents: true,
      bufferDeltas: false // Real-time for hook events
    });
    
    this.sessionId = this.generateSessionId();
    
    // Bridge events to external listeners
    this.eventBridge.on('stream_event', (event) => {
      this.emit('stream_event', event);
    });
  }
  
  /**
   * Register all SDK hooks - This would be called from Python/SDK side
   * The actual hook registration happens in the Python agent creation
   */
  registerSDKHooks(): Record<string, Function> {
    const hookCallbacks: Record<string, Function> = {};
    
    if (this.config.enableAgentHooks) {
      hookCallbacks.onAgentInitialized = this.createAgentInitializedHook();
      hookCallbacks.onBeforeInvocation = this.createBeforeInvocationHook();
      hookCallbacks.onAfterInvocation = this.createAfterInvocationHook();
    }
    
    if (this.config.enableModelHooks) {
      hookCallbacks.onBeforeModelInvocation = this.createBeforeModelInvocationHook();
      hookCallbacks.onAfterModelInvocation = this.createAfterModelInvocationHook();
    }
    
    if (this.config.enableToolHooks) {
      hookCallbacks.onBeforeToolInvocation = this.createBeforeToolInvocationHook();
      hookCallbacks.onAfterToolInvocation = this.createAfterToolInvocationHook();
    }
    
    if (this.config.enableMessageHooks) {
      hookCallbacks.onMessageAdded = this.createMessageAddedHook();
    }
    
    return hookCallbacks;
  }
  
  /**
   * Create agent initialized hook
   */
  private createAgentInitializedHook() {
    return (hookEvent: any) => {
      const context: HookEventContext = {
        hookType: SDKHookEventType.AGENT_INITIALIZED,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        metadata: {
          agentType: hookEvent.agent?.constructor?.name,
          hookEventType: 'AgentInitializedEvent'
        }
      };
      
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create before invocation hook
   */
  private createBeforeInvocationHook() {
    return (hookEvent: any) => {
      const invocationId = this.generateInvocationId();
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.BEFORE_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: invocationId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        startTime: Date.now(),
        metadata: {
          invocationId,
          hookEventType: 'BeforeInvocationEvent'
        }
      };
      
      if (this.config.enablePerformanceTracking) {
        this.performanceTracking.set(invocationId, Date.now());
      }
      
      this.activeContexts.set(invocationId, context);
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create after invocation hook
   */
  private createAfterInvocationHook() {
    return (hookEvent: any) => {
      const invocationId = this.findActiveInvocationId(hookEvent);
      const startTime = this.performanceTracking.get(invocationId || '');
      const endTime = Date.now();
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.AFTER_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: invocationId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        startTime,
        endTime,
        duration: startTime ? endTime - startTime : undefined,
        exception: hookEvent.exception,
        metadata: {
          invocationId,
          hookEventType: 'AfterInvocationEvent',
          isReversed: true // AfterInvocation uses reverse callback ordering
        }
      };
      
      if (invocationId) {
        this.activeContexts.delete(invocationId);
        this.performanceTracking.delete(invocationId);
      }
      
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create before model invocation hook
   */
  private createBeforeModelInvocationHook() {
    return (hookEvent: any) => {
      const modelId = this.generateModelInvocationId();
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.BEFORE_MODEL_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: modelId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        modelId: hookEvent.agent?.model?.config?.model_id,
        messages: this.config.enableErrorCapture ? hookEvent.agent?.messages : undefined,
        systemPrompt: hookEvent.agent?.system_prompt,
        startTime: Date.now(),
        metadata: {
          modelInvocationId: modelId,
          hookEventType: 'BeforeModelInvocationEvent',
          messageCount: hookEvent.agent?.messages?.length || 0
        }
      };
      
      if (this.config.enablePerformanceTracking) {
        this.performanceTracking.set(modelId, Date.now());
      }
      
      this.activeContexts.set(modelId, context);
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create after model invocation hook
   */
  private createAfterModelInvocationHook() {
    return (hookEvent: any) => {
      const modelId = this.findActiveModelInvocationId(hookEvent);
      const startTime = this.performanceTracking.get(modelId || '');
      const endTime = Date.now();
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.AFTER_MODEL_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: modelId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        stopResponse: hookEvent.stop_response ? {
          message: hookEvent.stop_response.message,
          stopReason: hookEvent.stop_response.stop_reason
        } : undefined,
        startTime,
        endTime,
        duration: startTime ? endTime - startTime : undefined,
        exception: hookEvent.exception,
        metadata: {
          modelInvocationId: modelId,
          hookEventType: 'AfterModelInvocationEvent',
          isReversed: true,
          hasException: !!hookEvent.exception,
          stopReason: hookEvent.stop_response?.stop_reason
        }
      };
      
      if (modelId) {
        this.activeContexts.delete(modelId);
        this.performanceTracking.delete(modelId);
      }
      
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create before tool invocation hook
   */
  private createBeforeToolInvocationHook() {
    return (hookEvent: any) => {
      const toolId = this.generateToolInvocationId(hookEvent.tool_use?.toolUseId);
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.BEFORE_TOOL_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: toolId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        selectedTool: hookEvent.selected_tool,
        toolUse: hookEvent.tool_use ? {
          toolUseId: hookEvent.tool_use.toolUseId,
          name: hookEvent.tool_use.name,
          input: hookEvent.tool_use.input
        } : undefined,
        invocationState: this.config.enableErrorCapture ? hookEvent.invocation_state : undefined,
        startTime: Date.now(),
        metadata: {
          toolInvocationId: toolId,
          hookEventType: 'BeforeToolInvocationEvent',
          toolName: hookEvent.tool_use?.name,
          toolUseId: hookEvent.tool_use?.toolUseId
        }
      };
      
      if (this.config.enablePerformanceTracking) {
        this.performanceTracking.set(toolId, Date.now());
      }
      
      this.activeContexts.set(toolId, context);
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create after tool invocation hook
   */
  private createAfterToolInvocationHook() {
    return (hookEvent: any) => {
      const toolId = this.findActiveToolInvocationId(hookEvent.tool_use?.toolUseId);
      const startTime = this.performanceTracking.get(toolId || '');
      const endTime = Date.now();
      
      const context: HookEventContext = {
        hookType: SDKHookEventType.AFTER_TOOL_INVOCATION,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        traceId: toolId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        selectedTool: hookEvent.selected_tool,
        toolUse: hookEvent.tool_use ? {
          toolUseId: hookEvent.tool_use.toolUseId,
          name: hookEvent.tool_use.name,
          input: hookEvent.tool_use.input
        } : undefined,
        invocationState: this.config.enableErrorCapture ? hookEvent.invocation_state : undefined,
        toolResult: hookEvent.result,
        startTime,
        endTime,
        duration: startTime ? endTime - startTime : undefined,
        exception: hookEvent.exception,
        metadata: {
          toolInvocationId: toolId,
          hookEventType: 'AfterToolInvocationEvent',
          isReversed: true,
          toolName: hookEvent.tool_use?.name,
          toolUseId: hookEvent.tool_use?.toolUseId,
          hasException: !!hookEvent.exception,
          resultStatus: hookEvent.result?.status
        }
      };
      
      if (toolId) {
        this.activeContexts.delete(toolId);
        this.performanceTracking.delete(toolId);
      }
      
      this.processHookEvent(context);
    };
  }
  
  /**
   * Create message added hook
   */
  private createMessageAddedHook() {
    return (hookEvent: any) => {
      const context: HookEventContext = {
        hookType: SDKHookEventType.MESSAGE_ADDED,
        timestamp: new Date().toISOString(),
        sessionId: this.sessionId,
        agent: this.config.enableErrorCapture ? hookEvent.agent : undefined,
        message: hookEvent.message,
        metadata: {
          hookEventType: 'MessageAddedEvent',
          messageRole: hookEvent.message?.role,
          messageLength: JSON.stringify(hookEvent.message?.content || []).length
        }
      };
      
      this.processHookEvent(context);
    };
  }
  
  /**
   * Process hook event and convert to SDK native event
   */
  private processHookEvent(context: HookEventContext): void {
    this.eventCount++;
    
    const sdkEvent: SDKNativeEvent = {
      id: this.generateEventId(),
      timestamp: context.timestamp,
      type: this.mapHookTypeToSDKType(context.hookType),
      sessionId: this.sessionId,
      
      // Model context
      modelId: context.modelId,
      messages: context.messages,
      systemPrompt: context.systemPrompt,
      
      // Tool context
      toolName: context.toolUse?.name,
      toolInput: context.toolUse?.input,
      toolResult: context.toolResult,
      toolUseId: context.toolUse?.toolUseId,
      
      // Content
      content: context.message?.content,
      
      // Performance
      metrics: {
        latencyMs: context.duration,
        cycleCount: this.eventCount
      },
      
      // Error handling
      error: context.exception?.message,
      stopReason: context.stopResponse?.stopReason,
      
      // Rich metadata
      metadata: {
        ...context.metadata,
        hookType: context.hookType,
        traceId: context.traceId,
        startTime: context.startTime,
        endTime: context.endTime,
        duration: context.duration,
        hasException: !!context.exception,
        activeContexts: this.activeContexts.size,
        totalEvents: this.eventCount
      }
    };
    
    // Truncate large contexts if needed
    if (this.config.maxContextSize > 0) {
      const eventSize = JSON.stringify(sdkEvent).length;
      if (eventSize > this.config.maxContextSize) {
        sdkEvent.metadata = { ...sdkEvent.metadata, truncated: true, originalSize: eventSize };
        delete sdkEvent.messages;
        delete sdkEvent.toolInput;
      }
    }
    
    this.eventBridge.processSDKEvent(sdkEvent);
  }
  
  /**
   * Map hook type to SDK event type
   */
  private mapHookTypeToSDKType(hookType: SDKHookEventType): SDKEventType {
    switch (hookType) {
      case SDKHookEventType.AGENT_INITIALIZED:
        return SDKEventType.AGENT_INITIALIZED;
      case SDKHookEventType.BEFORE_MODEL_INVOCATION:
        return SDKEventType.MODEL_INVOCATION_START;
      case SDKHookEventType.AFTER_MODEL_INVOCATION:
        return SDKEventType.MODEL_INVOCATION_END;
      case SDKHookEventType.BEFORE_TOOL_INVOCATION:
        return SDKEventType.TOOL_INVOCATION_START;
      case SDKHookEventType.AFTER_TOOL_INVOCATION:
        return SDKEventType.TOOL_INVOCATION_END;
      case SDKHookEventType.MESSAGE_ADDED:
        return SDKEventType.MESSAGE_ADDED;
      default:
        return SDKEventType.METRICS_UPDATE;
    }
  }
  
  /**
   * Helper methods for ID generation and context tracking
   */
  private generateSessionId(): string {
    return `sdk_hook_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private generateEventId(): string {
    return `hook_evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private generateInvocationId(): string {
    return `inv_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  }
  
  private generateModelInvocationId(): string {
    return `model_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  }
  
  private generateToolInvocationId(toolUseId?: string): string {
    return toolUseId ? `tool_${toolUseId}` : `tool_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  }
  
  private findActiveInvocationId(hookEvent: any): string | undefined {
    // Try to match by agent reference or other context
    for (const [id, context] of this.activeContexts.entries()) {
      if (context.hookType === SDKHookEventType.BEFORE_INVOCATION && 
          context.agent === hookEvent.agent) {
        return id;
      }
    }
    return undefined;
  }
  
  private findActiveModelInvocationId(hookEvent: any): string | undefined {
    for (const [id, context] of this.activeContexts.entries()) {
      if (context.hookType === SDKHookEventType.BEFORE_MODEL_INVOCATION && 
          context.agent === hookEvent.agent) {
        return id;
      }
    }
    return undefined;
  }
  
  private findActiveToolInvocationId(toolUseId?: string): string | undefined {
    if (toolUseId) {
      return `tool_${toolUseId}`;
    }
    return undefined;
  }
  
  /**
   * Get current hook statistics
   */
  getHookStatistics(): Record<string, any> {
    return {
      sessionId: this.sessionId,
      totalEvents: this.eventCount,
      activeContexts: this.activeContexts.size,
      activePerformanceTracking: this.performanceTracking.size,
      config: this.config,
      eventBridgeMetrics: this.eventBridge.getSessionMetrics()
    };
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    this.activeContexts.clear();
    this.performanceTracking.clear();
    this.eventBridge.destroy();
    this.removeAllListeners();
  }
}

/**
 * Factory function to create SDK hook integration
 */
export function createSDKHookIntegration(config?: Partial<HookConfig>): SDKHookIntegration {
  return new SDKHookIntegration(config);
}