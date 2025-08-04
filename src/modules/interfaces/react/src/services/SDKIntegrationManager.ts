/**
 * SDK Integration Manager - Unified service for Strands SDK integration
 * 
 * This service orchestrates all SDK-aligned components to provide a unified
 * interface for integrating with the Strands SDK's event system, streaming
 * capabilities, hook system, and telemetry. It serves as the main entry point
 * for React components to interact with SDK native features while maintaining
 * backward compatibility with existing implementations.
 * 
 * Key Features:
 * - Unified SDK integration with comprehensive event streaming
 * - Automatic hook registration and event capture
 * - Real-time metrics collection and cost tracking
 * - Backward compatibility with existing React event system
 * - Thread-safe service orchestration and lifecycle management
 * - Built-in error handling and recovery mechanisms
 * - Export capabilities for external monitoring and analytics
 * 
 * @author Cyber-AutoAgent Team  
 * @version 0.2.0
 * @since 2025-08-02
 */

import { EventEmitter } from 'events';
import { SDKEventStreamBridge } from './SDKEventStreamBridge.js';
import { SDKEnhancedCallbackHandler } from './SDKEnhancedCallbackHandler.js';
import { SDKHookIntegration } from './SDKHookIntegration.js';
import { SDKMetricsCollector } from './SDKMetricsCollector.js';
import { StreamEvent, SDKTelemetryEvent } from '../types/events.js';

/**
 * Integration Configuration
 */
interface SDKIntegrationConfig {
  // Feature flags
  enableSDKStreaming: boolean;
  enableHookIntegration: boolean;
  enableMetricsCollection: boolean;
  enableCostTracking: boolean;
  enableLegacyCompatibility: boolean;
  
  // Performance settings
  streamBufferMs: number;
  metricsUpdateInterval: number;
  maxEventHistory: number;
  maxTraceHistory: number;
  
  // Cost tracking
  costPerInputToken: number;
  costPerOutputToken: number;
  currency: string;
  
  // Export settings
  enableMetricsExport: boolean;
  exportInterval: number;
  exportFormat: 'json' | 'prometheus' | 'datadog';
  
  // Debug settings
  enableDebugLogging: boolean;
  logLevel: 'info' | 'debug' | 'trace';
}

/**
 * Integration Status
 */
interface IntegrationStatus {
  isInitialized: boolean;
  isStreaming: boolean;
  isCollectingMetrics: boolean;
  hasErrors: boolean;
  lastError?: string;
  startTime: number;
  uptime: number;
  
  // Service status
  services: {
    eventBridge: boolean;
    callbackHandler: boolean;
    hookIntegration: boolean;
    metricsCollector: boolean;
  };
  
  // Statistics
  stats: {
    totalEvents: number;
    totalStreamEvents: number;
    totalHookEvents: number;
    totalMetricsUpdates: number;
    errorCount: number;
  };
}

/**
 * SDK Integration Manager
 */
export class SDKIntegrationManager extends EventEmitter {
  private readonly config: SDKIntegrationConfig;
  private readonly sessionId: string;
  private readonly startTime: number;
  
  // SDK service instances
  private eventBridge?: SDKEventStreamBridge;
  private callbackHandler?: SDKEnhancedCallbackHandler;
  private hookIntegration?: SDKHookIntegration;
  private metricsCollector?: SDKMetricsCollector;
  
  // Status tracking
  private status: IntegrationStatus;
  private eventHistory: StreamEvent[] = [];
  private statusUpdateInterval?: NodeJS.Timeout;
  
  constructor(config: Partial<SDKIntegrationConfig> = {}) {
    super();
    
    this.config = {
      // Feature flags
      enableSDKStreaming: true,
      enableHookIntegration: true,
      enableMetricsCollection: true,
      enableCostTracking: true,
      enableLegacyCompatibility: true,
      
      // Performance settings
      streamBufferMs: 100,
      metricsUpdateInterval: 5000,
      maxEventHistory: 10000,
      maxTraceHistory: 1000,
      
      // Cost tracking
      costPerInputToken: 0.0015, // Claude-3.5-Sonnet pricing
      costPerOutputToken: 0.0075,
      currency: 'USD',
      
      // Export settings
      enableMetricsExport: true,
      exportInterval: 30000,
      exportFormat: 'json',
      
      // Debug settings
      enableDebugLogging: false,
      logLevel: 'info',
      
      ...config
    };
    
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
    this.status = this.initializeStatus();
    
    this.debugLog('SDK Integration Manager initialized', { sessionId: this.sessionId });
  }
  
