/**
 * Cyber-AutoAgent React Application - Main Entry Point
 * 
 * Professional-grade cybersecurity assessment interface built with React Ink.
 * Provides enterprise-level Docker integration, real-time streaming, and 
 * intuitive command-line experience for security professionals.
 * 
 * Architecture Overview:
 * - Multi-layered state management with React contexts
 * - Direct Docker integration for high-performance assessment execution  
 * - Real-time event streaming with intelligent display grouping
 * - Professional terminal UI with keyboard shortcuts and commands
 * - Comprehensive configuration management with persistent storage
 * 
 * Key Features:
 * - Full-screen streaming with unlimited scrolling
 * - AWS credential management and Docker container execution
 * - Slash command system (/help, /config, /plugins, etc.)
 * - Memory search and operation history tracking
 * - Theme management and professional styling
 * 
 * @author Cyber-AutoAgent Team
 * @version 0.1.3
 * @since 2025-01-01
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Box, Text, useApp, useInput, useStdout, Static, measureElement, DOMElement } from 'ink';
import ansiEscapes from 'ansi-escapes';
import fs from 'fs';

// Modal Management
import { useModalManager, ModalType } from './hooks/useModalManager.js';
import { ModalRegistry } from './components/ModalRegistry.js';

// Core UI Components
import { Header } from './components/Header.js';
import { Footer } from './components/Footer.js';
import { OperationStatusDisplay } from './components/OperationStatusDisplay.js';
import { UnifiedInputPrompt } from './components/UnifiedInputPrompt.js';
import { DirectProfessionalTerminal } from './components/DirectProfessionalTerminal.js';
import { UnconstrainedTerminal } from './components/UnconstrainedTerminal.js';
import { ConfigEditorV2 } from './components/ConfigEditorV2.js';
import { MemorySearch } from './components/MemorySearch.js';
import { InitializationFlow } from './components/InitializationFlow.js';
import { ModuleSelector } from './components/ModuleSelector.js';
import { SafetyWarning } from './components/SafetyWarning.js';

// Type Definitions
import { StreamEvent, EventType, ToolEvent, AgentEvent } from './types/events.js';

// Core Services
import { DirectDockerService } from './services/DirectDockerService.js';
import { AssessmentFlow } from './services/AssessmentFlow.js';
import { OperationManager, Operation } from './services/OperationManager.js';
import { InputParser, ParsedCommand } from './services/InputParser.js';

// Context Providers
import { ConfigProvider, useConfig } from './contexts/ConfigContext.js';
import { ModuleProvider, useModule } from './contexts/ModuleContext.js';

// Custom Hooks
import { useSlashCommands } from './hooks/useSlashCommands.js';
import { useStreamCompression } from './hooks/useStreamCompression.js';

// Theme System
import { themeManager } from './themes/theme-manager.js';

/**
 * Main Application Component Properties
 * 
 * @interface AppProps
 * @property {string} [module] - Pre-selected security module (general)
 * @property {string} [target] - Pre-defined target for assessment (IP, domain, URL)
 * @property {string} [objective] - Pre-set assessment objective description
 */
interface AppProps {
  module?: string;
  target?: string;
  objective?: string;
}

/**
 * Operation History Entry for UI Display
 * 
 * Represents a single entry in the application's operation history log,
 * used for tracking user actions, system events, and assessment progress.
 * 
 * @interface OperationHistoryEntry
 * @property {string} id - Unique identifier for the history entry
 * @property {Date} timestamp - When the entry was created
 * @property {'operation'|'command'|'info'|'error'} type - Category of the entry
 * @property {string} content - Human-readable description of the entry
 * @property {Operation} [operation] - Associated operation object (if applicable)
 */
interface OperationHistoryEntry {
  id: string;
  timestamp: Date;
  type: 'operation' | 'command' | 'info' | 'error';
  content: string;
  operation?: Operation;
}

/**
 * AppContent - Main Application Content Component
 * 
 * The core application logic container that manages all assessment operations,
 * user interactions, Docker services, and UI state. Serves as the central
 * orchestrator for the entire cybersecurity assessment workflow.
 */
