// Event normalization utilities for stream rendering
// Keeps UI renderers simple by standardizing event shapes at the edge

// NOTE: using local normalizeToolInput defined below

export type AnyEvent = Record<string, any>;

// Deterministic tool id (1s bucket) so headers always render but remain stable
function makeToolId(name: string, ts?: string | number): string {
  const t = typeof ts === 'string' ? Date.parse(ts) : (typeof ts === 'number' ? ts : Date.now());
  const bucket = Math.floor((isNaN(t) ? Date.now() : t) / 1000);
  const safe = (name || 'tool').toString().trim() || 'tool';
  return `${safe}-${bucket}`;
}

// Normalize common timestamp shape to ISO string when possible
function normalizeTimestamp(ts: any): string | undefined {
  if (!ts && ts !== 0) return undefined;
  if (typeof ts === 'number') return new Date(ts).toISOString();
  if (typeof ts === 'string') {
    const n = Date.parse(ts);
    return isNaN(n) ? undefined : new Date(n).toISOString();
  }
  return undefined;
}

// Coerce tool input into stable shapes
function normalizeToolInput(toolName: string, input: any): any {
  const name = (toolName || '').toLowerCase();
  if (input == null) return {};

  // Defensive clone for plain objects/arrays to avoid accidental mutation by callers
  const clone = (val: any): any => {
    if (Array.isArray(val)) return val.slice();
    if (val && typeof val === 'object') return { ...val };
    return val;
  };

  let toolInput = clone(input);

  // If backend passed a JSON-looking string for whole input, try parse
  if (typeof toolInput === 'string') {
    const s = toolInput.trim();
    if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
      try { toolInput = JSON.parse(s); } catch { /* ignore */ }
    }
  }

  // Shell: support command/cmd/commands and correct JSON-string arrays
  if (name === 'shell') {
    const raw = toolInput.command ?? toolInput.commands ?? toolInput.cmd ?? toolInput.input;

    const toCommands = (value: any): any[] | undefined => {
      if (value == null) return undefined;
      if (Array.isArray(value)) return value; // preserve array elements (strings or objects)
      if (typeof value === 'string') {
        const s = value.trim();
        if ((s.startsWith('[') && s.endsWith(']')) || (s.startsWith('{') && s.endsWith('}'))) {
          try {
            const normalized = s.replace(/\\n/g, '\n');
            const parsed = JSON.parse(normalized);
            if (Array.isArray(parsed)) return parsed;
            if (parsed && typeof parsed === 'object') return [parsed];
          } catch {
            /* keep as raw string below */
          }
        }
        return [value];
      }
      if (typeof value === 'object') return [value];
      return [String(value)];
    };

    const commands = toCommands(raw);
    return { ...toolInput, command: commands };
  }

  // http_request: make method upper-case and ensure url string
  if (name === 'http_request') {
    const method = (toolInput.method || 'GET').toString().toUpperCase();
    const url = toolInput.url != null ? String(toolInput.url) : '';
    return { ...toolInput, method, url };
  }

  // file_write: coerce path/content to strings when present
  if (name === 'file_write') {
    const path = toolInput.path != null ? String(toolInput.path) : undefined;
    const content = toolInput.content != null ? String(toolInput.content) : undefined;
    return { ...toolInput, path, content };
  }

  // editor: avoid flooding UI with large file_text payloads; provide preview + stats instead
  if (name === 'editor') {
    const cloneInput: any = { ...toolInput };
    const path = cloneInput.path != null ? String(cloneInput.path) : undefined;
    const command = cloneInput.command != null ? String(cloneInput.command) : undefined;
    const fileText: any = cloneInput.file_text;
    let file_text_preview: string | undefined;
    let file_text_length: number | undefined;
    let file_text_lines: number | undefined;
    if (typeof fileText === 'string') {
      file_text_length = fileText.length;
      file_text_lines = fileText.split('\n').length;
      // Keep a small preview to help debugging without breaking the UI
      file_text_preview = fileText.slice(0, 1000);
    }
    // Remove heavy field from normalized input to prevent UI crashes
    delete cloneInput.file_text;
    return {
      ...cloneInput,
      ...(path ? { path } : {}),
      ...(command ? { command } : {}),
      ...(file_text_length != null ? { file_text_length } : {}),
      ...(file_text_lines != null ? { file_text_lines } : {}),
      ...(file_text_preview ? { file_text_preview, file_text_omitted: true } : {}),
    };
  }

  // python_repl: trim overly large code payloads to a preview to keep render stable
  if (name === 'python_repl') {
    const cloneInput: any = { ...toolInput };
    const code: any = cloneInput.code;
    if (typeof code === 'string' && code.length > 2000) {
      cloneInput.code_preview = code.slice(0, 1000);
      cloneInput.code_length = code.length;
      delete cloneInput.code; // omit full code; preview is sufficient for display
    }
    return cloneInput;
  }

  if (name === 'prompt_optimizer') {
    const cloneInput: any = { ...toolInput };
    const normalized: any = {};
    const action = cloneInput.action ?? cloneInput.Action;
    normalized.action = action ? String(action) : 'apply';

    if (cloneInput.trigger) normalized.trigger = String(cloneInput.trigger);
    if (cloneInput.reviewer) normalized.reviewer = String(cloneInput.reviewer);
    if (cloneInput.note) normalized.note = clampString(String(cloneInput.note), 400);
    if (cloneInput.context) normalized.context = clampString(String(cloneInput.context), 400);
    if (cloneInput.prompt) normalized.prompt = clampString(String(cloneInput.prompt), 400);
    if (cloneInput.current_step != null) normalized.current_step = Number(cloneInput.current_step);
    if (cloneInput.expires_after_steps != null) {
      normalized.expires_after_steps = Number(cloneInput.expires_after_steps);
    }

    const overlayRaw = cloneInput.overlay;
    let overlayObj: any = overlayRaw;
    if (typeof overlayRaw === 'string') {
      try { overlayObj = JSON.parse(overlayRaw); } catch { overlayObj = undefined; }
    }
    if (overlayObj && typeof overlayObj === 'object') {
      const payload = overlayObj.payload && typeof overlayObj.payload === 'object' ? overlayObj.payload : overlayObj;
      const directives = payload.directives;
      if (Array.isArray(directives) && directives.length > 0) {
        const cleaned = directives
          .map((item: any) => String(item).trim())
          .filter((item: string) => Boolean(item));
        if (cleaned.length > 0) {
          const slice = cleaned.slice(0, 4);
          const preview = slice.join(', ');
          normalized.directives = cleaned.length > 4
            ? `${preview}, ... (+${cleaned.length - 4} more)`
            : preview;
        }
      }
      if (payload.trajectory) normalized.trajectory = sanitizeAllStrings(payload.trajectory);
      if (payload.metadata && typeof payload.metadata === 'object') {
        normalized.metadata = sanitizeAllStrings(payload.metadata);
      }
    }

    return normalized;
  }


  // editor/python_repl/etc.: leave as-is except shallow clone done above
  return toolInput;
}