  /**
   * Initialize all SDK services
   */
  async initialize(): Promise<void> {
    try {
      this.debugLog('Initializing SDK services...');
      
      // Initialize event bridge
      if (this.config.enableSDKStreaming) {
        await this.initializeEventBridge();
      }
      
      // Initialize callback handler
      await this.initializeCallbackHandler();
      
      // Initialize hook integration
      if (this.config.enableHookIntegration) {
        await this.initializeHookIntegration();
      }
      
      // Initialize metrics collector
      if (this.config.enableMetricsCollection) {
        await this.initializeMetricsCollector();
      }
      
      // Wire up service connections
      this.wireServices();
      
      // Start status monitoring
      this.startStatusMonitoring();
      
      this.status.isInitialized = true;
      this.debugLog('SDK Integration Manager initialized successfully');
      
      this.emit('initialized', { sessionId: this.sessionId, status: this.status });
      
    } catch (error) {
      this.handleError('Failed to initialize SDK Integration Manager', error);
      throw error;
    }
  }
  
  /**
   * Initialize event bridge
   */
  private async initializeEventBridge(): Promise<void> {
    this.eventBridge = new SDKEventStreamBridge({
      enableReasoningStream: true,
      enableMetricsStream: this.config.enableMetricsCollection,
      enableDebugEvents: this.config.enableDebugLogging,
      bufferDeltas: true,
      deltaBufferMs: this.config.streamBufferMs
    });
    
    this.eventBridge.on('stream_event', (event: StreamEvent) => {
      this.handleStreamEvent(event);
    });
    
    this.status.services.eventBridge = true;
    this.debugLog('Event bridge initialized');
  }
  
  /**
   * Initialize callback handler
   */
  private async initializeCallbackHandler(): Promise<void> {
    this.callbackHandler = new SDKEnhancedCallbackHandler();
    
    this.callbackHandler.on('stream_event', (event: StreamEvent) => {
      this.handleStreamEvent(event);
    });
    
    this.status.services.callbackHandler = true;
    this.debugLog('Callback handler initialized');
  }
  
  /**
   * Initialize hook integration
   */
  private async initializeHookIntegration(): Promise<void> {
    this.hookIntegration = new SDKHookIntegration({
      enableModelHooks: true,
      enableToolHooks: true,
      enableMessageHooks: true,
      enableAgentHooks: true,
      enablePerformanceTracking: this.config.enableMetricsCollection,
      enableErrorCapture: true,
      maxContextSize: 1000000
    });
    
    this.hookIntegration.on('stream_event', (event: StreamEvent) => {
      this.handleStreamEvent(event);
      this.status.stats.totalHookEvents++;
    });
    
    this.status.services.hookIntegration = true;
    this.debugLog('Hook integration initialized');
  }
  
  /**
   * Initialize metrics collector
   */
  private async initializeMetricsCollector(): Promise<void> {
    this.metricsCollector = new SDKMetricsCollector({
      enableCostTracking: this.config.enableCostTracking,
      enablePerformanceAnalysis: true,
      enableResourceMonitoring: true,
      costPerInputToken: this.config.costPerInputToken,
      costPerOutputToken: this.config.costPerOutputToken,
      currency: this.config.currency,
      maxTraceHistory: this.config.maxTraceHistory,
      exportInterval: this.config.exportInterval
    });
    
    this.metricsCollector.on('metrics_update', (event: SDKTelemetryEvent) => {
      this.handleMetricsUpdate(event);
    });
    
    this.metricsCollector.on('metrics_export', (data: any) => {
      this.emit('metrics_export', data);
    });
    
    this.status.services.metricsCollector = true;
    this.debugLog('Metrics collector initialized');
  }
  
  /**
   * Wire up connections between services
   */
  private wireServices(): void {
    // Connect metrics collector to receive SDK metrics
    if (this.metricsCollector && this.callbackHandler) {
      // The callback handler would provide SDK metrics to the collector
      // This would typically happen through the Python/SDK integration
    }
    
    this.debugLog('Services wired together');
  }
  
  /**
   * Handle stream events from any service
   */
  private handleStreamEvent(event: StreamEvent): void {
    try {
      // Add to event history
      this.eventHistory.push(event);
      
      // Trim history if needed
      if (this.eventHistory.length > this.config.maxEventHistory) {
        this.eventHistory = this.eventHistory.slice(-this.config.maxEventHistory);
      }
      
      // Update statistics
      this.status.stats.totalEvents++;
      this.status.stats.totalStreamEvents++;
      
      // Emit to external listeners
      this.emit('stream_event', event);
      
      this.debugLog('Stream event processed', { type: event.type });
      
    } catch (error) {
      this.handleError('Error processing stream event', error);
    }
  }
  
  /**
   * Handle metrics updates
   */
  private handleMetricsUpdate(event: SDKTelemetryEvent): void {
    try {
      this.status.stats.totalMetricsUpdates++;
      this.emit('metrics_update', event);
      
      this.debugLog('Metrics update processed');
      
    } catch (error) {
      this.handleError('Error processing metrics update', error);
    }
  }
  
