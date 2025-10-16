/**
 * Direct Docker Execution Service
 * 
 * Provides high-performance Docker container execution for Cyber-AutoAgent assessments.
 * Features real-time event streaming with structured JSON event parsing from container stdout.
 * Eliminates WebSocket overhead by parsing events directly from Docker's stdout stream.
 * 
 * Key Features:
 * - Real-time streaming of assessment progress and tool outputs
 * - Structured event parsing with automatic grouping and buffering
 * - Error handling and container lifecycle management
 * - Full AWS credential and environment variable support
 * 
 * Event Flow: Docker Container → stdout → Event Parser → React Components
 * 
 * @author Cyber-AutoAgent Team
 * @since v0.1.3
 */

import { EventEmitter } from 'events';
import Dockerode from 'dockerode';
import { Transform } from 'stream';
import fs from 'fs';
import path from 'path';
import { AssessmentParams } from '../types/Assessment.js';
import { Config } from '../contexts/ConfigContext.js';
import { StreamEvent, EventType } from '../types/events.js';
import { ContainerManager, DeploymentMode } from './ContainerManager.js';
import { createLogger } from '../utils/logger.js';
import { flattenEnvironment } from '../utils/env.js';

/**
 * Sanitize target name for filesystem use (matches Python agent logic)
 * Removes/replaces characters that could cause filesystem issues
 */
