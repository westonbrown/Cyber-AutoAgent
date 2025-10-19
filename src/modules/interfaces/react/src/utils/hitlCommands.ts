/**
 * HITL Command Utilities
 *
 * Helper functions for sending Human-in-the-Loop feedback commands
 * to the Python backend via stdin using the __HITL_COMMAND__ protocol.
 */

import { ExecutionService } from '../services/ExecutionService.js';

// Global reference to execution service for HITL commands
let _executionService: ExecutionService | null = null;

/**
 * Set the execution service reference for HITL commands
 */
export const setExecutionServiceForHITL = (service: ExecutionService | null): void => {
  _executionService = service;
};

/**
 * Send a HITL command to the Python process via stdin
 *
 * Commands are wrapped in __HITL_COMMAND__<json>__HITL_COMMAND_END__
 * format for the Python FeedbackInputHandler to parse.
 */
const sendHITLCommand = async (command: Record<string, any>): Promise<void> => {
  try {
    const commandJson = JSON.stringify(command);
    const formattedCommand = `__HITL_COMMAND__${commandJson}__HITL_COMMAND_END__`;

    // Send via execution service to Python process stdin
    if (_executionService && 'sendUserInput' in _executionService) {
      await (_executionService as any).sendUserInput(formattedCommand);
    } else {
      console.error('[HITL] No execution service available to send command');
    }
  } catch (error) {
    console.error('Failed to send HITL command:', error);
  }
};

/**
 * Submit user feedback for a paused tool execution
 */
export const submitFeedback = (
  feedbackType: 'correction' | 'suggestion' | 'approval' | 'rejection',
  content: string,
  toolId: string
): void => {
  sendHITLCommand({
    type: 'submit_feedback',
    feedback_type: feedbackType,
    content,
    tool_id: toolId,
  });
};

/**
 * Confirm or reject the agent's interpretation of feedback
 */
export const confirmInterpretation = (
  approved: boolean,
  toolId: string
): void => {
  sendHITLCommand({
    type: 'confirm_interpretation',
    approved,
    tool_id: toolId,
  });
};

/**
 * Request manual intervention (pause agent for human review)
 */
export const requestManualIntervention = (): void => {
  sendHITLCommand({
    type: 'request_manual_intervention',
  });
};
