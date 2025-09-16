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

  // editor/python_repl/etc.: leave as-is except shallow clone done above
  return toolInput;
}

function normalizeToolName(e: AnyEvent): string {
  return (e.toolName || e.tool_name || e.tool || '').toString();
}

// Normalize event in-place (returns a new shallow-cloned object)
export function normalizeEvent(event: AnyEvent): AnyEvent {
  if (!event || typeof event !== 'object') return event;

  const e: AnyEvent = { ...event };

  // Standardize common timestamp field to ISO string if present
  if (e.timestamp && typeof e.timestamp === 'number') {
    try { e.timestamp = new Date(e.timestamp).toISOString(); } catch {}
  }

  switch (e.type) {
    case 'tool_start': {
      const toolName = e.toolName || e.tool_name || 'tool';
      const rawInput = e.args !== undefined ? e.args : (e.tool_input !== undefined ? e.tool_input : {});
      const normalizedInput = normalizeToolInput(toolName, rawInput);

      e.tool_name = toolName;
      e.tool_input = normalizedInput;
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

    default:
      return e;
  }
}
