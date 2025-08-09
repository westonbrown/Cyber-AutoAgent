/**
 * useCommandHandler Hook
 * 
 * Extracts command handling logic from App.tsx for better separation of concerns.
 * Handles slash commands, natural language processing, and user input routing.
 */

import { useCallback } from 'react';
import { InputParser, ParsedCommand } from '../services/InputParser.js';
import { AssessmentFlow } from '../services/AssessmentFlow.js';
import { OperationManager } from '../services/OperationManager.js';
import { ApplicationState } from './useApplicationState.js';

interface UseCommandHandlerProps {
  commandParser: InputParser;
  assessmentFlowManager: AssessmentFlow;
  operationManager: OperationManager;
  appState: ApplicationState;
  actions: any;
  applicationConfig: any;
  addOperationHistoryEntry: (type: string, content: string, operation?: any) => void;
  openConfig: () => void;
  openMemorySearch: () => void;
  openModuleSelector: (callback: (moduleName: string) => void) => void;
  openSafetyWarning: (context: any) => void;
  openDocumentation: (docIndex?: number) => void;
  handleScreenClear: () => void;
  refreshStatic: () => void;
  modalManager: any;
  setAssessmentFlowState?: (state: any) => void;
}

export function useCommandHandler({
  commandParser,
  assessmentFlowManager,
  operationManager,
  appState,
  actions,
  applicationConfig,
  addOperationHistoryEntry,
  openConfig,
  openMemorySearch,
  openModuleSelector,
  openSafetyWarning,
  openDocumentation,
  handleScreenClear,
  refreshStatic,
  modalManager,
  setAssessmentFlowState
}: UseCommandHandlerProps) {

  const handleUnifiedInput = useCallback(async (userInput: string) => {
    if (!userInput.trim()) return;
    
    // Check if user handoff is active - send input to container
    if (appState.userHandoffActive && appState.executionService) {
      try {
        // ExecutionService doesn't have sendUserInput, but DirectDockerService does
        // We need to check if the service has this method
        const service = appState.executionService as any;
        if (service.sendUserInput) {
          await service.sendUserInput(userInput);
          addOperationHistoryEntry('info', `User response sent: ${userInput}`);
          actions.setUserHandoff(false);
          return;
        } else {
          addOperationHistoryEntry('error', 'Current execution service does not support user input');
          return;
        }
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to send input to agent: ${error}`);
        return;
      }
    }
    
    // Parse the user input to determine command type and parameters
    const parsedInput = commandParser.parse(userInput);
    
    try {
      switch (parsedInput.type) {
        case 'slash':
          const args = parsedInput.args || [];
          await handleSlashCommand(parsedInput.command!, args);
          break;
        case 'natural':
          await handleNaturalLanguageCommand(parsedInput);
          break;
        case 'flow':
          await handleGuidedFlowInput(userInput);
          break;
        default:
          addOperationHistoryEntry('error', 'Unknown command format. Type /help for available commands.');
      }
    } catch (error) {
      // Use addOperationHistoryEntry instead of console.error to keep everything in React Ink
      addOperationHistoryEntry('error', `Input handling error: ${error}`);
      addOperationHistoryEntry('error', `Error processing command: ${error}`);
    }
  }, [commandParser, appState.userHandoffActive, appState.executionService, actions, addOperationHistoryEntry]);

  const handleHealthCheck = useCallback(async () => {
    try {
      // Import HealthMonitor dynamically to avoid circular dependencies
      const { HealthMonitor } = await import('../services/HealthMonitor.js');
      const monitor = HealthMonitor.getInstance();
      
      addOperationHistoryEntry('info', 'Running system health check...');
      
      // Get detailed health status
      const { status, recommendations } = await monitor.getDetailedHealth();
      
      // Format health report
      let healthReport = `\n🔍 SYSTEM HEALTH CHECK\n`;
      healthReport += `═══════════════════════════════════════\n\n`;
      
      // Overall status
      const overallIcon = status.overall === 'healthy' ? '✅' : 
                         status.overall === 'degraded' ? '⚠️' : '❌';
      healthReport += `Overall Status: ${overallIcon} ${status.overall.toUpperCase()}\n`;
      healthReport += `Docker Engine: ${status.dockerRunning ? '✅ Running' : '❌ Stopped'}\n`;
      healthReport += `Last Check: ${status.lastCheck.toLocaleTimeString()}\n\n`;
      
      // Service status
      healthReport += `📊 SERVICE STATUS\n`;
      healthReport += `─────────────────────────────────────\n`;
      
      if (status.services.length === 0) {
        healthReport += `No services detected (Local CLI mode)\n`;
      } else {
        status.services.forEach(service => {
          const statusIcon = service.status === 'running' ? '✅' : 
                           service.status === 'stopped' ? '❌' : '❓';
          const healthIcon = service.health === 'healthy' ? '💚' : 
                           service.health === 'unhealthy' ? '💔' : 
                           service.health === 'starting' ? '🟡' : '';
          
          healthReport += `${statusIcon} ${service.displayName}`;
          if (service.status === 'running' && service.uptime) {
            healthReport += ` (${service.uptime})`;
          }
          if (healthIcon) {
            healthReport += ` ${healthIcon}`;
          }
          if (service.message) {
            healthReport += ` - ${service.message}`;
          }
          healthReport += `\n`;
        });
      }
      
      // Recommendations
      if (recommendations.length > 0) {
        healthReport += `\n💡 RECOMMENDATIONS\n`;
        healthReport += `─────────────────────────────────────\n`;
        recommendations.forEach(rec => {
          healthReport += `• ${rec}\n`;
        });
      }
      
      // Quick stats
      const runningServices = status.services.filter(s => s.status === 'running').length;
      const totalServices = status.services.length;
      if (totalServices > 0) {
        healthReport += `\n📈 SUMMARY: ${runningServices}/${totalServices} services running\n`;
      }
      
      addOperationHistoryEntry('info', healthReport);
      
    } catch (error) {
      addOperationHistoryEntry('error', `Health check failed: ${error}`);
    }
  }, [addOperationHistoryEntry]);

  const handleSlashCommand = useCallback(async (command: string, args: string[]) => {
    // Handle command aliases
    const aliases: Record<string, string> = {
      'c': 'config',
      'h': 'help',
      'm': 'plugins',
      'mod': 'plugins',
      'p': 'plugins',
      'clr': 'clear',
      'cls': 'clear',
      'q': 'exit',
      'quit': 'exit'
    };
    
    const resolvedCommand = aliases[command] || command;
    
    switch (resolvedCommand) {
      case 'config':
        openConfig();
        break;
      case 'memory':
        // Memory functionality requires Python environment with Mem0
        addOperationHistoryEntry('info', 'Memory operations require running in container mode with Mem0 installed');
        break;
      case 'clear':
        handleScreenClear();
        break;
      case 'help':
        // Display comprehensive help message
        const helpMessage = `
▣ Cyber-AutoAgent Command Reference

ASSESSMENT COMMANDS:
  target <url>          - Set assessment target
  execute [objective]   - Start assessment with optional focus
  reset                 - Clear current configuration

SLASH COMMANDS:
  /help                 - Show this help message
  /docs                 - Browse documentation interactively
  /plugins              - Select security assessment module
  /config               - View current configuration
  /health               - Check system and container status
  /setup                - Choose deployment mode

KEYBORD SHORTCUTS:
  Ctrl+C                - Clear input / Pause assessment
  Ctrl+L                - Clear screen

EXAMPLES:
  target https://testphp.vulnweb.com
  execute focus on OWASP Top 10

For detailed instructions, use: /docs`;
        addOperationHistoryEntry('info', helpMessage);
        break;
      case 'health':
        // Perform detailed health check using HealthMonitor service
        await handleHealthCheck();
        break;
      case 'plugins':
        if (args.length > 0) {
          const moduleName = args[0];
          if (commandParser.getAvailableModules().includes(moduleName)) {
            assessmentFlowManager.processUserInput(`module ${moduleName}`);
            addOperationHistoryEntry('info', `Plugin loaded: ${moduleName}`);
          } else {
            addOperationHistoryEntry('error', `Unknown plugin: ${moduleName}. Available plugins: ${commandParser.getAvailableModules().join(', ')}`);
          }
        } else {
          openModuleSelector((moduleName) => {
            assessmentFlowManager.processUserInput(`module ${moduleName}`);
            addOperationHistoryEntry('info', `Plugin loaded: ${moduleName}`);
          });
        }
        break;
      case 'docs':
        // Parse document number if provided
        let docNumber: number | undefined = undefined;
        if (args.length > 0) {
          const parsedNum = parseInt(args[0]);
          if (!isNaN(parsedNum) && parsedNum >= 1 && parsedNum <= 7) {
            docNumber = parsedNum;
          } else {
            addOperationHistoryEntry('error', 'Invalid document number. Please use a number between 1 and 7.');
            return;
          }
        }
        
        // Open documentation viewer modal
        openDocumentation(docNumber);
        addOperationHistoryEntry('info', docNumber ? 
          `Opening documentation (Document ${docNumber})...` : 
          'Opening interactive documentation browser...'
        );
        break;
      case 'setup':
      case 'set':  // Support /set as alias for /setup
        // Don't clear screen - show setup inline with main view
        // This prevents duplicate headers
        actions.setInitializationFlow(true);
        
        process.env.CYBER_SHOW_SETUP = 'true';
        
        addOperationHistoryEntry('info', 'Opening deployment setup wizard...');
        break;
      default:
        addOperationHistoryEntry('error', `Unknown command: /${command}. Type /help for available commands.`);
    }
  }, [
    openConfig, openMemorySearch, openModuleSelector,
    openDocumentation, handleScreenClear, handleHealthCheck, commandParser, assessmentFlowManager, 
    addOperationHistoryEntry, actions, modalManager
  ]);

  const handleNaturalLanguageCommand = useCallback(async (parsed: ParsedCommand) => {
    if (!parsed.target) {
      addOperationHistoryEntry('error', 'Invalid natural language command. Missing target.');
      return;
    }

    // Set the parsed parameters
    if (parsed.module) {
      assessmentFlowManager.processUserInput(`module ${parsed.module}`);
    }
    if (parsed.target) {
      assessmentFlowManager.processUserInput(`target ${parsed.target}`);
    }
    if (parsed.objective) {
      assessmentFlowManager.processUserInput(`objective ${parsed.objective}`);
    }

    // Show safety warning before execution if ready
    if (assessmentFlowManager.isReadyForAssessmentExecution()) {
      const state = assessmentFlowManager.getState();
      openSafetyWarning({
        module: state.module!,
        target: state.target!,
        objective: state.objective || ''
      });
    }
  }, [assessmentFlowManager, addOperationHistoryEntry, openSafetyWarning, setAssessmentFlowState]);

  const handleGuidedFlowInput = useCallback(async (input: string) => {
    // Special handling for 'execute' when already ready (bypass normal flow)
    if ((input.toLowerCase() === 'execute' || input === '') && 
        assessmentFlowManager.isReadyForAssessmentExecution()) {
      const state = assessmentFlowManager.getState();
      openSafetyWarning({
        module: state.module!,
        target: state.target!,
        objective: state.objective || ''
      });
      return;
    }
    
    // For all other cases (including "execute" during objective stage),
    // let the AssessmentFlow handle it normally
    
    const result = assessmentFlowManager.processUserInput(input);
    
    if (result.error) {
      addOperationHistoryEntry('error', result.error);
    } else if (result.success) {
      // Add success message to operation history
      addOperationHistoryEntry('info', result.message);
      
      // If there's a next prompt, show it as well
      if (result.nextPrompt) {
        addOperationHistoryEntry('info', `→ ${result.nextPrompt}`);
      }
      
      // Update the React state to match the AssessmentFlow state
      if (setAssessmentFlowState) {
        const currentState = assessmentFlowManager.getState();
        setAssessmentFlowState({
          step: currentState.stage === 'ready' ? 'ready' : 
                currentState.stage === 'objective' ? 'objective' :
                currentState.stage === 'target' ? 'target' :
                currentState.stage === 'module' ? 'module' : 'idle',
          module: currentState.module,
          target: currentState.target,
          objective: currentState.objective
        });
      }
      
      // Check if the result indicates we should show safety warning immediately
      // (e.g., user typed "execute" or "execute <objective>" during objective step)
      if (result.readyToExecute && assessmentFlowManager.isReadyForAssessmentExecution()) {
        const state = assessmentFlowManager.getState();
        openSafetyWarning({
          module: state.module!,
          target: state.target!,
          objective: state.objective || ''
        });
        return; // Exit early to avoid duplicate safety warning
      }
    }
    
    // Check if ready after processing (e.g., after setting objective with empty input)
    if (assessmentFlowManager.isReadyForAssessmentExecution() && input === '') {
      const state = assessmentFlowManager.getState();
      openSafetyWarning({
        module: state.module!,
        target: state.target!,
        objective: state.objective || ''
      });
    }
  }, [assessmentFlowManager, addOperationHistoryEntry, openSafetyWarning, setAssessmentFlowState]);

  return {
    handleUnifiedInput,
    handleSlashCommand,
    handleNaturalLanguageCommand,
    handleGuidedFlowInput
  };
}