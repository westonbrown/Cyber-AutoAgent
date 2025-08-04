/**
 * SDK Metrics Collector - Enhanced observability using Strands SDK EventLoopMetrics
 * 
 * This service provides comprehensive metrics collection and aggregation using the
 * Strands SDK's native EventLoopMetrics system. It offers real-time performance
 * monitoring, cost tracking, tool usage analytics, and comprehensive observability
 * for the Cyber-AutoAgent system.
 * 
 * Key Features:
 * - Native integration with SDK's EventLoopMetrics and telemetry system
 * - Real-time cost tracking with token usage and model pricing
 * - Tool usage analytics with success rates and performance metrics
 * - Event loop performance monitoring with cycle analysis
 * - Memory and resource utilization tracking
 * - Export capabilities for external monitoring systems
 * - Thread-safe metrics aggregation and reporting
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.2.0
 * @since 2025-08-02
 */

import { EventEmitter } from 'events';
import { SDKTelemetryEvent, StreamEvent } from '../types/events.js';

/**
 * SDK Metrics Structure - Based on Strands EventLoopMetrics
 */
interface SDKEventLoopMetrics {
  // Core cycle metrics
  cycle_count: number;
  total_duration: number;
  average_cycle_time: number;
  cycle_durations: number[];
  
  // Token usage metrics
  accumulated_usage: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  
  // Performance metrics
  accumulated_metrics: {
    latencyMs: number;
  };
  
  // Tool usage metrics
  tool_usage: Record<string, {
    tool_info: {
      tool_use_id: string;
      name: string;
      input_params: any;
    };
    execution_stats: {
      call_count: number;
      success_count: number;
      error_count: number;
      total_time: number;
      average_time: number;
      success_rate: number;
    };
  }>;
  
  // Execution traces
  traces: Array<{
    id: string;
    name: string;
    raw_name?: string;
    parent_id?: string;
    start_time: number;
    end_time?: number;
    duration?: number;
    children: any[];
    metadata: Record<string, any>;
    message?: any;
  }>;
}

/**
 * Enhanced Metrics with cost tracking and analysis
 */
interface EnhancedMetrics extends SDKEventLoopMetrics {
  // Cost analysis
  cost_analysis: {
    total_estimated_cost: number;
    model_costs: Record<string, number>;
    tool_costs: Record<string, number>;
    currency: string;
    cost_per_token: number;
    cost_breakdown: {
      input_token_cost: number;
      output_token_cost: number;
      tool_execution_cost: number;
    };
  };
  
  // Performance analysis
  performance_analysis: {
    events_per_second: number;
    average_response_time: number;
    slowest_operations: Array<{
      operation: string;
      duration: number;
      timestamp: string;
    }>;
    error_rate: number;
    uptime: number;
  };
  
  // Resource utilization
  resource_utilization: {
    memory_usage_mb: number;
    active_connections: number;
    buffer_sizes: Record<string, number>;
    queue_depths: Record<string, number>;
  };
  
  // Session metadata
  session_metadata: {
    session_id: string;
    start_time: number;
    last_update: number;
    total_events: number;
    unique_tools: number;
    model_switches: number;
  };
}

/**
 * Metrics Collection Configuration
 */
interface MetricsConfig {
  enableCostTracking: boolean;
  enablePerformanceAnalysis: boolean;
  enableResourceMonitoring: boolean;
  costPerInputToken: number;
  costPerOutputToken: number;
  currency: string;
  maxTraceHistory: number;
  metricsRetentionHours: number;
  exportInterval: number;
}

/**
 * SDK Metrics Collector Service
 */
export class SDKMetricsCollector extends EventEmitter {
  private readonly config: MetricsConfig;
  private readonly sessionId: string;
  private readonly startTime: number;
  private metrics: EnhancedMetrics;
  private metricsUpdateInterval?: NodeJS.Timeout;
  private lastExport: number = 0;
  
