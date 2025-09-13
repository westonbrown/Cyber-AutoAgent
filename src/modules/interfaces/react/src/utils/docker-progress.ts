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

export class DockerProgressAggregator {
  private services: string[];
  private onUpdate: (message: string) => void;
  private lastEmit = 0;
  private throttleMs: number;

  // Tracking state
  private pullReady = new Set<string>();
  private created = new Set<string>();
  private started = new Set<string>();

  // Optional current label to display during a phase
  private label: string | null = null;

  constructor(services: string[], onUpdate: (message: string) => void, throttleMs = 500) {
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
    const now = Date.now();
    if (now - this.lastEmit >= this.throttleMs) {
      this.lastEmit = now;
      this.onUpdate(message);
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
    const total = this.services.length || Math.max(1, this.pullReady.size);
    const done = Math.min(this.pullReady.size, total);
    return `${this.label || 'Downloading images…'} ${done}/${total} ready`;
  }

  private summarizeCreate(): string {
    const total = this.services.length || Math.max(1, this.created.size);
    const done = Math.min(this.created.size, total);
    return `Creating containers… ${done}/${total}`;
  }

  private summarizeStart(): string {
    const total = this.services.length || Math.max(1, this.started.size);
    const done = Math.min(this.started.size, total);
    return `Starting containers… ${done}/${total}`;
  }

  update(chunk: string) {
    if (!chunk) return;
    const lines = chunk.split('\n');

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;

      // Pull/image readiness indicators
      // Examples:
      //   "Status: Downloaded newer image for <image>" 
      //   "Status: Image is up to date for <image>"
      //   "Pull complete"
      if (/Status:\s+(Downloaded newer image|Image is up to date)/i.test(line)) {
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
      if (creatingMatch) {
        const svc = this.normalizeService(creatingMatch[1]);
        if (svc) this.created.add(svc);
        else this.created.add(`create-${this.created.size + 1}`);
        this.emitThrottled(this.summarizeCreate());
        continue;
      }

      const startingMatch = line.match(/^Starting\s+([^\s.]+).*$/i);
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
        // Enter pull phase - show generic summary instead of raw line
        this.emitThrottled(this.summarizePull());
        continue;
      }

      if (/Creating\s+/i.test(line)) {
        this.emitThrottled(this.summarizeCreate());
        continue;
      }

      if (/Starting\s+/i.test(line)) {
        this.emitThrottled(this.summarizeStart());
        continue;
      }

      // As a fallback, we can surface infrequent useful notes (sanitized)
      // But generally, avoid emitting arbitrary compose lines to keep UI clean
    }
  }

  finalize() {
    // Emit a final tidy message if we made progress but the last update was ago
    if (this.pullReady.size > 0) {
      this.onUpdate(this.summarizePull());
    }
    if (this.created.size > 0) {
      this.onUpdate(this.summarizeCreate());
    }
    if (this.started.size > 0) {
      this.onUpdate(this.summarizeStart());
    }
  }
}

