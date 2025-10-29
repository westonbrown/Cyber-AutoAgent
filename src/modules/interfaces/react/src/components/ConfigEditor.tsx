/**
 * Configuration Editor
 * 
 * Expandable sections with inline editing for application configuration.
 * Features hierarchical navigation and real-time validation.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Text, useInput } from 'ink';
import SelectInput from 'ink-select-input';
import TextInput, { UncontrolledTextInput } from 'ink-text-input';
import { useConfig } from '../contexts/ConfigContext.js';
import { themeManager } from '../themes/theme-manager.js';
import { Header } from './Header.js';
import { loggingService } from '../services/LoggingService.js';
import { PasswordInput } from './PasswordInput.js';
import { TokenInput } from './TokenInput.js';

interface ConfigEditorProps {
  onClose: () => void;
}

type EditingField = {
  field: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'multiselect';
  options?: Array<{label: string; value: string}>;
} | null;

interface ConfigField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'select' | 'password' | 'multiselect';
  options?: Array<{label: string; value: string}>;
  description?: string;
  section: string;
  required?: boolean;
}

interface ConfigSection {
  name: string;
  label: string;
  description: string;
  expanded: boolean;
}

// MCP constants
const MCP_TRANSPORT_OPTIONS = [
  { label: 'stdio', value: 'stdio' },
  { label: 'sse', value: 'sse' },
  { label: 'streamable-http', value: 'streamable-http' }
] as const;

const MCP_PLUGIN_OPTIONS = [
  { label: '*', value: '*' },
  { label: 'general', value: 'general' },
  { label: 'ctf', value: 'ctf' }
] as const;

// Define all configuration fields with their metadata
const CONFIG_FIELDS: ConfigField[] = [
  // Models - Primary configuration
  { key: 'modelProvider', label: 'Model Provider', type: 'select', section: 'Models', required: true,
    options: [
      { label: 'AWS Bedrock', value: 'bedrock' },
      { label: 'Ollama (Local)', value: 'ollama' },
      { label: 'LiteLLM', value: 'litellm' }
    ]
  },
  { key: 'modelId', label: 'Primary Model', type: 'text', section: 'Models', required: true },
  { key: 'embeddingModel', label: 'Embedding Model', type: 'text', section: 'Models' },
  { key: 'evaluationModel', label: 'Evaluation Model', type: 'text', section: 'Models' },
  { key: 'swarmModel', label: 'Swarm Model', type: 'text', section: 'Models' },

  // Models - Credentials (shown in Models section based on provider)
  { key: 'awsAccessKeyId', label: 'AWS Access Key ID', type: 'password', section: 'Models' },
  { key: 'awsSecretAccessKey', label: 'AWS Secret Access Key', type: 'password', section: 'Models' },
  { key: 'awsBearerToken', label: 'AWS Bearer Token', type: 'password', section: 'Models' },
  { key: 'awsRegion', label: 'AWS Region', type: 'text', section: 'Models' },
  { key: 'awsProfile', label: 'AWS Profile Name', type: 'text', section: 'Models',
    description: 'Optional credential profile (supports LiteLLM Bedrock/SageMaker).' },
  { key: 'awsRoleArn', label: 'AWS Role ARN', type: 'text', section: 'Models',
    description: 'Assume this IAM role before invoking Bedrock/SageMaker endpoints.' },
  { key: 'awsSessionName', label: 'AWS Role Session Name', type: 'text', section: 'Models',
    description: 'Session name used when assuming the specified IAM role.' },
  { key: 'awsWebIdentityTokenFile', label: 'AWS Web Identity Token File', type: 'text', section: 'Models',
    description: 'Path to Web Identity token (IRSA / OIDC environments).' },
  { key: 'awsStsEndpoint', label: 'AWS STS Endpoint', type: 'text', section: 'Models',
    description: 'Custom STS endpoint for GovCloud or private regions.' },
  { key: 'awsExternalId', label: 'AWS External ID', type: 'text', section: 'Models',
    description: 'External ID for cross-account role assumptions.' },
  { key: 'sagemakerBaseUrl', label: 'SageMaker Base URL Override', type: 'text', section: 'Models',
    description: 'Override runtime URL for private/VPC SageMaker endpoints.' },
  { key: 'ollamaHost', label: 'Ollama Host', type: 'text', section: 'Models' },
  { key: 'openaiApiKey', label: 'OpenAI API Key', type: 'password', section: 'Models' },
  { key: 'anthropicApiKey', label: 'Anthropic API Key', type: 'password', section: 'Models' },
  { key: 'geminiApiKey', label: 'Gemini API Key', type: 'password', section: 'Models' },
  { key: 'xaiApiKey', label: 'X.AI API Key', type: 'password', section: 'Models' },
  { key: 'cohereApiKey', label: 'Cohere API Key', type: 'password', section: 'Models' },
  { key: 'azureApiKey', label: 'Azure API Key', type: 'password', section: 'Models' },
  { key: 'azureApiBase', label: 'Azure API Base', type: 'text', section: 'Models' },
  { key: 'azureApiVersion', label: 'Azure API Version', type: 'text', section: 'Models' },
  { key: 'temperature', label: 'Temperature (optional)', type: 'number', section: 'Models',
    description: 'Sampling temperature (0.0-2.0). Leave as Auto for provider defaults.' },
  { key: 'maxTokens', label: 'Max Output Tokens (optional)', type: 'number', section: 'Models',
    description: 'Leave as Auto for provider/model defaults.' },
  { key: 'topP', label: 'Top P (optional)', type: 'number', section: 'Models',
    description: 'Nucleus sampling (0.0-1.0). Leave as Auto. Note: Anthropic requires temperature OR top_p, not both.' },
  { key: 'thinkingBudget', label: 'Thinking Budget (optional)', type: 'number', section: 'Models',
    description: 'Claude thinking models only. Leave as Auto for model defaults.' },
  { key: 'reasoningEffort', label: 'Reasoning Effort (optional)', type: 'select', section: 'Models',
    description: 'OpenAI O1/GPT-5 only. Leave as Auto for default.',
    options: [
      { label: 'Auto', value: '' },
      { label: 'Low', value: 'low' },
      { label: 'Medium', value: 'medium' },
      { label: 'High', value: 'high' }
    ]
  },
  { key: 'maxCompletionTokens', label: 'Max Completion Tokens (optional)', type: 'number', section: 'Models',
    description: 'OpenAI O1/GPT-5 only. Leave as Auto for default.' },

  // Operations (renamed from Assessment)
  { key: 'iterations', label: 'Max Iterations', type: 'number', section: 'Operations' },
  { key: 'autoApprove', label: 'Auto-Approve Tools', type: 'boolean', section: 'Operations' },
  { key: 'maxThreads', label: 'Max Threads', type: 'number', section: 'Operations' },
  { key: 'dockerTimeout', label: 'Docker Timeout (s)', type: 'number', section: 'Operations' },
  { key: 'verbose', label: 'Verbose Output', type: 'boolean', section: 'Operations' },

  // Memory
  { key: 'memoryBackend', label: 'Memory Backend', type: 'select', section: 'Memory',
    options: [
      { label: 'FAISS (Local)', value: 'FAISS' },
      { label: 'Mem0 Platform', value: 'mem0' },
      { label: 'OpenSearch', value: 'opensearch' }
    ]
  },
  { key: 'keepMemory', label: 'Keep Memory After Operations', type: 'boolean', section: 'Memory' },
  { key: 'mem0ApiKey', label: 'Mem0 API Key', type: 'password', section: 'Memory' },
  { key: 'opensearchHost', label: 'OpenSearch Host', type: 'text', section: 'Memory' },

  // Observability
  { key: 'observability', label: 'Enable Remote Observability', type: 'boolean', section: 'Observability',
    description: 'Export traces to Langfuse. Requires Langfuse infrastructure. Auto-detected based on deployment mode. Token counting always enabled.' },
  { key: 'langfuseHost', label: 'Langfuse Host', type: 'text', section: 'Observability' },
  { key: 'langfusePublicKey', label: 'Langfuse Public Key', type: 'password', section: 'Observability' },
  { key: 'langfuseSecretKey', label: 'Langfuse Secret Key', type: 'password', section: 'Observability' },
  { key: 'enableLangfusePrompts', label: 'Enable Prompt Management', type: 'boolean', section: 'Observability' },

  // Evaluation
  { key: 'autoEvaluation', label: 'Auto-Evaluation', type: 'boolean', section: 'Evaluation',
    description: 'Requires Langfuse infrastructure for Ragas metrics. Auto-detected based on deployment mode.' },
  { key: 'minToolAccuracyScore', label: 'Min Tool Accuracy', type: 'number', section: 'Evaluation' },
  { key: 'minEvidenceQualityScore', label: 'Min Evidence Quality', type: 'number', section: 'Evaluation' },
  { key: 'minAnswerRelevancyScore', label: 'Min Answer Relevancy', type: 'number', section: 'Evaluation' },

  // Dynamic Pricing - Current Model pricing (populated based on active modelId)
  { key: 'currentModel.inputCostPer1k',
    label: 'Current Model - Input Cost (per 1K tokens)', type: 'number', section: 'Pricing',
    description: 'Cost per 1000 input tokens for your selected model' },
  { key: 'currentModel.outputCostPer1k',
    label: 'Current Model - Output Cost (per 1K tokens)', type: 'number', section: 'Pricing',
    description: 'Cost per 1000 output tokens for your selected model' },

  // Output
  { key: 'outputDir', label: 'Output Directory', type: 'text', section: 'Output' },
  { key: 'outputFormat', label: 'Output Format', type: 'select', section: 'Output',
    options: [
      { label: 'Markdown', value: 'markdown' },
      { label: 'JSON', value: 'json' },
      { label: 'HTML', value: 'html' }
    ]
  },
  { key: 'unifiedOutput', label: 'Unified Output Structure', type: 'boolean', section: 'Output' }
];

const SECTIONS: ConfigSection[] = [
  { name: 'Models', label: 'Models & Credentials', description: 'AI provider and authentication', expanded: false },
  { name: 'Operations', label: 'Operations', description: 'Execution parameters', expanded: false },
  { name: 'Memory', label: 'Memory', description: 'Vector storage configuration', expanded: false },
  { name: 'Observability', label: 'Observability', description: 'Remote tracing (auto-detected, token counting always enabled)', expanded: false },
  { name: 'Evaluation', label: 'Evaluation', description: 'Quality assessment with Ragas (auto-detected)', expanded: false },
  { name: 'Pricing', label: 'Model Pricing', description: 'Token cost configuration per 1K tokens', expanded: false },
  { name: 'MCP', label: 'MCP Servers', description: 'Model Context Protocol server connections', expanded: false },
  { name: 'Output', label: 'Output', description: 'Report and logging', expanded: false }
];

/**
 * Detect model capabilities based on model ID
 * Simple pattern matching - easily extensible for new models
 */
