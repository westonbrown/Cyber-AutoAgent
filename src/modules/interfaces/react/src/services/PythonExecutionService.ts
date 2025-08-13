/**
 * Python Execution Service
 * 
 * Handles direct Python execution for local CLI mode, including:
 * - Virtual environment management
 * - Requirements installation
 * - Process execution and monitoring
 * - Output streaming
 */

import { EventEmitter } from 'events';
import { exec, spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { createLogger } from '../utils/logger.js';
import { AssessmentParams } from '../types/Assessment.js';
import { Config } from '../contexts/ConfigContext.js';
import { StreamEvent, EventType, ToolEvent, AgentEvent } from '../types/events.js';

// Define OutputEvent locally since it's part of PythonSystemEvent
interface OutputEvent {
  type: EventType.OUTPUT;
  content: string;
  timestamp: number;
  id: string;
  sessionId: string;
}

const execAsync = promisify(exec);

export class PythonExecutionService extends EventEmitter {
  private readonly logger = createLogger('PythonExecutionService');
  private activeProcess?: ChildProcess;
  private isExecutionActive = false;
  private streamEventBuffer = '';
  private abortController?: AbortController;
  private sessionId = `py-${Date.now()}`;
  
  // Paths
  private readonly projectRoot: string;
  private readonly venvPath: string;
  private readonly pythonPath: string;
  private readonly pipPath: string;
  private readonly srcPath: string;
  private readonly requirementsPath: string;
  private pythonCommand: string = 'python3'; // Will be updated by checkPythonVersion
  
  constructor() {
    super();
    
    // Get __dirname equivalent for ES modules
    const __filename = fileURLToPath(import.meta.url);
    const __dirname = path.dirname(__filename);
    
    // Determine project root by searching for pyproject.toml
    this.projectRoot = this.findProjectRoot();
    this.venvPath = path.join(this.projectRoot, '.venv');
    this.pythonPath = path.join(this.venvPath, process.platform === 'win32' ? 'Scripts/python' : 'bin/python');
    this.pipPath = path.join(this.venvPath, process.platform === 'win32' ? 'Scripts/pip' : 'bin/pip');
    this.srcPath = path.join(this.projectRoot, 'src');
    this.requirementsPath = path.join(this.projectRoot, 'requirements.txt');
  }

  /**
   * Find the project root by searching upward for pyproject.toml
   */
  private findProjectRoot(): string {
    // Get __dirname equivalent for ES modules
    const __filename = fileURLToPath(import.meta.url);
    let currentDir = path.dirname(__filename);
    
    // Search upward until we find pyproject.toml or reach filesystem root
    while (currentDir !== path.dirname(currentDir)) {
      const pyprojectPath = path.join(currentDir, 'pyproject.toml');
      if (fs.existsSync(pyprojectPath)) {
        return currentDir;
      }
      currentDir = path.dirname(currentDir);
    }
    
    // Fallback to environment variable or current working directory
    if (process.env.CYBER_PROJECT_ROOT && fs.existsSync(process.env.CYBER_PROJECT_ROOT)) {
      return process.env.CYBER_PROJECT_ROOT;
    }
    
    // Last resort: assume we're in a subdirectory and go up a few levels
    const __dirname = path.dirname(fileURLToPath(import.meta.url));
    return path.resolve(__dirname, '..', '..', '..', '..', '..');
  }
  
  /**
   * Check if Python 3.10+ is installed
   */
  async checkPythonVersion(): Promise<{ installed: boolean; version?: string; error?: string; pythonCommand?: string }> {
    // Try multiple Python commands in order of preference
    const pythonCommands = ['python3.11', 'python3.12', 'python3.13', 'python3.10', 'python3', 'python'];
    
    for (const cmd of pythonCommands) {
      try {
        const { stdout } = await execAsync(`${cmd} --version`);
        const versionMatch = stdout.match(/Python (\d+)\.(\d+)\.(\d+)/);
        
        if (versionMatch) {
          const major = parseInt(versionMatch[1]);
          const minor = parseInt(versionMatch[2]);
          const version = `${major}.${minor}.${versionMatch[3]}`;
          
          this.logger.debug(`Found Python via ${cmd}: version ${version}`);
          
          if (major >= 3 && minor >= 10) {
            // Store the working Python command
            this.pythonCommand = cmd;
            this.logger.info(`Using Python command: ${cmd} (version ${version})`);
            return { installed: true, version, pythonCommand: cmd };
          }
        }
      } catch (error) {
        // Try next command
        this.logger.debug(`Command ${cmd} failed: ${error}`);
        continue;
      }
    }
    
    // If we get here, no suitable Python was found
    // Check what version is installed (if any) to provide helpful error
    try {
      const { stdout } = await execAsync('python3 --version').catch(() => execAsync('python --version'));
      const versionMatch = stdout.match(/Python (\d+)\.(\d+)\.(\d+)/);
      
      if (versionMatch) {
        const version = `${versionMatch[1]}.${versionMatch[2]}.${versionMatch[3]}`;
        return { 
          installed: false, 
          error: `Python ${version} found, but 3.10+ is required. Please install Python 3.10 or higher from https://www.python.org/downloads/` 
        };
      }
    } catch {
      // No Python found at all
    }
    
    return { 
      installed: false, 
      error: 'Python not found. Please install Python 3.10 or higher from https://www.python.org/downloads/' 
    };
  }

  /**
   * Check current environment status
   */
  async checkEnvironmentStatus(): Promise<{
    pythonInstalled: boolean;
    pythonVersion?: string;
    venvExists: boolean;
    venvValid: boolean;
    dependenciesInstalled: boolean;
    packageInstalled: boolean;
    requirementsFile: string | null;
  }> {
    const start = Date.now();
    
    // Check Python
    const pythonCheck = await this.checkPythonVersion();
    this.logger.debug(`Python check took ${Date.now() - start}ms`);
    
    // Check venv
    const venvExists = fs.existsSync(this.venvPath);
    let venvValid = false;
    if (venvExists) {
      // Check if venv has Python executable
      venvValid = fs.existsSync(this.pythonPath);
    }
    this.logger.debug(`Venv check took ${Date.now() - start}ms total`);
    
    // Check dependencies
    let dependenciesInstalled = false;
    let packageInstalled = false;
    
    if (venvValid) {
      try {
        // Check if pip is available - add timeout
        const pipStart = Date.now();
        await execAsync(`"${this.pipPath}" --version`, { timeout: 5000 });
        dependenciesInstalled = true;
        this.logger.debug(`Pip check took ${Date.now() - pipStart}ms`);
        
        // Check if our package is installed - add timeout
        const pkgStart = Date.now();
        await execAsync(`"${this.pythonPath}" -c "import cyberautoagent"`, {
          env: { ...process.env, PYTHONPATH: this.srcPath },
          timeout: 5000
        });
        packageInstalled = true;
        this.logger.debug(`Package check took ${Date.now() - pkgStart}ms`);
      } catch (error) {
        // Dependencies or package not properly installed
        this.logger.debug(`Dependency check error: ${error}`);
      }
    }
    
    // Find requirements file
    let requirementsFile: string | null = null;
    if (fs.existsSync(this.requirementsPath)) {
      requirementsFile = 'requirements.txt';
    } else if (fs.existsSync(path.join(this.projectRoot, 'pyproject.toml'))) {
      requirementsFile = 'pyproject.toml';
    } else if (fs.existsSync(path.join(this.projectRoot, 'setup.py'))) {
      requirementsFile = 'setup.py';
    }
    
    return {
      pythonInstalled: pythonCheck.installed,
      pythonVersion: pythonCheck.version,
      venvExists,
      venvValid,
      dependenciesInstalled,
      packageInstalled,
      requirementsFile
    };
  }
  
  /**
   * Setup Python environment for CLI mode with intelligent state detection
   */
  async setupPythonEnvironment(onProgress?: (message: string) => void): Promise<void> {
    const progress = (msg: string) => {
      this.logger.info(msg);
      onProgress?.(msg);
      this.emit('progress', msg);
    };
    
    try {
      // Step 1: Check current environment status
      progress('Analyzing current environment...');
      const status = await this.checkEnvironmentStatus();
      
      if (!status.pythonInstalled) {
        throw new Error(status.pythonVersion ? 
          `Python ${status.pythonVersion} found, but 3.10+ is required` :
          'Python 3.10+ is not installed. Please install from https://python.org');
      }
      
      progress(`✓ Python ${status.pythonVersion} detected (using ${this.pythonCommand})`);
      
      // Step 2: Handle virtual environment
      if (!status.venvExists) {
        progress('Creating virtual environment...');
        await execAsync(`${this.pythonCommand} -m venv "${this.venvPath}"`);
        progress('✓ Virtual environment created');
      } else if (!status.venvValid) {
        progress('Repairing corrupted virtual environment...');
        // Remove and recreate
        await execAsync(`rm -rf "${this.venvPath}"`);
        await execAsync(`${this.pythonCommand} -m venv "${this.venvPath}"`);
        progress('✓ Virtual environment repaired');
      } else {
        progress('✓ Virtual environment already exists and is valid');
      }
      
      // Step 3: Check requirements file
      if (!status.requirementsFile) {
        throw new Error('No requirements.txt, pyproject.toml, or setup.py found in project root');
      }
      progress(`✓ Found ${status.requirementsFile} for dependency management`);
      
      // Step 4: Handle pip upgrade (only if needed)
      if (!status.dependenciesInstalled) {
        progress('Upgrading pip...');
        await execAsync(`"${this.pythonPath}" -m pip install --upgrade pip`);
        progress('✓ Pip upgraded');
      } else {
        progress('✓ Pip already available');
      }
      
      // Step 5: Handle dependencies
      if (!status.dependenciesInstalled || !status.packageInstalled) {
        progress('Installing/updating Python dependencies...');
        
        if (status.requirementsFile === 'requirements.txt') {
          await execAsync(`"${this.pipPath}" install -r "${this.requirementsPath}"`, {
            cwd: this.projectRoot
          });
        } else if (status.requirementsFile === 'pyproject.toml' || status.requirementsFile === 'setup.py') {
          // For pyproject.toml, install in editable mode with all dependencies
          progress('Installing from pyproject.toml...');
          await execAsync(`"${this.pipPath}" install -e . --verbose`, {
            cwd: this.projectRoot
          });
        }
        
        progress('✓ Dependencies installed/updated');
      } else {
        progress('✓ Dependencies already installed');
      }
      
      // Step 6: Final verification
      progress('Verifying installation...');
      try {
        await execAsync(`"${this.pythonPath}" -c "import cyberautoagent; print('Cyber-AutoAgent version:', getattr(cyberautoagent, '__version__', 'dev'))"`, {
          env: { ...process.env, PYTHONPATH: this.srcPath }
        });
        progress('✓ Cyber-AutoAgent package verified and ready');
      } catch (error) {
        // Last resort - try development install
        progress('Installing Cyber-AutoAgent in development mode...');
        await execAsync(`"${this.pipPath}" install -e .`, {
          cwd: this.projectRoot
        });
        progress('✓ Cyber-AutoAgent installed in development mode');
      }
      
      progress('✓ Python environment setup complete!');
      
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      progress(`✗ Setup failed: ${errorMsg}`);
      throw error;
    }
  }
  
  /**
   * Execute assessment using Python directly
   */
  async executeAssessment(
    params: AssessmentParams,
    config: Config
  ): Promise<void> {
    if (this.isExecutionActive) {
      throw new Error('Assessment already running');
    }
    
    this.isExecutionActive = true;
    this.abortController = new AbortController();
    
    return new Promise<void>((resolve, reject) => {
      try {
      // Ensure environment is set up
      const venvExists = fs.existsSync(this.pythonPath);
      if (!venvExists) {
        throw new Error('Python environment not set up. Please run setup first.');
      }
      
      // Build command arguments
      const objective = params.objective || `Perform comprehensive ${params.module.replace('_', ' ')} assessment`;
      const args = [
        path.join(this.srcPath, 'cyberautoagent.py'),
        '--module', params.module,
        '--objective', objective,
        '--target', params.target,
        '--iterations', String(config.iterations || 100),
        '--provider', config.modelProvider || 'bedrock',
      ];
      
      if (config.modelId) {
        args.push('--model', config.modelId);
      }
      
      // For Ollama, the modelId is used as the ollama model
      if (config.modelProvider === 'ollama' && config.modelId) {
        args.push('--ollama-model', config.modelId);
      }
      
      // Set up environment variables
      const env = {
        ...process.env,
        PYTHONPATH: this.srcPath,
        PYTHONUNBUFFERED: '1',
        FORCE_COLOR: '1',
        // React UI integration - critical for event emission
        BYPASS_TOOL_CONSENT: config.confirmations ? 'false' : 'true',
        __REACT_INK__: 'true',
        CYBERAGENT_NO_BANNER: 'true',  // Suppress banner in React mode
        DEV: config.verbose ? 'true' : 'false',
        // AWS Configuration
        AWS_ACCESS_KEY_ID: config.awsAccessKeyId || '',
        AWS_SECRET_ACCESS_KEY: config.awsSecretAccessKey || '',
        AWS_BEARER_TOKEN_BEDROCK: config.awsBearerToken || '',
        AWS_REGION: config.awsRegion || 'us-east-1',
        // Ollama Configuration
        OLLAMA_HOST: config.ollamaHost || '',
        // Observability settings from config (matching Docker service behavior)
        ENABLE_OBSERVABILITY: config.observability ? 'true' : 'false',
        ENABLE_AUTO_EVALUATION: config.autoEvaluation ? 'true' : 'false',
        ENABLE_LANGFUSE_PROMPTS: config.enableLangfusePrompts ? 'true' : 'false',
        // Langfuse configuration when observability is enabled
        ...(config.observability && {
          LANGFUSE_HOST: config.langfuseHost,
          LANGFUSE_PUBLIC_KEY: config.langfusePublicKey,
          LANGFUSE_SECRET_KEY: config.langfuseSecretKey,
          LANGFUSE_PROMPT_LABEL: config.langfusePromptLabel,
          LANGFUSE_PROMPT_CACHE_TTL: String(config.langfusePromptCacheTTL)
        }),
        // Evaluation settings when auto-evaluation is enabled
        ...(config.autoEvaluation && {
          RAGAS_EVALUATOR_MODEL: config.evaluationModel,
          EVALUATION_BATCH_SIZE: String(config.evaluationBatchSize)
        })
      };
      
      this.logger.info('Starting Python assessment', { 
        args, 
        cwd: this.projectRoot,
        config: {
          iterations: config.iterations,
          modelProvider: config.modelProvider,
          modelId: config.modelId,
          observability: config.observability,
          autoEvaluation: config.autoEvaluation
        }
      });
      
      // Emit startup events exactly like Docker mode for consistency
      this.emit('event', {
        type: 'output',
        content: '▶ Initializing Python assessment environment...',
        timestamp: Date.now()
      });
      
      setTimeout(() => {
        this.emit('event', {
          type: 'output',
          content: '◆ Python environment ready',
          timestamp: Date.now()
        });
      }, 500);
      
      setTimeout(() => {
        this.emit('event', {
          type: 'output',
          content: '◆ Setting up direct Python security assessment environment',
          timestamp: Date.now()
        });
      }, 1000);
      
      setTimeout(() => {
        this.emit('event', {
          type: 'output',
          content: '◆ Loading Python-based cybersecurity tools...',
          timestamp: Date.now()
        });
      }, 1800);
      
      // Emit thinking indicator during tool setup
      this.emit('event', {
        type: 'thinking',
        context: 'startup',
        startTime: Date.now(),
        metadata: {
          message: 'Preparing Python security assessment environment'
        }
      });
      
      // Spawn Python process
      this.activeProcess = spawn(this.pythonPath, args, {
        cwd: this.projectRoot,
        env,
        shell: false
      });
      
      // Emit started event
      this.emit('started');
      
      // Handle stdout
      this.activeProcess.stdout?.on('data', (data: Buffer) => {
        const output = data.toString();
        this.processOutputStream(output);
      });
      
      // Handle stderr
      this.activeProcess.stderr?.on('data', (data: Buffer) => {
        const output = data.toString();
        // Python may output regular messages to stderr
        this.processOutputStream(output);
      });
      
      // Handle process exit
      this.activeProcess.on('exit', (code, signal) => {
        this.isExecutionActive = false;
        
        if (signal === 'SIGTERM' || signal === 'SIGINT') {
          this.emit('stopped');
          resolve(); // Process was stopped intentionally
        } else if (code === 0) {
          this.emit('complete');
          resolve(); // Process completed successfully
        } else {
          // Provide more detailed error information
          const errorMsg = `Python process exited with code ${code}. Check that all dependencies are installed and the cyberautoagent module can be imported.`;
          const error = new Error(errorMsg);
          this.emit('error', error);
          reject(error); // Process failed
        }
        
        this.activeProcess = undefined;
      });
      
      // Handle process error
      this.activeProcess.on('error', (error) => {
        this.logger.error('Process error', error);
        this.emit('error', error);
        this.isExecutionActive = false;
        this.activeProcess = undefined;
        reject(error); // Process startup failed
      });
      
      } catch (error) {
        this.isExecutionActive = false;
        this.logger.error('Failed to start assessment', error as Error);
        reject(error);
      }
    });
  }
  
  /**
   * Process output stream and emit structured events
   * UNIFIED APPROACH: Use the exact same event parsing as DirectDockerService
   */
  private processOutputStream(data: string): void {
    // Add to buffer
    this.streamEventBuffer += data;
    
    // Look for structured event markers (UNIFIED with Docker service)
    const eventRegex = /__CYBER_EVENT__(.+?)__CYBER_EVENT_END__/gs;
    let match;
    
    while ((match = eventRegex.exec(this.streamEventBuffer)) !== null) {
      try {
        const eventData = JSON.parse(match[1]);
        // Pass through the event with all properties
        const event: any = {
          type: eventData.type as EventType,
          content: eventData.content,
          data: eventData.data || {},
          metadata: eventData.metadata || {},
          timestamp: eventData.timestamp || Date.now(),
          id: eventData.id || `evt-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          sessionId: eventData.sessionId || this.sessionId,
          // Include all original properties for compatibility
          ...eventData
        };
        
        // Handle special event types that Docker service also handles
        if (event.type === 'tool_discovery_start') {
          this.emit('event', {
            type: 'output',
            content: '◆ Loading cybersecurity assessment tools:',
            timestamp: Date.now()
          });
        } else if (event.type === 'tool_available') {
          this.emit('event', {
            type: 'output',
            content: `  ✓ ${eventData.tool_name} (${eventData.description})`,
            timestamp: Date.now()
          });
        } else if (event.type === 'tool_unavailable') {
          this.emit('event', {
            type: 'output',
            content: `  ○ ${eventData.tool_name} (${eventData.description} - not available)`,
            timestamp: Date.now()
          });
        } else if (event.type === 'environment_ready') {
          this.emit('event', {
            type: 'output',
            content: `◆ Environment ready - ${eventData.tool_count} cybersecurity tools loaded`,
            timestamp: Date.now()
          });
          
          setTimeout(() => {
            this.emit('event', {
              type: 'output',
              content: '◆ Configuring assessment parameters and evidence collection',
              timestamp: Date.now()
            });
          }, 500);
          
          setTimeout(() => {
            this.emit('event', {
              type: 'output',
              content: '◆ Security assessment environment ready - Beginning evaluation',
              timestamp: Date.now()
            });
            // Add spacing and start thinking animation
            setTimeout(() => {
              this.emit('event', {
                type: 'output',
                content: '',
                timestamp: Date.now()
              });
              this.emit('event', {
                type: 'output',
                content: '',
                timestamp: Date.now()
              });
              
              // Note: Removed delayed_thinking_start to avoid duplicate animations during startup
              // The startup thinking animation is already active and more appropriate
            }, 100);
          }, 1000);
        } else {
          // Emit all other events as-is
          this.emit('event', event);
        }
      } catch (error) {
        // Silently skip parsing errors - don't pollute output
      }
    }
    
    // Clean processed events from buffer
    this.streamEventBuffer = this.streamEventBuffer.replace(eventRegex, '');
    
    // Keep only last 10KB to prevent memory issues (same as Docker service)
    if (this.streamEventBuffer.length > 10240) {
      this.streamEventBuffer = this.streamEventBuffer.slice(-5120);
    }
    
    // DO NOT process remaining lines - let structured events handle everything
    // This ensures consistency across all execution modes
  }
  
  /**
   * Stop the running assessment
   */
  async stop(): Promise<void> {
    if (this.activeProcess) {
      this.logger.info('Stopping Python process');
      
      // Kill the process
      if (process.platform === 'win32') {
        exec(`taskkill /pid ${this.activeProcess.pid} /T /F`);
      } else {
        this.activeProcess.kill('SIGTERM');
      }
      
      // Give it time to clean up with timeout cleanup
      await new Promise<void>(resolve => {
        const timeout = setTimeout(resolve, 1000);
        // Ensure timeout is cleaned up
        timeout.unref();
      });
      
      // Force kill if still running
      if (this.activeProcess) {
        this.activeProcess.kill('SIGKILL');
      }
    }
    
    this.isExecutionActive = false;
    this.abortController?.abort();
  }
  
  /**
   * Check if execution is currently active
   */
  isActive(): boolean {
    return this.isExecutionActive;
  }
  
  /**
   * Send user input to the Python process (for handoff_to_user tool)
   */
  async sendUserInput(input: string): Promise<void> {
    if (!this.activeProcess || !this.isExecutionActive) {
      throw new Error('No active Python process to send input to');
    }

    try {
      // Send input to Python process stdin with newline
      if (this.activeProcess.stdin) {
        this.activeProcess.stdin.write(input + '\n');
      } else {
        throw new Error('Python process stdin is not available');
      }
    } catch (error) {
      throw new Error(`Error sending input to Python process: ${error}`);
    }
  }

  /**
   * Cleanup resources and remove all event listeners
   */
  cleanup(): void {
    // Stop any active process
    if (this.activeProcess) {
      this.activeProcess.kill('SIGKILL');
      this.activeProcess = undefined;
    }
    
    // Abort any pending operations
    this.abortController?.abort();
    
    // Remove all event listeners to prevent memory leaks
    this.removeAllListeners();
    
    // Reset state
    this.isExecutionActive = false;
    this.streamEventBuffer = '';
    
    this.logger.info('PythonExecutionService cleaned up');
  }
  
  /**
   * Dispose of the service (alias for cleanup)
   */
  dispose(): void {
    this.cleanup();
  }
}