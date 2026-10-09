import { describe, expect, it } from "vitest";
import { histogramBars, rangeCheck, sweepValues, telemetrySeries, trainingRanges } from "./workload";

describe("rangeCheck", () => {
  it("places a value inside the trained range", () => {
    expect(rangeCheck(8, [4, 12])).toEqual({ inside: true, fraction: 0.5 });
  });
  it("flags a value outside it and pins the marker to the nearer end", () => {
    expect(rangeCheck(50, [4, 12])).toEqual({ inside: false, fraction: 1 });
    expect(rangeCheck(1, [4, 12])).toEqual({ inside: false, fraction: 0 });
  });
  it("handles a range that is a single value", () => {
    expect(rangeCheck(10, [10, 10])).toEqual({ inside: true, fraction: 0.5 });
    expect(rangeCheck(30, [10, 10]).inside).toBe(false);
  });
});

describe("trainingRanges", () => {
  it("takes the ranges every model agrees on from the first model card", () => {
    const ranges = trainingRanges([{ numeric_ranges: { concurrency: [4, 12], target_tps: [10, 30] } }, { numeric_ranges: { concurrency: [4, 12] } }]);
    expect(ranges).toEqual({ concurrency: [4, 12], target_tps: [10, 30] });
  });
  it("is empty when no model exists", () => {
    expect(trainingRanges([])).toEqual({});
  });
});

describe("sweepValues", () => {
  it("spreads evenly between the two ends, inclusive", () => {
    expect(sweepValues("target_tps", 10, 50, 5)).toEqual([10, 20, 30, 40, 50]);
  });
  it("uses whole workers and drops duplicates", () => {
    expect(sweepValues("concurrency", 1, 4, 8)).toEqual([1, 2, 3, 4]);
  });
  it("needs two distinct ends", () => {
    expect(sweepValues("target_tps", 20, 20, 5)).toEqual([]);
  });
});

describe("telemetrySeries", () => {
  it("orders samples by time and measures seconds from the first", () => {
    const series = telemetrySeries([
      { sample_kind: "FINAL", captured_at: "2026-10-10T03:02:10Z", active_connections: 3, waiting_connections: 0, blocked_sessions: 1, lock_wait_count: 2, cache_hit_ratio: "99.5", host_cpu_percent: "40.5", host_memory_percent: "90" },
      { sample_kind: "INITIAL", captured_at: "2026-10-10T03:02:00Z", active_connections: 1, waiting_connections: 0, blocked_sessions: 0, lock_wait_count: 0, cache_hit_ratio: "99.5", host_cpu_percent: "0", host_memory_percent: "90" },
    ]);
    expect(series.map((point) => point.seconds)).toEqual([0, 10]);
    expect(series[1]).toMatchObject({ activeConnections: 3, lockWaits: 2, blockedSessions: 1, cpu: 40.5 });
  });
  it("leaves the first CPU reading out because psutil reports zero before it has a baseline", () => {
    const series = telemetrySeries([{ sample_kind: "INITIAL", captured_at: "2026-10-10T03:02:00Z", active_connections: 1, waiting_connections: 0, blocked_sessions: 0, lock_wait_count: 0, cache_hit_ratio: null, host_cpu_percent: "0", host_memory_percent: "90" }]);
    expect(series[0].cpu).toBeNull();
  });
});

describe("histogramBars", () => {
  const histogram = [
    { lower_ms: 0, upper_ms: 1, count: 0 },
    { lower_ms: 1, upper_ms: 2, count: 0 },
    { lower_ms: 2, upper_ms: 5, count: 7 },
    { lower_ms: 5, upper_ms: 10, count: 0 },
    { lower_ms: 10, upper_ms: 20, count: 14 },
    { lower_ms: 20, upper_ms: 50, count: 0 },
    { lower_ms: 5000, upper_ms: null, count: 0 },
  ];
  it("drops the empty buckets at both ends but keeps gaps in the middle", () => {
    const bars = histogramBars(histogram);
    expect(bars.map((bar) => bar.label)).toEqual(["2 to 5", "5 to 10", "10 to 20"]);
    expect(bars.map((bar) => bar.share)).toEqual([0.5, 0, 1]);
  });
  it("labels the open-ended bucket", () => {
    expect(histogramBars([{ lower_ms: 5000, upper_ms: null, count: 3 }])[0].label).toBe("over 5,000");
  });
  it("is empty when nothing was recorded", () => {
    expect(histogramBars([{ lower_ms: 0, upper_ms: 1, count: 0 }])).toEqual([]);
  });
});
