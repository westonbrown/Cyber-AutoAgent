export class ByteBudgetRingBuffer<T> {
  private items: T[] = [];
  private byteLimit: number;
  private currentBytes = 0;
  private estimator: (item: T) => number;

  constructor(byteLimit: number, estimator?: (item: T) => number) {
    this.byteLimit = Math.max(1024, byteLimit | 0);
    this.estimator = estimator || ((item: any) => {
      // Roughly estimate size focusing on common fields
      try {
        if (item == null) return 0;
        let bytes = 64; // base overhead per item
        if (typeof item === 'string') return bytes + item.length;
        if (typeof item === 'object') {
          const s = (item as any);
          const addStr = (v: any) => { if (typeof v === 'string') bytes += v.length; };
          addStr(s.content);
          addStr(s.command);
          addStr(s.message);
          addStr(s.tool_name);
          addStr(s.tool);
          // If content is non-string but serializable, add minimal
          if (s.content && typeof s.content === 'object' && !Array.isArray(s.content)) {
            bytes += 128;
          }
          return bytes;
        }
        return 32;
      } catch {
        return 128;
      }
    });
  }

  clear() {
    this.items = [];
    this.currentBytes = 0;
  }

  push(item: T) {
    const size = this.estimator(item);
    this.items.push(item);
    this.currentBytes += size;
    this.enforceBudget();
  }

  pushMany(items: T[]) {
    for (const it of items) {
      this.push(it);
    }
  }

  private enforceBudget() {
    // Remove from the front until under budget
    if (this.currentBytes <= this.byteLimit) return;
    // Remove 10% headroom in one go to reduce churn
    const target = Math.floor(this.byteLimit * 0.9);
    while (this.items.length > 0 && this.currentBytes > target) {
      const removed = this.items.shift()!;
      this.currentBytes -= this.estimator(removed);
    }
  }

  toArray(): T[] {
    return this.items.slice();
  }

  size(): number {
    return this.items.length;
  }

  bytes(): number {
    return this.currentBytes;
  }
}
