import { describe, expect, it } from "vitest";
import { logDomain, logTicks } from "./scale";

describe("logDomain", () => {
  it("pads the data range on both sides so no point sits on an axis", () => {
    const [low, high] = logDomain([10, 400])!;
    expect(low).toBeLessThan(10);
    expect(low).toBeGreaterThan(5);
    expect(high).toBeGreaterThan(400);
    expect(high).toBeLessThan(700);
  });
  it("ignores values a log scale cannot show", () => {
    expect(logDomain([0, -3, 20, 50])![0]).toBeGreaterThan(10);
  });
  it("has no domain without positive data", () => {
    expect(logDomain([])).toBeNull();
    expect(logDomain([0])).toBeNull();
  });
});

describe("logTicks", () => {
  it("uses 1, 2, 5 steps inside the domain", () => {
    expect(logTicks([7, 560])).toEqual([10, 20, 50, 100, 200, 500]);
  });
  it("still gives ticks for a narrow range", () => {
    expect(logTicks([6, 16])).toEqual([10]);
    expect(logTicks([11, 14]).length).toBeGreaterThan(0);
  });
});
