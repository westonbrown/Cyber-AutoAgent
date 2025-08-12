/**
 * Operation Management Service
 * Handles operation lifecycle, progress tracking, cost monitoring, and model switching
 * Now uses configurable pricing from ConfigContext instead of hardcoded values
 */

import { Config } from '../contexts/ConfigContext.js';
import { loggingService } from './LoggingService.js';

export interface Operation {
  id: string;
  module: string;
  target: string;
  objective: string;
  startTime: Date;
  endTime?: Date;
  currentStep: number;
  totalSteps: number;
  status: 'running' | 'paused' | 'completed' | 'error' | 'cancelled';
  description: string;
  findings: number;
  logs: OperationLog[];
  cost: CostInfo;
  model: string;
}

export interface OperationLog {
  timestamp: Date;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  tool?: string;
  step?: number;
}

export interface CostInfo {
  tokensUsed: number;
  estimatedCost: number;
  inputTokens: number;
  outputTokens: number;
  modelPricing: {
    inputCostPer1k: number;
    outputCostPer1k: number;
  };
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  inputCostPer1k: number;
  outputCostPer1k: number;
  contextLimit: number;
  isAvailable: boolean;
}

export class OperationManager {
  private operations: Map<string, Operation> = new Map();
  private currentOperation: Operation | null = null;
  private config: Config;
  private sessionCost: CostInfo = {
    tokensUsed: 0,
    estimatedCost: 0,
    inputTokens: 0,
    outputTokens: 0,
    modelPricing: { inputCostPer1k: 0, outputCostPer1k: 0 }
  };

  constructor(config: Config) {
    this.config = config;
    // Load session data if available
    this.loadSessionData();
  }

  // Get available models with pricing from configuration
  private getAvailableModelsFromConfig(): ModelInfo[] {
    const models: ModelInfo[] = [];
    
    // Add models from configuration pricing
    if (this.config.modelPricing) {
      Object.entries(this.config.modelPricing).forEach(([modelId, pricing]) => {
        models.push({
          id: modelId,
          name: this.getModelDisplayName(modelId),
          provider: 'bedrock',
          inputCostPer1k: pricing.inputCostPer1k,
          outputCostPer1k: pricing.outputCostPer1k,
          contextLimit: this.getModelContextLimit(modelId),
          isAvailable: true
        });
      });
    }
    
    return models;
  }

  // Helper to get display names for models
  private getModelDisplayName(modelId: string): string {
    const nameMap: { [key: string]: string } = {
      'us.anthropic.claude-sonnet-4-20250514-v1:0': 'Claude Sonnet 4',
      'claude-3-5-sonnet-20241022-v2:0': 'Claude 3.5 Sonnet v2',
      'claude-3-5-sonnet-20240620-v1:0': 'Claude 3.5 Sonnet v1',
      'claude-3-haiku-20240307-v1:0': 'Claude 3 Haiku',
      'claude-3-sonnet-20240229-v1:0': 'Claude 3 Sonnet',
      'claude-3-opus-20240229-v1:0': 'Claude 3 Opus',
      'anthropic.claude-v2': 'Claude 2.0',
      'anthropic.claude-v2:1': 'Claude 2.1',
      'anthropic.claude-instant-v1': 'Claude Instant',
      'meta.llama3-1-405b-instruct-v1:0': 'Llama 3.1 405B',
      'meta.llama3-1-70b-instruct-v1:0': 'Llama 3.1 70B',
      'meta.llama3-1-8b-instruct-v1:0': 'Llama 3.1 8B',
      'amazon.titan-text-premier-v1:0': 'Amazon Titan Premier',
      'amazon.titan-text-express-v1': 'Amazon Titan Express',
      'cohere.command-r-plus-v1:0': 'Cohere Command R+',
      'cohere.command-r-v1:0': 'Cohere Command R'
    };
    return nameMap[modelId] || modelId;
  }