  constructor(config: Partial<MetricsConfig> = {}) {
    super();
    
    this.config = {
      enableCostTracking: true,
      enablePerformanceAnalysis: true,
      enableResourceMonitoring: true,
      costPerInputToken: 0.0015, // Default for Claude-3.5-Sonnet per 1K tokens
      costPerOutputToken: 0.0075, // Default for Claude-3.5-Sonnet per 1K tokens
      currency: 'USD',
      maxTraceHistory: 1000,
      metricsRetentionHours: 24,
      exportInterval: 30000, // 30 seconds
      ...config
    };
    
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
    this.metrics = this.initializeMetrics();
    
    // Start periodic metrics updates
    this.startMetricsCollection();
  }
  
  /**
   * Process SDK EventLoopMetrics update
   */
  processSDKMetrics(sdkMetrics: any): void {
    try {
      // Update core SDK metrics
      this.updateCoreMetrics(sdkMetrics);
      
      // Perform cost analysis
      if (this.config.enableCostTracking) {
        this.updateCostAnalysis();
      }
      
      // Update performance analysis
      if (this.config.enablePerformanceAnalysis) {
        this.updatePerformanceAnalysis();
      }
      
      // Update resource utilization
      if (this.config.enableResourceMonitoring) {
        this.updateResourceUtilization();
      }
      
      // Emit metrics update event
      this.emitMetricsUpdate();
      
      // Export metrics if interval reached
      this.checkExportInterval();
      
    } catch (error) {
      console.error('Error processing SDK metrics:', error);
    }
  }
  
  /**
   * Update core metrics from SDK
   */
  private updateCoreMetrics(sdkMetrics: any): void {
    // Update cycle metrics
    if (sdkMetrics.cycle_count !== undefined) {
      this.metrics.cycle_count = sdkMetrics.cycle_count;
    }
    
    if (sdkMetrics.total_duration !== undefined) {
      this.metrics.total_duration = sdkMetrics.total_duration;
      this.metrics.average_cycle_time = this.metrics.cycle_count > 0 
        ? this.metrics.total_duration / this.metrics.cycle_count 
        : 0;
    }
    
    // Update usage metrics
    if (sdkMetrics.accumulated_usage) {
      this.metrics.accumulated_usage = {
        inputTokens: sdkMetrics.accumulated_usage.inputTokens || 0,
        outputTokens: sdkMetrics.accumulated_usage.outputTokens || 0,
        totalTokens: sdkMetrics.accumulated_usage.totalTokens || 0
      };
    }
    
    // Update performance metrics
    if (sdkMetrics.accumulated_metrics) {
      this.metrics.accumulated_metrics = {
        latencyMs: sdkMetrics.accumulated_metrics.latencyMs || 0
      };
    }
    
    // Update tool usage
    if (sdkMetrics.tool_usage) {
      this.metrics.tool_usage = sdkMetrics.tool_usage;
    }
    
    // Update traces
    if (sdkMetrics.traces) {
      this.metrics.traces = sdkMetrics.traces.slice(-this.config.maxTraceHistory);
    }
    
    // Update session metadata
    this.metrics.session_metadata.last_update = Date.now();
    this.metrics.session_metadata.total_events++;
    this.metrics.session_metadata.unique_tools = Object.keys(this.metrics.tool_usage).length;
  }
  
  /**
   * Update cost analysis
   */
  private updateCostAnalysis(): void {
    const usage = this.metrics.accumulated_usage;
    
    // Calculate token costs
    const inputCost = (usage.inputTokens / 1000) * this.config.costPerInputToken;
    const outputCost = (usage.outputTokens / 1000) * this.config.costPerOutputToken;
    
    // Estimate tool execution costs (placeholder - could be enhanced)
    const toolCost = Object.values(this.metrics.tool_usage)
      .reduce((sum, tool) => sum + (tool.execution_stats.call_count * 0.001), 0);
    
    this.metrics.cost_analysis = {
      total_estimated_cost: inputCost + outputCost + toolCost,
      model_costs: {
        'input_tokens': inputCost,
        'output_tokens': outputCost
      },
      tool_costs: Object.fromEntries(
        Object.entries(this.metrics.tool_usage).map(([name, tool]) => [
          name,
          tool.execution_stats.call_count * 0.001
        ])
      ),
      currency: this.config.currency,
      cost_per_token: (inputCost + outputCost) / Math.max(usage.totalTokens, 1),
      cost_breakdown: {
        input_token_cost: inputCost,
        output_token_cost: outputCost,
        tool_execution_cost: toolCost
      }
    };
  }
  