  /**
   * Get SDK hook callbacks for Python integration
   * Returns functions that can be registered with the Strands SDK
   */
  getSDKHookCallbacks(): Record<string, Function> {
    if (!this.hookIntegration) {
      throw new Error('Hook integration not initialized');
    }
    
    return this.hookIntegration.registerSDKHooks();
  }
  
  /**
   * Get SDK callback handler for Python integration
   * Returns the callback handler that can be used with SDK agents
   */
  getSDKCallbackHandler(): SDKEnhancedCallbackHandler {
    if (!this.callbackHandler) {
      throw new Error('Callback handler not initialized');
    }
    
    return this.callbackHandler;
  }
  
  /**
   * Process SDK metrics (called from Python integration)
   */
  processSDKMetrics(sdkMetrics: any): void {
    if (this.metricsCollector) {
      this.metricsCollector.processSDKMetrics(sdkMetrics);
    }
  }
  
  /**
   * Get current integration status
   */
  getStatus(): IntegrationStatus {
    this.status.uptime = Date.now() - this.startTime;
    return { ...this.status };
  }
  
  /**
   * Get comprehensive metrics summary
   */
  getMetricsSummary(): Record<string, any> {
    const summary: Record<string, any> = {
      session: {
        id: this.sessionId,
        uptime: Date.now() - this.startTime,
        status: this.status
      },
      
      events: {
        totalEvents: this.status.stats.totalEvents,
        streamEvents: this.status.stats.totalStreamEvents,
        hookEvents: this.status.stats.totalHookEvents,
        recentEvents: this.eventHistory.slice(-10).map(e => ({ type: e.type, timestamp: e.timestamp }))
      }
    };
    
    // Add SDK metrics if available
    if (this.metricsCollector) {
      summary.sdkMetrics = this.metricsCollector.getMetricsSummary();
    }
    
    return summary;
  }
  
  /**
   * Get event history
   */
  getEventHistory(limit?: number): StreamEvent[] {
    if (limit) {
      return this.eventHistory.slice(-limit);
    }
    return [...this.eventHistory];
  }
  
  /**
   * Clear event history
   */
  clearEventHistory(): void {
    this.eventHistory = [];
    this.debugLog('Event history cleared');
  }
  
  /**
   * Start status monitoring
   */
  private startStatusMonitoring(): void {
    this.statusUpdateInterval = setInterval(() => {
      this.status.uptime = Date.now() - this.startTime;
      this.emit('status_update', this.status);
    }, this.config.metricsUpdateInterval);
  }
  
  /**
   * Initialize status structure
   */
  private initializeStatus(): IntegrationStatus {
    return {
      isInitialized: false,
      isStreaming: false,
      isCollectingMetrics: false,
      hasErrors: false,
      startTime: this.startTime,
      uptime: 0,
      
      services: {
        eventBridge: false,
        callbackHandler: false,
        hookIntegration: false,
        metricsCollector: false
      },
      
      stats: {
        totalEvents: 0,
        totalStreamEvents: 0,
        totalHookEvents: 0,
        totalMetricsUpdates: 0,
        errorCount: 0
      }
    };
  }
  
  /**
   * Handle errors
   */
  private handleError(message: string, error: any): void {
    this.status.hasErrors = true;
    this.status.lastError = `${message}: ${error.message || error}`;
    this.status.stats.errorCount++;
    
    console.error(`[SDKIntegrationManager] ${message}:`, error);
    this.emit('error', { message, error, sessionId: this.sessionId });
  }
  
  /**
   * Debug logging
   */
  private debugLog(message: string, data?: any): void {
    if (this.config.enableDebugLogging) {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [SDKIntegrationManager] ${message}`, data || '');
    }
  }
  
  /**
   * Generate unique session ID
   */
  private generateSessionId(): string {
    return `sdk_integration_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Clean up all services and resources
   */
  destroy(): void {
    this.debugLog('Destroying SDK Integration Manager...');
    
    if (this.statusUpdateInterval) {
      clearInterval(this.statusUpdateInterval);
    }
    
    // Destroy all services
    if (this.eventBridge) {
      this.eventBridge.destroy();
    }
    
    if (this.callbackHandler) {
      this.callbackHandler.destroy();
    }
    
    if (this.hookIntegration) {
      this.hookIntegration.destroy();
    }
    
    if (this.metricsCollector) {
      this.metricsCollector.destroy();
    }
    
    // Clear event history
    this.eventHistory = [];
    
    this.removeAllListeners();
    
    this.debugLog('SDK Integration Manager destroyed');
  }
}

/**
 * Factory function to create and initialize SDK integration manager
 */
export async function createSDKIntegrationManager(config?: Partial<SDKIntegrationConfig>): Promise<SDKIntegrationManager> {
  const manager = new SDKIntegrationManager(config);
  await manager.initialize();
  return manager;
}