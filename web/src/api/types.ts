import type { Numeric } from "../lib/format";

export type ComponentState = "connected" | "offline" | "active" | "awaiting_data" | "unavailable" | "ready";

export interface SystemStatus {
  database: ComponentState;
  telemetry: ComponentState;
  ml_models: ComponentState;
  telemetry_samples: number | null;
  model_artifacts: number;
}

export interface WorkloadConfiguration {
  concurrency?: number;
  target_tps?: number;
  duration_seconds?: number;
  burstiness?: number;
  account_skew?: number;
  seed?: number;
  operation_mix?: Record<string, number>;
}

export type RunStatus = "RUNNING" | "COMPLETED" | "FAILED";

export interface Experiment {
  experiment_id: string;
  scenario: string;
  configuration: WorkloadConfiguration;
  started_at: string;
  completed_at: string | null;
  status: RunStatus;
  actual_tps: Numeric;
  average_latency_ms: Numeric;
  p50_latency_ms: Numeric;
  p95_latency_ms: Numeric;
  p99_latency_ms: Numeric;
  successful_operations: number | null;
  failed_operations: number | null;
  host_cpu_avg_percent: Numeric;
  lock_wait_count_max: Numeric;
  telemetry_sample_count: number | null;
}

export const TARGETS = ["average_latency_ms", "p95_latency_ms", "actual_tps", "host_cpu_avg_percent", "lock_wait_count_max"] as const;
export type Target = (typeof TARGETS)[number];

export interface MetricError {
  absolute_error: number | null;
  percentage_error: number | null;
}

export interface Validation {
  validation_id: string;
  actual_experiment_id: string | null;
  scenario: string;
  workload_configuration: WorkloadConfiguration;
  predicted_metrics: Record<string, number> | null;
  actual_metrics: Record<string, number | null> | null;
  error_metrics: Record<string, MetricError> | null;
  validation_status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  error_message: string | null;
  created_at: string;
}

export interface TargetAccuracy {
  count: number;
  mae: number;
  rmse: number;
  r2: number | null;
  mape: number | null;
}

export interface ValidationSummary {
  validation_count: number;
  pending_or_failed_count: number;
  overall: Partial<Record<Target, TargetAccuracy>>;
}
