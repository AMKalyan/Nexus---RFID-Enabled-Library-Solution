import { expect, it, vi } from "vitest";
import { PATTERNS, playConfirmation } from "./audio";

it("defines distinct confirmation patterns", () => {
  expect(PATTERNS.ok).toHaveLength(1);
  expect(PATTERNS.warn).toHaveLength(2);
  expect(PATTERNS.error[0].freq).toBeLessThan(PATTERNS.ok[0].freq);
  expect(PATTERNS.error[0].ms).toBeGreaterThan(PATTERNS.ok[0].ms);
});

it("schedules one oscillator per tone", () => {
  const start = vi.fn();
  const stop = vi.fn();
  const ctx = {
    currentTime: 0,
    destination: {},
    createOscillator: () => ({ frequency: { value: 0 }, connect: () => undefined, start, stop }),
    createGain: () => ({ gain: { value: 0 }, connect: () => undefined }),
  } as unknown as AudioContext;
  playConfirmation("warn", ctx);
  expect(start).toHaveBeenCalledTimes(2);
  expect(stop).toHaveBeenCalledTimes(2);
});

it("does nothing when audio is unavailable", () => {
  expect(() => playConfirmation("ok", null)).not.toThrow();
});
