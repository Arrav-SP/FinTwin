import type { Job, Target, Validation } from "../api/types";

const seconds = (from: string, to: number) => Math.max(Math.round((to - new Date(from).getTime()) / 1000), 0);

/**
 * What to tell the person waiting on a background job. The fraction is elapsed time over the
 * requested duration, which is an estimate: the server does not report progress.
 */
export function jobProgress(job: Job, now: number): { message: string; fraction: number | null } {
  if (job.status === "queued" || !job.started_at) return { message: "Waiting for an earlier run to finish", fraction: null };
  if (job.status === "completed" || job.status === "failed") {
    const took = seconds(job.started_at, job.finished_at ? new Date(job.finished_at).getTime() : now);
    return job.status === "completed" ? { message: `Finished in ${took} s`, fraction: 1 } : { message: `Stopped after ${took} s`, fraction: null };
  }
  const elapsed = seconds(job.started_at, now);
  const planned = job.request.workload.duration_seconds;
  if (elapsed >= planned) return { message: `Finishing, ${elapsed} s so far`, fraction: 1 };
  return { message: `Running, ${elapsed} s of about ${planned} s`, fraction: elapsed / planned };
}

export interface ValidationPoint {
  id: string;
  scenario: string;
  predicted: number;
  measured: number;
}

/** One point per completed check that has both a predicted and a measured value for the metric. */
export function validationPoints(validations: Validation[], target: Target): ValidationPoint[] {
  return validations.flatMap((item) => {
    if (item.validation_status !== "COMPLETED") return [];
    const predicted = item.predicted_metrics?.[`predicted_${target}`];
    const measured = item.actual_metrics?.[target];
    if (typeof predicted !== "number" || typeof measured !== "number") return [];
    return [{ id: item.validation_id, scenario: item.scenario, predicted, measured }];
  });
}

const EVIDENCE_LABELS: Record<string, string> = {
  host_cpu_avg_percent: "Host CPU average (%)",
  host_memory_avg_percent: "Host memory average (%)",
  active_connections_max: "Active connections, peak",
  max_connections: "Connection limit",
  lock_wait_count_max: "Lock requests waiting, peak",
  average_latency_ms: "Average latency (ms)",
  p95_latency_ms: "P95 latency (ms)",
  ratio: "P95 over average",
  db_cache_hit_ratio: "Cache hit ratio (%)",
};

/** A readable name for a field the advisor cites as evidence. */
export function evidenceLabel(field: string): string {
  if (EVIDENCE_LABELS[field]) return EVIDENCE_LABELS[field];
  const words = field.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