  /**
   * Update performance analysis
   */
  private updatePerformanceAnalysis(): void {
    const now = Date.now();
    const sessionDuration = now - this.startTime;
    const eventsPerSecond = this.metrics.session_metadata.total_events / (sessionDuration / 1000);
    
    // Calculate error rate
    const totalToolCalls = Object.values(this.metrics.tool_usage)
      .reduce((sum, tool) => sum + tool.execution_stats.call_count, 0);
    const totalErrors = Object.values(this.metrics.tool_usage)
      .reduce((sum, tool) => sum + tool.execution_stats.error_count, 0);
    const errorRate = totalToolCalls > 0 ? totalErrors / totalToolCalls : 0;
    
    // Find slowest operations from traces
    const slowestOps = this.metrics.traces
      .filter(trace => trace.duration !== undefined)
      .sort((a, b) => (b.duration || 0) - (a.duration || 0))
      .slice(0, 5)
      .map(trace => ({
        operation: trace.name,
        duration: trace.duration || 0,
        timestamp: new Date(trace.start_time).toISOString()
      }));
    
    this.metrics.performance_analysis = {
      events_per_second: eventsPerSecond,
      average_response_time: this.metrics.cycle_count > 0 
        ? this.metrics.accumulated_metrics.latencyMs / this.metrics.cycle_count 
        : 0,
      slowest_operations: slowestOps,
      error_rate: errorRate,
      uptime: sessionDuration
    };
  }
  
  /**
   * Update resource utilization (placeholder - would integrate with system monitoring)
   */
  private updateResourceUtilization(): void {
    // In a real implementation, this would integrate with system monitoring
    // For now, provide basic estimates
    this.metrics.resource_utilization = {
      memory_usage_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
      active_connections: 1, // Placeholder
      buffer_sizes: {
        event_buffer: this.metrics.traces.length,
        metrics_buffer: Object.keys(this.metrics.tool_usage).length
      },
      queue_depths: {
        processing_queue: 0 // Placeholder
      }
    };
  }
  
  /**
   * Emit metrics update event
   */
  private emitMetricsUpdate(): void {
    const telemetryEvent: SDKTelemetryEvent = {
      id: this.generateEventId(),
      timestamp: new Date().toISOString(),
      type: 'metrics_update' as any,
      sessionId: this.sessionId,
      
      metrics: {
        latencyMs: this.metrics.accumulated_metrics.latencyMs,
        cycleCount: this.metrics.cycle_count,
        toolCallCount: Object.values(this.metrics.tool_usage)
          .reduce((sum, tool) => sum + tool.execution_stats.call_count, 0),
        eventLoopDuration: this.metrics.total_duration
      },
      
      usage: this.metrics.accumulated_usage,
      
      cost: {
        totalCost: this.metrics.cost_analysis.total_estimated_cost,
        modelCost: this.metrics.cost_analysis.model_costs.input_tokens + 
                   this.metrics.cost_analysis.model_costs.output_tokens,
        toolCost: Object.values(this.metrics.cost_analysis.tool_costs)
          .reduce((sum, cost) => sum + cost, 0),
        currency: this.metrics.cost_analysis.currency
      }
    };
    
    this.emit('metrics_update', telemetryEvent);
  }
  
  /**
   * Check if export interval has been reached
   */
  private checkExportInterval(): void {
    const now = Date.now();
    if (now - this.lastExport >= this.config.exportInterval) {
      this.exportMetrics();
      this.lastExport = now;
    }
  }
  
