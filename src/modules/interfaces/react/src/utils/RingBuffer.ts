export class RingBuffer<T> {
  private buf: T[];
  private head = 0;
  private size = 0;
  constructor(private readonly cap: number) {
    if (cap <= 0 || !Number.isFinite(cap)) throw new Error('RingBuffer capacity must be > 0');
    this.buf = new Array(cap);
  }
  push(x: T) {
    const idx = (this.head + this.size) % this.cap;
    this.buf[idx] = x as any;
    if (this.size < this.cap) {
      this.size += 1;
    } else {
      this.head = (this.head + 1) % this.cap;
    }
  }
  pushMany(items: T[]) {
    for (const it of items) this.push(it);
  }
  clear() {
    this.head = 0;
    this.size = 0;
  }
  toArray(): T[] {
    const out: T[] = new Array(this.size);
    for (let i = 0; i < this.size; i++) {
      out[i] = this.buf[(this.head + i) % this.cap] as any;
    }
    return out;
  }
}