function normalizeToolName(e: AnyEvent): string {
  return (e.toolName || e.tool_name || e.tool || '').toString();
}

// Clamp and sanitize string fields to keep UI stable
function clampString(s: unknown, max = 32768): unknown {
  if (typeof s !== 'string') return s;
  return s.length > max ? s.slice(0, max) + `... (truncated ${s.length - max} chars)` : s;
}

function sanitizeAllStrings(obj: any): any {
  if (!obj || typeof obj !== 'object') return obj;
  const out: any = Array.isArray(obj) ? [] : {};
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'string') out[k] = clampString(v);
    else if (v && typeof v === 'object') out[k] = sanitizeAllStrings(v);
    else out[k] = v;
  }
  return out;
}

// Normalize event in-place (returns a new shallow-cloned object)
export function normalizeEvent(event: AnyEvent): AnyEvent {
  if (!event || typeof event !== 'object') return event;

  const e: AnyEvent = { ...event };

  // Standardize common timestamp field to ISO string if present
  if (e.timestamp && typeof e.timestamp === 'number') {
    try { e.timestamp = new Date(e.timestamp).toISOString(); } catch {}
  }

  // First, clamp top-level common stringy fields defensively
  for (const key of ['content','message','delta','error']) {
    if (key in e) (e as any)[key] = clampString((e as any)[key]);
  }

  switch (e.type) {
    case 'specialist_start': {
      // Normalize specialist start payload fields (snake_case -> camelCase)
      const specialist = (e.specialist || e.name || '').toString() || 'validation';
      // Normalize artifact paths
      const artifactPaths = Array.isArray((e as any).artifactPaths)
        ? (e as any).artifactPaths
        : (Array.isArray((e as any).artifact_paths) ? (e as any).artifact_paths : undefined);
      return {
        ...e,
        specialist,
        ...(artifactPaths ? { artifactPaths } : {}),
      };
    }

    case 'specialist_progress': {
      // Normalize progress fields
      const gate = (e as any).gate;
      const totalGates = (e as any).totalGates ?? (e as any).total_gates;
      const tool = (e as any).tool;
      return {
        ...e,
        ...(gate != null ? { gate: Number(gate) } : {}),
        ...(totalGates != null ? { totalGates: Number(totalGates) } : {}),
        ...(tool ? { tool: String(tool) } : {}),
      };
    }

    case 'specialist_end': {
      // Normalize result object keys for UI renderer
      const result = (e as any).result || {};
      const normalizedResult: any = { ...result };
      if ('validation_status' in normalizedResult && !('validationStatus' in normalizedResult)) {
        normalizedResult.validationStatus = normalizedResult.validation_status;
      }
      if ('severity_max' in normalizedResult && !('severityMax' in normalizedResult)) {
        normalizedResult.severityMax = normalizedResult.severity_max;
      }
      if ('failed_gates' in normalizedResult && !('failedGates' in normalizedResult)) {
        normalizedResult.failedGates = normalizedResult.failed_gates;
      }
      return { ...e, result: normalizedResult };
    }

    case 'tool_start': {
      const toolName = e.toolName || e.tool_name || 'tool';
      const rawInput = e.args !== undefined ? e.args : (e.tool_input !== undefined ? e.tool_input : {});
      const normalizedInput = normalizeToolInput(toolName, rawInput);

      e.tool_name = toolName;
      // Clamp tool input deeply to prevent large payloads
      e.tool_input = sanitizeAllStrings(normalizedInput);
      // Preserve originals for debugging but prefer normalized accessors
      if (e.args !== undefined) delete e.args;
      // Ensure a deterministic toolId if upstream omitted it (leave Terminal's fallback as secondary)
      if (!e.toolId && !e.tool_id) {
        const bucket = Math.floor((e.timestamp ? Date.parse(e.timestamp) : Date.now()) / 1000);
        e.toolId = `${toolName}-${bucket}`;
      }
      return e;
    }

    case 'command': {
      // If command content is a JSON object with a `command` field, unwrap for display
      if (typeof e.content === 'string' && e.content.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(e.content);
          if (parsed && typeof parsed === 'object' && parsed.command) {
            e.content = String(parsed.command);
          }
        } catch {}
      }
      return e;
    }

    case 'tool_output': {
      // Standardize shape: tool, status, output.text
      if (e.output && typeof e.output === 'string') {
        e.output = { text: e.output };
      }
      if (!e.status) e.status = 'success';
      return e;
    }

    case 'prompt_change': {
      if (typeof e.overlay === 'string') {
        try { e.overlay = JSON.parse(e.overlay); } catch { e.overlay = undefined; }
      }
      if (e.overlay && typeof e.overlay === 'object') {
        e.overlay = sanitizeAllStrings(e.overlay);
      }
      if (Array.isArray(e.directives)) {
        e.directives = e.directives.map((item: any) => clampString(String(item)));
      }
      if (e.summary) {
        e.summary = clampString(String(e.summary));
      }
      if (e.note) {
        e.note = clampString(String(e.note));
      }
      return e;
    }


    default:
      break;
  }

  // As a final guard, clamp any nested string fields in metadata/unknown payloads
  if (e.metadata && typeof e.metadata === 'object') {
    e.metadata = sanitizeAllStrings(e.metadata);
  }
  return e;
}