  // Helper to get context limits for models
  private getModelContextLimit(modelId: string): number {
    const contextLimits: { [key: string]: number } = {
      'us.anthropic.claude-sonnet-4-20250514-v1:0': 200000,
      'claude-3-5-sonnet-20241022-v2:0': 200000,
      'claude-3-5-sonnet-20240620-v1:0': 200000,
      'claude-3-haiku-20240307-v1:0': 200000,
      'claude-3-sonnet-20240229-v1:0': 200000,
      'claude-3-opus-20240229-v1:0': 200000,
      'anthropic.claude-v2': 100000,
      'anthropic.claude-v2:1': 200000,
      'anthropic.claude-instant-v1': 100000,
      'meta.llama3-1-405b-instruct-v1:0': 128000,
      'meta.llama3-1-70b-instruct-v1:0': 128000,
      'meta.llama3-1-8b-instruct-v1:0': 128000,
      'amazon.titan-text-premier-v1:0': 32000,
      'amazon.titan-text-express-v1': 8000,
      'cohere.command-r-plus-v1:0': 128000,
      'cohere.command-r-v1:0': 128000
    };
    return contextLimits[modelId] || 8000;
  }

  // Start a new operation
  startOperation(module: string, target: string, objective: string, model: string): Operation {
    const operation: Operation = {
      id: this.generateOperationId(),
      module,
      target,
      objective,
      startTime: new Date(),
      currentStep: 0,
      totalSteps: 50, // Default, will be updated
      status: 'running',
      description: 'Initializing operation...',
      findings: 0,
      logs: [],
      cost: {
        tokensUsed: 0,
        estimatedCost: 0,
        inputTokens: 0,
        outputTokens: 0,
        modelPricing: this.getModelPricing(model)
      },
      model
    };

    this.operations.set(operation.id, operation);
    this.currentOperation = operation;
    
    this.addLog(operation.id, 'info', `Operation started: ${module} → ${target}`);
    
    return operation;
  }

  // Update operation progress
  updateProgress(operationId: string, step: number, totalSteps: number, description: string): void {
    const operation = this.operations.get(operationId);
    if (!operation) return;

    operation.currentStep = step;
    operation.totalSteps = totalSteps;
    operation.description = description;
    
    this.addLog(operationId, 'info', `Step ${step}/${totalSteps}: ${description}`);
  }

  // Update operation with partial updates
  updateOperation(operationId: string, updates: Partial<Operation>): void {
    const operation = this.operations.get(operationId);
    if (operation) {
      Object.assign(operation, updates);
      this.operations.set(operationId, operation);
    }
  }

  // Add finding to operation
  addFinding(operationId: string, finding: string): void {
    const operation = this.operations.get(operationId);
    if (!operation) return;

    operation.findings++;
    this.addLog(operationId, 'success', `Finding #${operation.findings}: ${finding}`);
  }

  // Pause operation
  pauseOperation(operationId: string): boolean {
    const operation = this.operations.get(operationId);
    if (!operation || operation.status !== 'running') return false;

    operation.status = 'paused';
    this.addLog(operationId, 'warning', 'Operation paused');
    return true;
  }

  // Resume operation
  resumeOperation(operationId: string): boolean {
    const operation = this.operations.get(operationId);
    if (!operation || operation.status !== 'paused') return false;

    operation.status = 'running';
    this.addLog(operationId, 'info', 'Operation resumed');
    return true;
  }

  // Complete operation
  completeOperation(operationId: string, success: boolean = true): void {
    const operation = this.operations.get(operationId);
    if (!operation) return;

    operation.status = success ? 'completed' : 'error';
    operation.endTime = new Date();
    
    const duration = Math.floor((operation.endTime.getTime() - operation.startTime.getTime()) / 1000);
    this.addLog(operationId, success ? 'success' : 'error', 
      `Operation ${success ? 'completed' : 'failed'} in ${duration}s with ${operation.findings} findings`);

    if (this.currentOperation?.id === operationId) {
      this.currentOperation = null;
    }
  }

  // Switch model during operation
  switchModel(operationId: string, newModel: string): boolean {
    const operation = this.operations.get(operationId);
    if (!operation) return false;

    const oldModel = operation.model;
    operation.model = newModel;
    operation.cost.modelPricing = this.getModelPricing(newModel);
    
    this.addLog(operationId, 'info', `Model switched from ${oldModel} to ${newModel}`);
    return true;
  }