  /**
   * Export metrics for external monitoring
   */
  private exportMetrics(): void {
    const exportData = {
      session_id: this.sessionId,
      timestamp: new Date().toISOString(),
      metrics: this.metrics,
      summary: this.getMetricsSummary()
    };
    
    this.emit('metrics_export', exportData);
  }
  
  /**
   * Initialize metrics structure
   */
  private initializeMetrics(): EnhancedMetrics {
    return {
      cycle_count: 0,
      total_duration: 0,
      average_cycle_time: 0,
      cycle_durations: [],
      
      accumulated_usage: {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0
      },
      
      accumulated_metrics: {
        latencyMs: 0
      },
      
      tool_usage: {},
      traces: [],
      
      cost_analysis: {
        total_estimated_cost: 0,
        model_costs: {},
        tool_costs: {},
        currency: this.config.currency,
        cost_per_token: 0,
        cost_breakdown: {
          input_token_cost: 0,
          output_token_cost: 0,
          tool_execution_cost: 0
        }
      },
      
      performance_analysis: {
        events_per_second: 0,
        average_response_time: 0,
        slowest_operations: [],
        error_rate: 0,
        uptime: 0
      },
      
      resource_utilization: {
        memory_usage_mb: 0,
        active_connections: 0,
        buffer_sizes: {},
        queue_depths: {}
      },
      
      session_metadata: {
        session_id: this.sessionId,
        start_time: this.startTime,
        last_update: this.startTime,
        total_events: 0,
        unique_tools: 0,
        model_switches: 0
      }
    };
  }
  
  /**
   * Start periodic metrics collection
   */
  private startMetricsCollection(): void {
    this.metricsUpdateInterval = setInterval(() => {
      // Trigger periodic updates
      if (this.config.enablePerformanceAnalysis) {
        this.updatePerformanceAnalysis();
      }
      
      if (this.config.enableResourceMonitoring) {
        this.updateResourceUtilization();
      }
      
      this.emitMetricsUpdate();
    }, 5000); // Update every 5 seconds
  }
  
  /**
   * Get comprehensive metrics summary
   */
  getMetricsSummary(): Record<string, any> {
    return {
      session: {
        id: this.sessionId,
        duration: Date.now() - this.startTime,
        uptime: this.metrics.performance_analysis.uptime
      },
      
      performance: {
        cycles: this.metrics.cycle_count,
        averageCycleTime: this.metrics.average_cycle_time,
        totalDuration: this.metrics.total_duration,
        eventsPerSecond: this.metrics.performance_analysis.events_per_second,
        errorRate: this.metrics.performance_analysis.error_rate
      },
      
      usage: this.metrics.accumulated_usage,
      
      costs: {
        total: this.metrics.cost_analysis.total_estimated_cost,
        breakdown: this.metrics.cost_analysis.cost_breakdown,
        currency: this.metrics.cost_analysis.currency
      },
      
      tools: Object.keys(this.metrics.tool_usage).length,
      
      resources: this.metrics.resource_utilization
    };
  }
  
  /**
   * Get current metrics (full structure)
   */
  getCurrentMetrics(): EnhancedMetrics {
    return { ...this.metrics };
  }
  
  /**
   * Reset metrics (useful for testing or new sessions)
   */
  resetMetrics(): void {
    this.metrics = this.initializeMetrics();
    this.emit('metrics_reset', { sessionId: this.sessionId });
  }
  
  /**
   * Generate unique IDs
   */
  private generateSessionId(): string {
    return `sdk_metrics_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  private generateEventId(): string {
    return `metrics_evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Clean up resources
   */
  destroy(): void {
    if (this.metricsUpdateInterval) {
      clearInterval(this.metricsUpdateInterval);
    }
    
    // Final export before cleanup
    this.exportMetrics();
    
    this.removeAllListeners();
  }
}

/**
 * Factory function to create SDK metrics collector
 */
export function createSDKMetricsCollector(config?: Partial<MetricsConfig>): SDKMetricsCollector {
  return new SDKMetricsCollector(config);
}