const getModelCapabilities = (modelId: string | undefined) => {
  if (!modelId) return { hasThinking: false, hasReasoning: false, requiresTemp1: false };

  const id = modelId.toLowerCase();

  // Thinking models (Claude extended thinking with THINKING_BUDGET)
  const hasThinking =
    id.includes('claude-sonnet-4-5') ||
    id.includes('claude-sonnet-4-20') ||
    id.includes('claude-opus-4');

  // Reasoning models (OpenAI O1/GPT-5 with REASONING_EFFORT)
  const hasReasoning =
    id.includes('o1-') ||
    id.includes('o3-') ||
    id.includes('gpt-5') ||
    id.includes('reasoning');

  // Models that require temperature=1.0 exactly (Claude thinking + OpenAI reasoning)
  const requiresTemp1 = hasThinking || hasReasoning;

  return { hasThinking, hasReasoning, requiresTemp1 };
};

export const ConfigEditor: React.FC<ConfigEditorProps> = ({ onClose }) => {
  const { config, updateConfig, saveConfig } = useConfig();
  const theme = themeManager.getCurrentTheme();

  const [sections, setSections] = useState(SECTIONS);
  const [selectedSectionIndex, setSelectedSectionIndex] = useState(0);
  const [selectedFieldIndex, setSelectedFieldIndex] = useState(0);
  const [editingField, setEditingField] = useState<EditingField>(null);
  const [tempValue, setTempValue] = useState('');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [navigationMode, setNavigationMode] = useState<'sections' | 'fields'>('sections');
  const [lastEscTime, setLastEscTime] = useState<number | null>(null);

  // Use ref to track timeout for cleanup
  const messageTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const messageIdRef = React.useRef(0);
  const messagePriorityRef = React.useRef(-1);
  const messageLockRef = React.useRef(0);
  // Latch to swallow Enter after field commit
  const enterLatchRef = React.useRef(0);

  // Use ref for handleSave to avoid stale closure issues
  const handleSaveRef = React.useRef<(() => void) | undefined>(undefined);

  // Use ref to protect message during saves
  const isSavingRef = React.useRef(false);


  // Screen clearing is handled by modal manager's refreshStatic()

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
    };
  }, []);

  const showMessage = useCallback((text: string, type: 'success' | 'error' | 'info', ttl = 3000) => {
    const priority = type === 'error' ? 2 : type === 'success' ? 1 : 0;
    const now = Date.now();
    if (messageLockRef.current > now && priority <= messagePriorityRef.current) {
      return;
    }
    if (messagePriorityRef.current > priority) {
      return;
    }
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current);
      messageTimeoutRef.current = null;
    }
    const nextId = messageIdRef.current + 1;
    messageIdRef.current = nextId;
    setMessage({ text, type });
    messagePriorityRef.current = priority;
    messageLockRef.current = ttl > 0 ? now + ttl : 0;
    if (ttl > 0) {
      messageTimeoutRef.current = setTimeout(() => {
        if (messageIdRef.current === nextId) {
          setMessage(null);
          messageTimeoutRef.current = null;
          messagePriorityRef.current = -1;
          messageLockRef.current = 0;
        }
      }, ttl);
    }
  }, []);

  // ==== MCP state & helpers ====
  const [selectedMcpIndex, setSelectedMcpIndex] = useState(0);
  const [mcpTestStatus, setMcpTestStatus] = useState<Record<number, string>>({});

  const normalizeTransport = (t: string | undefined) => (t || '').replace('_', '-');

  // Ensure `config.mcp` exists with sane defaults
  useEffect(() => {
    if (!(config as any).mcp) {
      updateConfig({ mcp: { enabled: false, connections: [] } });
    } else {
      // Normalize any legacy transport values
      const mcp = (config as any).mcp;
      if (Array.isArray(mcp?.connections)) {
        let mutated = false;
        const next = mcp.connections.map((c: any) => {
          const nt = normalizeTransport(c.transport);
          if (nt && nt !== c.transport) {
            mutated = true;
            return { ...c, transport: nt };
          }
          return c;
        });
        if (mutated) {
          updateConfig({ mcp: { ...mcp, connections: next } });
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getMcpConnections = () => (config as any).mcp?.connections ?? [];

  const setMcpEnabled = (val: boolean) => {
    const mcp = (config as any).mcp ?? { enabled: false, connections: [] };
    updateConfig({ mcp: { ...mcp, enabled: val } });
    setUnsavedChanges(true);
  };

  const addMcpConnection = () => {
    const mcp = (config as any).mcp ?? { enabled: false, connections: [] };
    const nextConnections = [...(mcp.connections ?? []), {
      id: `conn-${(mcp.connections?.length ?? 0) + 1}`,
      transport: 'stdio',
      command: [],
      plugins: ['general'],
      timeoutSeconds: 300,
      toolLimit: 8
    }];
    updateConfig({ mcp: { ...mcp, connections: nextConnections } });
    setSelectedMcpIndex(Math.max(0, nextConnections.length - 1));
    setUnsavedChanges(true);
    showMessage('Added new MCP connection', 'success', 2000);
    // Keep MCP section expanded and stay in fields mode
    setNavigationMode('fields');
    setSections(prev => {
      const copy = [...prev];
      const idx = copy.findIndex(s => s.name === 'MCP');
      if (idx !== -1) copy[idx] = { ...copy[idx], expanded: true };
      return copy;
    });
  };

  const removeMcpConnection = () => {
    const mcp = (config as any).mcp ?? { enabled: false, connections: [] };
    const conns = [...(mcp.connections ?? [])];
    if (conns.length === 0) return;
    conns.splice(selectedMcpIndex, 1);
    const nextIdx = Math.max(0, selectedMcpIndex - 1);
    updateConfig({ mcp: { ...mcp, connections: conns } });
    setSelectedMcpIndex(nextIdx);
    setUnsavedChanges(true);
    showMessage('Removed MCP connection', 'success', 2000);
    // Keep MCP section expanded and stay in fields mode
    setNavigationMode('fields');
    setSections(prev => {
      const copy = [...prev];
      const idx = copy.findIndex(s => s.name === 'MCP');
      if (idx !== -1) copy[idx] = { ...copy[idx], expanded: true };
      return copy;
    });
  };

  const updateMcpConnection = (key: string, value: any) => {
    const mcp = (config as any).mcp ?? { enabled: false, connections: [] };
    const conns = [...(mcp.connections ?? [])];
    if (!conns[selectedMcpIndex]) return;

    const curr = { ...conns[selectedMcpIndex] };
    if (key === 'transport') {
      curr.transport = normalizeTransport(String(value));
    } else if (key === 'plugins') {
      curr.plugins = Array.isArray(value) ? value : [];
    } else if (key === 'command') {
      curr.command = value;
    } else if (key === 'headers') {
      curr.headers = value;
    } else if (key === 'id') {
      curr.id = String(value);
    } else if (key === 'server_url') {
      curr.server_url = String(value);
    } else if (key === 'timeoutSeconds') {
      curr.timeoutSeconds = Number(value);
    } else if (key === 'toolLimit') {
      curr.toolLimit = Number(value);
    } else {
      (curr as any)[key] = value;
    }

    conns[selectedMcpIndex] = curr;
    updateConfig({ mcp: { ...mcp, connections: conns } });
    setUnsavedChanges(true);
  };

  const getSelectedMcp = () => getMcpConnections()[selectedMcpIndex];

  const testMcpConnection = async () => {
    // Keep section expanded & remain in fields mode
    setNavigationMode('fields');
    setSections(prev => {
      const copy = [...prev];
      const idx = copy.findIndex(s => s.name === 'MCP');
      if (idx !== -1) copy[idx] = { ...copy[idx], expanded: true };
      return copy;
    });
    enterLatchRef.current = Date.now() + 250;

    const idx = selectedMcpIndex;
    const conn = getSelectedMcp();
    if (!conn) {
      showMessage('No MCP connection selected', 'error', 3000);
      setMcpTestStatus(prev => ({ ...prev, [idx]: 'No connection selected' }));
      return;
    }

    const t = normalizeTransport(conn.transport);
    if (t === 'stdio') {
      showMessage('Test Connection: not applicable for stdio transport', 'info', 3000);
      setMcpTestStatus(prev => ({ ...prev, [idx]: 'N/A for stdio' }));
      return;
    }

    const baseUrl = conn.server_url;
    if (!baseUrl) {
      showMessage('server_url is required to test HTTP/SSE MCP servers', 'error', 4000);
      setMcpTestStatus(prev => ({ ...prev, [idx]: 'Missing server_url' }));
      return;
    }

    setMcpTestStatus(prev => ({ ...prev, [idx]: 'Testing…' }));

    try {
      const f: any = (globalThis as any).fetch;
      if (!f) {
        showMessage('Fetch API not available in this runtime', 'error', 4000);
        setMcpTestStatus(prev => ({ ...prev, [idx]: 'Fetch API unavailable' }));
        return;
      }

      // Build headers from connection config
      const baseHeaders: Record<string, string> = {};
      if (conn.headers && typeof conn.headers === 'object') {
        for (const [k, v] of Object.entries(conn.headers)) {
          if (typeof v === 'string') baseHeaders[k] = v;
        }
      }

      // Helper: read small body snippet
      const bodySnippet = async (resp: any) => {
        try {
          const text = await resp.text();
          return text.length > 240 ? text.slice(0, 240) + '…' : text;
        } catch {
          return '';
        }
      };

      // --- Strategy 1: SSE GET (negotiation)
      const sseHeaders: Record<string, string> = { ...baseHeaders };
      sseHeaders['Accept'] = 'text/event-stream';
      sseHeaders['Cache-Control'] = 'no-cache';
      sseHeaders['Connection'] = 'keep-alive';
      if (t === 'streamable-http') {
        // Some servers use this hint
        sseHeaders['Mcp-Transport'] = 'streamable-http';
      }

      const sseCtl = new AbortController();
      const sseTimeout = setTimeout(() => sseCtl.abort(), 3500);
      let resp = await f(baseUrl, { method: 'GET', headers: sseHeaders, signal: sseCtl.signal });
      clearTimeout(sseTimeout);

      // Fallback to /stream path if server expects it
      if (resp && (resp.status === 404 || resp.status === 400)) {
        const altUrl = baseUrl.replace(/\/?$/, '/stream');
        const altCtl = new AbortController();
        const altTimeout = setTimeout(() => altCtl.abort(), 3500);
        const altResp = await f(altUrl, { method: 'GET', headers: sseHeaders, signal: altCtl.signal });
        clearTimeout(altTimeout);
        if (altResp) resp = altResp;
      }

      if (resp && ((resp.status >= 200 && resp.status < 400) || resp.status === 406 || resp.status === 101)) {
        showMessage(`Connection OK (${resp.status}, SSE)`, 'success', 3000);
        setMcpTestStatus(prev => ({ ...prev, [idx]: `OK (${resp.status})` }));
        return;
      }

      // If 406, we already presented Accept; proceed to JSON-RPC POST probe for streamable-http
      const status1 = resp?.status ?? 'no-response';

      // --- Strategy 2: JSON-RPC ping via POST (some streamable-http servers accept this)
      const postHeaders: Record<string, string> = { ...baseHeaders };
      postHeaders['Content-Type'] = 'application/json';
      postHeaders['Accept'] = 'application/json';

      const body = JSON.stringify({ jsonrpc: '2.0', id: 'health-check', method: 'ping' });

      const postCtl = new AbortController();
      const postTimeout = setTimeout(() => postCtl.abort(), 3500);
      let postResp = await f(baseUrl, { method: 'POST', headers: postHeaders, body, signal: postCtl.signal });
      clearTimeout(postTimeout);

      // Fallback to /mcp for POST if baseUrl ends not in /mcp
      if (postResp && (postResp.status === 404 || postResp.status === 400)) {
        if (!/\/mcp\/?$/.test(baseUrl)) {
          const alt = baseUrl.replace(/\/?$/, '/mcp');
          const altCtl2 = new AbortController();
          const altTimeout2 = setTimeout(() => altCtl2.abort(), 3500);
          const altResp2 = await f(alt, { method: 'POST', headers: postHeaders, body, signal: altCtl2.signal });
          clearTimeout(altTimeout2);
          if (altResp2) postResp = altResp2;
        }
      }

      if (postResp && ((postResp.status >= 200 && postResp.status < 400) || postResp.status === 406 || postResp.status === 101)) {
        showMessage(`Connection OK (${postResp.status}, POST)`, 'success', 3000);
        setMcpTestStatus(prev => ({ ...prev, [idx]: `OK (${postResp.status})` }));
        return;
      }

      // If we got here, all strategies failed — show best diagnostic
      const snippet = resp ? await bodySnippet(resp) : '';
      const code = status1;
      const note = snippet ? ` — ${snippet}` : '';
      showMessage(`Connection FAILED (${code})${note}`, 'error', 7000);
      setMcpTestStatus(prev => ({ ...prev, [idx]: `FAILED (${code})${snippet ? `: ${snippet}` : ''}` }));
    } catch (e: any) {
      const msg = e?.name === 'AbortError' ? 'timeout' : (e?.message || String(e));
      showMessage(`Connection FAILED: ${msg}`, 'error', 6000);
      setMcpTestStatus(prev => ({ ...prev, [idx]: `FAILED: ${msg}` }));
    }
  };

  // Build pseudo fields for MCP so generic navigation works
  const getMcpFields = (): ConfigField[] => {
    const conns = getMcpConnections();
    const conn = conns[selectedMcpIndex];
    const idxLabel = conns.length === 0
      ? 'Connection Index (0/0)'
      : `Connection Index (${selectedMcpIndex + 1}/${conns.length})`;
    const base: ConfigField[] = [
      { key: 'mcp.enabled', label: 'MCP Enabled', type: 'boolean', section: 'MCP' },
      { key: 'mcp.connectionIndex', label: idxLabel, type: 'number', section: 'MCP', description: 'Use ←/→ to switch connections' },
    ];
    if (!conn) {
      return base;
    }
    return base.concat([
      { key: 'mcp.conn.id', label: 'Connection ID', type: 'text', section: 'MCP', required: true },
      { key: 'mcp.conn.transport', label: 'Transport', type: 'select', options: MCP_TRANSPORT_OPTIONS as any, section: 'MCP', required: true },
      { key: 'mcp.conn.server_url', label: 'Server URL', type: 'text', section: 'MCP', description: 'Required for sse/streamable-http' },
      { key: 'mcp.conn.command', label: 'Command (JSON array)', type: 'text', section: 'MCP', description: 'Example: ["python","-m","shyhurricane.server"]' },
      { key: 'mcp.conn.headers', label: 'Headers (JSON)', type: 'text', section: 'MCP', description: 'Example: {"Authorization":"Bearer ${HTB_TOKEN}"}' },
      { key: 'mcp.conn.plugins', label: 'Plugins', type: 'multiselect', section: 'MCP', options: MCP_PLUGIN_OPTIONS as any, description: "Select one or more. If '*' is selected it will be the only selection." },
      { key: 'mcp.conn.timeoutSeconds', label: 'Timeout (seconds)', type: 'number', section: 'MCP' },
      { key: 'mcp.conn.toolLimit', label: 'Tool Limit', type: 'number', section: 'MCP' },
      { key: 'mcp.conn.test', label: 'Test Connection', type: 'text', section: 'MCP', description: 'Press Enter to run HTTP check against server_url' },
    ]);
  };
  // Ensure MCP section stays open while editing fields
  useEffect(() => {
    if (navigationMode !== 'fields') return;
    setSections(prev => {
      const curr = prev[selectedSectionIndex];
      if (!curr || curr.name !== 'MCP' || curr.expanded) return prev;
      const copy = [...prev];
      copy[selectedSectionIndex] = { ...curr, expanded: true };
      return copy;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navigationMode, selectedSectionIndex, (config as any).mcp?.enabled, (config as any).mcp?.connections?.length]);
  // ==== end MCP helpers ====
  // Auto-adjust observability and evaluation based on deployment mode
  useEffect(() => {
    const deploymentMode = config.deploymentMode;

    // For local-cli and single-container, default to disabled
    if (deploymentMode === 'local-cli' || deploymentMode === 'single-container') {
      // Only update if not explicitly set by user (check if still at default true values)
      if (config.observability === true && !config.langfuseHostOverride) {
        updateConfig({ observability: false });
        showMessage('Observability disabled for local/single-container mode', 'info');
      }
      if (config.autoEvaluation === true) {
        updateConfig({ autoEvaluation: false });
        showMessage('Auto-evaluation disabled for local/single-container mode', 'info');
      }
    }
    // For full-stack, these can remain enabled (user can still toggle)
  }, [config.deploymentMode, updateConfig, showMessage]);

  // Get fields for the current section
  const getCurrentSectionFields = useCallback(() => {
    const currentSection = sections[selectedSectionIndex];
    if (!currentSection?.expanded) return [];

    // MCP custom section uses generated fields so navigation works
    if (currentSection.name === 'MCP') {
      return getMcpFields();
    }

    let fields = CONFIG_FIELDS.filter(f => f.section === currentSection.name);

    // Filter credentials based on provider
    if (currentSection.name === 'Models') {
      // Detect model capabilities
      const capabilities = getModelCapabilities(config.modelId);
      const isSageMakerModel = config.modelProvider === 'litellm' &&
        (config.modelId ? config.modelId.toLowerCase().startsWith('sagemaker/') : false);

      fields = fields.filter(f => {
        // Always show provider and model fields
        if (['modelProvider', 'modelId', 'embeddingModel', 'evaluationModel', 'swarmModel'].includes(f.key)) {
          return true;
        }

        // Model-specific advanced parameters (only show if model supports them)
        if (f.key === 'thinkingBudget' && !capabilities.hasThinking) return false;
        if (f.key === 'reasoningEffort' && !capabilities.hasReasoning) return false;
        if (f.key === 'maxCompletionTokens' && !capabilities.hasReasoning) return false;

        // Show provider-specific credentials and token configs
        if (config.modelProvider === 'bedrock') {
          const bedrockFields = [
            'awsAccessKeyId', 'awsSecretAccessKey', 'awsBearerToken', 'awsRegion',
            'awsProfile', 'awsRoleArn', 'awsSessionName', 'awsWebIdentityTokenFile', 'awsStsEndpoint', 'awsExternalId',
            'temperature', 'maxTokens', 'thinkingBudget'
          ];
          return bedrockFields.includes(f.key);
        } else if (config.modelProvider === 'ollama') {
          return ['ollamaHost', 'temperature', 'maxTokens'].includes(f.key);
        } else if (config.modelProvider === 'litellm') {
          const litellmFields = [
            'openaiApiKey', 'anthropicApiKey', 'geminiApiKey', 'xaiApiKey', 'cohereApiKey',
            'azureApiKey', 'azureApiBase', 'azureApiVersion',
            'awsAccessKeyId', 'awsSecretAccessKey', 'awsBearerToken', 'awsRegion',
            'awsProfile', 'awsRoleArn', 'awsSessionName', 'awsWebIdentityTokenFile', 'awsStsEndpoint', 'awsExternalId',
            'temperature', 'maxTokens', 'topP', 'thinkingBudget', 'reasoningEffort', 'maxCompletionTokens',
            'sagemakerBaseUrl'
          ];
          if (f.key === 'sagemakerBaseUrl') {
            return isSageMakerModel;
          }
          return litellmFields.includes(f.key);
        }

        return false;
      });
    }

    // Filter memory fields based on backend
    if (currentSection.name === 'Memory') {
      fields = fields.filter(f => {
        if (['memoryBackend', 'keepMemory'].includes(f.key)) return true;
        if (config.memoryBackend === 'mem0' && f.key === 'mem0ApiKey') return true;
        if (config.memoryBackend === 'opensearch' && f.key === 'opensearchHost') return true;
        return false;
      });
    }

    return fields;
  }, [sections, selectedSectionIndex, config.modelProvider, config.memoryBackend, config.modelId]);

  // Basic pre-save validation for required fields and dependent settings
  const validateBeforeSave = useCallback(() => {
    // Required fields
    const requiredFields: Array<{ key: string; label: string }> = [
      { key: 'modelProvider', label: 'Model Provider' },
      { key: 'modelId', label: 'Primary Model' },
    ];
    const missing = requiredFields.filter(f => !(config as any)[f.key]);
    if (missing.length > 0) {
      return `Missing required: ${missing.map(m => m.label).join(', ')}`;
    }
    // Observability requirements when enabled
    if (config.observability) {
      if (!config.langfuseHost && !config.langfuseHostOverride) {
        return 'Observability is enabled but Langfuse Host is not set.';
      }
      if (!config.langfusePublicKey || !config.langfuseSecretKey) {
        return 'Observability requires Langfuse Public and Secret keys.';
      }
    }
    return '';
  }, [config]);

  const handleSave = useCallback(() => {
    // Don't show intermediate "Saving..." message to reduce re-renders

    (async () => {
      try {
        await saveConfig();

        const timestamp = new Date().toLocaleTimeString();
        setUnsavedChanges(false);

        // Delay notification to prevent rapid re-renders that cause WASM memory issues
        // This is especially important in long-running sessions with multiple operations
        // Increased to 300ms to match Terminal.tsx throttle intervals
        setTimeout(() => {
          showMessage(`Configuration saved at ${timestamp}`, 'success', 5000);
        }, 300);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        setTimeout(() => {
          showMessage(`Save failed: ${errorMessage}`, 'error', 5000);
        }, 300);
      }
    })();
  }, [saveConfig, showMessage]);

  // Store handleSave in ref to avoid stale closures
  React.useEffect(() => {
    handleSaveRef.current = handleSave;
  }, [handleSave]);

  // Handle keyboard navigation
  useInput((input, key) => {
    // Swallow the Enter key that immediately follows a field submit to avoid collapsing the section
    if (key.return) {
      const now = Date.now();
      if (enterLatchRef.current && now < enterLatchRef.current) {
        return; // ignore this Enter
      }
    }

    if (editingField) {
      // In edit mode
      if (key.escape) {
        setEditingField(null);
        setTempValue('');
      }
      return;
    }

    // Navigation mode
    if (key.escape) {
      if (navigationMode === 'fields') {
        // Go back to section navigation but KEEP section expanded
        setNavigationMode('sections');
        setSelectedFieldIndex(0);
      } else {
        // Double-ESC to exit from sections list
        const now = Date.now();
        const withinWindow = lastEscTime && now - lastEscTime < 1200;
        if (unsavedChanges) {
          showMessage('Unsaved changes. Press Ctrl+S to save or Esc twice to exit without saving.', 'info');
          setLastEscTime(now);
        } else if (withinWindow) {
          onClose();
        } else {
          showMessage('Press Esc again to exit', 'info');
          setLastEscTime(now);
        }
      }
    }

    if (key.upArrow) {
      if (navigationMode === 'sections') {
        setSelectedSectionIndex(prev => Math.max(0, prev - 1));
      } else {
        const fields = getCurrentSectionFields();
        setSelectedFieldIndex(prev => Math.max(0, prev - 1));
      }
    }

    if (key.downArrow) {
      if (navigationMode === 'sections') {
        setSelectedSectionIndex(prev => Math.min(sections.length - 1, prev + 1));
      } else {
        const fields = getCurrentSectionFields();
        setSelectedFieldIndex(prev => Math.min(fields.length - 1, prev + 1));
      }
    }

    if (key.return) {
      if (navigationMode === 'sections') {
        // Toggle section expansion
        const newSections = [...sections];
        newSections[selectedSectionIndex].expanded = !newSections[selectedSectionIndex].expanded;
        setSections(newSections);

        // If expanding, switch to field navigation
        if (newSections[selectedSectionIndex].expanded) {
          setNavigationMode('fields');
          setSelectedFieldIndex(0);
        }
      } else {
        // Edit field (with MCP special actions)
        const fields = getCurrentSectionFields();
        const field = fields[selectedFieldIndex];
        if (!field) return;
        if (field.key === 'mcp.conn.test') {
          // Ensure MCP stays open, then trigger test without entering edit mode
          setNavigationMode('fields');
          const newSections = [...sections];
          newSections[selectedSectionIndex].expanded = true;
          setSections(newSections);
          enterLatchRef.current = Date.now() + 250;
          testMcpConnection();
          return;
        }
        startEditing(field);
      }
    }
    // MCP quick controls when editing connections
    const currentSection = sections[selectedSectionIndex];
    if (navigationMode === 'fields' && currentSection?.name === 'MCP') {
      if (input?.toLowerCase?.() === 'a') {
        addMcpConnection();
        return;
      }
      if (input?.toLowerCase?.() === 'd') {
        removeMcpConnection();
        return;
      }
      if (key.leftArrow) {
        const conns = getMcpConnections();
        if (conns.length > 0) setSelectedMcpIndex(i => Math.max(0, i - 1));
      }
      if (key.rightArrow) {
        const conns = getMcpConnections();
        if (conns.length > 0) setSelectedMcpIndex(i => Math.min(conns.length - 1, i + 1));
      }
    }
    if ((key.ctrl || key.meta) && (input?.toLowerCase?.() === 's')) {
      showMessage('Saving configuration...', 'info', 0);
      handleSaveRef.current?.();
      return;
    }

    // Expand/collapse with arrows in sections mode
    if (navigationMode === 'sections') {
      if (key.leftArrow) {
        const newSections = [...sections];
        if (newSections[selectedSectionIndex].expanded) {
          newSections[selectedSectionIndex].expanded = false;
          setSections(newSections);
        }
      }
      if (key.rightArrow) {
        const newSections = [...sections];
        if (!newSections[selectedSectionIndex].expanded) {
          newSections[selectedSectionIndex].expanded = true;
          setSections(newSections);
          setNavigationMode('fields');
          setSelectedFieldIndex(0);
        }
      }
    }
  }, { isActive: !editingField });

  // Separate input handler for when editing to handle Ctrl+S and Ctrl+V
  useInput((input, key) => {
    // Handle Ctrl/Cmd+S for save
    if ((key.ctrl || key.meta) && (input?.toLowerCase?.() === 's')) {
      // Save the current editing value first
      if (editingField && tempValue) {
        const field = getCurrentSectionFields().find(f => f.key === editingField.field);
        if (field) {
          if (field.type === 'number') {
            const numValue = parseFloat(tempValue);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            // Clean and sanitize the value, especially for tokens/keys
            const cleanedValue = cleanInputForKey(field.key, tempValue);
            updateConfigValue(field.key, cleanedValue);
          }
        }
      }
      setEditingField(null);
      setTempValue('');
      showMessage('Saving configuration...', 'info', 0);
      handleSaveRef.current?.();
      // Prevent the 's' from being added to the input
      return;
    }

    // Handle Ctrl+V for paste - prevent 'v' from being inserted
    if (key.ctrl && input === 'v') {
      // Don't allow the 'v' to be inserted - just ignore for now
      // Users can use regular system paste (Cmd+V on Mac, which Ink handles)
      return;
    }

    if (key.escape) {
      setEditingField(null);
      setTempValue('');
    }
  }, { isActive: editingField !== null });

  // Sanitize input values for specific keys (tokens, API keys, etc.)
  const cleanInputForKey = (key: string, raw: string): string => {
    if (typeof raw !== 'string') return raw;

    // List of fields that should have all whitespace stripped
    const secretFields = new Set([
      'awsBearerToken',
      'awsAccessKeyId',
      'awsSecretAccessKey',
      'awsSessionToken',
      'openaiApiKey',
      'anthropicApiKey',
      'geminiApiKey',
      'xaiApiKey',
      'cohereApiKey',
      'mem0ApiKey',
      'langfusePublicKey',
      'langfuseSecretKey',
      'langfuseEncryptionKey'
    ]);

    if (secretFields.has(key)) {
      // Remove ALL whitespace (spaces, tabs, newlines, etc.) from secrets
      let cleaned = raw.replace(/\s+/g, '');

      // For bearer tokens, ensure it's valid base64
      if (key === 'awsBearerToken') {
        // Remove any non-base64 characters
        cleaned = cleaned.replace(/[^A-Za-z0-9+/=]/g, '');
      }

      return cleaned;
    }

    // For other fields, just trim outer whitespace
    return raw.trim();
  };

  const updateConfigValue = useCallback((key: string, value: any) => {
    // Validate temperature for models that require temperature=1.0
    if (key === 'temperature' && value !== null && value !== undefined && value !== '') {
      const capabilities = getModelCapabilities(config.modelId);
      if (capabilities.requiresTemp1) {
        const tempValue = typeof value === 'string' ? parseFloat(value) : value;
        if (tempValue !== 1.0) {
          showMessage(
            `${config.modelId} requires temperature=1.0 (reasoning models only support this value)`,
            'error',
            5000
          );
          return; // Block the change
        }
      }
    }

    // Special handling for provider changes - set appropriate default models
    if (key === 'modelProvider') {
      const updates: any = { modelProvider: value };

      // Set default models based on provider
      if (value === 'ollama') {
        // Set Ollama-specific defaults
        updates.modelId = 'qwen3-coder:30b-a3b-q4_K_M';
        updates.embeddingModel = 'mxbai-embed-large';
        updates.evaluationModel = 'qwen3-coder:30b-a3b-q4_K_M';
        updates.swarmModel = 'qwen3-coder:30b-a3b-q4_K_M';
        // Clear temperature to null so backend uses model-specific defaults
        updates.temperature = null;
      } else if (value === 'bedrock') {
        // Set AWS Bedrock defaults - Latest Sonnet 4.5 with 1M context + thinking
        updates.modelId = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
        updates.embeddingModel = 'amazon.titan-embed-text-v2:0';
        updates.evaluationModel = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.swarmModel = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        // Clear temperature to null so backend uses model-specific defaults (1.0 for Sonnet 4.5)
        updates.temperature = null;
      } else if (value === 'litellm') {
        // Set LiteLLM defaults
        updates.modelId = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.embeddingModel = 'bedrock/amazon.titan-embed-text-v2:0';
        updates.evaluationModel = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        updates.swarmModel = 'bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0';
        // Clear temperature to null so backend uses model-specific defaults
        updates.temperature = null;
      }

      updateConfig(updates);
      setUnsavedChanges(true);
      showMessage(`Switched to ${value} provider with default models`, 'info');
      return;
    }

    // Special handling for currentModel pricing - update the actual model's pricing
    if (key.startsWith('currentModel.')) {
      const pricingKey = key.replace('currentModel.', '');
      const currentModelId = config.modelId;

      if (!currentModelId) {
        showMessage('No model selected to configure pricing', 'error');
        return;
      }

      // Update pricing for the current model
      const newConfig = { ...config };
      if (!newConfig.modelPricing) {
        newConfig.modelPricing = {};
      }
      if (!newConfig.modelPricing[currentModelId]) {
        newConfig.modelPricing[currentModelId] = {
          inputCostPer1k: 0,
          outputCostPer1k: 0
        };
      }

      // Update the specific pricing field
      (newConfig.modelPricing[currentModelId] as any)[pricingKey] = value;

      updateConfig(newConfig);
      setUnsavedChanges(true);
      return;
    }

    // Handle nested keys
    if (key.includes('.')) {
      const parts = key.split('.');
      const newConfig = { ...config };
      let current: any = newConfig;

      // Navigate to the parent object
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) {
          current[parts[i]] = {};
        }
        current = current[parts[i]];
      }

      // Set the final value
      current[parts[parts.length - 1]] = value;

      // Update the entire config
      updateConfig(newConfig);
    } else {
      updateConfig({ [key]: value });
    }
    setUnsavedChanges(true);
  }, [config, updateConfig]);


  const startEditing = useCallback((field: ConfigField) => {
    // Prevent editing of read-only fields
    if (field.key === 'modelPricingInfo') {
      showMessage('Model pricing is configured in ~/.cyber-autoagent/config.json under "modelPricing"', 'info');
      return;
    }
    // MCP section custom handlers
    if (field.section === 'MCP') {
      if (field.key === 'mcp.enabled') {
        setMcpEnabled(!((config as any).mcp?.enabled ?? false));
        return;
      }
      if (field.key === 'mcp.connectionIndex') {
        showMessage('Use ←/→ to switch connections', 'info', 2000);
        return;
      }
    }

    const currentValue = config[field.key as keyof typeof config];

    if (field.type === 'boolean') {
      // Toggle boolean immediately
      updateConfigValue(field.key, !currentValue);
      return;
    }

    // Set up editing state
    setEditingField({
      field: field.key,
      type: field.type as any,
      options: field.options
    });

    // Set initial value for editing
    // For password/secret fields, start with empty to avoid paste issues
    if (field.type === 'password') {
      // Always start with empty field for password types to ensure clean paste
      // This prevents the issue where pasting inserts in the middle of masked text
      setTempValue('');
      if (currentValue) {
        // Show brief message that field is cleared for re-entry
        showMessage('Field cleared. Enter or paste new value (Cmd+V on Mac)', 'info', 2000);
      }
    } else if (field.type === 'number') {
      setTempValue(String(currentValue || 0));
    } else {
      setTempValue(String(currentValue || ''));
    }
  }, [config, updateConfigValue, showMessage]);

  const getValue = (key: string): string => {
    // MCP pseudo values
    if (key.startsWith('mcp.')) {
      const mcp = (config as any).mcp ?? { enabled: false, connections: [] };
      if (key === 'mcp.enabled') return mcp.enabled ? 'Enabled' : 'Disabled';
      if (key === 'mcp.connectionIndex') return String(selectedMcpIndex + 1);
      const conn = getSelectedMcp();
      if (!conn) return 'No connections';
      if (key === 'mcp.conn.id') return String(conn.id ?? '');
      if (key === 'mcp.conn.transport') return String(conn.transport ?? 'stdio');
      if (key === 'mcp.conn.server_url') return String(conn.server_url ?? '');
      if (key === 'mcp.conn.command') return Array.isArray(conn.command) ? JSON.stringify(conn.command) : '';
      if (key === 'mcp.conn.headers') return conn.headers ? JSON.stringify(conn.headers) : '';
      if (key === 'mcp.conn.plugins') return Array.isArray(conn.plugins) ? conn.plugins.join(', ') : '';
      if (key === 'mcp.conn.timeoutSeconds') return String(conn.timeoutSeconds ?? '');
      if (key === 'mcp.conn.toolLimit') return String(conn.toolLimit ?? '');
      if (key === 'mcp.conn.test') {
        const status = mcpTestStatus[selectedMcpIndex];
        return status ? `Press Enter to test — ${status}` : 'Press Enter to test';
      }
    }

    // Special handling for model pricing info
    if (key === 'modelPricingInfo') {
      if (config.modelPricing && Object.keys(config.modelPricing).length > 0) {
        const modelCount = Object.keys(config.modelPricing).length;
        return `${modelCount} models configured with custom pricing`;
      }
      return 'Using default AWS Bedrock pricing';
    }

    // Special handling for currentModel pricing - use actual modelId from config
    if (key.startsWith('currentModel.')) {
      const pricingKey = key.replace('currentModel.', '');
      const currentModelId = config.modelId;

      if (!currentModelId) {
        return 'No model selected';
      }

      // Check if pricing exists for current model
      const modelPricing = config.modelPricing?.[currentModelId];
      if (modelPricing && pricingKey in modelPricing) {
        const value = modelPricing[pricingKey as keyof typeof modelPricing];
        return String(value || 0);
      }

      // Provider-specific defaults
      if (config.modelProvider === 'ollama') {
        return '0.000'; // Ollama is free
      } else if (config.modelProvider === 'litellm') {
        return pricingKey === 'inputCostPer1k' ? '0.001' : '0.002'; // LiteLLM example defaults
      } else {
        return pricingKey === 'inputCostPer1k' ? '0.003' : '0.015'; // Bedrock defaults
      }
    }

    // Handle nested keys (e.g., modelPricing.model.inputCostPer1k)
    let value: any = config;
    const parts = key.split('.');
    for (const part of parts) {
      if (value && typeof value === 'object') {
        value = value[part as keyof typeof value];
      } else {
        value = undefined;
        break;
      }
    }

    const field = CONFIG_FIELDS.find(f => f.key === key);

    if (value === undefined || value === null || value === '') {
      // Show computed defaults for model-specific parameters
      if (key === 'temperature') {
        // Thinking/reasoning models require temperature=1.0
        const capabilities = getModelCapabilities(config.modelId);
        if (capabilities.requiresTemp1) {
          return '1.0 (required)';
        }
        return 'Auto';
      }
      if (key === 'maxTokens' && config.modelId?.includes('claude-sonnet-4-5-20250929')) {
        return '16000';
      }
      if (key === 'thinkingBudget' && config.modelId?.includes('claude-sonnet-4-5-20250929')) {
        return '7000';
      }
      if (key === 'maxTokens' && config.modelId?.includes('claude-sonnet-4-20250514')) {
        return '32000';
      }
      if (key === 'thinkingBudget' && config.modelId?.includes('claude-sonnet-4-20250514')) {
        return '10000';
      }

      // Show provider defaults for common optional fields
      if (key === 'topP') {
        return 'Auto';
      }
      if (key === 'reasoningEffort') {
        return 'Auto';
      }
      if (key === 'maxCompletionTokens') {
        return 'Auto';
      }
      if (key === 'maxTokens') {
        return 'Auto (provider default)';
      }
      if (key === 'thinkingBudget') {
        return 'Auto (provider default)';
      }

      return 'Not set';
    }

    if (field?.type === 'password' && value) {
      return '*'.repeat(8);
    }

    if (field?.type === 'boolean') {
      return value ? 'Enabled' : 'Disabled';
    }

    // Add "(required)" hint for temperature=1.0 on reasoning models
    if (key === 'temperature' && value !== null && value !== undefined && value !== '') {
      const capabilities = getModelCapabilities(config.modelId);
      if (capabilities.requiresTemp1) {
        return `${value} (required)`;
      }
    }

    return String(value);
  };

  const renderNotification = () => {
    if (!message) return null;

    // Create a prominent notification box that stands out
    return (
      <Box
        borderStyle="double"
        borderColor={
          message.type === 'success' ? theme.success :
          message.type === 'error' ? theme.danger :
          theme.primary
        }
        paddingX={1}
        marginBottom={1}
      >
        <Text
          bold
          color={
            message.type === 'success' ? theme.success :
            message.type === 'error' ? theme.danger :
            theme.primary
          }
        >
          {message.type === 'success' && '━━━ '}
          {message.text}
          {message.type === 'success' && ' ━━━'}
        </Text>
      </Box>
    );
  };

  const renderHeader = () => {
    return (
      <Box marginBottom={1} flexDirection="column">
        <Box>
          <Text bold color={theme.primary} wrap="wrap">Configuration Editor</Text>
          {unsavedChanges && <Text color={theme.warning} wrap="wrap"> [Unsaved]</Text>}
        </Box>
        <Text color={theme.muted} wrap="wrap">
          {navigationMode === 'sections'
            ? 'Navigate with ↑↓ arrows • Enter to expand section • Ctrl+S to save • Esc to continue and exit'
            : 'Navigate with ↑↓ arrows • Enter to edit field • Cmd+V to paste (Mac) • Ctrl+S to save • Esc to collapse section'}
        </Text>
      </Box>
    );
  };

  const renderSections = () => {
    return (
      <Box flexDirection="column">
        {sections.map((section, sectionIndex) => {
          const isSelected = sectionIndex === selectedSectionIndex && navigationMode === 'sections';
          const fields = CONFIG_FIELDS.filter(f => f.section === section.name);
          const configuredCount = fields.filter(f => {
            const value = config[f.key as keyof typeof config];
            return value !== undefined && value !== null && value !== '';
          }).length;

          return (
            <Box key={section.name} flexDirection="column" marginBottom={1}>
              {/* Section Header */}
              <Box>
                <Text
                  bold={isSelected}
                  color={isSelected ? theme.accent : theme.foreground}
                  wrap="wrap"
                >
                  {isSelected ? '▸ ' : '  '}
                  {section.expanded ? '▼ ' : '▶ '}
                  {section.label}
                </Text>
                <Text color={theme.muted} wrap="wrap">
                  {' '}({configuredCount}/{fields.length} configured)
                </Text>
              </Box>

              {/* Section Description */}
              <Box paddingLeft={4}>
                <Text color={theme.muted} wrap="wrap">{section.description}</Text>
                {section.name === 'MCP' && (
                  <Text color={theme.muted} wrap="wrap"> — Keys: A = add, D = delete, ←/→ switch connection, Enter = edit field, Enter on "Test Connection" to run check</Text>
                )}
              </Box>

              {/* Fields (if expanded) */}
              {section.expanded && navigationMode === 'fields' && sectionIndex === selectedSectionIndex && (
                <>
                {section.name === 'MCP' && (() => {
                  const conns = getMcpConnections();
                  const hasAny = conns.length > 0;
                  return (
                    <Box paddingLeft={4} marginTop={1}>
                      <Text color={theme.muted}>
                        {hasAny ? (
                          <>Manage connections (A=add, D=delete, ←/→ switch). Selected: {selectedMcpIndex + 1}/{conns.length}{getSelectedMcp()?.id ? ` — ${getSelectedMcp()?.id}` : ''}</>
                        ) : (
                          <>No connections yet — press A to add your first MCP server</>
                        )}
                      </Text>
                    </Box>
                  );
                })()}
                <Box flexDirection="column" paddingLeft={2} marginTop={1}>
                  {getCurrentSectionFields().map((field, fieldIndex) => {
                    const isFieldSelected = fieldIndex === selectedFieldIndex;
                    const isEditing = editingField?.field === field.key;

                    return (
                      <Box key={field.key} marginY={0.25}>
                        {(() => {
                          const cols = (() => { try { return Math.max(40, Math.min(Number((process as any)?.stdout?.columns || 80), 200)); } catch { return 80; } })();
                          const labelWidth = Math.max(20, Math.min(48, Math.floor(cols * 0.38)));
                          return (
                            <>
                              <Box width={labelWidth}>
                                <Text
                                  bold={isFieldSelected}
                                  color={isFieldSelected ? theme.accent : theme.muted}
                                >
                                  {isFieldSelected ? '▸ ' : '  '}{field.label}:
                                  {field.required && <Text color={theme.danger}> *</Text>}
                                </Text>
                              </Box>
                              <Box flexGrow={1}>
                                {isEditing ? renderEditingField(field) : (
                                  <Text
                                    bold={isFieldSelected}
                                    color={
                                      getValue(field.key) === 'Not set' ? theme.muted :
                                      field.type === 'boolean' && getValue(field.key) === 'Enabled' ? theme.success :
                                      isFieldSelected ? theme.foreground : theme.primary
                                    }
                                  >
                                    {getValue(field.key)}
                                  </Text>
                                )}
                              </Box>
                            </>
                          );
                        })()}
                      </Box>
                    );
                  })}
                </Box>
                </>
              )}
            </Box>
          );
        })}
      </Box>
    );
  };

  const renderEditingField = (field: ConfigField) => {
    if (!editingField) return null;

    // MCP transport (single select with custom updater)
    if (field.key === 'mcp.conn.transport') {
      return (
        <SelectInput
          items={(MCP_TRANSPORT_OPTIONS as any)}
          onSelect={(item) => {
            updateMcpConnection('transport', item.value);
            setEditingField(null);
            setTempValue('');
            // Keep section expanded & remain in fields mode
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);
            // Swallow next Enter from this commit
            enterLatchRef.current = Date.now() + 250;
          }}
          indicatorComponent={({ isSelected }) => (
            <Text color={isSelected ? theme.primary : 'transparent'}>❯ </Text>
          )}
          itemComponent={({ isSelected, label }) => (
            <Text color={isSelected ? theme.primary : theme.foreground}>{label}</Text>
          )}
        />
      );
    }

    // MCP plugins multiselect
    if (field.key === 'mcp.conn.plugins') {
      const conn = getSelectedMcp();
      const initial = new Set<string>((conn?.plugins ?? []) as string[]);
      const MultiSelect: React.FC<{ options: Array<{label:string; value:string}>; initial: Set<string>; onDone: (vals: string[]) => void; }> = ({ options, initial, onDone }) => {
        const [cursor, setCursor] = useState(0);
        const [sel, setSel] = useState<Set<string>>(new Set(initial));
        useInput((input, key) => {
          if (key.upArrow) setCursor(c => Math.max(0, c - 1));
          if (key.downArrow) setCursor(c => Math.min(options.length - 1, c + 1));
          if (key.escape) {
            setEditingField(null);
            setTempValue('');
          }
          if (input === ' ') {
            const opt = options[cursor];
            if (!opt) return;
            const next = new Set(sel);
            if (opt.value === '*') {
              // Selecting '*' makes it the only selection
              if (sel.has('*')) {
                next.delete('*');
              } else {
                next.clear();
                next.add('*');
              }
            } else {
              // Selecting others removes '*'
              next.delete('*');
              if (next.has(opt.value)) next.delete(opt.value); else next.add(opt.value);
            }
            setSel(next);
          }
          if (key.return) {
            const vals = Array.from(sel);
            onDone(vals);
          }
        }, { isActive: true });
        return (
          <Box flexDirection="column">
            {options.map((opt, i) => (
              <Text key={opt.value} color={i === cursor ? theme.primary : theme.foreground}>
                [{sel.has(opt.value) ? 'x' : ' '}] {opt.label}
              </Text>
            ))}
            <Text color={theme.muted}>Space = toggle • Enter = save • Esc = cancel</Text>
          </Box>
        );
      };
      return (
        <MultiSelect
          options={MCP_PLUGIN_OPTIONS as any}
          initial={initial}
          onDone={(vals) => {
            updateMcpConnection('plugins', vals);
            setEditingField(null);
            setTempValue('');
            // Keep section expanded & remain in fields mode
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);
            // Swallow next Enter from this commit
            enterLatchRef.current = Date.now() + 250;
          }}
        />
      );
    }

    // MCP JSON fields
    if (field.key === 'mcp.conn.headers' || field.key === 'mcp.conn.command') {
      return (
        <TextInput
          value={tempValue}
          onChange={(v) => setTempValue(v)}
          onSubmit={(value) => {
            try {
              const parsed = JSON.parse(value || (field.key === 'mcp.conn.headers' ? '{}' : '[]'));
              if (field.key === 'mcp.conn.headers' && (parsed && typeof parsed === 'object' && !Array.isArray(parsed))) {
                updateMcpConnection('headers', parsed);
              } else if (field.key === 'mcp.conn.command' && Array.isArray(parsed)) {
                updateMcpConnection('command', parsed);
              } else {
                throw new Error('Invalid JSON shape');
              }
              setEditingField(null);
              setTempValue('');
              setNavigationMode('fields');
              const newSections = [...sections];
              newSections[selectedSectionIndex].expanded = true;
              setSections(newSections);
              enterLatchRef.current = Date.now() + 250;
            } catch (e: any) {
              showMessage(`Invalid JSON: ${e?.message || String(e)}`, 'error', 5000);
            }
          }}
        />
      );
    }

    // MCP scalar fields & index setter
    if (field.key.startsWith('mcp.conn.') || field.key === 'mcp.connectionIndex') {
      return (
        <TextInput
          value={tempValue}
          onChange={(v) => setTempValue(v)}
          onSubmit={(value) => {
            if (field.key === 'mcp.connectionIndex') {
              const conns = getMcpConnections();
              const idx = Math.max(0, Math.min(conns.length - 1, Math.max(0, (parseInt(value, 10) || 1) - 1)));
              setSelectedMcpIndex(idx);
              setEditingField(null);
              setTempValue('');
              setNavigationMode('fields');
              const newSections = [...sections];
              newSections[selectedSectionIndex].expanded = true;
              setSections(newSections);
              enterLatchRef.current = Date.now() + 250;
              return;
            }
            if (field.key === 'mcp.conn.timeoutSeconds' || field.key === 'mcp.conn.toolLimit') {
              const num = parseInt(value, 10);
              if (!Number.isFinite(num)) {
                showMessage('Enter a valid number', 'error', 3000);
                return;
              }
              updateMcpConnection(field.key.split('.').pop() as string, num);
            } else if (field.key === 'mcp.conn.id' || field.key === 'mcp.conn.server_url') {
              updateMcpConnection(field.key.split('.').pop() as string, value);
            } else {
              // Fallback: no-op
            }
            setEditingField(null);
            setTempValue('');
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);
            enterLatchRef.current = Date.now() + 250;
          }}
        />
      );
    }

    if (field.type === 'select' && editingField.options) {
      return (
        <SelectInput
          items={editingField.options.map(opt => ({
            label: opt.label,
            value: opt.value
          }))}
          onSelect={(item) => {
            updateConfigValue(field.key, item.value);
            setEditingField(null);

            // Ensure section stays expanded and move to next field
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after selection
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
            // Swallow next Enter
            enterLatchRef.current = Date.now() + 250;
          }}
          indicatorComponent={({ isSelected }) => (
            <Text color={isSelected ? theme.primary : 'transparent'}>❯ </Text>
          )}
          itemComponent={({ isSelected, label }) => (
            <Text color={isSelected ? theme.primary : theme.foreground}>
              {label}
            </Text>
          )}
        />
      );
    }

    // Use TokenInput for AWS Bearer token
    if (field.key === 'awsBearerToken') {
      return (
        <TokenInput
          fieldKey={field.key}
          onSubmit={(value) => {
            // Clean and sanitize the value
            const cleanedValue = cleanInputForKey(field.key, value);
            updateConfigValue(field.key, cleanedValue);
            setEditingField(null);
            setTempValue('');

            // Brief success message
            showMessage(`Token saved (${cleanedValue.length} chars)`, 'success', 2000);

            // Ensure we stay in fields navigation mode and section stays expanded
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after saving
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
          }}
        />
      );
    }

    // Use custom PasswordInput for other password fields
    if (field.type === 'password') {
      return (
        <PasswordInput
          fieldKey={field.key}
          onSubmit={(value) => {
            // Clean and sanitize the value
            const cleanedValue = cleanInputForKey(field.key, value);
            updateConfigValue(field.key, cleanedValue);
            setEditingField(null);
            setTempValue('');

            // Ensure we stay in fields navigation mode and section stays expanded
            setNavigationMode('fields');
            const newSections = [...sections];
            newSections[selectedSectionIndex].expanded = true;
            setSections(newSections);

            // Move to next field after saving
            const fields = getCurrentSectionFields();
            if (selectedFieldIndex < fields.length - 1) {
              setSelectedFieldIndex(prev => prev + 1);
            }
          }}
        />
      );
    }

    return (
      <TextInput
        value={tempValue}
        onChange={(newValue) => {
          // Debug logging for non-password fields
          // Directly update temp value (no verbose debug logging)
          setTempValue(newValue);
        }}
        onSubmit={(value) => {
          // Debug logging for non-password fields
          // Avoid verbose debug logging of field values

          if (field.type === 'number') {
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
              updateConfigValue(field.key, numValue);
            }
          } else {
            // Clean and sanitize the value, especially for tokens/keys
            const cleanedValue = cleanInputForKey(field.key, value);

            // More debug logging
            // No debug logging of cleaned token values
            updateConfigValue(field.key, cleanedValue);
          }
          setEditingField(null);
          setTempValue('');

          // Ensure we stay in fields navigation mode and section stays expanded
          setNavigationMode('fields');
          const newSections = [...sections];
          newSections[selectedSectionIndex].expanded = true;
          setSections(newSections);

          // Move to next field after saving
          const fields = getCurrentSectionFields();
          if (selectedFieldIndex < fields.length - 1) {
            setSelectedFieldIndex(prev => prev + 1);
          }
          enterLatchRef.current = Date.now() + 250;
        }}
        mask={undefined}
      />
    );
  };

  // Quick status summary
  const getConfigStatus = () => {
    const hasProvider = config.modelProvider;
    const hasCredentials = 
      (config.modelProvider === 'bedrock' && (config.awsAccessKeyId || config.awsBearerToken)) ||
      (config.modelProvider === 'ollama' && config.ollamaHost) ||
      (config.modelProvider === 'litellm');
    const hasModel = config.modelId;
    
    if (!hasProvider) return { status: 'error', message: 'No provider selected' };
    if (!hasCredentials) return { status: 'warning', message: 'Missing credentials' };
    if (!hasModel) return { status: 'warning', message: 'No model selected' };
    
    return { status: 'success', message: 'Ready' };
  };
  
  // Deployment mode status
  const getDeploymentModeDisplay = () => {
    const mode = config.deploymentMode || 'unknown';
    const observabilityStatus = config.observability ? 'enabled' : 'disabled';
    const evaluationStatus = config.autoEvaluation ? 'enabled' : 'disabled';
    
    return {
      mode: mode.replace('-', ' ').toUpperCase(),
      observability: observabilityStatus,
      evaluation: evaluationStatus,
      description: getDeploymentDescription(mode)
    };
  };
  
  const getDeploymentDescription = (mode: string) => {
    switch (mode) {
      case 'cli': return 'Python CLI mode (token counting enabled, remote traces disabled)';
      case 'container': return 'Single container mode (token counting enabled, remote traces disabled)';
      case 'compose': return 'Full stack mode (token counting + remote traces enabled)';
      default: return 'Deployment mode detection in progress';
    }
  };
  
  const status = getConfigStatus();
  const deploymentStatus = getDeploymentModeDisplay();







  // Main render logic
  return (
    <Box flexDirection="column">
      <Box
        flexDirection="column"
        borderStyle="single"
        borderColor={theme.primary}
        padding={1}
        marginTop={1}
        width="100%"
      >
        {/* Notification appears INSIDE the main border at the very top */}
        {message && (
          <Box
            borderStyle="double"
            borderColor={
              message.type === 'success' ? theme.success :
              message.type === 'error' ? theme.danger :
              theme.primary
            }
            paddingX={1}
            marginBottom={1}
          >
            <Text
              bold
              wrap="wrap"
              color={
                message.type === 'success' ? theme.success :
                message.type === 'error' ? theme.danger :
                theme.primary
              }
            >
              {message.type === 'success' && '✓ '}
              {message.type === 'error' && '✗ '}
              {message.type === 'info' && '⏳ '}
              {message.text}
            </Text>
          </Box>
        )}
        
        {renderHeader()}
      
      {/* Status bar */}
      <Box marginBottom={1} flexDirection="column">
        <Text
          wrap="wrap"
          color={
            status.status === 'success' ? theme.success :
            status.status === 'warning' ? theme.warning :
            theme.danger
          }
        >
          Status: {status.message}
        </Text>
        <Text color={theme.muted} wrap="wrap">
          Deployment: {deploymentStatus.mode} |
          Observability: {deploymentStatus.observability} |
          Evaluation: {deploymentStatus.evaluation}
        </Text>
        <Text color={theme.muted} wrap="wrap">
          {deploymentStatus.description}
        </Text>
      </Box>
      
      {/* Main configuration sections */}
      <Box flexDirection="column" flexGrow={1}>
        {renderSections()}
      </Box>
      
        {/* Footer with shortcuts */}
        <Box marginTop={1} borderTop borderColor={unsavedChanges ? theme.warning : theme.muted} paddingTop={1}>
          <Text color={theme.muted} wrap="wrap">
            {navigationMode === 'sections'
              ? '↑↓ Navigate sections • Enter to expand/collapse • Ctrl+S to save • Esc to exit'
              : '↑↓ Navigate fields • Enter to edit • Esc to collapse • Ctrl+S to save'
            }
          </Text>
          {unsavedChanges && (
            <Text color={theme.warning} bold wrap="wrap">
              {' '}[Unsaved Changes]
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
