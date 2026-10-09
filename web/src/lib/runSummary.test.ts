import { describe, expect, it } from "vitest";
import type { Experiment } from "../api/types";
import { deliveredShare, describeRun, usesCurrentTiming } from "./runSummary";

const run = (overrides: Partial<Experiment> = {}): Experiment => ({
  experiment_id: "1be70501-efd7-4e99-8262-7c402b8c2004",
  scenario: "HIGH_CONCURRENCY_TRANSFER",
  configuration: { concurrency: 32, target_tps: 400, duration_seconds: 10, account_skew: 1.5 },
  started_at: "2026-10-10T03:02:00Z",
  completed_at: "2026-10-10T03:02:14Z",
  status: "COMPLETED",
  actual_tps: "274.7316",
  average_latency_ms: "109.3",
  p50_latency_ms: null,
  p95_latency_ms: "593.6",
  p99_latency_ms: null,
  successful_operations: 4000,
  failed_operations: 0,
  host_cpu_avg_percent: "40.3",
  lock_wait_count_max: 31,
  telemetry_sample_count: 40,
  ...overrides,
});

describe("describeRun", () => {
  it("states the shortfall when the database could not keep up", () => {
    const summary = describeRun(run());
    expect(summary.headline).toBe("High concurrency transfer asked for 400 transactions a second and got 275.");
    expect(summary.detail).toBe("32 workers for 10 s. At the worst moment 31 lock requests were waiting. No operation failed.");
  });

  it("says the target was held when delivery is within five percent", () => {
    const summary = describeRun(run({ scenario: "NORMAL_DAY", configuration: { concurrency: 4, target_tps: 10, duration_seconds: 10 }, actual_tps: "10.06", lock_wait_count_max: 0 }));
    expect(summary.headline).toBe("Normal day held its target of 10 transactions a second.");
    expect(summary.detail).toBe("4 workers for 10 s. Nothing waited on a lock. No operation failed.");
  });

  it("reports failures and never turns a missing measurement into a number", () => {
    const summary = describeRun(run({ actual_tps: null, lock_wait_count_max: null, failed_operations: 3 }));
    expect(summary.headline).toBe("High concurrency transfer finished without a recorded throughput.");
    expect(summary.detail).toBe("32 workers for 10 s. Lock waits were not recorded. 3 operations failed.");
  });

  it("does not describe results for a run that did not complete", () => {
    expect(describeRun(run({ status: "FAILED" })).headline).toBe("High concurrency transfer stopped before it finished.");
    expect(describeRun(run({ status: "RUNNING" })).headline).toBe("High concurrency transfer is still running.");
  });
});

describe("deliveredShare", () => {
  it("is the delivered fraction of the requested rate, capped at one", () => {
    expect(deliveredShare("274.7", 400)).toBeCloseTo(0.687, 3);
    expect(deliveredShare(10.06, 10)).toBe(1);
  });
  it("is absent when either side is missing", () => {
    expect(deliveredShare(null, 400)).toBeNull();
    expect(deliveredShare(12, undefined)).toBeNull();
  });
});

describe("usesCurrentTiming", () => {
  it("recognises runs recorded by the current runner from their stored configuration", () => {
    expect(usesCurrentTiming(run())).toBe(true);
    expect(usesCurrentTiming(run({ configuration: { concurrency: 4, target_tps: 10 } }))).toBe(false);
  });
});
