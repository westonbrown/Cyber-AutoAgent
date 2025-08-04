import { describe, it, expect, beforeEach } from '@jest/globals';
import { AssessmentFlow } from '../services/AssessmentFlow.js';

describe('AssessmentFlow', () => {
  let flow: AssessmentFlow;
  
  beforeEach(() => {
    flow = new AssessmentFlow();
  });
  
  describe('Initial State', () => {
    it('should start in module stage', () => {
      expect(flow.getCurrentWorkflowStage()).toBe('module');
    });
    
    it('should have null values for module, target, and objective', () => {
      const state = flow.getState();
      expect(state.module).toBeNull();
      expect(state.target).toBeNull();
      expect(state.objective).toBeNull();
    });
    
    it('should not be ready initially', () => {
      expect(flow.isReadyForAssessmentExecution()).toBe(false);
    });
  });
  
  describe('Module Input', () => {
    it('should accept valid module command', () => {
      const result = flow.processUserInput('module general');
      expect(result.success).toBe(true);
      expect(result.message).toContain('loaded successfully');
      expect(flow.getCurrentWorkflowStage()).toBe('target');
    });
    
    it('should reject invalid module', () => {
      const result = flow.processUserInput('module invalid_module');
      expect(result.success).toBe(false);
      expect(result.error).toContain('Available modules:');
    });
    
    it('should require module command format', () => {
      const result = flow.processUserInput('general');
      expect(result.success).toBe(false);
      expect(result.error).toContain('Usage: module');
    });
  });
  
  describe('Target Input', () => {
    beforeEach(() => {
      flow.processUserInput('module general');
    });
    
    it('should accept valid target command', () => {
      const result = flow.processUserInput('target example.com');
      expect(result.success).toBe(true);
      expect(result.message).toContain('Target');
      expect(flow.getCurrentWorkflowStage()).toBe('objective');
    });
    
    it('should accept target without normalization', () => {
      flow.processUserInput('target example.com');
      const state = flow.getState();
      expect(state.target).toBe('example.com');
    });
    
    it('should accept any target format', () => {
      flow.processUserInput('target localhost:8080/api/v1');
      const state = flow.getState();
      expect(state.target).toBe('localhost:8080/api/v1');
    });
    
    it('should require target command format', () => {
      const result = flow.processUserInput('example.com');
      expect(result.success).toBe(false);
      expect(result.error).toContain('Usage: target');
    });
  });
  
  describe('Objective Input', () => {
    beforeEach(() => {
      flow.processUserInput('module general');
      flow.processUserInput('target https://api.example.com');
    });
    
    it('should accept custom objective', () => {
      const result = flow.processUserInput('test for SQL injection');
      expect(result.success).toBe(true);
      expect(flow.getCurrentWorkflowStage()).toBe('ready');
      expect(flow.isReadyForAssessmentExecution()).toBe(true);
    });
    
    it('should accept empty objective for default', () => {
      const result = flow.processUserInput('');
      expect(result.success).toBe(true);
      expect(result.message).toContain('default');
      expect(flow.getCurrentWorkflowStage()).toBe('ready');
    });
  });
  
  describe('Complete Flow', () => {
    it('should complete full flow and provide parameters', () => {
      flow.processUserInput('module network');
      flow.processUserInput('target 192.168.1.1');
      flow.processUserInput('port scanning');
      
      expect(flow.isReadyForAssessmentExecution()).toBe(true);
      
      const params = flow.getValidatedAssessmentParameters();
      expect(params).not.toBeNull();
      expect(params?.module).toBe('network');
      expect(params?.target).toBe('192.168.1.1');
      expect(params?.objective).toBe('port scanning');
    });
  });
  
  describe('Reset Functionality', () => {
    it('should reset entire flow', () => {
      flow.processUserInput('module general');
      flow.processUserInput('target example.com');
      flow.resetCompleteWorkflow();
      
      expect(flow.getCurrentWorkflowStage()).toBe('module');
      const state = flow.getState();
      expect(state.module).toBeNull();
      expect(state.target).toBeNull();
    });
    
    it('should reset to target stage keeping module', () => {
      flow.processUserInput('module general');
      flow.processUserInput('target example.com');
      flow.resetToTargetConfiguration();
      
      expect(flow.getCurrentWorkflowStage()).toBe('target');
      const state = flow.getState();
      expect(state.module).toBe('general');
      expect(state.target).toBeNull();
    });
  });
  
  describe('Help Text', () => {
    it('should provide context-aware help', () => {
      const moduleHelp = flow.getHelp();
      expect(moduleHelp).toContain('Load a module');
      
      flow.processUserInput('module general');
      const targetHelp = flow.getHelp();
      expect(targetHelp).toContain('set target');
      
      flow.processUserInput('target example.com');
      const objectiveHelp = flow.getHelp();
      expect(objectiveHelp).toContain('objective');
    });
  });
  
  describe('Prompt Generation', () => {
    it('should generate appropriate prompts', () => {
      expect(flow.getCurrentPrompt()).toBe('[no module] > ');
      
      flow.processUserInput('module network');
      expect(flow.getCurrentPrompt()).toBe('[network] > ');
      
      flow.processUserInput('target 192.168.1.1');
      expect(flow.getCurrentPrompt()).toBe('[network → 192.168.1.1] > ');
    });
  });
});