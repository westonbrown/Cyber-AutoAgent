/**
 * OperationManager cost calculation tests across pricing matrices
 */
import { describe, it, expect } from '@jest/globals';
import { OperationManager } from '../../../src/services/OperationManager.js';
import type { Config } from '../../../src/contexts/ConfigContext.js';

describe('OperationManager cost calculation', () => {
  const baseConfig: Config = {
    // minimal viable config
    modelProvider: 'bedrock',
    modelId: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
    awsRegion: 'us-east-1',
    dockerImage: 'image',
    dockerTimeout: 300,
    volumes: [],
    iterations: 10,
    autoApprove: true,
    confirmations: false,
    maxThreads: 5,
    outputFormat: 'markdown',
    verbose: false,
    memoryMode: 'auto',
    keepMemory: true,
    memoryBackend: 'FAISS',
    outputDir: './outputs',
    unifiedOutput: true,
    theme: 'retro',
    showMemoryUsage: false,
    showOperationId: true,
    environment: {},
    reportSettings: { includeRemediation: true, includeCWE: true, includeTimestamps: true, includeEvidence: true, includeMemoryOps: true },
    observability: false,
    isConfigured: true,
    allowExecutionFallback: true,
    modelPricing: {
      'us.anthropic.claude-sonnet-4-20250514-v1:0': { inputCostPer1k: 0.006, outputCostPer1k: 0.03 },
      'claude-3-haiku-20240307-v1:0': { inputCostPer1k: 0.00025, outputCostPer1k: 0.00125 },
      'llama3.2:3b': { inputCostPer1k: 0, outputCostPer1k: 0 }, // local free
    },
  } as any;

  it('computes estimatedCost from input/output token totals and pricing', () => {
    const om = new OperationManager(baseConfig);
    const op = om.startOperation('general', 'example.com', 'assessment', 'us.anthropic.claude-sonnet-4-20250514-v1:0');

    om.updateTokenUsage(op.id, 2000, 1000); // 2k input, 1k output
    const updated = om.getOperation(op.id)!;
    // expected cost = (2k/1k)*0.006 + (1k/1k)*0.03 = 0.012 + 0.03 = 0.042
    expect(Number(updated.cost.estimatedCost.toFixed(6))).toBeCloseTo(0.042, 6);
  });

  it('uses config pricing for alternative model and yields different cost', () => {
    const om = new OperationManager(baseConfig);
    const op = om.startOperation('general', 'example.com', 'assessment', 'claude-3-haiku-20240307-v1:0');
    om.updateTokenUsage(op.id, 1000, 2000);
    const updated = om.getOperation(op.id)!;
    const expected = (1000/1000)*0.00025 + (2000/1000)*0.00125; // 0.00025 + 0.0025 = 0.00275
    expect(Number(updated.cost.estimatedCost.toFixed(6))).toBeCloseTo(expected, 6);
  });

  it('treats ollama provider as free (0 cost)', () => {
    const cfg = { ...baseConfig, modelProvider: 'ollama' as const };
    const om = new OperationManager(cfg);
    const op = om.startOperation('general', 'example.com', 'assessment', 'llama3.2:3b');
    om.updateTokenUsage(op.id, 5000, 5000);
    const updated = om.getOperation(op.id)!;
    expect(updated.cost.estimatedCost).toBe(0);
  });
});