  // Update token usage
  updateTokenUsage(operationId: string, inputTokens: number, outputTokens: number): void {
    const operation = this.operations.get(operationId);
    if (!operation) return;

    operation.cost.inputTokens += inputTokens;
    operation.cost.outputTokens += outputTokens;
    operation.cost.tokensUsed = operation.cost.inputTokens + operation.cost.outputTokens;
    
    // Calculate cost
    const pricing = operation.cost.modelPricing;
    operation.cost.estimatedCost = 
      (operation.cost.inputTokens / 1000) * pricing.inputCostPer1k +
      (operation.cost.outputTokens / 1000) * pricing.outputCostPer1k;

    // Update session totals
    this.sessionCost.inputTokens += inputTokens;
    this.sessionCost.outputTokens += outputTokens;
    this.sessionCost.tokensUsed = this.sessionCost.inputTokens + this.sessionCost.outputTokens;
    this.sessionCost.estimatedCost += (inputTokens / 1000) * pricing.inputCostPer1k + (outputTokens / 1000) * pricing.outputCostPer1k;
  }

  // Add log entry
  addLog(operationId: string, level: OperationLog['level'], message: string, tool?: string): void {
    const operation = this.operations.get(operationId);
    if (!operation) return;

    operation.logs.push({
      timestamp: new Date(),
      level,
      message,
      tool,
      step: operation.currentStep
    });
  }

  // Get current operation
  getCurrentOperation(): Operation | null {
    return this.currentOperation;
  }

  // Get operation by ID
  getOperation(operationId: string): Operation | null {
    return this.operations.get(operationId) || null;
  }

  // Get all operations
  getAllOperations(): Operation[] {
    return Array.from(this.operations.values());
  }

  // Get session cost
  getSessionCost(): CostInfo {
    return { ...this.sessionCost };
  }

  // Get available models
  getAvailableModels(): ModelInfo[] {
    return this.getAvailableModelsFromConfig();
  }

  // Get model info
  getModelInfo(modelId: string): ModelInfo | null {
    const models = this.getAvailableModelsFromConfig();
    return models.find(m => m.id === modelId) || null;
  }

  // Calculate context usage percentage
  calculateContextUsage(modelId: string, tokensUsed: number): number {
    const model = this.getModelInfo(modelId);
    if (!model) return 0;
    
    return Math.max(0, Math.min(100, (tokensUsed / model.contextLimit) * 100));
  }

  // Get operation duration as formatted string
  getOperationDuration(operationId: string): string {
    const operation = this.operations.get(operationId);
    if (!operation) return '0s';
    
    const endTime = operation.endTime || new Date();
    const duration = endTime.getTime() - operation.startTime.getTime();
    
    const seconds = Math.floor(duration / 1000) % 60;
    const minutes = Math.floor(duration / (1000 * 60)) % 60;
    const hours = Math.floor(duration / (1000 * 60 * 60));
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  }

  // Private methods
  private generateOperationId(): string {
    const timestamp = new Date().toISOString().replace(/[-:.]/g, '').slice(0, 15);
    const random = Math.random().toString(36).substring(2, 6);
    return `OP_${timestamp}_${random}`;
  }

  private getModelPricing(modelId: string): { inputCostPer1k: number; outputCostPer1k: number } {
    // Try to get pricing from configuration first
    if (this.config.modelPricing && this.config.modelPricing[modelId]) {
      const pricing = this.config.modelPricing[modelId];
      return {
        inputCostPer1k: pricing.inputCostPer1k,
        outputCostPer1k: pricing.outputCostPer1k
      };
    }
    
    // Fallback to model info if not in config pricing
    const model = this.getModelInfo(modelId);
    return model ? 
      { inputCostPer1k: model.inputCostPer1k, outputCostPer1k: model.outputCostPer1k } :
      { inputCostPer1k: 0, outputCostPer1k: 0 };
  }

  private loadSessionData(): void {
    // Load session data from memory (localStorage not available in Node.js)
    // In production, this would use a file-based storage or database
    try {
      // For now, just use in-memory storage
      // Session data initialized silently
    } catch (error) {
      // Only log errors to avoid interfering with React Ink UI
      loggingService.warn('Failed to load session data:', error);
    }
  }

  private saveSessionData(): void {
    // Save session data (localStorage not available in Node.js)
    // In production, this would use a file-based storage or database
    try {
      // For now, just use in-memory storage
      // Session data saved to memory - silent operation
    } catch (error) {
      loggingService.warn('Failed to save session data:', error);
    }
  }

  // Clean up and save data
  destroy(): void {
    this.saveSessionData();
  }
}