function sanitizeTargetName(target: string): string {
  return target
    .replace(/https?:\/\//g, '')  // Remove protocol
    .replace(/[\/\\:*?"<>|]/g, '_')  // Replace invalid chars
    .replace(/\s+/g, '_')  // Replace spaces
    .replace(/_+/g, '_')  // Collapse multiple underscores
    .replace(/^_|_$/g, '');  // Trim underscores
}

/**
 * DirectDockerService - Docker container execution service
 * 
 * Manages the complete lifecycle of Cyber-AutoAgent Docker containers with
 * error handling, event streaming, and AWS integration.
 * 
 * @extends EventEmitter
 * @emits 'event' - Parsed structured events from container stdout
 * @emits 'started' - Container execution has begun
 * @emits 'complete' - Assessment has completed successfully
 * @emits 'stopped' - Container was stopped or cancelled
 * @emits 'error' - Execution error occurred
 */
const logger = createLogger('DirectDockerService');
export class DirectDockerService extends EventEmitter {
  private autoExecuteSent: boolean = false;
  private readonly dockerClient: Dockerode;
  private activeContainer?: Dockerode.Container;
  private containerStream?: any;
  private isExecutionActive = false;
  private streamEventBuffer = '';
  private abortController?: AbortController;
  private activeExec?: Dockerode.Exec;
  // Track when backend signals operation completion to avoid premature "complete"
  private seenOperationComplete = false;
  // Auto-confirm interactive handoffs when configured (maps to BYPASS_TOOL_CONSENT)
  private autoConfirm = true;
  // Raw tool stdout buffering (guarded) for cases where backend doesn't emit consolidated tool_output events
  private inToolExecution = false;
  private toolOutputBuffer = '';
  private sawBackendToolOutput = false;
  private _currentToolName: string | undefined = undefined;

  /** Emit a chunk of buffered tool output */
  private emitToolOutputChunk(content: string): void {
    try {
      this.emit('event', {
        type: 'output',
        content,
        timestamp: Date.now(),
        metadata: { fromToolBuffer: true, tool: this._currentToolName, chunked: true }
      } as any);
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

  /**
   * Initialize the Docker service with connection to Docker daemon
   */
  constructor() {
    super();
    this.dockerClient = new Dockerode();
  }

  /**
   * Execute assessment directly via Docker
   */
  async executeAssessment(
    params: AssessmentParams,
    config: Config
  ): Promise<void> {
    // Reset per-run state to ensure clean behavior when reusing the service in the same app session
    this.resetSessionState();
    this.abortController = new AbortController();
    if (this.isExecutionActive) {
      throw new Error('Assessment already running');
    }

    this.isExecutionActive = true;
    this.abortController = new AbortController();

    try {
      // Validate params before proceeding
      if (!params || !params.module || !params.target) {
        const error = new Error(`Invalid assessment parameters: ${JSON.stringify(params)}`);
        throw error;
      }
      
      // Build command arguments
      // Pass module explicitly to enable module-specific prompts and tools
      const objective = params.objective || `Perform ${params.module.replace('_', ' ')} assessment`;
      
      // Initialize environment variables - always pass objective via env to avoid escaping issues
      let env: string[] = [`CYBER_OBJECTIVE=${objective}`];
      const resolvedRegion =
        config.awsRegion ||
        process.env.AWS_REGION ||
        process.env.AWS_REGION_NAME ||
        process.env.AWS_DEFAULT_REGION ||
        'us-east-1';
      
      // Decide auto-confirm behavior from config (default true when confirmations are disabled)
      this.autoConfirm = !(config.confirmations === true);
      
      const args = [
        // Note: --service-mode will be added later ONLY for new containers, not for docker exec
        '--module', params.module,
        '--objective', 'via environment',  // Placeholder, actual value comes from env
        '--target', params.target,
        '--iterations', String(config.iterations || 100),
        '--provider', config.modelProvider || 'bedrock',
      ];

      if (config.modelId) {
        args.push('--model', config.modelId);
      }

      if (config.awsRegion) {
        args.push('--region', config.awsRegion);
      }

      // Output directory and memory persistence
      args.push('--output-dir', '/app/outputs');
      args.push('--keep-memory');  // Always keep memory for continuity
      
      // Check for existing memory and use it if found
      const sanitizedTarget = sanitizeTargetName(params.target);
      const outputPath = path.resolve(config.outputDir || './outputs');
      const targetMemoryPath = path.join(outputPath, sanitizedTarget, 'memory');
      
      // Ensure output directory exists
      if (!fs.existsSync(outputPath)) {
        fs.mkdirSync(outputPath, { recursive: true });
      }
      
      // Check if memory exists for this target
      const faissPath = path.join(targetMemoryPath, 'mem0.faiss');
      const pklPath = path.join(targetMemoryPath, 'mem0.pkl');
      
      // Check for existing memory files
      
      if (fs.existsSync(faissPath) && fs.existsSync(pklPath)) {
        // Count memory entries for better context
        const faissSize = fs.statSync(faissPath).size;
        const memoryContext = faissSize > 1000 ? 'knowledge base' : 'previous findings';
        
        this.emit('event', {
          type: 'output',
          content: `▶ MEMORY: Loading existing ${memoryContext} for ${params.target}`,
          timestamp: Date.now()
        });
        this.emit('event', {
          type: 'output',
          content: `◆ Memory path: ${targetMemoryPath}`,
          timestamp: Date.now()
        });
      }

      // Add standard environment variables
      env.push(
        'PYTHONUNBUFFERED=1', // Disable Python output buffering for real-time streaming
        `BYPASS_TOOL_CONSENT=${config.confirmations ? 'false' : 'true'}`,
        'CYBER_UI_MODE=react',
        'CYBERAGENT_NO_BANNER=true',
        `DEV=${config.verbose ? 'true' : 'false'}`,
      );

      // AWS credentials
      if (config.awsAccessKeyId && config.awsSecretAccessKey) {
        env.push(`AWS_ACCESS_KEY_ID=${config.awsAccessKeyId}`);
        env.push(`AWS_SECRET_ACCESS_KEY=${config.awsSecretAccessKey}`);
      }

      if (config.awsSessionToken) {
        env.push(`AWS_SESSION_TOKEN=${config.awsSessionToken}`);
      }

      if (config.awsBearerToken) {
        env.push(`AWS_BEARER_TOKEN_BEDROCK=${config.awsBearerToken}`);
      }

      if (resolvedRegion) {
        env.push(`AWS_DEFAULT_REGION=${resolvedRegion}`);
        env.push(`AWS_REGION=${resolvedRegion}`);
        env.push(`AWS_REGION_NAME=${resolvedRegion}`);
      }

      if (config.awsProfile) {
        env.push(`AWS_PROFILE=${config.awsProfile}`);
        env.push(`AWS_DEFAULT_PROFILE=${config.awsProfile}`);
      }

      if (config.awsRoleArn) {
        env.push(`AWS_ROLE_ARN=${config.awsRoleArn}`);
        env.push(`AWS_ROLE_NAME=${config.awsRoleArn}`);
      }

      if (config.awsSessionName) {
        env.push(`AWS_ROLE_SESSION_NAME=${config.awsSessionName}`);
      }

      if (config.awsWebIdentityTokenFile) {
        env.push(`AWS_WEB_IDENTITY_TOKEN_FILE=${config.awsWebIdentityTokenFile}`);
      }

      if (config.awsStsEndpoint) {
        env.push(`AWS_STS_ENDPOINT=${config.awsStsEndpoint}`);
      }

      if (config.awsExternalId) {
        env.push(`AWS_EXTERNAL_ID=${config.awsExternalId}`);
      }

      if (config.sagemakerBaseUrl) {
        env.push(`SAGEMAKER_BASE_URL=${config.sagemakerBaseUrl}`);
      }

      // Ollama configuration
      if (config.ollamaHost) {
        env.push(`OLLAMA_HOST=${config.ollamaHost}`);
      }

      // LiteLLM configuration
      if (config.openaiApiKey) {
        env.push(`OPENAI_API_KEY=${config.openaiApiKey}`);
      }
      if (config.anthropicApiKey) {
        env.push(`ANTHROPIC_API_KEY=${config.anthropicApiKey}`);
      }
      if (config.geminiApiKey) {
        env.push(`GEMINI_API_KEY=${config.geminiApiKey}`);
      }
      if (config.xaiApiKey) {
        env.push(`XAI_API_KEY=${config.xaiApiKey}`);
      }
      if (config.cohereApiKey) {
        env.push(`COHERE_API_KEY=${config.cohereApiKey}`);
      }
      if (config.azureApiKey) {
        env.push(`AZURE_API_KEY=${config.azureApiKey}`);
        env.push(`AZURE_OPENAI_API_KEY=${config.azureApiKey}`); 
      }
      if (config.azureApiBase) {
        env.push(`AZURE_API_BASE=${config.azureApiBase}`);
        env.push(`AZURE_OPENAI_ENDPOINT=${config.azureApiBase}`); 
      }
      if (config.azureApiVersion) {
        env.push(`AZURE_API_VERSION=${config.azureApiVersion}`);
        env.push(`OPENAI_API_VERSION=${config.azureApiVersion}`); 
      }
      if (config.embeddingModel) {
        env.push(`CYBER_AGENT_EMBEDDING_MODEL=${config.embeddingModel}`);
      }
      if (config.maxTokens) {
        env.push(`MAX_TOKENS=${config.maxTokens}`);
        env.push(`CYBER_AGENT_MAX_TOKENS=${config.maxTokens}`);
      }
      if (config.temperature !== undefined) {
        env.push(`CYBER_AGENT_TEMPERATURE=${config.temperature}`);
      }
      if (config.topP !== undefined) {
        env.push(`CYBER_AGENT_TOP_P=${config.topP}`);
      }
      if (config.thinkingBudget) {
        env.push(`THINKING_BUDGET=${config.thinkingBudget}`);
      }
      if (config.reasoningEffort) {
        env.push(`REASONING_EFFORT=${config.reasoningEffort}`);
      }
      if (config.maxCompletionTokens) {
        env.push(`MAX_COMPLETION_TOKENS=${config.maxCompletionTokens}`);
      }

      // Model Configuration - pass separate models from config
      if (config.swarmModel) {
        env.push(`CYBER_AGENT_SWARM_MODEL=${config.swarmModel}`);
      }
      if (config.evaluationModel) {
        env.push(`CYBER_AGENT_EVALUATION_MODEL=${config.evaluationModel}`);
      }

      // Debug logging: what we're about to send to Docker
      const maskEnv = (vars: string[]) => {
        const SENSITIVE = new Set([
          'AWS_SECRET_ACCESS_KEY', 'AWS_BEARER_TOKEN_BEDROCK', 'AWS_SESSION_TOKEN', 'AWS_EXTERNAL_ID',
          'OPENAI_API_KEY',
          'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'XAI_API_KEY', 'COHERE_API_KEY',
          'AZURE_API_KEY', 'LANGFUSE_SECRET_KEY'
        ]);
        const out: Record<string, string> = {};
        for (const e of vars) {
          const idx = e.indexOf('=');
          if (idx > 0) {
            const k = e.slice(0, idx);
            const v = e.slice(idx + 1);
            out[k] = SENSITIVE.has(k) ? '***' : v;
          }
        }
        return out;
      };
      logger.info('Docker exec plan', {
        args,
        env: maskEnv(env),
        target: params.target,
        module: params.module,
        mode: await ContainerManager.getInstance().getCurrentMode()
      });

      // Get deployment mode for configuration and messaging decisions
      const deploymentManager = ContainerManager.getInstance();
      const currentDeploymentMode = await deploymentManager.getCurrentMode();
      
      // Observability settings from config - respects user configuration in all deployment modes
      env.push(`ENABLE_OBSERVABILITY=${config.observability ? 'true' : 'false'}`);
      
      if (config.observability) {
        // Inform user about observability based on deployment mode
        if (currentDeploymentMode === 'single-container') {
          this.emit('event', {
            type: 'output',
            content: '[Observability] Enabled for single-container mode (external Langfuse required)',
            timestamp: Date.now()
          });
        } else if (currentDeploymentMode === 'full-stack') {
          this.emit('event', {
            type: 'output',
            content: '[Observability] Enabled with full observability stack',
            timestamp: Date.now()
          });
        }
        
        // Smart Langfuse host configuration:
        // 1. If langfuseHostOverride is true, always use the configured host
        // 2. If host is not localhost/default, use it (custom deployment)
        // 3. Otherwise, let container auto-detect (Docker vs localhost)
        if (config.langfuseHostOverride || 
            (config.langfuseHost && 
             config.langfuseHost !== 'http://localhost:3000' && 
             !config.langfuseHost.includes('localhost:3000'))) {
          env.push(`LANGFUSE_HOST=${config.langfuseHost}`);
          this.emit('event', {
            type: 'output',
            content: `[Observability] Using configured Langfuse host: ${config.langfuseHost}`,
            timestamp: Date.now()
          });
        } else {
          this.emit('event', {
            type: 'output',
            content: '[Observability] Using container auto-detection for Langfuse host',
            timestamp: Date.now()
          });
        }
        
        env.push(`LANGFUSE_PUBLIC_KEY=${config.langfusePublicKey || 'cyber-public'}`);
        env.push(`LANGFUSE_SECRET_KEY=${config.langfuseSecretKey || 'cyber-secret'}`);
        
        if (config.enableLangfusePrompts) {
          env.push(`ENABLE_LANGFUSE_PROMPTS=true`);
          env.push(`LANGFUSE_PROMPT_LABEL=${config.langfusePromptLabel || 'production'}`);
          env.push(`LANGFUSE_PROMPT_CACHE_TTL=${config.langfusePromptCacheTTL || 300}`);
        }
      } else {
        // User disabled observability - respect their choice
        this.emit('event', {
          type: 'output',
          content: `[Observability] Disabled by user configuration in ${currentDeploymentMode} mode`,
          timestamp: Date.now()
        });
      }

      // Evaluation settings from config
      env.push(`ENABLE_AUTO_EVALUATION=${config.autoEvaluation ? 'true' : 'false'}`);
      if (config.autoEvaluation) {
        if (config.evaluationModel) {
          env.push(`RAGAS_EVALUATOR_MODEL=${config.evaluationModel}`);
        }
        env.push(`EVALUATION_BATCH_SIZE=${config.evaluationBatchSize || 5}`);
        // LLM-driven evaluation tunables (ensure container sees the same values as local Python)
        if (config.minToolCalls !== undefined) env.push(`EVAL_MIN_TOOL_CALLS=${config.minToolCalls}`);
        if (config.minEvidence !== undefined) env.push(`EVAL_MIN_EVIDENCE=${config.minEvidence}`);
        if (config.evalMaxWaitSecs !== undefined) env.push(`EVALUATION_MAX_WAIT_SECS=${config.evalMaxWaitSecs}`);
        if (config.evalPollIntervalSecs !== undefined) env.push(`EVALUATION_POLL_INTERVAL_SECS=${config.evalPollIntervalSecs}`);
        if (config.evalSummaryMaxChars !== undefined) env.push(`EVAL_SUMMARY_MAX_CHARS=${config.evalSummaryMaxChars}`);
      }

      // Merge user-provided environment overrides (flattened)
      const envMap = new Map<string, string>();
      for (const entry of env) {
        const idx = entry.indexOf('=');
        if (idx > 0) {
          const key = entry.slice(0, idx).toUpperCase();
          const value = entry.slice(idx + 1);
          envMap.set(key, value);
        }
      }
      const userEnvironment = flattenEnvironment(config.environment as any);
      for (const [key, value] of Object.entries(userEnvironment)) {
        if (value !== undefined) {
          envMap.set(key.toUpperCase(), value);
        }
      }
      env = Array.from(envMap.entries()).map(([key, value]) => `${key}=${value}`);

      // Prefer re-using the long-lived service container when available.
      // CYBER_DOCKER_REUSE defaults to true; set to `false` to force ad-hoc containers.
      const reuseEnv = process.env.CYBER_DOCKER_REUSE;
      const ENABLE_SERVICE_CONTAINER_REUSE = reuseEnv !== 'false'
        && (currentDeploymentMode === 'single-container' || currentDeploymentMode === 'full-stack');
      
      if (ENABLE_SERVICE_CONTAINER_REUSE) {
        const serviceContainer = await this.findServiceContainer();

        if (serviceContainer) {
          this.emit('event', {
            type: 'output',
            content: '◆ Reusing existing service container (docker exec)',
            timestamp: Date.now()
          });
          logger.info('Exec into existing service container', { name: 'cyber-autoagent' });

          await this.execIntoContainer(serviceContainer, args, env, currentDeploymentMode);
          return;
        }
      }

      // Create a new ad-hoc container for the assessment
      const dockerImage = process.env.CYBER_DOCKER_IMAGE || 'cyber-autoagent:latest';
      let dockerNetwork = process.env.CYBER_DOCKER_NETWORK || 'bridge';

      // If running in full-stack mode, attempt to infer compose network from a stack container
      if (!process.env.CYBER_DOCKER_NETWORK && currentDeploymentMode === 'full-stack') {
        const inferred = await this.inferComposeNetworkFrom('cyber-langfuse');
        if (inferred) {
          dockerNetwork = inferred;
          this.emit('event', {
            type: 'output',
            content: `◆ Using compose network for ad-hoc container: ${dockerNetwork}`,
            timestamp: Date.now()
          });
        }
      }

      // Resolve optional tools bind robustly
      const binds: string[] = [];
      binds.push(`${outputPath}:/app/outputs`);

      try {
        const candidateRoots: string[] = [];
        if (process.env.CYBER_PROJECT_ROOT) {
          candidateRoots.push(process.env.CYBER_PROJECT_ROOT);
        }
        // As a fallback, try cwd only if a tools dir actually exists
        candidateRoots.push(process.cwd());

        for (const root of candidateRoots) {
          const toolsDir = path.join(root, 'tools');
          if (fs.existsSync(toolsDir) && fs.statSync(toolsDir).isDirectory()) {
            binds.push(`${toolsDir}:/app/tools`);
            break;
          }
        }
      } catch {
        // If any error occurs during tools resolution, skip binding tools to avoid failure
      }


      logger.info('Creating ad-hoc container', { image: dockerImage, network: dockerNetwork, binds, args, env: maskEnv(env) });
      this.activeContainer = await this.dockerClient.createContainer({
        Image: dockerImage,
        // Override the entrypoint to run the Python agent directly so we emit structured events
        Entrypoint: ['python', '/app/src/cyberautoagent.py'],
        Cmd: args,
        Env: env,
        AttachStdout: true,
        AttachStderr: true,
        AttachStdin: true,
        Tty: true,  // Enable TTY for interactive tools
        OpenStdin: true,
        StdinOnce: false,
        User: 'root',
        HostConfig: {
          AutoRemove: true,
          NetworkMode: dockerNetwork,
          Binds: binds,
          CapAdd: ['NET_RAW','NET_ADMIN','SYS_PTRACE']
        },
        WorkingDir: '/app',
      });

      // Emit preflight details before attaching streams
      setTimeout(() => {
        this.emit('event', { type: 'output', content: '▶ Preflight checks', timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Execution mode: Docker (${currentDeploymentMode})`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Docker image: ${dockerImage}`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Output directory mount: ${outputPath} -> /app/outputs`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Network: ${dockerNetwork}`, timestamp: Date.now() });
        this.emit('event', { type: 'output', content: `✓ Provider: ${config.modelProvider || 'unknown'} (${config.modelId || 'default-model'})`, timestamp: Date.now() });
      }, 900);

      // Attach to container streams
      const stream = await this.activeContainer.attach({
        stream: true,
        stdin: true,
        stdout: true,
        stderr: true,
      });
      
      // Store stream for sending user input
      this.containerStream = stream;

      // Create event parser
      const eventParser = new Transform({
        transform: (chunk, encoding, callback) => {
          this.parseEvents(chunk.toString());
          callback();
        },
      });

      // Handle stream - With Tty:true, stream is NOT multiplexed
      // We get a single stream, not separate stdout/stderr
      // So we pipe directly to the parser instead of using demuxStream
      stream.pipe(eventParser);
      
      // Consume the stream to trigger transform function
      eventParser.on('data', () => {});
      
      eventParser.on('error', (error) => {
        // Emit parser errors as events instead of console.error
        this.emit('event', {
          type: 'output',
          content: `Event parser error: ${error}`,
          timestamp: Date.now()
        });
      });
      
      stream.on('error', (error) => {
        // Emit stream errors as events instead of console.error
        this.emit('event', {
          type: 'output',
          content: `Stream error: ${error}`,
          timestamp: Date.now()
        });
      });
      
      stream.on('end', () => {
        this.isExecutionActive = false;
        this.abortController = undefined;
        // Clear stream buffer to prevent stale prompt detection
        this.streamEventBuffer = '';
        // Only emit "complete" when backend signaled operation_complete
        if (this.seenOperationComplete) this.emit('complete');
        else this.emit('stopped');
      });
      
      // Handle abort signal
      this.abortController.signal.addEventListener('abort', () => {
        this.stop();
      });

      // Use the same deployment mode already retrieved earlier
      const deploymentMode = currentDeploymentMode;
      
      // Emit startup thinking indicator BEFORE any output so the UI shows animation immediately
      this.emit('event', {
        type: 'thinking',
        context: 'startup',
        startTime: Date.now(),
        metadata: {
          message: deploymentMode === 'local-cli'
            ? 'Preparing Python security assessment environment'
            : 'Preparing security assessment environment'
        }
      });

      // Start container with progressive status updates based on deployment mode
      if (deploymentMode === 'local-cli') {
        this.emit('event', {
          type: 'output',
          content: '▶ Initializing Python assessment environment...',
          timestamp: Date.now()
        });
      } else {
        this.emit('event', {
          type: 'output',
          content: '▶ Initializing security assessment container...',
          timestamp: Date.now()
        });
      }
      
      await this.activeContainer.start();
      
      // Initial startup messages based on deployment mode
      setTimeout(() => {
        if (deploymentMode === 'local-cli') {
          this.emit('event', {
            type: 'output',
            content: '◆ Python environment ready',
            timestamp: Date.now()
          });
        } else {
          this.emit('event', {
            type: 'output',
            content: '◆ Container started successfully',
            timestamp: Date.now()
          });
        }
      }, 500);

      setTimeout(() => {
        if (deploymentMode === 'local-cli') {
          this.emit('event', {
            type: 'output', 
            content: '◆ Setting up direct Python security assessment environment',
            timestamp: Date.now()
          });
        } else if (deploymentMode === 'single-container') {
          this.emit('event', {
            type: 'output', 
            content: '◆ Setting up minimal containerized security environment',
            timestamp: Date.now()
          });
        } else {
          this.emit('event', {
            type: 'output', 
            content: '◆ Setting up isolated security sandbox environment',
            timestamp: Date.now()
          });
        }
      }, 1000);


      // Provider is already emitted in preflight checks (✓ Provider: ... at ~900ms).
      // Avoid emitting here to prevent interleaving with tool discovery output.

      setTimeout(() => {
        if (deploymentMode === 'local-cli') {
          this.emit('event', {
            type: 'output',
            content: '◆ Loading Python-based cybersecurity tools...',
            timestamp: Date.now()
          });
        } else {
          this.emit('event', {
            type: 'output',
            content: '◆ Discovering cybersecurity assessment tools...',
            timestamp: Date.now()
          });
        }
      }, 1800);

      // (startup thinking emitted earlier to avoid gaps)
      
      this.emit('started');

      // Wait for container to finish
      this.activeContainer.wait((err, data) => {
        if (err) {
          // Emit container errors as events instead of console.error
          this.emit('event', {
            type: 'output',
            content: `Container wait error: ${err}`,
            timestamp: Date.now()
          });
        } else if (data && data.StatusCode !== 0) {
          // Emit container exit errors as events instead of console.error
          this.emit('event', {
            type: 'output',
            content: `Container exited with error code: ${data.StatusCode}`,
            timestamp: Date.now()
          });
        } else {
          // Container completed successfully - ensure cleanup
          this.isExecutionActive = false;
          this.streamEventBuffer = '';
        }
      });
    } catch (error) {
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.streamEventBuffer = '';
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Parse structured events from stdout and capture tool discovery
   */
  private parseEvents(data: string) {
    // Tool discovery is now handled via structured events in parseEvents
    
    // Filter out binary/control characters but preserve ANSI escape codes
    // ANSI codes use ESC (0x1B) followed by [ so we need to preserve those
    // Only remove: NUL, SOH-BS, VT, FF, SO-SUB (except ESC), FS-US, DEL, and other control chars
    const cleanedData = data.replace(/[\x00-\x08\x0B\x0C\x0E-\x1A\x1C-\x1F\x7F-\x9F\uFFFD]/g, '');
    
    this.streamEventBuffer += cleanedData;

    const eventRegex = /__CYBER_EVENT__(.+?)__CYBER_EVENT_END__/s;
    let match;
    let processedEvents = false;

    while ((match = eventRegex.exec(this.streamEventBuffer))) {
      processedEvents = true;
      const start = match.index as number;
      const end = start + match[0].length;
      // Capture any raw text preceding this structured event and buffer it if a tool is running
      const preText = this.streamEventBuffer.slice(0, start);
      if (preText && this.inToolExecution) {
        this.toolOutputBuffer += preText;
        // Clamp tool output buffer to prevent unbounded growth
        const MAX_TOOL_OUTPUT = 1 * 1024 * 1024; // 1 MiB cap
        if (this.toolOutputBuffer.length > MAX_TOOL_OUTPUT) {
          this.toolOutputBuffer = this.toolOutputBuffer.slice(-MAX_TOOL_OUTPUT);
        }
        // Chunk out as we accumulate
        this.flushToolOutputChunks(false);
      }
      try {
        const eventData = JSON.parse(match[1]);

        // For legacy events, pass through all properties
        const event: any = {
          type: eventData.type as EventType,
          content: eventData.content,
          data: eventData.data || {},
          metadata: eventData.metadata || {},
          timestamp: eventData.timestamp || Date.now(),
          id: eventData.id || `evt-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          sessionId: eventData.sessionId || '',
          // Include all original properties for legacy events
          ...eventData
        };

        // Track tool execution state for raw output buffering
        if (eventData.type === 'tool_start' || eventData.type === 'tool_invocation_start') {
          this.inToolExecution = true;
          this.toolOutputBuffer = '';
          this.sawBackendToolOutput = false;
          try { this._currentToolName = eventData.tool_name || eventData.toolName || eventData.tool || undefined; } catch {}
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
          try { this._currentToolName = undefined; } catch {}
        }

        // Handle tool discovery events with improved formatting
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
            content: `  ○ ${eventData.tool_name} (${eventData.description}) - unavailable`,
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
          }, 300);
          
          setTimeout(() => {
            this.emit('event', {
              type: 'output',
              content: '◆ Security assessment environment ready - Beginning evaluation',
              timestamp: Date.now()
            });
            // Add improved spacing and start thinking animation
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
        } else if (event.type === 'output') {
          // Track if this is backend-consolidated tool output
          if (event.metadata && (event.metadata as any).fromToolBuffer) {
            this.sawBackendToolOutput = true;
          }
        } else if (event.type === 'operation_complete') {
              // Backend signaled completion; mark and emit complete once
          this.seenOperationComplete = true;
          this.emit('complete');
        } else if (event.type === 'assessment_complete') {
              // React backend emits assessment_complete after final report generation
          this.seenOperationComplete = true;
          this.emit('complete');
        } else if (event.type === 'user_handoff') {
          // Structured user handoff from backend: if autoConfirm is enabled, press Enter automatically
          if (this.autoConfirm) {
            logger.info('Auto-confirming user_handoff');
            setTimeout(() => {
              if (this.containerStream && this.isExecutionActive) {
                try {
                  this.containerStream.write('\r\n');
                  logger.info('stdin write (auto-confirm)', { data: '\r\\n' });
                  setTimeout(() => {
                    try { if (this.containerStream && this.isExecutionActive) this.containerStream.write('\r\n'); } catch {}
                  }, 200);
                  setTimeout(() => {
                    try { if (this.containerStream && this.isExecutionActive) this.containerStream.write('execute\r\n'); } catch {}
                  }, 1200);
                } catch (err) {
                  logger.error('stdin write (auto-confirm) error', err as any);
                }
              }
            }, 200);
          }
        }
        
        this.emit('event', event);

        // Immediately slice buffer after processing event
        this.streamEventBuffer = this.streamEventBuffer.slice(end);

        // Immediately check for interactive prompts after processing each event
        this.handleInteractivePrompts();
        
      } catch (error) {
        // Emit parsing errors as events instead of console.error
        this.emit('event', {
          type: 'output',
          content: `Error parsing event: ${error}`,
          timestamp: Date.now()
        });
        
        // Skip this malformed event to avoid infinite loop
        const skipLength = match.index + match[0].length;
        this.streamEventBuffer = this.streamEventBuffer.slice(skipLength);
      }
    }
    
    // Check for interactive prompts that need automatic responses
    this.handleInteractivePrompts();
    
    // If no structured events were found in this chunk, opportunistically capture raw output
    if (!processedEvents && cleanedData) {
      if (this.inToolExecution) {
        this.toolOutputBuffer += cleanedData;
        const MAX_TOOL_OUTPUT = 1 * 1024 * 1024; // 1 MiB cap
        if (this.toolOutputBuffer.length > MAX_TOOL_OUTPUT) {
          this.toolOutputBuffer = this.toolOutputBuffer.slice(-MAX_TOOL_OUTPUT);
        }
        // Chunk out as we accumulate
        this.flushToolOutputChunks(false);
      }
      // Clear buffer to avoid duplicating raw data as preText on the next structured event
      this.streamEventBuffer = '';
    }

    // Keep only last 32KB to prevent memory issues
    if (this.streamEventBuffer.length > 32768) {
      this.streamEventBuffer = this.streamEventBuffer.slice(-16384);
    }
  }

  /**
   * Handle interactive prompts by automatically sending appropriate responses
   */
  private handleInteractivePrompts() {
    // Don't process prompts if container is not actively running
    // This prevents UI from showing stale prompts after assessment completion
    if (!this.isExecutionActive || !this.containerStream) {
      return;
    }

    // Check for assessment execution prompt and auto-execute (original behavior)
    // The prompt may have a module prefix like "◆ general > " or similar
    // Support multiple variants of the execute prompt (with or without quotes/box UI wording)
    const executePromptPattern = /Press\s+Enter\s+or\s+type\s+["']?execute["']?\s+to\s+start\s+assessment|Type\s+["']?execute["']?\s*\(default\)|^\s*execute\s*:\s*press\s+enter/ims;

    if (executePromptPattern.test(this.streamEventBuffer)) {
      logger.info('Prompt detected: auto-sending Enter', { bufferLength: this.streamEventBuffer.length });
      // Give a brief delay to ensure the container is ready for input
      setTimeout(() => {
        if (this.containerStream && this.isExecutionActive) {
          try {
            // Send execute command directly for exec sessions
            this.containerStream.write('execute\r\n');
            logger.info('stdin write sent', { data: 'execute\\r\\n' });
            this.autoExecuteSent = true;
            // Safety resend Enter after 500ms in case first is missed
            setTimeout(() => {
              try {
                if (this.containerStream && this.isExecutionActive) {
                  this.containerStream.write('\r\n');
                  logger.info('stdin fallback sent', { data: '\\r\\n' });
                }
              } catch {}
            }, 500);
          } catch (err) {
            logger.error('stdin write error', err as any);
          }
        }
      }, 500); // Increased initial delay for exec sessions

      // Remove the prompt from buffer to prevent duplicate executions (tolerant to quotes/spacing)
      this.streamEventBuffer = this.streamEventBuffer
        .replace(/.*Press\s+Enter\s+or\s+type\s+["']?execute["']?\s+to\s+start\s+assessment[^\n]*\n?/gi, '')
        .replace(/.*Type\s+["']?execute["']?\s*\(default\)[^\n]*\n?/gi, '');
    }
  }

  /**
   * Stop the running assessment - forcefully kills container and job
   */
  async stop(): Promise<void> {
    if (!this.isExecutionActive) {
      return;
    }

    try {
      if (this.activeContainer) {
        // Force kill the ad-hoc container to ensure immediate termination
        await this.activeContainer.kill('SIGKILL');
      } else if (this.activeExec && this.containerStream) {
        // Exec session in persistent service container: try sending Ctrl-C to terminate the process
        try {
          this.containerStream.write('\x03'); // SIGINT
        } catch {}
      }

      // Clean up container/exec stream if exists
      if (this.containerStream) {
        try {
          this.containerStream.destroy();
        } catch {}
        this.containerStream = undefined;
      }

      this.activeExec = undefined;
      this.activeContainer = undefined;
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.emit('stopped');
      // Don't log here - let the App component handle user-facing messages
    } catch {
      // Force cleanup even if termination fails
      this.activeExec = undefined;
      this.activeContainer = undefined;
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.emit('stopped');
    }
  }

  /**
   * Send user input to the container
   */
  async sendUserInput(input: string): Promise<void> {
    if (!this.containerStream || !this.isExecutionActive) {
      throw new Error('No active container to send input to');
    }

    try {
      // Send input to container stdin with newline
      const payload = input + '\n';
      logger.info('stdin write (user)', { data: payload });
      this.containerStream.write(payload);
    } catch (error) {
      logger.error('stdin write (user) error', error as any);
      // Re-throw error for caller to handle, don't use console.error
      throw new Error(`Error sending input to container: ${error}`);
    }
  }

  /**
   * Check if assessment is running
   */
  isAssessing(): boolean {
    return this.isExecutionActive;
  }

  /**
   * Check if Docker is available
   */
  static async checkDocker(): Promise<boolean> {
    try {
      const dockerClient = new Dockerode();
      await dockerClient.ping();
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Stop the active container
   */
  async stopContainer(): Promise<void> {
    if (!this.activeContainer) {
      return;
    }
    
    try {
      await this.activeContainer.stop();
      this.activeContainer = undefined;
    } catch (error) {
      // Container might already be stopped
      this.activeContainer = undefined;
    }
  }

  /**
   * Reset lightweight per-run flags and buffers
   */
  private resetSessionState(): void {
    this.autoExecuteSent = false;
    this.seenOperationComplete = false;
    this.streamEventBuffer = '';
  }

  /**
   * Cleanup resources and remove all event listeners
   */
  cleanup(): void {
    // Stop any active container
    if (this.activeContainer) {
      this.stopContainer().catch(error => {
        // Silently handle cleanup errors - not critical for user experience
      });
    }
    
    // Destroy stream if exists
    if (this.containerStream) {
      try {
        this.containerStream.destroy();
      } catch (error) {
        // Silently handle cleanup errors - not critical for user experience
      }
      this.containerStream = undefined;
    }
    
    // Abort any pending operations
    this.abortController?.abort();
    
    // Remove all event listeners to prevent memory leaks
    this.removeAllListeners();
    
    // Reset state
    this.isExecutionActive = false;
    this.activeContainer = undefined;
    this.containerStream = undefined;
    this.abortController = undefined;
    
    // DirectDockerService cleaned up - emit event instead of console.log
    this.emit('event', {
      type: 'output',
      content: 'DirectDockerService cleaned up',
      timestamp: Date.now()
    });
  }

  /**
   * Find the running service container for reuse.
   * Prefers exact name match (container_name), then falls back to Compose labels.
   */
  private async findServiceContainer(): Promise<Dockerode.Container | null> {
    try {
      const containers = await this.dockerClient.listContainers({ all: true });
      // Prefer exact name match and running state
      let candidate = containers.find(c => c.State === 'running' && (c.Names || []).some(n => n.replace(/^\//, '') === 'cyber-autoagent'));
      if (!candidate) {
        // Fallback: match by compose service label
        candidate = containers.find(c => c.State === 'running' && c.Labels && (c.Labels as any)['com.docker.compose.service'] === 'cyber-autoagent');
      }
      if (!candidate) return null;
      const cont = this.dockerClient.getContainer(candidate.Id);
      try {
        const info = await cont.inspect();
        logger.info('Service container candidate', {
          name: (candidate.Names || [])[0],
          image: candidate.Image,
          tty: info?.Config?.Tty,
          openStdin: info?.Config?.OpenStdin,
        });
      } catch {}
      return cont;
    } catch {
      return null;
    }
  }

  /**
   * Infer the compose network by inspecting a known stack container and returning its first network name.
   */
  private async inferComposeNetworkFrom(containerName: string): Promise<string | null> {
    try {
      const containers = await this.dockerClient.listContainers({ all: true });
      const target = containers.find(c => (c.Names || []).some(n => n.replace(/^\//, '') === containerName));
      if (!target) return null;
      const info = await this.dockerClient.getContainer(target.Id).inspect();
      const networks = info.NetworkSettings?.Networks || {} as Record<string, unknown>;
      const names = Object.keys(networks);
      return names.length > 0 ? names[0] : null;
    } catch {
      return null;
    }
  }

  /**
   * Exec into an existing container and stream events, mirroring createContainer path.
   */
  private async execIntoContainer(
    container: Dockerode.Container,
    args: string[],
    env: string[],
    deploymentMode: DeploymentMode
  ): Promise<void> {
    // Reset per-run state at the beginning of a new exec session
    this.resetSessionState();
    this.abortController = new AbortController();
    // Fallback auto-execute in exec reuse path
    this.isExecutionActive = true;
    
    // Prepare command (python entrypoint + args) to align with container Entrypoint
    const cmd = ['python', '/app/src/cyberautoagent.py', ...args];

    // Ensure TTY and stdin are enabled for interactive prompts
    const exec = await container.exec({
      Cmd: cmd,
      AttachStdout: true,
      AttachStderr: true,
      AttachStdin: true,
      Tty: true,
      Env: env,
      WorkingDir: '/app'
    });

    this.activeExec = exec;

    const stream: any = await new Promise((resolve, reject) => {
      exec.start({ hijack: true, stdin: true }, (err, s) => {
        if (err) return reject(err);
        resolve(s);
      });
    });

    this.containerStream = stream;
    // Reset completion flag for new exec session (already done in resetSessionState, keep for safety)
    this.seenOperationComplete = false;
    // Clear any residual buffer so prompt detection is fresh
    this.streamEventBuffer = '';

    // Don't send initial input - let the auto-response handler deal with prompts

    // Log exec start
    const cmdStr = ['python', '/app/src/cyberautoagent.py', ...args].join(' ');
    logger.info('Exec session started', { cmd: cmdStr });

    // Create event parser and pipe (TTY=true means single stream)
    const eventParser = new Transform({
      transform: (chunk, _enc, cb) => { this.parseEvents(chunk.toString()); cb(); }
    });
    stream.pipe(eventParser);

    eventParser.on('error', (error) => {
      logger.error('Event parser error', error as any);
      this.emit('event', { type: 'output', content: `Event parser error: ${error}`, timestamp: Date.now() });
    });
    stream.on('error', (error: any) => {
      logger.error('Exec stream error', error);
      this.emit('event', { type: 'output', content: `Stream error: ${error}`, timestamp: Date.now() });
    });
    stream.on('end', () => {
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.streamEventBuffer = '';
      logger.info('Exec stream ended', { seenOperationComplete: this.seenOperationComplete });
      if (this.seenOperationComplete) this.emit('complete');
      else this.emit('stopped');
    });

    // Startup user messages to mirror container path
    this.emit('event', {
      type: 'output',
      content: deploymentMode === 'local-cli' ? '▶ Initializing Python assessment environment...' : '▶ Initializing security assessment (exec)...',
      timestamp: Date.now()
    });

    setTimeout(() => {
      this.emit('event', { type: 'output', content: '◆ Container ready (exec)', timestamp: Date.now() });
    }, 500);

    // Handle abort
    this.abortController?.signal.addEventListener('abort', () => {
      this.stop();
    });

    // Consume the stream to trigger transform events
    eventParser.on('data', () => {});

    this.emit('started');
  }
  
  /**
   * Dispose of the service (alias for cleanup)
   */
  dispose(): void {
    this.cleanup();
  }

  /**
   * Ensure required Docker resources exist
   */
  static async ensureDockerResources(): Promise<void> {
    const dockerClient = new Dockerode();
    
    // Check if network exists
    try {
      await dockerClient.getNetwork('cyberagent-network').inspect();
    } catch {
      // Create network if it doesn't exist
      await dockerClient.createNetwork({
        Name: 'cyberagent-network',
        Driver: 'bridge',
      });
    }
    
    // Check if image exists
    try {
      await dockerClient.getImage('cyber-autoagent:sudo').inspect();
    } catch {
      throw new Error('Docker image cyber-autoagent:sudo not found. Please run setup first.');
    }
  }
}
