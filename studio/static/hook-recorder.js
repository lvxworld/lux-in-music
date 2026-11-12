/* PCM capture stays in the local browser. The output is silent to avoid feedback. */
class HookRecorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(2048); this.used = 0; this.closed = false;
    this.port.onmessage = (event) => {
      if (event.data === "stop") {
        if (this.used) this.port.postMessage({ pcm: this.buffer.slice(0, this.used) });
        this.closed = true; this.port.postMessage({ done: true });
      }
    };
  }
  process(inputs) {
    if (this.closed) return false;
    const input = inputs[0]?.[0];
    if (input) for (const sample of input) {
      this.buffer[this.used++] = sample;
      if (this.used === this.buffer.length) {
        this.port.postMessage({ pcm: this.buffer }, [this.buffer.buffer]);
        this.buffer = new Float32Array(2048); this.used = 0;
      }
    }
    return true;
  }
}
registerProcessor("lux-hook-recorder", HookRecorder);
