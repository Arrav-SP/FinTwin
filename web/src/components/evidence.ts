import { TARGETS, type Target, type Validation } from "../api/types";

export interface EvidenceRow {
  key: Target;
  predicted: number;
  measured: number;
  percentageError: number | null;
}

/** Horizontal positions of the predicted and measured markers on a shared scale starting at zero. */
export function gapGeometry(predicted: number, measured: number, width: number) {
  const top = Math.max(predicted, measured) * 1.15;
  if (top <= 0) return { predictedX: 0, measuredX: 0 };
  return { predictedX: (predicted / top) * width, measuredX: (measured / top) * width };
}

export function pairValidationMetrics(validation: Pick<Validation, "predicted_metrics" | "actual_metrics" | "error_metrics">): EvidenceRow[] {
  const rows: EvidenceRow[] = [];
  for (const key of TARGETS) {
    const predicted = validation.predicted_metrics?.[`predicted_${key}`];
    const measured = validation.actual_metrics?.[key];
    if (typeof predicted !== "number" || typeof measured !== "number") continue;
    rows.push({ key, predicted, measured, percentageError: validation.error_metrics?.[key]?.percentage_error ?? null });
  }
  return rows;
}

export const TARGET_LABELS: Record<Target, { label: string; unit: string }> = {
  average_latency_ms: { label: "Average latency", unit: "ms" },
  p95_latency_ms: { label: "P95 latency", unit: "ms" },
  actual_tps: { label: "Throughput", unit: "TPS" },
  host_cpu_avg_percent: { label: "Host CPU", unit: "%" },
  lock_wait_count_max: { label: "Lock waits", unit: "" },
};