const AppContent: React.FC<AppProps> = ({ 
  module: presetSecurityModule, 
  target: presetAssessmentTarget, 
  objective: presetObjectiveDescription 
}) => {
  // Core Ink hooks for application lifecycle
  const { exit: terminateApplication } = useApp();
  const { stdout } = useStdout();
  const { write: writeToStdout } = stdout;
  
  // Configuration and theme management
  const { config: applicationConfig } = useConfig();
  const isApplicationConfigured = applicationConfig.isConfigured;
  const currentTheme = themeManager.getCurrentTheme();
  
  // Core service initialization (singleton pattern)
  const [assessmentFlowManager] = useState(() => new AssessmentFlow());
  const [operationManager] = useState(() => new OperationManager(applicationConfig));
  const [commandParser] = useState(() => new InputParser());
  
  // Docker service and session ID for operation tracking
  const [dockerService] = useState(() => new DirectDockerService());
  const [sessionId] = useState(() => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  
  // Application state management - UI controls and operation tracking
  const [isTerminalVisible, setIsTerminalVisible] = useState(false);
  const [operationHistoryEntries, setOperationHistoryEntries] = useState<OperationHistoryEntry[]>([]);
  const [activeOperation, setActiveOperation] = useState<Operation | null>(null);
  const [userHandoffActive, setUserHandoffActive] = useState(false);
  const [assessmentFlowState, setAssessmentFlowState] = useState({
    step: 'idle' as 'idle' | 'module' | 'target' | 'objective' | 'ready',
    module: undefined as string | undefined,
    target: undefined as string | undefined,
    objective: undefined as string | undefined
  });
  const [operationMetrics, setOperationMetrics] = useState<{
    tokens?: number;
    cost?: number;
    duration: string;
    memoryOps: number;
    evidence: number;
  } | undefined>(undefined);
  
  // Modal Management - Centralized system
  const modalManager = useModalManager();
  const { 
    activeModal, 
    modalContext, 
    staticKey,
    openConfig,
    openMemorySearch,
    openModuleSelector,
    openSafetyWarning,
    closeModal,
    isModalOpen
  } = modalManager;
  
  // Professional Static refresh function (Gemini CLI pattern)
  const refreshStatic = useCallback(() => {
    stdout.write(ansiEscapes.clearTerminal);
    modalManager.refreshStatic();
  }, [stdout, modalManager]);
  
  // Surgical refresh for non-disruptive updates (preserves scroll position)
  const refreshStaticOnly = useCallback(() => {
    modalManager.refreshStatic();
  }, [modalManager]);
  
  // Track if we've done initial refresh to prevent duplicate headers
  const hasInitialRefresh = useRef(false);
  
  // UI state management - remaining display preferences
  const [isFirstRunExperience, setIsFirstRunExperience] = useState(true);
  const [isInitializationFlowActive, setIsInitializationFlowActive] = useState(true); // Start with true, will be updated by effect
  const [hasUserDismissedInit, setHasUserDismissedInit] = useState(false); // Track if user manually dismissed
  const [isDockerServiceAvailable, setIsDockerServiceAvailable] = useState(false);
  const [terminalDisplayHeight, setTerminalDisplayHeight] = useState<number>(process.stdout.rows || 24);
  const [terminalDisplayWidth, setTerminalDisplayWidth] = useState<number>(process.stdout.columns || 80);
  const [sessionErrorCount, setSessionErrorCount] = useState(0);
  
  // Refs for layout
  const footerRef = useRef<DOMElement>(null);
  
  // Hooks
  const { currentModule } = useModule();
  const { executeSlashCommand } = useSlashCommands();
  const { filterOutput, getCompressionStatus } = useStreamCompression();

  const handleScreenClear = useCallback(() => {
    // Clear all dynamic application state for fresh start
    setOperationHistoryEntries([]);
    setSessionErrorCount(0);
    setIsTerminalVisible(false);
    setActiveOperation(null);
    
    // Professional screen clearing (Gemini CLI pattern)
    refreshStatic();
  }, [refreshStatic]);

  // Initialize and check Docker availability
  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Check if Docker is available
        const isDockerAvailable = await DirectDockerService.checkDocker();
        setIsDockerServiceAvailable(isDockerAvailable);
        
        if (!isDockerAvailable) {
          addOperationHistoryEntry('error', 'Docker is not available. Please ensure Docker Desktop is running.');
        } else {
          // Ensure Docker resources exist
          try {
            await DirectDockerService.ensureDockerResources();
          } catch (error) {
            addOperationHistoryEntry('error', `Docker setup required: ${error}`);
          }
        }
        
        // Don't show welcome message here - wait for config to load
        
        // Initialize with CLI args if provided
        if (presetSecurityModule && presetAssessmentTarget) {
          await handleCommandLineInitialization(presetSecurityModule, presetAssessmentTarget, presetObjectiveDescription);
        }
      } catch (error) {
        console.error('Initialization error:', error);
        addOperationHistoryEntry('error', `Initialization error: ${error}`);
      }
    };
    
    initializeApp();
  }, []);

  // Show welcome message after config loads
  useEffect(() => {
    if (isFirstRunExperience && applicationConfig !== undefined) {
      // Small delay to ensure config is fully loaded
      const timer = setTimeout(() => {
        if (!applicationConfig.isConfigured) {
          addOperationHistoryEntry('info', 'First-time setup detected. Use /config to configure your AI provider.');
        } else {
          addOperationHistoryEntry('info', 'Configuration complete! Type /help for commands or try: scan example.com');
        }
        setIsFirstRunExperience(false);
      }, 100);
      
      return () => clearTimeout(timer);
    }
  }, [applicationConfig, isFirstRunExperience]);

  // Update terminal dimensions based on stdout changes with debouncing
  // Professional resize handling with Static refresh (Gemini CLI pattern)
  const [staticNeedsRefresh, setStaticNeedsRefresh] = useState(false);
  const isInitialMount = useRef(true);
  
  useEffect(() => {
    let resizeTimeout: NodeJS.Timeout;
    
    const updateTerminalDimensions = () => {
      // Clear any pending resize timeout
      clearTimeout(resizeTimeout);
      
      // Debounce resize events to prevent excessive re-renders
      resizeTimeout = setTimeout(() => {
        const newWidth = process.stdout.columns || 80;
        const newHeight = process.stdout.rows || 24;
        
        // Only trigger refresh for significant size changes (more than 5 chars/lines)
        const widthDiff = Math.abs(newWidth - terminalDisplayWidth);
        const heightDiff = Math.abs(newHeight - terminalDisplayHeight);
        
        if (widthDiff > 5 || heightDiff > 2) {
          setTerminalDisplayHeight(newHeight);
          setTerminalDisplayWidth(newWidth);
          setStaticNeedsRefresh(true);
        } else if (newWidth !== terminalDisplayWidth || newHeight !== terminalDisplayHeight) {
          // Minor changes - just update dimensions without triggering refresh
          setTerminalDisplayHeight(newHeight);
          setTerminalDisplayWidth(newWidth);
        }
      }, 300); // 300ms debounce like Gemini CLI
    };
    
    // Listen for terminal resize events
    process.stdout.on('resize', updateTerminalDimensions);
    updateTerminalDimensions();
    
    return () => {
      clearTimeout(resizeTimeout);
      process.stdout.off('resize', updateTerminalDimensions);
    };
  }, [terminalDisplayWidth, terminalDisplayHeight]);
  
  // Debounced static refresh on resize (Fixed to not clear terminal unnecessarily)
  useEffect(() => {
    // Skip refreshing Static during first mount
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    // For resize events, only update Static key without clearing terminal
    const handler = setTimeout(() => {
      if (staticNeedsRefresh) {
        setStaticNeedsRefresh(false);
        // Only refresh Static key, don't clear terminal for resize events
        refreshStaticOnly();
      }
    }, 300);
    return () => clearTimeout(handler);
  }, [staticNeedsRefresh, refreshStaticOnly]);

  // Sync initialization flow state with configuration
  useEffect(() => {
    // Only update if user hasn't manually dismissed the init flow
    if (!hasUserDismissedInit) {
      // Check for actual configuration completeness, not just the flag
      const isActuallyConfigured = applicationConfig.isConfigured && 
        applicationConfig.modelProvider && 
        applicationConfig.modelId &&
        (
          // Check for provider-specific credentials
          (applicationConfig.modelProvider === 'bedrock' && 
            (applicationConfig.awsBearerToken || applicationConfig.awsAccessKeyId)) ||
          (applicationConfig.modelProvider === 'ollama') ||
          (applicationConfig.modelProvider === 'litellm')
        );
      
      // Update initialization flow state based on actual configuration
      setIsInitializationFlowActive(!isActuallyConfigured);
    }
  }, [applicationConfig, hasUserDismissedInit]);

  // Synchronize flow state with AssessmentFlow service
  useEffect(() => {
    const currentAssessmentState = assessmentFlowManager.getState();
    setAssessmentFlowState({
      step: currentAssessmentState.module ? (currentAssessmentState.target ? (currentAssessmentState.objective !== undefined ? 'ready' : 'objective') : 'target') : 'module',
      module: currentAssessmentState.module,
      target: currentAssessmentState.target, 
      objective: currentAssessmentState.objective
    });
  }, [assessmentFlowManager]);

  // Handle global keyboard shortcuts for professional terminal interaction
  const isTerminalInteractive = process.stdin.isTTY;
  
  useInput((input, key) => {
    if (!isTerminalInteractive) return; // Skip keyboard handling in non-TTY environments
    
    if (key.ctrl && input === 'c') {
      if (activeOperation?.status === 'running') {
        handleAssessmentPause();
      } else {
        terminateApplication();
      }
    }
    
    if (key.ctrl && input === 'l') {
      handleScreenClear();
    }
    
    if (key.ctrl && input === 'r') {
      // Toggle stream compression (handled by useStreamCompression hook)
      return;
    }
    
    if (key.ctrl && input === 'i') {
      // Toggle input visibility during streaming for emergency commands
      if (isTerminalVisible) {
        // Force show input even during streaming for emergency commands
        setIsTerminalVisible(false);
        setTimeout(() => setIsTerminalVisible(true), 100);
      }
      return;
    }
    
    if (key.escape) {
      if (activeModal !== ModalType.NONE) {
        closeModal();
      } else if (isTerminalVisible && activeOperation?.status === 'running') {
        // Immediately cancel current operation and kill container
        handleAssessmentCancel();
      } else {
        // Exit application when not in modal or running operation
        terminateApplication();
      }
    }
  }, { isActive: isTerminalInteractive });

  // Core event handler - processes all streaming events from Docker containers
  const handleStreamingEvent = useCallback((event: StreamEvent) => {
    // Track and log error events for debugging and user feedback
    if (event.type === EventType.TOOL_ERROR || event.type === EventType.SYSTEM_ERROR) {
      setSessionErrorCount(prev => prev + 1);
      addOperationHistoryEntry('error', `Error: ${(event as any).message || (event as any).error || 'Unknown error'}`);
    }
    
    // Handle user handoff events
    if (event.type === 'user_handoff') {
      setUserHandoffActive(true);
      // The event will be displayed in the terminal, just enable input
    }
    
    // Update operation progress based on tool and agent events
    if (activeOperation) {
      if (event.type === 'tool_start') {
        const toolEvent = event as any;
        operationManager.updateProgress(
          activeOperation.id, 
          activeOperation.currentStep + 1, 
          activeOperation.totalSteps, 
          `Running ${toolEvent.tool}`
        );
      } else if (event.type === 'agent_complete') {
        operationManager.completeOperation(activeOperation.id, true);
        setActiveOperation(null);
        addOperationHistoryEntry('info', `Operation ${activeOperation.id} completed successfully`);
      }
    }
  }, [activeOperation, operationManager]);

  const addOperationHistoryEntry = useCallback((type: OperationHistoryEntry['type'], content: string, operation?: Operation) => {
    const historyEntry: OperationHistoryEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`,
      timestamp: new Date(),
      type,
      content,
      operation
    };
    setOperationHistoryEntries(prev => [...prev, historyEntry]);
    
    if (type === 'error') {
      setSessionErrorCount(prev => prev + 1);
    }
  }, []);


  const handleAssessmentPause = useCallback(() => {
    if (activeOperation) {
      const pauseSuccess = operationManager.pauseOperation(activeOperation.id);
      if (pauseSuccess) {
        setActiveOperation(prev => prev ? { ...prev, status: 'paused' } : null);
        addOperationHistoryEntry('info', 'Operation paused. Type "resume" to continue.');
      }
    }
  }, [activeOperation, operationManager, handleStreamingEvent]);

  const handleAssessmentCancel = useCallback(async () => {
    if (activeOperation && dockerService) {
      try {
        // Use cancel() method which immediately stops container and aborts job
        await dockerService.cancel();
        operationManager.completeOperation(activeOperation.id, false);
        setActiveOperation(null);
        setIsTerminalVisible(false);
        
        // Single clean termination message
        addOperationHistoryEntry('info', '✓ Container terminated and cleanup completed');
      } catch (error) {
        addOperationHistoryEntry('error', `✗ Failed to terminate security assessment: ${error}`);
        addOperationHistoryEntry('error', '⚠ Manual intervention may be required - check Docker containers with: docker ps');
      }
    }
  }, [activeOperation, dockerService, operationManager]);

  const handleCommandLineInitialization = useCallback(async (module: string, target: string, objective?: string) => {
    try {
      // Use natural language parsing for CLI arguments
      const scanCommand = `scan ${target}${objective ? ` ${objective}` : ''}`;
      const parsedCommand = commandParser.parse(scanCommand);
      
      if (parsedCommand.type === 'natural' && parsedCommand.module && parsedCommand.target) {
        await handleNaturalLanguageCommand(parsedCommand);
      } else {
        // Fallback to guided assessment flow
        await handleGuidedFlowInput(`module ${module}`);
        await handleGuidedFlowInput(`target ${target}`);
        if (objective) {
          await handleGuidedFlowInput(objective);
        }
        await handleGuidedFlowInput('execute');
      }
    } catch (error) {
      console.error('CLI initialization error:', error);
      addOperationHistoryEntry('error', `Failed to initialize with CLI args: ${error}`);
    }
  }, [commandParser]);

  // Main unified input handler for all user commands and interactions
  const handleUnifiedInput = useCallback(async (userInput: string) => {
    if (!userInput.trim()) return;
    
    // Check if user handoff is active - send input to container
    if (userHandoffActive) {
      try {
        await dockerService.sendUserInput(userInput);
        addOperationHistoryEntry('info', `User response sent: ${userInput}`);
        setUserHandoffActive(false); // Reset handoff state
        return;
      } catch (error) {
        addOperationHistoryEntry('error', `Failed to send input to agent: ${error}`);
        return;
      }
    }
    
    // Don't add user input to history - it's not displayed anymore
    
    // Parse the user input to determine command type and parameters
    const parsedInput = commandParser.parse(userInput);
    
    try {
      switch (parsedInput.type) {
        case 'natural':
          await handleNaturalLanguageCommand(parsedInput);
          break;
        case 'flow':
          await handleGuidedFlowInput(userInput);
          break;
        case 'slash':
          await handleSlashCommand(parsedInput.command || '', parsedInput.args || []);
          break;
        default:
          // Remove the user input from error message since it's already shown
          addOperationHistoryEntry('error', `Unknown command. Type /help for available commands.`);
      }
    } catch (error) {
      console.error('Input handling error:', error);
      addOperationHistoryEntry('error', `Error processing command: ${error}`);
    }
  }, [commandParser, userHandoffActive, dockerService]);

  // Handle natural language commands
  const handleNaturalLanguageCommand = useCallback(async (parsed: ParsedCommand) => {
    if (!parsed.target) {
      addOperationHistoryEntry('error', 'Invalid natural language command. Missing target.');
      return;
    }

    // Use current module from context instead of detecting
    if (!currentModule) {
      addOperationHistoryEntry('error', 'No module selected. Use /module to select a security module first.');
      return;
    }

    // Show safety warning before execution
    openSafetyWarning({
      module: currentModule,
      target: parsed.target,
      objective: parsed.objective || ''
    });
  }, [currentModule]);

  // Handle guided flow input
  const handleGuidedFlowInput = useCallback(async (input: string) => {
    const result = assessmentFlowManager.processUserInput(input);
    
    if (result.message) {
      addOperationHistoryEntry(result.success ? 'info' : 'error', result.message);
    }
    
    if (result.error) {
      addOperationHistoryEntry('error', result.error);
    }
    
    // Update flow state
    const state = assessmentFlowManager.getState();
    setAssessmentFlowState({
      step: state.module ? (state.target ? (state.objective !== undefined ? 'ready' : 'objective') : 'target') : 'module',
      module: state.module,
      target: state.target,
      objective: state.objective
    });
    
    // Auto-execute if ready and user typed 'execute' or empty string
    if (assessmentFlowManager.isReadyForAssessmentExecution() && (input === 'execute' || input === '')) {
      // Show safety warning before execution
      openSafetyWarning({
        module: state.module!,
        target: state.target!,
        objective: state.objective || ''
      });
    }
  }, [assessmentFlowManager, operationManager, applicationConfig]);

  // Handle slash commands
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
        if (args.length > 0) {
          // Search memory with query
          addOperationHistoryEntry('command', `Memory search: ${args.join(' ')}`);
          // Memory search is implemented - open the modal
        } else {
          openMemorySearch();
        }
        break;
      case 'clear':
        handleScreenClear();
        break;
      case 'help':
        showHelpMessage();
        break;
      case 'health':
        // Execute the health command through useSlashCommands
        await executeSlashCommand('/health');
        break;
      case 'model':
        if (args.length > 0) {
          await handleModelSwitch(args[0]);
        } else {
          showAvailableModels();
        }
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
          // Show interactive plugin selector
          openModuleSelector((moduleName) => {
            assessmentFlowManager.processUserInput(`module ${moduleName}`);
            addOperationHistoryEntry('info', `Plugin loaded: ${moduleName}`);
          });
        }
        break;
      case 'pause':
        handleAssessmentPause();
        break;
      case 'resume':
        handleOperationResume();
        break;
      case 'reset':
        assessmentFlowManager.resetCompleteWorkflow();
        setAssessmentFlowState({
          step: 'target',
          module: 'general', 
          target: undefined,
          objective: undefined
        });
        addOperationHistoryEntry('info', 'Assessment workflow reset. Please specify a target.');
        break;
      case 'exit':
        terminateApplication();
        break;
      default:
        await executeSlashCommand(`/${command} ${args.join(' ')}`);
    }
  }, [executeSlashCommand, terminateApplication, assessmentFlowManager]);

  // Helper functions
  const startAssessment = useCallback(async (operation: Operation) => {
    // Optional debug logging (disable for production)
    // const debugLog = `[${new Date().toISOString()}] START_ASSESSMENT: Operation=${JSON.stringify(operation)} Config=${JSON.stringify({provider: config.modelProvider, model: config.modelId, region: config.awsRegion, hasBearer: !!config.awsBearerToken, hasKeys: !!(config.awsAccessKeyId && config.awsSecretAccessKey)})}\n`;
    // fs.appendFileSync('/tmp/cyber-app-debug.log', debugLog);
    
    // Reset error count at start of new operation
    setSessionErrorCount(0);
    
    if (!assessmentFlowManager.isReadyForAssessmentExecution() && !operation) {
      addOperationHistoryEntry('error', 'Assessment not ready. Complete module→target→objective flow first.');
      return;
    }

    const params = assessmentFlowManager.getValidatedAssessmentParameters();
    if (!params && !operation) {
      addOperationHistoryEntry('error', 'Cannot start assessment - missing parameters.');
      return;
    }

    try {
      // Prepare assessment parameters
      const assessmentParams = params || {
        module: operation.module,
        target: operation.target,
        objective: operation.objective
      };

      // Show immediate professional startup feedback
      addOperationHistoryEntry('info', `▶ Starting ${assessmentParams.module} security assessment`);
      addOperationHistoryEntry('info', `◆ Target: ${assessmentParams.target}`);
      if (assessmentParams.objective) {
        addOperationHistoryEntry('info', `◆ Objective: ${assessmentParams.objective}`);
      }
      addOperationHistoryEntry('info', `◆ Model: ${applicationConfig.modelId || 'claude-3-5-sonnet-20241022-v2:0'}`);
      addOperationHistoryEntry('info', '■ Launching secure Docker assessment environment...');
      
      // Show terminal when assessment starts
      setIsTerminalVisible(true);
      
      // Skip refresh during startup - header is already visible
      // Only refresh if we're transitioning from another view
      if (hasInitialRefresh.current) {
        refreshStatic();
      }
      
      // Use Docker service to start agent
      const service = dockerService;
      
      // Listen for events
      service.on('event', (event: StreamEvent) => {
        // Handle different event types
        if (event.type === EventType.TOOL_ERROR) {
          addOperationHistoryEntry('error', `Tool error: ${(event as ToolEvent).error || 'Unknown error'}`);
        } else if (event.type === EventType.AGENT_COMPLETE) {
          addOperationHistoryEntry('info', `Assessment completed: ${(event as AgentEvent).message || 'Complete'}`);
        }
        // Other events are handled by StreamDisplay component
      });
      
      service.on('started', () => {
        addOperationHistoryEntry('info', `✓ Security assessment environment initialized successfully`);
        addOperationHistoryEntry('info', `▶ Beginning comprehensive security evaluation of ${assessmentParams.target}`);
      });
      
      service.on('complete', () => {
        if (operation) {
          operationManager.completeOperation(operation.id, true);
          addOperationHistoryEntry('info', `✓ Security assessment completed successfully (Operation ${operation.id})`);
          addOperationHistoryEntry('info', '◆ Assessment results ready for review - Check terminal output above');
        }
        setActiveOperation(null);
        setIsTerminalVisible(false); // Hide terminal and show input when complete
        assessmentFlowManager.resetCompleteWorkflow();
        // Keep metrics visible after operation completes
      });
      
      service.on('stopped', () => {
        if (operation) {
          operationManager.completeOperation(operation.id, false);
          // Don't add redundant message here - handleAssessmentCancel already handles user feedback
        }
        setActiveOperation(null);
        setIsTerminalVisible(false); // Hide terminal and show input when stopped
        assessmentFlowManager.resetCompleteWorkflow();
        // Keep metrics visible after operation is stopped
      });
      
      await service.executeAssessment(assessmentParams, applicationConfig);
      
    } catch (error: any) {
      addOperationHistoryEntry('error', `Assessment failed: ${error.message}`);
      if (operation) {
        operationManager.completeOperation(operation.id, false);
      }
      setActiveOperation(null);
      setIsTerminalVisible(false); // Hide terminal and show input on error
    }
  }, [assessmentFlowManager, applicationConfig, operationManager, sessionId, dockerService]);

  const handleOperationResume = useCallback(() => {
    if (activeOperation?.status === 'paused') {
      const success = operationManager.resumeOperation(activeOperation.id);
      if (success) {
        setActiveOperation(prev => prev ? { ...prev, status: 'running' } : null);
        addOperationHistoryEntry('info', 'Operation resumed.');
      }
    }
  }, [activeOperation, operationManager, handleStreamingEvent]);

  const handleModelSwitch = useCallback(async (modelId: string) => {
    const availableModels = operationManager.getAvailableModels();
    const model = availableModels.find(m => m.id === modelId || m.name.toLowerCase().includes(modelId.toLowerCase()));
    
    if (!model) {
      addOperationHistoryEntry('error', `Model not found: ${modelId}. Use /model to see available models.`);
      return;
    }

    if (activeOperation) {
      operationManager.switchModel(activeOperation.id, model.id);
      addOperationHistoryEntry('info', `Switched to ${model.name} for current operation`);
    }
    
    // Update config model
    applicationConfig.modelId = model.id;
    addOperationHistoryEntry('info', `Default model set to ${model.name}`);
  }, [operationManager, activeOperation, applicationConfig]);

  const showAvailableModels = useCallback(() => {
    const models = operationManager.getAvailableModels();
    const modelList = models.map(m => `• ${m.name} (${m.id}) - $${m.inputCostPer1k}/1k input, $${m.outputCostPer1k}/1k output`).join('\n');
    addOperationHistoryEntry('info', `Available models:\n${modelList}`);
  }, [operationManager]);

  const showHelpMessage = useCallback(() => {
    const helpText = `
Cyber-AutoAgent Professional Platform v0.1.3

NATURAL LANGUAGE COMMANDS:
• scan https://example.com                    - Quick security scan
• analyze code in ./src/                      - Code security analysis  
• test api at api.example.com                 - API security testing

GUIDED FLOW:
• module general                              - Load security module
• target https://example.com                  - Set target system
• objective focus on authentication           - Set objective (optional)
• execute                                     - Start operation

SLASH COMMANDS:
• /config                                     - Configure settings
• /memory [query]                             - Search operation history
• /model [name]                               - Switch AI model
• /module [name]                              - Load security module
• /health                                     - Check container health status
• /pause                                      - Pause current operation
• /resume                                     - Resume paused operation
• /clear                                      - Clear screen
• /help                                       - Show this help
• /exit                                       - Exit application

KEYBOARD SHORTCUTS:
• Esc                                         - Exit application / Cancel operation / Close dialogs
• Ctrl+C                                      - Pause operation
• Ctrl+L                                      - Clear screen  
• Ctrl+R                                      - Toggle stream compression
• Ctrl+I                                      - Toggle input during streaming
`;
    addOperationHistoryEntry('info', helpText);
  }, []);

  // Handle safety warning confirmation
  const handleSafetyConfirm = useCallback(async () => {
    const pendingExecution = modalContext.pendingExecution;
    if (!pendingExecution) return;
    
    const operation = operationManager.startOperation(
      pendingExecution.module,
      pendingExecution.target,
      pendingExecution.objective || '',
      applicationConfig.modelId || 'claude-3-5-sonnet-20241022-v2:0'
    );
    
    setActiveOperation(operation);
    closeModal();
    addOperationHistoryEntry('operation', `Started operation: ${operation.id}`, operation);
    
    await startAssessment(operation);
  }, [modalContext.pendingExecution, operationManager, applicationConfig, closeModal]);

  // Memoized expensive calculations (Performance optimization)
  const contextUsage = useMemo(() => 
    operationManager.calculateContextUsage(
      applicationConfig.modelId || 'claude-3-5-sonnet-20241022-v2:0',
      operationManager.getSessionCost().tokensUsed
    ), [applicationConfig.modelId, operationManager]
  );

  // Memoized filtered operation history (Performance optimization)
  const filteredOperationHistory = useMemo(() => 
    operationHistoryEntries.filter((item) => {
      // Filter out user commands and module loads
      if (item.type === 'command') return false;
      if (item.content.startsWith('/')) return false;
      if (item.content.includes('Module loaded:')) return false;
      if (item.content.includes('Configuration complete!')) return false;
      // Keep errors and important operation messages
      return true;
    }), [operationHistoryEntries]
  );

  // Current directory for footer
  const currentDirectory = process.cwd();

  // Memoized modal registry with optimized dependencies (Performance optimization)
  const memoizedModalRegistry = useMemo(() => (
    <ModalRegistry
      activeModal={activeModal}
      modalContext={modalContext}
      onClose={closeModal}
      terminalWidth={terminalDisplayWidth}
      assessmentFlowManager={assessmentFlowManager}
      addOperationHistoryEntry={addOperationHistoryEntry}
      onSafetyConfirm={handleSafetyConfirm}
      isFirstRunExperience={isFirstRunExperience}
      setIsFirstRunExperience={setIsFirstRunExperience}
      setIsConfigurationModalOpen={(value) => value ? openConfig() : closeModal()}
    />
  ), [
    activeModal,
    modalContext,
    closeModal,
    terminalDisplayWidth,
    assessmentFlowManager,
    handleSafetyConfirm,
    isFirstRunExperience,
    openConfig
  ]);

  // Determine what content to show
  let mainContent = null;
  
  if (isInitializationFlowActive && !applicationConfig.isConfigured) {
    mainContent = (
      <InitializationFlow 
        onComplete={() => {
          setHasUserDismissedInit(true); // Mark that user has dismissed
          setIsInitializationFlowActive(false);
          // Mark that initial setup is complete
          hasInitialRefresh.current = true;
          // Skip refresh - header is already visible
          // Show config editor after initialization
          setTimeout(() => openConfig(), 50); // Small delay for smooth transition
        }}
      />
    );
  } else if (activeModal !== ModalType.NONE) {
    mainContent = memoizedModalRegistry;
  }
  
  // If we have special content (init flow or modal), render as overlay
  // Reuse the same Static component structure to avoid duplicates
  if (mainContent) {
    // Don't create a separate render path with its own Static
    // Fall through to main render below
  }

  // Main application layout (Gemini CLI-inspired)
  return (
    <Box flexDirection="column" width="100%">
      {/* Static area - includes header and filtered operation history */}
      <Static
        key={staticKey}
        items={[
          'header',
          ...filteredOperationHistory.map((item) => ({
            type: 'history',
            id: item.id,
            content: (
              <Box key={item.id} marginBottom={0} width="100%">
                <Text color={
                  item.type === 'operation' ? currentTheme.primary :
                  item.type === 'error' ? currentTheme.danger :
                  currentTheme.foreground
                }>
                  [{item.timestamp.toLocaleTimeString()}] {item.content}
                </Text>
              </Box>
            )
          }))
        ]}
      >
        {(item) => {
          if (item === 'header') {
            return (
              <Header 
                key="header"
                version="0.1.3" 
                terminalWidth={terminalDisplayWidth}
                nightly={false}
              />
            );
          }
          return (item as any).content;
        }}
      </Static>

      {/* Dynamic area - wrapped in a single container */}
      {mainContent ? (
        // Modal/special content overlay
        <Box key={`modal-view-${activeModal}`} flexDirection="column" width="100%">
          {mainContent}
        </Box>
      ) : isTerminalVisible ? (
        // Terminal view - header already rendered in main Static component above
        <Box flexDirection="column" width="100%" flexGrow={1}>
          <UnconstrainedTerminal
            dockerService={dockerService}
            sessionId={sessionId}
            onEvent={handleStreamingEvent}
            onMetricsUpdate={setOperationMetrics}
            terminalWidth={terminalDisplayWidth}
            collapsed={false}
          />
        </Box>
      ) : (
        // Normal view with input
        <Box flexDirection="column" width="100%">

        {/* Operation status display - hide when streaming */}
        {activeOperation && !isTerminalVisible && (
          <Box marginY={1}>
            <OperationStatusDisplay
              flowState={assessmentFlowState}
              currentOperation={activeOperation}
              showFlowProgress={false}
            />
          </Box>
        )}

        {/* Input area - hidden during operation execution for full screen streaming */}
        {!isTerminalVisible && (
          <Box marginTop={1}>
            <UnifiedInputPrompt
              flowState={assessmentFlowState}
              onInput={handleUnifiedInput}
              disabled={activeOperation?.status === 'running' && !userHandoffActive}
              userHandoffActive={userHandoffActive}
              availableModules={commandParser.getAvailableModules()}
              recentTargets={[]}
            />
          </Box>
        )}
        </Box>
      )}

      {/* Footer - always at bottom with spacing */}
      <Box>
        <Text> </Text>
        <Text> </Text>
        <Text> </Text>
        <Text> </Text>
        <Text> </Text>
        <Footer
            model={applicationConfig.modelId || 'claude-3-5-sonnet-20241022-v2:0'}
            contextRemaining={Math.max(0, 100 - contextUsage)}
            directory={currentDirectory}
            operationStatus={activeOperation ? {
              step: activeOperation.currentStep,
              totalSteps: activeOperation.totalSteps,
              description: activeOperation.description,
              isRunning: activeOperation.status === 'running'
            } : undefined}
            errorCount={sessionErrorCount}
            debugMode={false}
            operationMetrics={operationMetrics}
            connectionStatus={
              activeOperation?.status === 'running' ? 'connected' :
              isDockerServiceAvailable && applicationConfig.isConfigured ? 'connected' : 
              'offline'
            }
          />
      </Box>
    </Box>
  );
};

export const App: React.FC<AppProps> = (props) => {
  return (
    <ConfigProvider>
      <ModuleProvider>
        <AppContent {...props} />
      </ModuleProvider>
    </ConfigProvider>
  );
};