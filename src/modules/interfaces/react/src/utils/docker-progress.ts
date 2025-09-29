/**
 * Docker Compose Progress Aggregator
 *
 * Condenses noisy docker-compose output (Downloading/Extracting per-layer logs)
 * into high-level progress messages appropriate for UI display.
 *
 * Strategy:
 * - Track service-level progress using recognizable markers in compose output
 * - Suppress per-layer logs (Downloading [====], Extracting, etc.)
 * - Emit throttled updates (default 500ms) with concise messages:
 *   • "Downloading images… X/Y ready"
 *   • "Creating containers… A/Y"
 *   • "Starting containers… B/Y"
 * - Handle both `up` and `build` flows
 */

export interface DockerProgressUpdateMeta {
  phase: 'pull' | 'build' | 'create' | 'start';
  ratio: number;           // 0..1 within current phase
  pullReady: number;       // count of pulled images (approx)
  created: number;         // containers created
  started: number;         // containers started
  total: number;           // expected services/images/steps
}

export class DockerProgressAggregator {
  private services: string[];
  private onUpdate: (message: string, meta?: DockerProgressUpdateMeta) => void;
  private lastEmit = 0;
  private throttleMs: number;

  // Tracking state
  private pullReady = new Set<string>();
  private created = new Set<string>();
  private started = new Set<string>();

  // Optional current label to display during a phase
  private label: string | null = null;
  private currentPhase: DockerProgressUpdateMeta['phase'] = 'pull';
  // Build tracking
  private buildTotal = 0;
  private buildDone = 0;

constructor(services: string[], onUpdate: (message: string, meta?: DockerProgressUpdateMeta) => void, throttleMs = 500) {
    this.services = services || [];
    this.onUpdate = onUpdate;
    this.throttleMs = throttleMs;
  }

  setLabel(label: string) {
    this.label = label;
  }

  // Normalize a token to a service name if possible
  private normalizeService(token: string): string | null {
    if (!token) return null;
    // docker-compose often prints service names exactly as configured
    // but sometimes includes prefixes/suffixes. Try direct match first.
    if (this.services.includes(token)) return token;
    // Try fuzzy match: service token at end or start
    const match = this.services.find(s => token.endsWith(s) || token.startsWith(s));
    return match || null;
  }

private emitThrottled(message: string) {
    const meta = this.computeMeta();
    this.emitThrottledWithMeta(message, meta);
  }

  private emitThrottledWithMeta(message: string, meta: DockerProgressUpdateMeta) {
    const now = Date.now();
if (now - this.lastEmit >= this.throttleMs) {
      this.lastEmit = now;
      this.onUpdate(message, meta);
    }
  }

