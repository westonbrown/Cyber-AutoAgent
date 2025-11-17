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
import { exec, spawn, ChildProcess, execFileSync } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { createLogger } from '../utils/logger.js';
import { AssessmentParams } from '../types/Assessment.js';
import { Config } from '../contexts/ConfigContext.js';
import { StreamEvent, EventType, ToolEvent, AgentEvent } from '../types/events.js';
import { flattenEnvironment } from '../utils/env.js';

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
  // Emit policy: only stream raw stdout during active tool execution
  private inToolExecution = false;
  private toolOutputBuffer = '';
  // Track execution start time for duration reporting
  private startTime?: number;

  /** Emit a chunk of buffered tool output */
  private emitToolOutputChunk(content: string): void {
    try {
      this.emit('event', {
        type: 'output',
        content,
        timestamp: Date.now(),
        metadata: { fromToolBuffer: true, tool: (this as any)._currentToolName, chunked: true }
      });
    } catch {}
  }

  /**
   * Flush tool output buffer in chunks to keep memory flat and reduce latency.
   * If force=true, flush remaining buffer even if smaller than chunk size.
   */
  private flushToolOutputChunks(force: boolean = false): void {
    const CHUNK_SIZE = 64 * 1024; // 64 KiB
    const MIN_SPLIT = 32 * 1024;  // Prefer newline split after 32 KiB
    while (this.toolOutputBuffer.length > CHUNK_SIZE || (force && this.toolOutputBuffer.length > 0)) {
      const window = this.toolOutputBuffer.slice(0, CHUNK_SIZE);
      let n = Math.min(this.toolOutputBuffer.length, CHUNK_SIZE);
      const nl = window.lastIndexOf('\n');
      if (nl >= MIN_SPLIT && nl < CHUNK_SIZE) {
        n = nl + 1; // split on newline
      }
      const chunk = this.toolOutputBuffer.slice(0, n);
      this.emitToolOutputChunk(chunk);
      this.toolOutputBuffer = this.toolOutputBuffer.slice(n);
    }
  }
  // Track whether backend emitted consolidated tool output to avoid duplication
  private sawBackendToolOutput = false;
  // Track whether a user-initiated stop() was requested to treat exits as intentional
  private userStopRequested = false;
  
  // Paths
  private readonly projectRoot: string;
  private readonly venvPath: string;
  private readonly pythonPath: string;
  private readonly pipPath: string;
  private readonly srcPath: string;
  private readonly requirementsPath: string;
  private pythonCommand: string = 'python3'; // Will be updated by checkPythonVersion
  private stderrBuffer: string = '';
  
  constructor() {
    super();
    
    // Get current directory (where the React app is running)
    const currentDir = process.cwd();
    
    // Resolve actual Python project root by searching upward for pyproject.toml/setup.py
    this.projectRoot = this.resolveProjectRoot(currentDir);
    this.venvPath = path.join(this.projectRoot, '.venv');
    this.srcPath = path.join(this.projectRoot, 'src');

    // Platform-specific binaries inside the venv
    const isWindows = process.platform === 'win32';
    const venvBinDir = isWindows ? 'Scripts' : 'bin';
    const pythonExecutable = isWindows ? 'python.exe' : 'python';
    const pipExecutable = isWindows ? 'pip.exe' : 'pip';

    this.pythonPath = path.join(this.venvPath, venvBinDir, pythonExecutable);
    this.pipPath = path.join(this.venvPath, venvBinDir, pipExecutable);
    this.requirementsPath = path.join(this.projectRoot, 'pyproject.toml');
    // Note: Python version detection is performed in checkPythonVersion(), not in the constructor
  }

  /**
   * Resolve the Python project root by searching upwards for project markers.
   * Priority: 1) CYBER_PROJECT_ROOT env var (if valid), 2) nearest directory with pyproject.toml or setup.py,
   * 3) a directory containing docker/docker-compose.yml, 4) fallback to currentDir.
   */
  private resolveProjectRoot(currentDir: string): string {
    // Priority 1: explicit override
    const envRoot = process.env.CYBER_PROJECT_ROOT;
    if (envRoot) {
      const pyproject = path.join(envRoot, 'pyproject.toml');
      const setupPy = path.join(envRoot, 'setup.py');
      if (fs.existsSync(pyproject) || fs.existsSync(setupPy)) {
        return path.resolve(envRoot);
      }
    }

    // Priority 2/3: search upwards for markers
    let dir = path.resolve(currentDir);
    const maxLevels = 10;
    for (let i = 0; i < maxLevels; i++) {
      const pyproject = path.join(dir, 'pyproject.toml');
      const setupPy = path.join(dir, 'setup.py');
      const dockerCompose = path.join(dir, 'docker', 'docker-compose.yml');
      if (fs.existsSync(pyproject) || fs.existsSync(setupPy)) {
        return dir;
      }
      if (fs.existsSync(dockerCompose)) {
        // Likely the project root even if pyproject lives adjacent
        // Keep scanning one more level for pyproject
        const parent = path.dirname(dir);
        const parentPy = path.join(parent, 'pyproject.toml');
        if (fs.existsSync(parentPy)) return parent;
        return dir;
      }
      const parentDir = path.dirname(dir);
      if (parentDir === dir) break;
      dir = parentDir;
    }

    // Fallback: current working directory
    this.logger.warn('Could not find pyproject.toml or setup.py; falling back to current directory', { currentDir });
    return path.resolve(currentDir);
  }

  /**
   * Detect a suitable Python interpreter and set this.pythonCommand.
   * Returns detection result for UI and setup use.
   */
  public async checkPythonVersion(): Promise<{ installed: boolean; version?: string; error?: string }> {
    // Allow explicit override via environment (takes absolute precedence)
    const override = process.env.CYBER_PYTHON;

    // Build a broad candidate list in priority order
    const isWindows = process.platform === 'win32';
    const userHome = process.env.HOME || process.env.USERPROFILE || '';
    const condaPy = process.env.CONDA_PREFIX ? `${process.env.CONDA_PREFIX}/bin/python` : undefined;

    const versioned = ['3.12', '3.11', '3.10'];
    const baseNames = [
      ...versioned.map(v => `python3.${v.split('.')[1]}`),
      'python3',
      'python',
    ];
    const homebrew = [
      ...versioned.map(v => `/opt/homebrew/bin/python3.${v.split('.')[1]}`),
      ...versioned.map(v => `/usr/local/bin/python3.${v.split('.')[1]}`),
      '/opt/homebrew/bin/python3',
      '/usr/local/bin/python3',
    ];
    const pyenvShims = userHome
      ? [
          ...versioned.map(v => `${userHome}/.pyenv/shims/python3.${v.split('.')[1]}`),
          `${userHome}/.pyenv/shims/python3`,
          `${userHome}/.pyenv/shims/python`,
        ]
      : [];
    const asdfShims = userHome
      ? [
          ...versioned.map(v => `${userHome}/.asdf/shims/python3.${v.split('.')[1]}`),
          `${userHome}/.asdf/shims/python3`,
          `${userHome}/.asdf/shims/python`,
        ]
      : [];
    const windowsPy = isWindows ? ['py -3.12', 'py -3.11', 'py -3.10', 'py -3', 'py'] : [];

    const candidates = [
      ...(override ? [override] : []),
      ...(condaPy ? [condaPy] : []),
      ...windowsPy,
      ...baseNames,
      ...homebrew,
      ...pyenvShims,
      ...asdfShims,
    ];

    // De-dupe while preserving order
    const seen = new Set<string>();
    const commands = candidates.filter(c => {
      const key = c.trim();
      if (!key) return false;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    type Detected = { cmd: string; versionStr?: string; major?: number; minor?: number; ok: boolean };
    const detections: Detected[] = [];

    for (const cmd of commands) {
      try {
        const { stdout, stderr } = await execAsync(`${cmd} --version`, { timeout: 5000 });
        const versionLine = (stdout || stderr || '').toString().trim();
        const m = versionLine.match(/Python\s+(\d+)\.(\d+)/);
        if (!m) {
          detections.push({ cmd, versionStr: versionLine, ok: false });
          continue;
        }
        const major = parseInt(m[1]);
        const minor = parseInt(m[2]);
        const ok = major > 3 || (major === 3 && minor >= 10);
        detections.push({ cmd, versionStr: versionLine, major, minor, ok });
      } catch {
        // Ignore failures and continue to next candidate
      }
    }

    // Choose the highest version that satisfies >= 3.10
    let best: Detected | undefined = undefined;
    for (const d of detections) {
      if (!d.ok || d.major === undefined || d.minor === undefined) continue;
      if (!best) {
        best = d;
        continue;
      }
      if (d.major > best.major! || (d.major === best.major && d.minor! > best.minor!)) {
        best = d;
      }
    }

    // Log a concise detection table for transparency
    if (detections.length > 0) {
      try {
        this.logger.info('Python interpreter detection', {
          detections: detections.map(d => ({ cmd: d.cmd, version: d.versionStr || 'unknown', eligible: d.ok })),
          chosen: best ? { cmd: best.cmd, version: best.versionStr } : null,
          override: override || null,
        });
      } catch {}
    }

    if (best) {
      this.pythonCommand = best.cmd;
      return { installed: true, version: best.versionStr };
    }

    return { installed: false, error: 'Python 3.10+ is required but not found' };
  }
  
  /**
   * Get current Python command
   */
  getCurrentPythonCommand(): string {
    return this.pythonCommand;
  }
  
  /**
   * Get active process PID if running
   */
  getActiveProcessPid(): number | undefined {
    return this.activeProcess?.pid;
  }
  
  /**
   * Get session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }
  
  /**
   * Check if execution is currently active
   */
  isActive(): boolean {
    return this.isExecutionActive;
  }
  
  /**
   * Stop current execution
   */
  async stop(): Promise<void> {
    // Mark as user-initiated stop so exit handler treats non-zero exit as intentional
    this.userStopRequested = true;
    if (this.activeProcess) {
      this.logger.info('Stopping Python process', { pid: this.activeProcess.pid });

      try {
        // Kill entire process tree to prevent orphans
        // On Unix: negative PID kills the process group
        const pid = this.activeProcess.pid;
        if (pid) {
          try {
            // Try to kill process group first (kills all children)
            process.kill(-pid, 'SIGTERM');
            this.logger.info('Sent SIGTERM to process group', { pgid: -pid });
          } catch (pgErr) {
            // If process group kill fails, try individual process
            this.logger.warn('Process group kill failed, trying individual process', pgErr);
            this.activeProcess.kill('SIGTERM');
          }

          // If still running after 3 seconds, force kill entire tree
          setTimeout(() => {
            if (this.activeProcess && !this.activeProcess.killed) {
              this.logger.warn('Force killing Python process tree');
              try {
                process.kill(-pid, 'SIGKILL');
              } catch {
                this.activeProcess.kill('SIGKILL');
              }
            }
          }, 3000);
        }

      } catch (error) {
        this.logger.error('Error stopping Python process', error as Error);
      }
    }
    
    if (this.abortController) {
      this.abortController.abort();
    }
    
    this.isExecutionActive = false;
  }

  /**
   * Send user input to the active Python process (newline-terminated)
   */
  public async sendUserInput(input: string): Promise<void> {
    if (!this.activeProcess || !this.activeProcess.stdin) {
      throw new Error('No active Python process to receive input');
    }
    return new Promise<void>((resolve, reject) => {
      try {
        this.activeProcess!.stdin!.write(input.endsWith('\n') ? input : input + '\n', (err?: Error) => {
          if (err) return reject(err);
          resolve();
        });
      } catch (err) {
        reject(err as Error);
      }
    });
  }

  /**
   * Cleanup resources for the Python execution service
   */
  public cleanup(): void {
    try {
      // Best-effort stop
      void this.stop();
    } catch {}
    this.removeAllListeners();
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
    
    // Check requirements file
    const requirementsFile = fs.existsSync(this.requirementsPath) ? this.requirementsPath : null;
    
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
   * Preflight checks: emit bracketed status lines without mutating the environment.
   * Returns true if everything looks good, false otherwise.
   */
  async preflightChecks(onProgress?: (message: string) => void): Promise<boolean> {
    const say = (msg: string) => {
      this.logger.info(msg);
      onProgress?.(msg);
      this.emit('progress', msg);
    };

    let ok = true;
    const status = await this.checkEnvironmentStatus();

    if (!status.pythonInstalled) {
      say('[ERR] Python 3.10+ not found');
      ok = false;
    } else {
      say(`[OK] Python detected: ${status.pythonVersion}`);
    }

    if (!status.venvExists) {
      say(`[ERR] Virtual environment missing at ${this.venvPath}`);
      ok = false;
    } else if (!status.venvValid) {
      say(`[ERR] Virtual environment invalid at ${this.venvPath}`);
      ok = false;
    } else {
      say(`[OK] Virtual environment ready at ${this.venvPath}`);
    }

    if (!status.dependenciesInstalled) {
      say('[WARN] pip not available in venv or dependencies not installed');
    } else {
      say('[OK] pip available in venv');
    }

    if (!status.packageInstalled) {
      say('[ERR] Python package "cyberautoagent" not importable');
      ok = false;
    } else {
      say('[OK] cyberautoagent import verified');
    }

    if (status.requirementsFile) {
      say(`[OK] Project file detected: ${path.basename(status.requirementsFile)}`);
    } else {
      say('[WARN] No pyproject.toml or setup.py detected at resolved project root');
    }

    return ok;
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
      const status = await this.checkEnvironmentStatus();
      
      if (!status.pythonInstalled) {
        throw new Error('Python 3.10+ is required but not found. Please install Python first.');
      }
      
      progress(`[OK] Python ${status.pythonVersion} found`);
      
      // Step 2: Create or validate virtual environment
      if (!status.venvExists) {
        progress('[INFO] Creating Python virtual environment...');
        await execAsync(`${this.pythonCommand} -m venv "${this.venvPath}"`);
        progress('[OK] Virtual environment created');
      } else if (!status.venvValid) {
        progress('[INFO] Recreating corrupted virtual environment...');
        // Remove and recreate
        await execAsync(`rm -rf "${this.venvPath}"`);
        await execAsync(`${this.pythonCommand} -m venv "${this.venvPath}"`);
        progress('[OK] Virtual environment recreated');
      } else {
        // Validate venv Python version >= 3.10
        try {
          const { stdout: venvVerOut } = await execAsync(`"${this.pythonPath}" --version`);
          const versionStr = venvVerOut.trim();
          const m = versionStr.match(/Python (\d+)\.(\d+)/);
          if (m) {
            const vMaj = parseInt(m[1]);
            const vMin = parseInt(m[2]);
            if (!(vMaj > 3 || (vMaj === 3 && vMin >= 10))) {
              progress('[INFO] Recreating virtual environment with Python 3.10+...');
              await execAsync(`rm -rf "${this.venvPath}"`);
              await execAsync(`${this.pythonCommand} -m venv "${this.venvPath}"`);
              progress('[OK] Virtual environment recreated with compatible Python');
            } else {
              progress('[OK] Virtual environment found and valid');
            }
          } else {
            // If version parse fails, keep going but note it
            progress('[OK] Virtual environment found');
          }
        } catch {
          // If check fails, proceed without blocking
          progress('[OK] Virtual environment found');
        }
      }
      
      // Step 3: Install dependencies if needed
      if (!status.dependenciesInstalled || !status.packageInstalled) {
        progress('[INFO] Installing Python dependencies...');
        
        // Upgrade pip first with immediate feedback
        progress('[INFO] Upgrading pip...');
        await execAsync(`"${this.pipPath}" install --upgrade pip`, {
          cwd: this.projectRoot
        });
        progress('[OK] pip upgraded');
        
        // Install with editable mode for development
        progress('[INFO] Installing cyberautoagent package (this may take a moment)...');
        await execAsync(`"${this.pipPath}" install -e .`, {
          cwd: this.projectRoot
        });
        
        progress('[OK] Dependencies installed successfully');
      } else {
        progress('[OK] Dependencies already installed');
      }
      
      // Step 4: Verify installation
      try {
        await execAsync(`"${this.pythonPath}" -c "import cyberautoagent; print('Cyber-AutoAgent version:', getattr(cyberautoagent, '__version__', 'dev'))"`, {
          env: { ...process.env, PYTHONPATH: this.srcPath }
        });
        progress('[OK] Cyber-AutoAgent package verified and ready');
      } catch (error) {
        // Last resort - try development install
        progress('[INFO] Installing Cyber-AutoAgent in development mode...');
        await execAsync(`"${this.pipPath}" install -e .`, {
          cwd: this.projectRoot
        });
        progress('[OK] Cyber-AutoAgent installed in development mode');
      }
      
      progress('[OK] Python environment setup complete!');
      
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      progress(`[ERR] Setup failed: ${errorMsg}`);
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
    this.startTime = Date.now();
    // Reset stop flag at the beginning of a new execution
    this.userStopRequested = false;
    
    return new Promise<void>((resolve, reject) => {
      try {
      // Preflight checks for clarity in OSS UX
      void this.preflightChecks();

      // Ensure environment is set up
      const venvExists = fs.existsSync(this.pythonPath);
      if (!venvExists) {
        throw new Error('Python environment not set up. Please run setup first.');
      }
      
      // Build command arguments
      const objective = params.objective || `Perform ${params.module.replace('_', ' ')} assessment`;
      
      const args = [
        path.join(this.srcPath, 'cyberautoagent.py'),
        '--module', params.module,
        '--objective', 'via environment',  // Placeholder, actual value comes from env
        '--target', params.target,
        '--iterations', String(config.iterations || 100),
        '--provider', config.modelProvider || 'bedrock',
      ];
      
      if (config.modelId) {
        args.push('--model', config.modelId);
      }
      // Always pass region via CLI when provided to avoid relying solely on env
      if (config.awsRegion) {
        args.push('--region', config.awsRegion);
      }
      
      // Set up environment variables
      const resolvedRegion =
        config.awsRegion ||
        process.env.AWS_REGION ||
        process.env.AWS_REGION_NAME ||
        'us-east-1';

      const env: Record<string, string> = {
        ...process.env,
        PYTHONPATH: this.srcPath,
        PYTHONUNBUFFERED: '1',
        FORCE_COLOR: '1',
        // Always pass objective via environment to avoid escaping issues
        CYBER_OBJECTIVE: objective,
        // React UI integration - critical for event emission
        BYPASS_TOOL_CONSENT: config.confirmations ? 'false' : 'true',
        CYBER_UI_MODE: 'react',
        CYBERAGENT_NO_BANNER: 'true', // Suppress CLI banner in React UI mode
        DEV: config.verbose ? 'true' : 'false',
        // Set AWS region
        AWS_REGION: resolvedRegion,
        AWS_DEFAULT_REGION: resolvedRegion,
        AWS_REGION_NAME: resolvedRegion,
        ...(config.awsProfile
          ? { AWS_PROFILE: config.awsProfile, AWS_DEFAULT_PROFILE: config.awsProfile }
          : {}),
        ...(config.awsRoleArn
          ? { AWS_ROLE_ARN: config.awsRoleArn, AWS_ROLE_NAME: config.awsRoleArn }
          : {}),
        ...(config.awsSessionName
          ? { AWS_ROLE_SESSION_NAME: config.awsSessionName }
          : {}),
        ...(config.awsWebIdentityTokenFile
          ? { AWS_WEB_IDENTITY_TOKEN_FILE: config.awsWebIdentityTokenFile }
          : {}),
        ...(config.awsStsEndpoint ? { AWS_STS_ENDPOINT: config.awsStsEndpoint } : {}),
        ...(config.awsExternalId ? { AWS_EXTERNAL_ID: config.awsExternalId } : {}),
        ...(config.sagemakerBaseUrl ? { SAGEMAKER_BASE_URL: config.sagemakerBaseUrl } : {}),
        // Ollama Configuration
        ...(config.ollamaHost ? { OLLAMA_HOST: config.ollamaHost } : {}),
        // LiteLLM Configuration (only set if provided)
        ...(config.openaiApiKey ? { OPENAI_API_KEY: config.openaiApiKey } : {}),
        ...(config.anthropicApiKey ? { ANTHROPIC_API_KEY: config.anthropicApiKey } : {}),
        ...(config.geminiApiKey ? { GEMINI_API_KEY: config.geminiApiKey } : {}),
        ...(config.xaiApiKey ? { XAI_API_KEY: config.xaiApiKey } : {}),
        ...(config.cohereApiKey ? { COHERE_API_KEY: config.cohereApiKey } : {}),
        ...(config.azureApiKey ? {
          AZURE_API_KEY: config.azureApiKey,
          AZURE_OPENAI_API_KEY: config.azureApiKey 
        } : {}),
        ...(config.azureApiBase ? {
          AZURE_API_BASE: config.azureApiBase,
          AZURE_OPENAI_ENDPOINT: config.azureApiBase 
        } : {}),
        ...(config.azureApiVersion ? {
          AZURE_API_VERSION: config.azureApiVersion,
          OPENAI_API_VERSION: config.azureApiVersion 
        } : {}),
        ...(config.embeddingModel ? { CYBER_AGENT_EMBEDDING_MODEL: config.embeddingModel } : {}),
        ...(config.maxTokens ? { MAX_TOKENS: String(config.maxTokens) } : {}),
        ...(config.temperature !== undefined ? { CYBER_AGENT_TEMPERATURE: String(config.temperature) } : {}),
        ...(config.topP !== undefined ? { CYBER_AGENT_TOP_P: String(config.topP) } : {}),
        ...(config.thinkingBudget ? { THINKING_BUDGET: String(config.thinkingBudget) } : {}),
        ...(config.reasoningEffort ? { REASONING_EFFORT: config.reasoningEffort } : {}),
        ...(config.reasoningVerbosity ? { REASONING_VERBOSITY: config.reasoningVerbosity } : {}),
        ...(config.maxCompletionTokens ? { MAX_COMPLETION_TOKENS: String(config.maxCompletionTokens) } : {}),
        // Model Configuration - pass separate models from config
        ...(config.swarmModel ? { CYBER_AGENT_SWARM_MODEL: config.swarmModel } : {}),
        ...(config.evaluationModel ? { CYBER_AGENT_EVALUATION_MODEL: config.evaluationModel } : {}),
        // Observability settings from config (matching Docker service behavior)
        ENABLE_OBSERVABILITY: config.observability ? 'true' : 'false',
        ENABLE_AUTO_EVALUATION: config.autoEvaluation ? 'true' : 'false',
        ENABLE_LANGFUSE_PROMPTS: config.enableLangfusePrompts ? 'true' : 'false',
        // Langfuse configuration when observability is enabled
        ...(config.observability && {
          LANGFUSE_HOST: config.langfuseHost || '',
          LANGFUSE_PUBLIC_KEY: config.langfusePublicKey || '',
          LANGFUSE_SECRET_KEY: config.langfuseSecretKey || '',
          LANGFUSE_PROMPT_LABEL: config.langfusePromptLabel || '',
          LANGFUSE_PROMPT_CACHE_TTL: String(config.langfusePromptCacheTTL || '')
        }),
        // Evaluation settings when auto-evaluation is enabled
        ...(config.autoEvaluation && {
          RAGAS_EVALUATOR_MODEL: config.evaluationModel || '',
          EVALUATION_BATCH_SIZE: String(config.evaluationBatchSize || ''),
          // LLM-driven evaluation tunables
          ...(config.minToolCalls !== undefined ? { EVAL_MIN_TOOL_CALLS: String(config.minToolCalls) } : {}),
          ...(config.minEvidence !== undefined ? { EVAL_MIN_EVIDENCE: String(config.minEvidence) } : {}),
          ...(config.evalMaxWaitSecs !== undefined ? { EVALUATION_MAX_WAIT_SECS: String(config.evalMaxWaitSecs) } : {}),
          ...(config.evalPollIntervalSecs !== undefined ? { EVALUATION_POLL_INTERVAL_SECS: String(config.evalPollIntervalSecs) } : {}),
        ...(config.evalSummaryMaxChars !== undefined ? { EVAL_SUMMARY_MAX_CHARS: String(config.evalSummaryMaxChars) } : {}),
      })
      };

      const userEnvironment = flattenEnvironment(config.environment as any);
      for (const [key, value] of Object.entries(userEnvironment)) {
        env[key] = value;
      }
      // Only set AWS credentials/bearer if provided in config; do not overwrite existing env with empty strings
      if (config.awsAccessKeyId) env.AWS_ACCESS_KEY_ID = config.awsAccessKeyId;
      if (config.awsSecretAccessKey) env.AWS_SECRET_ACCESS_KEY = config.awsSecretAccessKey;
      if (config.awsBearerToken) env.AWS_BEARER_TOKEN_BEDROCK = config.awsBearerToken;
      if (config.awsSessionToken) env.AWS_SESSION_TOKEN = config.awsSessionToken;
      
      this.logger.info('Starting Python assessment', { 
        args, 
        cwd: this.projectRoot,
        provider: config.modelProvider,
        model: config.modelId
      });

      // Python backend will emit thinking(startup, urgent=true) immediately after operation_init
      // No need to emit it here as it causes activeThinkingRef to be set prematurely
      
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

      // Emit objective/target and plugin details early in the run
      setTimeout(() => {
        const objective = params.objective || `Comprehensive ${params.module.replace('_', ' ')} security assessment`;
        this.emit('event', {
          type: 'output',
          content: `◆ Objective: ${objective}`,
          timestamp: Date.now()
        });
        this.emit('event', {
          type: 'output',
          content: `◆ Target: ${params.target}`,
          timestamp: Date.now()
        });
      }, 1200);

      // Provider is already emitted in preflight checks (✓ Provider: ... at ~900ms).
      // Avoid emitting here to prevent interleaving with tool discovery output.
      
      // Emit expanded initial logs
      const resolvedOutputDir = path.isAbsolute(config.outputDir || '')
        ? (config.outputDir as string)
        : path.resolve(this.projectRoot, config.outputDir || './outputs');
      setTimeout(() => {
        this.emit('event', { type: 'output', content: '▶ Preflight checks', timestamp: Date.now() });
        // Python path and version
        try {
          const ver: string = execFileSync(this.pythonPath, ['--version']).toString().trim();
          this.emit('event', { type: 'output', content: `✓ Python: ${this.pythonPath} (${ver})`, timestamp: Date.now() });
        } catch (e) {
          // Suppress unknown version line to avoid noisy preflight output
        }
        this.emit('event', { type: 'output', content: `✓ Project root: ${this.projectRoot}` , timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Output directory: ${resolvedOutputDir}` , timestamp: Date.now() });
        this.emit('event', { type: 'output', content: '✓ Execution mode: Local Python CLI', timestamp: Date.now() });
        // Target and provider/model
        this.emit('event', { type: 'output', content: `✓ Target: ${params.target}`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Provider: ${config.modelProvider || 'unknown'} (${config.modelId || 'default-model'})`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Region: ${env.AWS_REGION || 'unknown'}` , timestamp: Date.now() });
        // Memory presence
        const sanitizedTarget = params.target
          .replace(/^https?:\/\//, '')  // Remove protocol
          .replace(/^ftp:\/\//, '')     // Remove ftp protocol
          .replace(/\/.*$/, '')         // Remove path components
          .replace(/[^a-zA-Z0-9.-]/g, '_'); // Replace invalid chars
        const memoryPath = path.join(resolvedOutputDir, sanitizedTarget, 'memory');
        const faissPath = path.join(memoryPath, 'mem0.faiss');
        if (fs.existsSync(faissPath)) {
          this.emit('event', { type: 'output', content: `✓ Existing memory found: ${memoryPath}`, timestamp: Date.now() });
        } else {
          this.emit('event', { type: 'output', content: `○ No existing memory found for ${params.target}`, timestamp: Date.now() });
        }
      }, 900);
      
      setTimeout(() => {
        this.emit('event', {
          type: 'output',
          content: '◆ Loading Python-based cybersecurity tools...',
          timestamp: Date.now()
        });
      }, 1800);
      
      // If aborted before process start, resolve immediately as stopped
      if (this.abortController?.signal?.aborted) {
        this.logger.info('Abort received before Python process spawn; stopping execution');
        this.isExecutionActive = false;
        try { this.emit('stopped'); } catch {}
        resolve();
        return;
      }

      // Spawn Python process
      // detached: true creates new process group for proper tree cleanup

      // DEBUG: Log full spawn command for diagnostics
      this.logger.info('=== SPAWN DEBUG ===');
      this.logger.info(`Python path: ${this.pythonPath}`);
      this.logger.info(`Working dir: ${this.projectRoot}`);
      this.logger.info(`Args: ${JSON.stringify(args, null, 2)}`);
      this.logger.info(`Provider: ${env.CYBER_AGENT_PROVIDER || 'not set'}`);
      this.logger.info(`Model: ${env.CYBER_AGENT_LLM_MODEL || 'not set'}`);
      this.logger.info(`Objective env: ${env.CYBER_OBJECTIVE || 'not set'}`);
      this.logger.info(`Target arg: ${args.find((a, i) => args[i-1] === '--target') || 'not found'}`);
      this.logger.info(`Module arg: ${args.find((a, i) => args[i-1] === '--module') || 'not found'}`);
      this.logger.info('===================');

      this.activeProcess = spawn(this.pythonPath, args, {
        cwd: this.projectRoot,
        env,
        shell: false,
        detached: true  // Create new process group to enable tree kill
      });
      
      // Emit started event
      this.emit('started');
      
      // Handle stdout
      this.activeProcess.stdout?.on('data', (data: Buffer) => {
        const output = data.toString();
        this.processOutputStream(output);
      });
      
      // Handle stderr (buffer to aid diagnostics)
      this.activeProcess.stderr?.on('data', (data: Buffer) => {
        const output = data.toString();
        // Python may output regular messages to stderr
        this.processOutputStream(output);
        // Keep a bounded buffer (~8KB) of stderr for error reporting
        this.stderrBuffer += output;
        if (this.stderrBuffer.length > 8192) {
          this.stderrBuffer = this.stderrBuffer.slice(this.stderrBuffer.length - 8192);
        }
      });
      
      // Handle process exit
      this.activeProcess.on('exit', (code, signal) => {
        this.isExecutionActive = false;
        
        const intentionalStop = this.userStopRequested || signal === 'SIGTERM' || signal === 'SIGINT' || signal === 'SIGKILL';
        if (intentionalStop) {
          // Treat any exit following a user stop (or termination signals) as a clean stop
          this.emit('stopped');
          this.userStopRequested = false; // reset flag
          resolve();
        } else if (code === 0) {
          // Compute human-readable duration
          const end = Date.now();
          const ms = this.startTime ? (end - this.startTime) : 0;
          const seconds = Math.max(0, Math.round(ms / 1000));
          const durationStr = `${seconds}s`;
          
          // Ensure any active spinners terminate in UI
          this.emit('event', { type: 'thinking_end' });
          
          // Emit a final metrics_update so UI can update duration/counters
          this.emit('event', {
            type: 'metrics_update',
            metrics: { duration: durationStr },
            duration: durationStr
          });
          
          // Emit a terminal stream event indicating operation completion
          this.emit('event', {
            type: 'operation_complete',
            duration: durationStr,
            metrics: { duration: durationStr }
          });
          
          this.emit('complete');
          resolve(); // Process completed successfully
        } else {
          // Parse stderr for common errors and provide actionable guidance
          const stderrLines = this.stderrBuffer.split(/\r?\n/).filter(Boolean);
          const tail = stderrLines.slice(-12).join('\n');

          // Detect common error patterns
          let userFriendlyMsg = '';
          let solution = '';

          if (this.stderrBuffer.includes('ModuleNotFoundError') || this.stderrBuffer.includes('ImportError')) {
            const missingModule = this.stderrBuffer.match(/No module named ['"]([^'"]+)['"]/)?.[1];
            userFriendlyMsg = `Missing Python dependency${missingModule ? `: ${missingModule}` : ''}`;
            solution = 'Run: uv sync --all-extras  (or: pip install -r requirements.txt)';
          } else if (this.stderrBuffer.includes('SyntaxError')) {
            userFriendlyMsg = 'Python syntax error in source code';
            solution = 'Check the stderr output below for the file and line number';
          } else if (this.stderrBuffer.includes('PermissionError') || this.stderrBuffer.includes('EACCES')) {
            userFriendlyMsg = 'Permission denied accessing files or directories';
            solution = 'Check file permissions in the project directory';
          } else if (this.stderrBuffer.includes('FileNotFoundError')) {
            const missingFile = this.stderrBuffer.match(/FileNotFoundError.*['"]([^'"]+)['"]/)?.[1];
            userFriendlyMsg = `Required file not found${missingFile ? `: ${missingFile}` : ''}`;
            solution = 'Ensure all required configuration files exist';
          } else if (this.stderrBuffer.includes('CUDA') || this.stderrBuffer.includes('torch')) {
            userFriendlyMsg = 'PyTorch/CUDA configuration issue';
            solution = 'Check GPU drivers or use CPU-only mode';
          } else if (code === 1 && !this.stderrBuffer.trim()) {
            userFriendlyMsg = 'Python process crashed without error output';
            solution = 'Try running: python src/cyberautoagent.py --help  to diagnose';
          } else {
            userFriendlyMsg = `Python process exited with code ${code}`;
            solution = 'Check stderr output below for details';
          }

          // Emit user-friendly error event for UI display
          this.emit('event', {
            type: 'error',
            error: userFriendlyMsg,
            solution: solution,
            exitCode: code
          });

          // Construct detailed error for logs
          const context = `cwd=${this.projectRoot} pythonPath=${this.pythonPath}`;
          const extra = tail ? `\n--- stderr (last 12 lines) ---\n${tail}\n-------------------` : '';
          const errorMsg = `${userFriendlyMsg}\n\nSolution: ${solution}\n\n${context}${extra}`;
          const error = new Error(errorMsg);
          this.emit('error', error);
          reject(error); // Process failed
        }

        this.activeProcess = undefined;
        this.stderrBuffer = '';
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
    // Use non-global regex with exec() loop to ensure proper cursor management
    const eventRegex = /__CYBER_EVENT__(.+?)__CYBER_EVENT_END__/s;
    let match;
    let processedEvents = false;
    let lastProcessedIndex = 0;

    while ((match = eventRegex.exec(this.streamEventBuffer)) !== null) {
      processedEvents = true;

      // Emit any raw text preceding this structured event
      const preText = this.streamEventBuffer.slice(lastProcessedIndex, match.index);
        if (preText && this.inToolExecution) {
          // Buffer raw output; flush on tool end so it appears once per tool
          this.toolOutputBuffer += preText;
          // Clamp tool output buffer to prevent unbounded growth
          const MAX_TOOL_OUTPUT = 1 * 1024 * 1024; // 1 MiB cap
          if (this.toolOutputBuffer.length > MAX_TOOL_OUTPUT) {
            this.toolOutputBuffer = this.toolOutputBuffer.slice(-MAX_TOOL_OUTPUT);
          }
          // Chunked emission to keep latency low
          this.flushToolOutputChunks(false);
        }

      try {
        const eventData = JSON.parse(match[1]);

        // Track tool execution state for raw output buffering (not for structured events)
        if (eventData.type === 'tool_start' || eventData.type === 'tool_invocation_start') {
          this.inToolExecution = true;
          this.toolOutputBuffer = '';
          this.sawBackendToolOutput = false; // reset per tool
          // Remember the current tool name for proper attribution on flush
          try { (this as any)._currentToolName = eventData.tool_name || eventData.toolName || eventData.tool || undefined; } catch {}
        } else if (
          eventData.type === 'tool_invocation_end' ||
          eventData.type === 'tool_result' ||
          eventData.type === 'step_header' ||
          eventData.type === 'tool_end'
        ) {
          // Flush any remaining raw output when tool ends, but only if backend
          // did NOT send a consolidated tool output event. This avoids duplicates.
          if (!this.sawBackendToolOutput) {
            // Flush remaining buffered output in chunks
            this.flushToolOutputChunks(true);
          }
          this.toolOutputBuffer = '';
          this.inToolExecution = false;
          this.sawBackendToolOutput = false;
          try { (this as any)._currentToolName = undefined; } catch {}
        }

        // Emit tool output immediately - backend already handles proper metadata and deduplication
        if (eventData.type === 'output') {
          // Track if this is backend-consolidated tool output
          if (eventData.metadata && eventData.metadata.fromToolBuffer) {
            this.sawBackendToolOutput = true;
          }
          // Always emit output events immediately for real-time display
          this.emit('event', eventData);
          lastProcessedIndex = match.index + match[0].length;
          this.streamEventBuffer = this.streamEventBuffer.slice(lastProcessedIndex);
          lastProcessedIndex = 0;
          continue;
        }

        // Emit system status event exactly like Docker mode
        if (eventData.type === 'tools_loaded') {
          this.emit('event', {
            type: 'output',
            content: eventData.content,
            timestamp: Date.now()
          });
        } else if (eventData.type === 'tool_discovery_start') {
          this.emit('event', {
            type: 'output',
            content: '◆ Loading cybersecurity assessment tools:',
            timestamp: Date.now()
          });
        } else if (eventData.type === 'tool_available') {
          this.emit('event', {
            type: 'output',
            content: `  ✓ ${eventData.tool_name} (${eventData.description})`,
            timestamp: Date.now()
          });
        } else if (eventData.type === 'tool_unavailable') {
          this.emit('event', {
            type: 'output',
            content: `  ○ ${eventData.tool_name} (${eventData.description}) - unavailable`,
            timestamp: Date.now()
          });
        } else if (eventData.type === 'environment_ready') {
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
          }, 1000);
        }
        // Forward all other events (step headers, tool calls, reasoning, etc.)
        else {
          this.emit('event', eventData);
        }

        // Update last processed index
        lastProcessedIndex = match.index + match[0].length;
        
        // Move past this match for next iteration
        this.streamEventBuffer = this.streamEventBuffer.slice(lastProcessedIndex);
        lastProcessedIndex = 0;

      } catch (error) {
        this.logger.warn('Failed to parse event', {
          data: match[1].substring(0, 100) + '...',
          error: error instanceof Error ? error.message : 'Unknown error'
        });
        // Move past this match to avoid infinite loop
        const skipLength = match.index + match[0].length;
        this.streamEventBuffer = this.streamEventBuffer.slice(skipLength);
        lastProcessedIndex = 0;
      }
    }

    if (!processedEvents) {
      // No structured events found in this chunk; emit raw output immediately
      if (data) {
        if (this.inToolExecution) {
          this.toolOutputBuffer += data;
          // Clamp tool output buffer to prevent unbounded growth
          const MAX_TOOL_OUTPUT = 1 * 1024 * 1024; // 1 MiB cap
          if (this.toolOutputBuffer.length > MAX_TOOL_OUTPUT) {
            this.toolOutputBuffer = this.toolOutputBuffer.slice(-MAX_TOOL_OUTPUT);
          }
          // Chunk out as we accumulate
          this.flushToolOutputChunks(false);
        }
        // Clear buffer regardless to avoid growth
        this.streamEventBuffer = '';
      }
    }

    // Always clamp stream buffer tail to avoid unbounded growth between chunks
    const MAX_STREAM_BUFFER = 32 * 1024;
    if (this.streamEventBuffer.length > MAX_STREAM_BUFFER) {
      this.streamEventBuffer = this.streamEventBuffer.slice(-16 * 1024);
    }
  }
  
  /**
   * Get metrics for this execution session
   */
  getMetrics(): { 
    sessionId: string;
    startTime?: number;
    isActive: boolean;
  } {
    return {
      sessionId: this.sessionId,
      startTime: this.startTime,
      isActive: this.isExecutionActive
    };
  }
}
