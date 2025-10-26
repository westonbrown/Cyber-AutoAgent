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
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [HITL-UI] Preparing to send command:`, JSON.stringify(command, null, 2));

  try {
    const commandJson = JSON.stringify(command);
    const formattedCommand = `__HITL_COMMAND__${commandJson}__HITL_COMMAND_END__`;

    console.log(`[${timestamp}] [HITL-UI] Formatted command length: ${formattedCommand.length} chars`);
    console.log(`[${timestamp}] [HITL-UI] Formatted command:`, formattedCommand);

    // Send via execution service to Python process stdin
    if (_executionService && 'sendUserInput' in _executionService) {
      console.log(`[${timestamp}] [HITL-UI] Execution service available, calling sendUserInput`);
      await (_executionService as any).sendUserInput(formattedCommand);
      console.log(`[${timestamp}] [HITL-UI] sendUserInput completed successfully`);
    } else {
      console.error(`[${timestamp}] [HITL-UI] ERROR: No execution service available to send command`);
      console.error(`[${timestamp}] [HITL-UI] _executionService:`, _executionService);
    }
  } catch (error) {
    console.error(`[${timestamp}] [HITL-UI] ERROR: Failed to send HITL command:`, error);
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
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [HITL-UI] submitFeedback() called:`, {
    feedbackType,
    contentLength: content.length,
    toolId,
    contentPreview: content.substring(0, 100)
  });

  sendHITLCommand({
    type: 'submit_feedback',
    feedback_type: feedbackType,
    content,
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
