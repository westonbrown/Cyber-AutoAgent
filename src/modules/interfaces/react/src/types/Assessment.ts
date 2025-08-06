/**
 * Type definitions for the Cyber-AutoAgent assessment system
 */

export interface AssessmentParams {
  module: string;
  target: string;
  objective?: string;
  availableTools?: string[];
}

export interface AssessmentState {
  stage: 'welcome' | 'setup' | 'config' | 'module' | 'target' | 'objective' | 'ready' | 'assessing' | 'complete';
  module: string | null;
  target: string | null;
  objective: string | null; // Keep for backward compatibility but now optional
  error?: string;
}

export interface Module {
  name: string;
  path: string;
  description: string;
  tools: string[];
}

export interface Memory {
  id: string;
  target: string;
  content: string;
  severity?: 'critical' | 'high' | 'medium' | 'low';
  category?: string;
  confidence?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface SessionInfo {
  id: string;
  target: string;
  module: string;
  objective?: string;
  startTime: Date;
  endTime?: Date;
  status: 'running' | 'complete' | 'error' | 'interrupted';
  findings?: number;
  outputPath?: string;
}

export interface ProviderConfig {
  type: 'bedrock' | 'ollama' | 'openai' | 'litellm';
  region?: string;
  apiKey?: string;
  host?: string;
  model?: string;
}