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
export class DirectDockerService extends EventEmitter {
  private readonly dockerClient: Dockerode;
  private activeContainer?: Dockerode.Container;
  private containerStream?: any;
  private isExecutionActive = false;
  private streamEventBuffer = '';
  private abortController?: AbortController;

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
    if (this.isExecutionActive) {
      throw new Error('Assessment already running');
    }

    this.isExecutionActive = true;
    this.abortController = new AbortController();

    try {
      // Build command arguments
      // Pass module explicitly to enable module-specific prompts and tools
      const objective = params.objective || `Perform comprehensive ${params.module.replace('_', ' ')} assessment`;
      const args = [
        '--module', params.module,
        '--objective', objective,
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
      
      // Debug logging disabled for production
      // console.error(`[DEBUG] Checking for memory files:`);
      // console.error(`[DEBUG] FAISS path: ${faissPath} - exists: ${fs.existsSync(faissPath)}`);
      // console.error(`[DEBUG] PKL path: ${pklPath} - exists: ${fs.existsSync(pklPath)}`);
      
      if (fs.existsSync(faissPath) && fs.existsSync(pklPath)) {
        // Memory exists - will be automatically loaded by Python agent
        this.emit('event', {
          type: 'output',
          content: `◆ Found existing memory for ${params.target} - loading knowledge from previous assessments`,
          timestamp: Date.now()
        });
      }

      // Environment variables
      const env = [
        'BYPASS_TOOL_CONSENT=true',
        '__REACT_INK__=true',
        'CYBERAGENT_NO_BANNER=true',
        'DEV=true',
      ];

      // AWS credentials - essential for agent to function
      if (config.awsAccessKeyId && config.awsSecretAccessKey) {
        env.push(`AWS_ACCESS_KEY_ID=${config.awsAccessKeyId}`);
        env.push(`AWS_SECRET_ACCESS_KEY=${config.awsSecretAccessKey}`);
      }

      if (config.awsBearerToken) {
        env.push(`AWS_BEARER_TOKEN_BEDROCK=${config.awsBearerToken}`);
      }

      if (config.awsRegion) {
        env.push(`AWS_DEFAULT_REGION=${config.awsRegion}`);
        env.push(`AWS_REGION=${config.awsRegion}`);
      }

      // Observability settings from config
      env.push(`ENABLE_OBSERVABILITY=${config.observability ? 'true' : 'false'}`);
      if (config.observability) {
        // Smart Langfuse host configuration:
        // 1. If langfuseHostOverride is true, always use the configured host
        // 2. If host is not localhost/default, use it (custom deployment)
        // 3. Otherwise, let container auto-detect (Docker vs localhost)
        if (config.langfuseHostOverride || 
            (config.langfuseHost && 
             config.langfuseHost !== 'http://localhost:3000' && 
             !config.langfuseHost.includes('localhost:3000'))) {
          env.push(`LANGFUSE_HOST=${config.langfuseHost}`);
          console.log(`[Observability] Using configured Langfuse host: ${config.langfuseHost}`);
        } else {
          console.log('[Observability] Using container auto-detection for Langfuse host');
        }
        
        env.push(`LANGFUSE_PUBLIC_KEY=${config.langfusePublicKey || 'cyber-public'}`);
        env.push(`LANGFUSE_SECRET_KEY=${config.langfuseSecretKey || 'cyber-secret'}`);
        
        if (config.enableLangfusePrompts) {
          env.push(`ENABLE_LANGFUSE_PROMPTS=true`);
          env.push(`LANGFUSE_PROMPT_LABEL=${config.langfusePromptLabel || 'production'}`);
          env.push(`LANGFUSE_PROMPT_CACHE_TTL=${config.langfusePromptCacheTTL || 300}`);
        }
      }

      // Evaluation settings from config
      env.push(`ENABLE_AUTO_EVALUATION=${config.autoEvaluation ? 'true' : 'false'}`);
      if (config.autoEvaluation && config.evaluationModel) {
        env.push(`RAGAS_EVALUATOR_MODEL=${config.evaluationModel}`);
        env.push(`EVALUATION_BATCH_SIZE=${config.evaluationBatchSize || 5}`);
      }

      // Debug logging disabled for production
      // console.error(`[DEBUG] Creating Docker container with args:`, args);
      // console.error(`[DEBUG] Environment variables:`, env.filter(e => !e.includes('AWS')).concat(['AWS_*=[REDACTED]']));
      // console.error(`[DEBUG] Output path:`, outputPath);
      // console.error(`[DEBUG] Target memory path:`, targetMemoryPath);
      
      // Create container
      this.activeContainer = await this.dockerClient.createContainer({
        Image: 'cyber-autoagent:sudo',
        Cmd: args, // Only pass arguments, entrypoint is already set in Docker image
        Env: env,
        AttachStdout: true,
        AttachStderr: true,
        AttachStdin: true,
        Tty: false,
        OpenStdin: true,
        StdinOnce: false,
        HostConfig: {
          AutoRemove: true,
          NetworkMode: 'docker_default',
          Binds: [
            `${outputPath}:/app/outputs`,
            `${process.cwd()}/tools:/app/tools`,
          ],
        },
        WorkingDir: '/app',
      });
      
      // console.error(`[DEBUG] Container created with ID: ${this.activeContainer.id}`);

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
      
      // console.error(`[DEBUG] Container created with ID: ${this.activeContainer.id}`);

      // Handle stream
      this.activeContainer.modem.demuxStream(stream, eventParser, eventParser);
      
      eventParser.on('data', () => {}); // Required to consume stream
      
      eventParser.on('error', (error) => {
        console.error('Event parser error:', error);
      });
      
      stream.on('error', (error) => {
        console.error('Stream error:', error);
      });
      
      stream.on('end', () => {
        this.isExecutionActive = false;
        this.abortController = undefined;
        this.emit('complete');
      });
      
      // Handle abort signal
      this.abortController.signal.addEventListener('abort', () => {
        this.stop();
      });

      // Get deployment mode to show appropriate startup messages
      const containerManager = ContainerManager.getInstance();
      const deploymentMode = await containerManager.getCurrentMode();
      
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

      // Emit thinking indicator during tool setup
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
      
      this.emit('started');

      // Wait for container to finish
      this.activeContainer.wait((err, data) => {
        if (err) {
          console.error('Container wait error:', err);
        } else if (data && data.StatusCode !== 0) {
          console.error('Container exited with error code:', data.StatusCode);
        }
      });

    } catch (error) {
      this.isExecutionActive = false;
      this.abortController = undefined;
      throw error;
    }
  }
  
