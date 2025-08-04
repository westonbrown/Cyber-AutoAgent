/**
 * AssessmentFlow Service - Professional Security Assessment State Machine
 * 
 * Manages the structured workflow for cybersecurity assessments with a guided
 * three-step process: Module Selection → Target Definition → Objective Setting.
 * Provides comprehensive validation, user guidance, and state management for
 * consistent assessment configuration across all security modules.
 * 
 * Assessment Workflow:
 * 1. Module Selection: Choose security domain (general)
 * 2. Target Definition: Specify assessment target (IP, domain, URL, etc.)
 * 3. Ready State: Assessment parameters validated and ready for execution
 * 
 * Key Features:
 * - Comprehensive input validation and sanitization
 * - Context-aware help system and user guidance
 * - Flexible objective setting with intelligent defaults
 * - State persistence and rollback capabilities
 * - Professional error handling with clear user feedback
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.1.3
 * @since 2025-01-01
 */

import { AssessmentState, AssessmentParams } from '../types/Assessment.js';

/**
 * Flow Operation Result Interface
 * 
 * Standardized response format for all assessment flow operations
 * providing consistent feedback, error handling, and user guidance.
 */
export interface FlowResult {
  /** Operation success status */
  success: boolean;
  /** User-friendly status or confirmation message */
  message: string;
  /** Next step guidance for user (optional) */
  nextPrompt?: string;
  /** Detailed error information for debugging (optional) */
  error?: string;
}

/**
 * AssessmentFlow - Professional Security Assessment State Machine
 * 
 * Orchestrates the complete assessment configuration workflow with robust
 * state management, validation, and user guidance. Ensures consistent
 * security assessment setup across all supported security domains.
 */
export class AssessmentFlow {
  /** Current assessment configuration state */
  private assessmentState: AssessmentState = {
    stage: 'target', // Start at target since we default to 'general' module
    module: 'general', // Default to general module
    target: null,
    objective: null // Auto-generated based on module
  };

  /** Available security assessment modules with comprehensive coverage */
  private readonly supportedSecurityModules = [
    'general',          // General-purpose security assessment
  ];

  /**
   * Initialize AssessmentFlow with default module selection state
   * Ready to guide user through complete assessment setup workflow
   */
  constructor() {
    // Initialize with 'general' module by default, starting at target stage
    // Users can change module with /module command if needed
  }

  /**
   * Get Current Assessment State
   * 
   * Returns a deep copy of the current assessment configuration state
   * to prevent external mutations and ensure state consistency.
   * 
   * @returns {AssessmentState} Complete current state with all parameters
   */
  getState(): AssessmentState {
    return { ...this.assessmentState };
  }

  /**
   * Get Current Workflow Stage
   * 
   * Returns the current stage in the assessment configuration workflow
   * for UI state management and user guidance.
   * 
   * @returns {AssessmentState['stage']} Current workflow stage
   */
  getCurrentWorkflowStage(): AssessmentState['stage'] {
    return this.assessmentState.stage;
  }

  /**
   * Get Validated Assessment Parameters
   * 
   * Returns complete assessment parameters only when the workflow is
   * in the 'ready' state with all required fields validated.
   * 
   * @returns {AssessmentParams | null} Validated parameters or null if not ready
   */
  getValidatedAssessmentParameters(): AssessmentParams | null {
    if (this.assessmentState.stage !== 'ready') {
      return null;
    }
    
    return {
      module: this.assessmentState.module!,
      target: this.assessmentState.target!,
      objective: this.assessmentState.objective || undefined
    };
  }

  /**
   * Check Assessment Readiness Status
   * 
   * Validates whether the assessment workflow is complete and all
   * required parameters have been configured for execution.
   * 
   * @returns {boolean} True if ready to execute assessment
   */
  isReadyForAssessmentExecution(): boolean {
    return this.assessmentState.stage === 'ready';
  }

  /**
   * Reset Complete Assessment Workflow
   * 
   * Resets the entire assessment flow to initial state, clearing
   * all configured parameters and returning to module selection.
   * Useful for starting a completely new assessment configuration.
   */
  resetCompleteWorkflow(): void {
    this.assessmentState = {
      stage: 'target', // Start at target since we default to 'general' module
      module: 'general', // Default to general module
      target: null,
      objective: null
    };
  }

  /**
   * Reset to Target Configuration Stage
   * 
   * Maintains the selected security module but resets target and
   * objective configuration. Useful for changing targets within
   * the same security domain without reselecting the module.
   */
  resetToTargetConfiguration(): void {
    this.assessmentState.stage = 'target';
    this.assessmentState.target = null;
    this.assessmentState.objective = null;
  }

  /**
   * Process User Input Based on Current Workflow Stage
   * 
   * Routes user input to the appropriate handler based on the current
   * assessment workflow stage. Provides intelligent validation and
   * guidance for each stage of the configuration process.
   * 
   * @param {string} userInput - Raw user input to process
   * @returns {FlowResult} Processing result with feedback and next steps
   */
  processUserInput(userInput: string): FlowResult {
    const sanitizedInput = userInput.trim();
    
    // Handle reset command regardless of current stage
    if (sanitizedInput === 'reset') {
      this.resetCompleteWorkflow();
      return {
        success: true,
        message: 'Assessment workflow reset. Please specify a target.',
        nextPrompt: 'Enter target to assess (e.g., https://example.com)'
      };
    }
    
    switch (this.assessmentState.stage) {
      case 'module':
        return this.processModuleSelectionInput(sanitizedInput);
      
      case 'target':
        return this.processTargetDefinitionInput(sanitizedInput);
      
      case 'objective':
        return this.processObjectiveSettingInput(sanitizedInput);
      
      case 'ready':
        return {
          success: false,
          message: 'Assessment configuration complete. Press Enter to start or type "reset" to reconfigure.',
          nextPrompt: 'Ready to execute security assessment'
        };
      
      default:
        return {
          success: false,
          message: 'Invalid workflow state detected',
          error: 'Assessment flow is in an invalid state - please reset and try again'
        };
    }
  }

