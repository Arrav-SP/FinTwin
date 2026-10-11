import type { Numeric } from "../lib/format";

export type ComponentState = "connected" | "offline" | "active" | "awaiting_data" | "unavailable" | "ready";

export interface SystemStatus {
  database: ComponentState;
  telemetry: ComponentState;
  ml_models: ComponentState;
  telemetry_samples: number | null;
  model_artifacts: number;
}

export interface RunLimits {
  max_concurrency: number;
  max_target_tps: number;
  max_duration_seconds: number;
}

/** What this browser may do. A private server is unrestricted; a public one asks for a sign-in before running. */
export interface Session {
  public: boolean;
  sign_in_available: boolean;
  signed_in: boolean;
  login: string | null;
  can_run: boolean;
  run_limits: RunLimits;
  runs_per_day: number | null;
  runs_left: number | null;
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
  /** True when the signed-in person started this run. The server never says who else did. */
  mine?: boolean;
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
  /** Checks left out because they were predicted before the current models were trained. */
  earlier_count: number;
  overall: Partial<Record<Target, TargetAccuracy>>;
}

export interface ExperimentDetail extends Experiment {
  requested_operations: number | null;
  completed_operations: number | null;
  error_rate: Numeric;
  active_connections_max: number | null;
  max_connections: number | null;
  blocked_sessions_max: number | null;
  db_deadlocks_delta: number | null;
  db_cache_hit_ratio: Numeric;
  host_memory_avg_percent: Numeric;
}

export interface TelemetrySample {
  sample_kind: "INITIAL" | "SAMPLE" | "FINAL";
  captured_at: string;
  active_connections: number | null;
  waiting_connections: number | null;
  blocked_sessions: number | null;
  lock_wait_count: number | null;
  cache_hit_ratio: Numeric;
  host_cpu_percent: Numeric;
  host_memory_percent: Numeric;
}

export interface ExperimentDetailResponse {
  experiment: ExperimentDetail;
  telemetry: TelemetrySample[];
  validations: Pick<Validation, "validation_id" | "validation_status" | "predicted_metrics" | "actual_metrics" | "error_metrics" | "created_at">[];
}

export interface OperationLatency {
  operation: string;
  count: number;
  failed: number;
  average_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  max_latency_ms: number;
  average_queue_wait_ms: number | null;
}

export interface HistogramBucket {
  lower_ms: number;
  upper_ms: number | null;
  count: number;
}

export interface LatencyBreakdown {
  count: number;
  operations: OperationLatency[];
  histogram: HistogramBucket[];
}

export interface ModelScores {
  mae: number;
  rmse: number;
  r2: number | null;
}

export interface ModelCard {
  target: Target;
  algorithm: string;
  training_samples: number;
  test_samples: number;
  metrics: ModelScores;
  /** Present on models trained with grouped cross-validation. */
  configurations?: number;
  cv_folds?: number;
  /** What each fold leaves out: "load settings" since evaluation began holding out whole loads. */
  held_out?: string;
  baseline?: ModelScores;
  repeat_spread?: number | null;
  scenario_values: string[];
  numeric_ranges: Record<string, number[]>;
  trained_at: string;
}

export interface ScenarioCatalogue {
  scenarios: { scenario: string; operation_mix: Record<string, number> }[];
  limits: RunLimits;
}

/** What a person chooses when describing a workload. */
export interface WorkloadInput {
  scenario: string;
  concurrency: number;
  target_tps: number;
  duration_seconds: number;
  account_skew: number;
}

export interface Prediction {
  workload: WorkloadInput;
  predictions: Record<string, number>;
  warnings: string[];
}

export type SweepParameter = "concurrency" | "target_tps";

export interface Sweep {
  parameter: SweepParameter;
  values: number[];
  model_derived_sensitivity: Record<string, number>;
  results: { configuration: WorkloadInput; predictions: Record<string, number>; warnings: string[] }[];
  warnings: string[];
}

export type JobKind = "workload" | "validation";
export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface JobRequest {
  kind: JobKind;
  workload: WorkloadInput;
  seed?: number;
  telemetry_interval?: number;
}

export interface Job {
  job_id: string;
  kind: JobKind;
  status: JobStatus;
  request: JobRequest;
  submitted_at: string;
  started_at: string | null;
  finished_at: string | null;
  result: { experiment_id: string | null; validation_id?: string } | null;
  error: string | null;
}

export interface Recommendation {
  recommendation_id: string;
  category: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  title: string;
  description: string;
  evidence: Record<string, Numeric>;
  recommended_action: string;
  expected_benefit: string;
  requires_validation: boolean;
}

export interface Assessment {
  overall_status: "NORMAL" | "ELEVATED";
  summary: string;
  recommendations: Recommendation[];
  query_statistics_available: boolean;
  warnings?: string[];
}
