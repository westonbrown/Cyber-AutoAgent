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
    
    // Determine project root (6 levels up from dist/services)
    this.projectRoot = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');
    this.venvPath = path.join(this.projectRoot, '.venv');
    this.pythonPath = path.join(this.venvPath, process.platform === 'win32' ? 'Scripts/python' : 'bin/python');
    this.pipPath = path.join(this.venvPath, process.platform === 'win32' ? 'Scripts/pip' : 'bin/pip');
    this.srcPath = path.join(this.projectRoot, 'src');
    this.requirementsPath = path.join(this.projectRoot, 'requirements.txt');
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
          
          if (major >= 3 && minor >= 10) {
            // Store the working Python command
            this.pythonCommand = cmd;
            return { installed: true, version, pythonCommand: cmd };
          }
        }
      } catch {
        // Try next command
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
    // Check Python
    const pythonCheck = await this.checkPythonVersion();
    
    // Check venv
    const venvExists = fs.existsSync(this.venvPath);
    let venvValid = false;
    if (venvExists) {
      // Check if venv has Python executable
      venvValid = fs.existsSync(this.pythonPath);
    }
    
    // Check dependencies
    let dependenciesInstalled = false;
    let packageInstalled = false;
    
    if (venvValid) {
      try {
        // Check if pip is available
        await execAsync(`"${this.pipPath}" --version`);
        dependenciesInstalled = true;
        
        // Check if our package is installed
        await execAsync(`"${this.pythonPath}" -c "import cyberautoagent"`, {
          env: { ...process.env, PYTHONPATH: this.srcPath }
        });
        packageInstalled = true;
      } catch {
        // Dependencies or package not properly installed
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
          await execAsync(`"${this.pipPath}" install -e .`, {
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
        // AWS Configuration
        AWS_ACCESS_KEY_ID: config.awsAccessKeyId || '',
        AWS_SECRET_ACCESS_KEY: config.awsSecretAccessKey || '',
        AWS_BEARER_TOKEN_BEDROCK: config.awsBearerToken || '',
        AWS_REGION: config.awsRegion || 'us-east-1',
        // Ollama Configuration
        OLLAMA_HOST: config.ollamaHost || '',
        // Disable Docker-specific features
        ENABLE_OBSERVABILITY: 'false',
        ENABLE_AUTO_EVALUATION: 'false',
        ENABLE_LANGFUSE_PROMPTS: 'false'
      };
      
      this.logger.info('Starting Python assessment', { args, cwd: this.projectRoot });
      
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
        } else if (code === 0) {
          this.emit('complete');
        } else {
          this.emit('error', new Error(`Process exited with code ${code}`));
        }
        
        this.activeProcess = undefined;
      });
      
      // Handle process error
      this.activeProcess.on('error', (error) => {
        this.logger.error('Process error', error);
        this.emit('error', error);
        this.isExecutionActive = false;
        this.activeProcess = undefined;
      });
      
    } catch (error) {
      this.isExecutionActive = false;
      this.logger.error('Failed to start assessment', error as Error);
      throw error;
    }
  }
  
  /**
   * Process output stream and emit structured events
   */
  private processOutputStream(data: string): void {
    // Add to buffer
    this.streamEventBuffer += data;
    
    // Process complete lines
    const lines = this.streamEventBuffer.split('\n');
    this.streamEventBuffer = lines.pop() || '';
    
    for (const line of lines) {
      if (!line.trim()) continue;
      
      try {
        // Try to parse as JSON event
        if (line.startsWith('{') && line.endsWith('}')) {
          const event = JSON.parse(line);
          this.emit('event', event);
        } else {
          // Emit as output event
          const event: OutputEvent = {
            type: EventType.OUTPUT,
            content: line,
            timestamp: Date.now(),
            id: `evt-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            sessionId: this.sessionId
          };
          this.emit('event', event);
        }
      } catch (error) {
        // If not JSON, emit as output
        const event: OutputEvent = {
          type: EventType.OUTPUT,
          content: line,
          timestamp: Date.now(),
          id: `evt-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          sessionId: this.sessionId
        };
        this.emit('event', event);
      }
    }
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
      
      // Give it time to clean up
      await new Promise(resolve => setTimeout(resolve, 1000));
      
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
}