  /**
   * Cancel the running assessment - immediately stops container and job
   */
  async cancel(): Promise<void> {
    if (this.abortController && !this.abortController.signal.aborted) {
      this.abortController.abort();
    }
    // Ensure immediate container termination
    await this.stop();
  }

  /**
   * Parse structured events from stdout and capture tool discovery
   */
  private parseEvents(data: string) {
    // Debug logging disabled for production
    // const rawLog = `[${new Date().toISOString()}] RAW: ${data}\n`;
    // fs.appendFileSync('/tmp/cyber-docker-raw.log', rawLog);
    
    // Tool discovery is now handled via structured events in parseEvents
    
    this.streamEventBuffer += data;
    
    // Look for event markers
    const eventRegex = /__CYBER_EVENT__(.+?)__CYBER_EVENT_END__/gs;
    let match;
    
    while ((match = eventRegex.exec(this.streamEventBuffer)) !== null) {
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

        // Handle tool discovery events
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
            // Add spacing and start thinking animation while waiting for reasoning
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
              
              // Start thinking animation while waiting for first reasoning
              this.emit('event', {
                type: 'delayed_thinking_start',
                context: 'reasoning',
                startTime: Date.now(),
                delay: 200
              });
            }, 100);
          }, 1000);
        }
        
        // Debug logging disabled for production use
        // console.error(`[DEBUG] Parsed structured event:`, {
        //   type: event.type,
        //   content: event.content ? (typeof event.content === 'string' ? event.content.substring(0, 100) : event.content) : undefined,
        //   timestamp: new Date(event.timestamp).toISOString()
        // });
        
        this.emit('event', event);
      } catch (error) {
        console.error('Error parsing event:', error);
        console.error('Raw event data:', match[1]);
      }
    }
    
    // Clean processed events from buffer
    this.streamEventBuffer = this.streamEventBuffer.replace(eventRegex, '');
    
    // Keep only last 10KB to prevent memory issues
    if (this.streamEventBuffer.length > 10240) {
      this.streamEventBuffer = this.streamEventBuffer.slice(-5120);
    }
  }


  /**
   * Stop the running assessment - forcefully kills container and job
   */
  async stop(): Promise<void> {
    if (!this.activeContainer || !this.isExecutionActive) {
      return;
    }

    try {
      // Force kill the container with SIGKILL to ensure immediate termination
      await this.activeContainer.kill('SIGKILL');
      
      // Clean up container stream if exists
      if (this.containerStream) {
        try {
          this.containerStream.destroy();
        } catch (streamError) {
          console.error('Error destroying container stream:', streamError);
        }
        this.containerStream = undefined;
      }
      
      this.activeContainer = undefined;
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.emit('stopped');
      // Don't log here - let the App component handle user-facing messages
    } catch (error) {
      console.error('✗ Error stopping container:', error);
      // Force cleanup even if kill fails
      this.activeContainer = undefined;
      this.isExecutionActive = false;
      this.abortController = undefined;
      this.emit('stopped');
      // Don't log here - let the App component handle user-facing messages
    }
  }

  /**
   * Send user input to the container (for handoff_to_user tool)
   */
  async sendUserInput(input: string): Promise<void> {
    if (!this.containerStream || !this.isExecutionActive) {
      throw new Error('No active container to send input to');
    }

    try {
      // Send input to container stdin with newline
      this.containerStream.write(input + '\n');
    } catch (error) {
      console.error('Error sending input to container:', error);
      throw error;
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