/** Audible confirmations for RFID reads (FR 06): found, misplaced and error/missing. */

export type Confirmation = "ok" | "warn" | "error";
type Tone = { freq: number; ms: number; gapMs: number };

export const PATTERNS: Record<Confirmation, Tone[]> = {
  ok: [{ freq: 880, ms: 120, gapMs: 0 }],
  warn: [
    { freq: 660, ms: 100, gapMs: 80 },
    { freq: 660, ms: 100, gapMs: 0 },
  ],
  error: [{ freq: 300, ms: 600, gapMs: 0 }],
};

let shared: AudioContext | null = null;

function defaultContext(): AudioContext | null {
  if (typeof window === "undefined" || !("AudioContext" in window)) return null;
  shared ??= new AudioContext();
  return shared;
}

export function playConfirmation(kind: Confirmation, ctx: AudioContext | null = defaultContext()): void {
  if (!ctx) return;
  let at = ctx.currentTime;
  for (const tone of PATTERNS[kind]) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = tone.freq;
    gain.gain.value = 0.15;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(at);
    osc.stop(at + tone.ms / 1000);
    at += (tone.ms + tone.gapMs) / 1000;
  }
}