  private suppressNoisy(line: string): boolean {
    const l = line.trim();
    if (!l) return true;
    const noisyPatterns = [
      /Downloading \[/i,
      /Extracting \[/i,
      /Verifying Checksum/i,
      /Pulling fs layer/i,
      /Digest:/i,
      /Status:\s+Downloading/i,
      /Layer already exists/i,
      /Waiting/i,
      /^$/,
    ];
    return noisyPatterns.some(rx => rx.test(l));
  }

private summarizePull(): string {
    this.currentPhase = 'pull';
    const total = this.services.length || Math.max(1, this.pullReady.size);
    const done = Math.min(this.pullReady.size, total);
    return `${this.label || 'Downloading images…'} ${done}/${total} ready`;
  }

private summarizeCreate(): string {
    this.currentPhase = 'create';
    const total = this.services.length || Math.max(1, this.created.size);
    const done = Math.min(this.created.size, total);
    return `Creating containers… ${done}/${total}`;
  }

private summarizeStart(): string {
    this.currentPhase = 'start';
    const total = this.services.length || Math.max(1, this.started.size);
    const done = Math.min(this.started.size, total);
    return `Starting containers… ${done}/${total}`;
  }

  private summarizeBuild(): string {
    this.currentPhase = 'build';
    const total = this.buildTotal || Math.max(1, this.buildDone);
    const done = Math.min(this.buildDone, total);
    return `Building image… ${done}/${total}`;
  }

  update(chunk: string) {
    if (!chunk) return;
    const lines = chunk.split('\n');

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;

      // Build detection and step tracking (BuildKit)
      // Examples:
      //   "Building cyber-autoagent"
      //   " => [ 2/17] RUN apt-get update ..."
      //   " => exporting to image"
      if (/^Building\s+/i.test(line) || /^#\d+\s+\[\d+\/\d+\]/.test(line)) {
        this.currentPhase = 'build';
        // no immediate summary; wait for step lines
      }

      const buildStep = line.match(/\[\s*(\d+)\s*\/\s*(\d+)\s*\]/);
      if (buildStep) {
        const cur = parseInt(buildStep[1], 10) || 0;
        const tot = parseInt(buildStep[2], 10) || 0;
        if (tot > 0) this.buildTotal = Math.max(this.buildTotal, tot);
        // consider a step done when we advance to next index
        this.buildDone = Math.max(this.buildDone, Math.min(cur - 1, tot));
        this.emitThrottled(this.summarizeBuild());
        continue;
      }

      if (/exporting to image/i.test(line) || /exporting layers/i.test(line) || /exporting manifest/i.test(line)) {
        this.currentPhase = 'build';
        if (this.buildTotal > 0) this.buildDone = this.buildTotal;
        this.emitThrottled(this.summarizeBuild());
        continue;
      }

      // Pull/image readiness indicators
      // Examples:
      //   "Status: Downloaded newer image for <image>" 
      //   "Status: Image is up to date for <image>"
      //   "Pull complete"
if (/Status:\s+(Downloaded newer image|Image is up to date)/i.test(line)) {
        this.currentPhase = 'pull';
        // Try to map to a service via trailing token after 'for '
        const m = line.match(/for\s+([\w\-.:/]+)\s*$/i);
        let service: string | null = null;
        if (m && m[1]) {
          service = this.normalizeService(m[1]);
        }
        // If we can't map, just record a generic completion (cap at total services)
        if (service) this.pullReady.add(service);
        else if (this.pullReady.size < Math.max(1, this.services.length)) this.pullReady.add(`img-${this.pullReady.size + 1}`);

        this.emitThrottled(this.summarizePull());
        continue;
      }

if (/Pull complete/i.test(line)) {
        this.currentPhase = 'pull';
        // Count as a partial milestone toward image readiness
        if (this.pullReady.size < Math.max(1, this.services.length)) {
          this.pullReady.add(`layer-${this.pullReady.size + 1}`);
          this.emitThrottled(this.summarizePull());
        }
        continue;
      }

      // Creating/Starting containers lines often look like:
      //   "Creating service_name ... done"
      //   "Starting service_name ... done"
const creatingMatch = line.match(/^Creating\s+([^\s.]+).*$/i);
      if (creatingMatch) { this.currentPhase = 'create'; }
      if (creatingMatch) {
        const svc = this.normalizeService(creatingMatch[1]);
        if (svc) this.created.add(svc);
        else this.created.add(`create-${this.created.size + 1}`);
        this.emitThrottled(this.summarizeCreate());
        continue;
      }

const startingMatch = line.match(/^Starting\s+([^\s.]+).*$/i);
      if (startingMatch) { this.currentPhase = 'start'; }
      if (startingMatch) {
        const svc = this.normalizeService(startingMatch[1]);
        if (svc) this.started.add(svc);
        else this.started.add(`start-${this.started.size + 1}`);
        this.emitThrottled(this.summarizeStart());
        continue;
      }

      // If it's a noisy progress line, skip it entirely
      if (this.suppressNoisy(line)) {
        continue;
      }

      // Non-noisy status hints: emit as-is but throttled and compact
if (/Pulling\s+/i.test(line)) {
        this.currentPhase = 'pull';
        // Enter pull phase - show generic summary instead of raw line
        this.emitThrottled(this.summarizePull());
        continue;
      }

if (/Creating\s+/i.test(line)) {
        this.currentPhase = 'create';
        this.emitThrottled(this.summarizeCreate());
        continue;
      }

if (/Starting\s+/i.test(line)) {
        this.currentPhase = 'start';
        this.emitThrottled(this.summarizeStart());
        continue;
      }

      // As a fallback, we can surface infrequent useful notes (sanitized)
      // But generally, avoid emitting arbitrary compose lines to keep UI clean
    }
  }

  finalize() {
    const meta = this.computeMeta();
    // Emit a final tidy message if we made progress but the last update was ago
if (this.pullReady.size > 0) {
      this.onUpdate(this.summarizePull(), meta);
    }
    if (this.created.size > 0) {
      this.onUpdate(this.summarizeCreate(), meta);
    }
    if (this.started.size > 0) {
      this.onUpdate(this.summarizeStart(), meta);
    }
  }

  private computeMeta(): DockerProgressUpdateMeta {
    let total = this.services.length || 1;
    let ratio = 0;
    if (this.currentPhase === 'pull') {
      total = this.services.length || Math.max(1, this.pullReady.size);
      ratio = Math.min(1, total ? this.pullReady.size / total : 0);
    } else if (this.currentPhase === 'build') {
      total = this.buildTotal || Math.max(1, this.buildDone);
      ratio = Math.min(1, total ? this.buildDone / total : 0);
    } else if (this.currentPhase === 'create') {
      total = this.services.length || Math.max(1, this.created.size);
      ratio = Math.min(1, total ? this.created.size / total : 0);
    } else {
      total = this.services.length || Math.max(1, this.started.size);
      ratio = Math.min(1, total ? this.started.size / total : 0);
    }
    return {
      phase: this.currentPhase,
      ratio,
      pullReady: this.pullReady.size,
      created: this.created.size,
      started: this.started.size,
      total
    };
  }
}