  /**
   * Process Security Module Selection Input
   * 
   * Validates and processes user input for security module selection.
   * Ensures the selected module is available and advances workflow to
   * target definition stage upon successful validation.
   */
  private processModuleSelectionInput(userInput: string): FlowResult {
    // Validate command format
    if (!userInput.startsWith('module ')) {
      return {
        success: false,
        message: 'Please specify a security module to load',
        error: 'Usage: module <security_domain>',
        nextPrompt: 'Available modules: ' + this.supportedSecurityModules.join(', ')
      };
    }

    const requestedModuleName = userInput.replace('module ', '').trim();
    
    // Validate module availability
    if (!this.supportedSecurityModules.includes(requestedModuleName)) {
      return {
        success: false,
        message: `Security module '${requestedModuleName}' is not available`,
        error: 'Available modules: ' + this.supportedSecurityModules.join(', '),
        nextPrompt: 'Please select a valid security module'
      };
    }

    // Update state and advance workflow
    this.assessmentState.module = requestedModuleName;
    this.assessmentState.stage = 'target';
    
    return {
      success: true,
      message: `Security module '${requestedModuleName}' loaded successfully`,
      nextPrompt: 'Now define your assessment target (IP, domain, URL, etc.):'
    };
  }

  /**
   * Process Assessment Target Definition Input
   * 
   * Validates and processes user input for assessment target definition.
   * Accepts flexible target formats including IPs, domains, URLs, and
   * file paths while ensuring basic input validation.
   */
  private processTargetDefinitionInput(userInput: string): FlowResult {
    // Validate command format
    if (!userInput.startsWith('target ')) {
      return {
        success: false,
        message: 'Please define your assessment target',
        error: 'Usage: target <target_specification>',
        nextPrompt: 'Examples: target example.com, target 192.168.1.1, target https://api.example.com'
      };
    }

    const targetSpecification = userInput.replace('target ', '').trim();
    
    // Validate target is not empty
    if (!targetSpecification) {
      return {
        success: false,
        message: 'Assessment target cannot be empty',
        error: 'Please provide a valid target specification',
        nextPrompt: 'Examples: domain, IP address, URL, or file path'
      };
    }

    // Update state and advance workflow to objective
    this.assessmentState.target = targetSpecification;
    this.assessmentState.stage = 'objective';
    
    return {
      success: true,
      message: `Assessment target defined: ${targetSpecification}`,
      nextPrompt: 'Optional: Enter specific objective or press Enter for default:'
    };
  }

  /**
   * Process Assessment Objective Setting Input
   * 
   * Handles custom objective definition or defaults to module-specific
   * objectives. Completes the assessment configuration workflow and
   * transitions to ready state for execution.
   */
  private processObjectiveSettingInput(userInput: string): FlowResult {
    // Empty input indicates use of module default objective
    if (!userInput) {
      this.assessmentState.objective = this.generateDefaultObjective(this.assessmentState.module!);
      this.assessmentState.stage = 'ready';
      return {
        success: true,
        message: `Using default ${this.assessmentState.module} assessment objective`,
        nextPrompt: 'Assessment configuration complete - Press Enter to execute'
      };
    }

    // Check if user typed 'execute' - treat as empty objective
    if (userInput.toLowerCase() === 'execute') {
      this.assessmentState.objective = this.generateDefaultObjective(this.assessmentState.module!);
      this.assessmentState.stage = 'ready';
      
      return {
        success: true,
        message: 'Using default objective',
        nextPrompt: 'Assessment configuration complete - Press Enter to execute'
      };
    }
    
    // Set custom assessment objective
    this.assessmentState.objective = userInput;
    this.assessmentState.stage = 'ready';
    
    return {
      success: true,
      message: `Custom objective configured: ${userInput}`,
      nextPrompt: 'Assessment configuration complete - Press Enter to execute'
    };
  }

  /**
   * Generate default objective based on module
   */
  private generateDefaultObjective(module: string): string {
    const objectives: Record<string, string> = {
      general: 'general security assessment and reconnaissance'
    };
    
    return objectives[module] || 'general security assessment';
  }


  /**
   * Get prompt for current stage
   */
  getCurrentPrompt(): string {
    switch (this.assessmentState.stage) {
      case 'module':
        return '[no module] > ';
      case 'target':
        return `[${this.assessmentState.module}] > `;
      case 'objective':
      case 'ready':
        return `[${this.assessmentState.module} → ${this.assessmentState.target}] > `;
      default:
        return '> ';
    }
  }

  /**
   * Get help text for current stage
   */
  getHelp(): string {
    switch (this.assessmentState.stage) {
      case 'module':
        return `Load a module to begin:\n` +
               this.supportedSecurityModules.map(m => `  module ${m}`).join('\n');
      
      case 'target':
        return `Module loaded. Now set target:\n` +
               `  target example.com\n` +
               `  target 192.168.1.1\n` +
               `  target https://api.example.com`;
      
      case 'objective':
        return `Target set. Enter objective or press Enter for default:\n` +
               `Examples:\n` +
               `  - sql injection testing\n` +
               `  - authentication bypass\n` +
               `  - port scanning`;
      
      case 'ready':
        return `Ready to assess. Press Enter to start or:\n` +
               `  reset     - Start over\n` +
               `  target    - Change target\n` +
               `  help      - Show this help`;
      
      default:
        return 'Type "help" for assistance';
    }
  }
}