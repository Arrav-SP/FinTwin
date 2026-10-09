import { describe, expect, it } from "vitest";
import type { Job, Validation } from "../api/types";
import { evidenceLabel, jobProgress, validationPoints } from "./jobs";

const job = (overrides: Partial<Job>): Job => ({
  job_id: "j1",
  kind: "workload",
  status: "running",
  request: { kind: "workload", workload: { scenario: "NORMAL_DAY", concurrency: 8, target_tps: 20, duration_seconds: 10, account_skew: 0 }, seed: 42, telemetry_interval: 1 },
  submitted_at: "2026-10-10T04:00:00Z",
  started_at: "2026-10-10T04:00:01Z",
  finished_at: null,
  result: null,
  error: null,
  ...overrides,
});

const at = (iso: string) => new Date(iso).getTime();

describe("jobProgress", () => {
  it("measures a running job against the duration that was asked for", () => {
    expect(jobProgress(job({}), at("2026-10-10T04:00:05Z"))).toEqual({ message: "Running, 4 s of about 10 s", fraction: 0.4 });
  });
  it("stops at full and says it is finishing when the run outlasts its duration", () => {
    expect(jobProgress(job({}), at("2026-10-10T04:00:20Z"))).toEqual({ message: "Finishing, 19 s so far", fraction: 1 });
  });
  it("explains a queued job without inventing progress", () => {
    expect(jobProgress(job({ status: "queued", started_at: null }), at("2026-10-10T04:00:05Z"))).toEqual({ message: "Waiting for an earlier run to finish", fraction: null });
  });
  it("reports how long a finished job took", () => {
    expect(jobProgress(job({ status: "completed", finished_at: "2026-10-10T04:00:12Z" }), at("2026-10-10T05:00:00Z"))).toEqual({ message: "Finished in 11 s", fraction: 1 });
    expect(jobProgress(job({ status: "failed", finished_at: "2026-10-10T04:00:03Z", error: "boom" }), 0)).toEqual({ message: "Stopped after 2 s", fraction: null });
  });
});

const validation = (overrides: Partial<Validation>): Validation => ({
  validation_id: "v1",
  actual_experiment_id: "e1",
  scenario: "NORMAL_DAY",
  workload_configuration: { concurrency: 10, target_tps: 10 },
  predicted_metrics: { predicted_average_latency_ms: 9.5, predicted_actual_tps: 12.1 },
  actual_metrics: { average_latency_ms: 18.8, actual_tps: 10.1 },
  error_metrics: {},
  validation_status: "COMPLETED",
  error_message: null,
  created_at: "2026-10-10T04:00:00Z",
  ...overrides,
});

describe("validationPoints", () => {
  it("pairs prediction and measurement for one metric across completed checks", () => {
    const points = validationPoints([validation({}), validation({ validation_id: "v2", predicted_metrics: { predicted_average_latency_ms: 10 }, actual_metrics: { average_latency_ms: 30 } })], "average_latency_ms");
    expect(points.map(({ predicted, measured }) => [predicted, measured])).toEqual([[9.5, 18.8], [10, 30]]);
  });
  it("leaves out checks that failed or lack either value", () => {
    const points = validationPoints([validation({ validation_status: "FAILED" }), validation({ actual_metrics: { average_latency_ms: null } }), validation({ predicted_metrics: null })], "average_latency_ms");
    expect(points).toEqual([]);
  });
});

describe("evidenceLabel", () => {
  it("turns a stored field name into words", () => {
    expect(evidenceLabel("host_memory_avg_percent")).toBe("Host memory average (%)");
    expect(evidenceLabel("lock_wait_count_max")).toBe("Lock requests waiting, peak");
    expect(evidenceLabel("p95_latency_ms")).toBe("P95 latency (ms)");
    expect(evidenceLabel("some_new_field")).toBe("Some new field");
  });
});
