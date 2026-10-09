import type { HistogramBucket, SweepParameter, TelemetrySample } from "../api/types";
import { toNumber } from "./format";

export type Range = [number, number];

/** Where a requested value sits against the range the models were trained on. */
export function rangeCheck(value: number, [low, high]: Range): { inside: boolean; fraction: number } {
  const inside = value >= low && value <= high;
  if (high === low) return { inside, fraction: inside ? 0.5 : value > high ? 1 : 0 };
  return { inside, fraction: Math.min(Math.max((value - low) / (high - low), 0), 1) };
}

/** The input ranges recorded at training time. Every model is trained on the same rows, so the first card speaks for all. */
export function trainingRanges(models: { numeric_ranges: Record<string, number[]> }[]): Record<string, Range> {
  const ranges: Record<string, Range> = {};
  for (const [feature, bounds] of Object.entries(models[0]?.numeric_ranges ?? {})) {
    if (bounds.length === 2) ranges[feature] = [bounds[0], bounds[1]];
  }
  return ranges;
}

/** Evenly spaced values for a sweep, inclusive of both ends. Workers are whole numbers. */
export function sweepValues(parameter: SweepParameter, from: number, to: number, steps: number): number[] {
  if (!Number.isFinite(from) || !Number.isFinite(to) || from === to || steps < 2) return [];
  const values = Array.from({ length: steps }, (_, index) => from + ((to - from) * index) / (steps - 1));
  const rounded = values.map((value) => (parameter === "concurrency" ? Math.round(value) : Number(value.toFixed(2))));
  return [...new Set(rounded)];
}

export interface TelemetryPoint {
  seconds: number;
  activeConnections: number | null;
  blockedSessions: number | null;
  lockWaits: number | null;
  cpu: number | null;
}

/** Telemetry samples in time order, with time measured from the first sample. */
export function telemetrySeries(samples: TelemetrySample[]): TelemetryPoint[] {
  const ordered = [...samples].sort((a, b) => a.captured_at.localeCompare(b.captured_at));
  if (ordered.length === 0) return [];
  const start = new Date(ordered[0].captured_at).getTime();
  return ordered.map((sample) => ({
    seconds: Math.round((new Date(sample.captured_at).getTime() - start) / 100) / 10,
    activeConnections: toNumber(sample.active_connections),
    blockedSessions: toNumber(sample.blocked_sessions),
    lockWaits: toNumber(sample.lock_wait_count),
    // The INITIAL reading has no earlier reading to compare with, so psutil reports zero for it.
    cpu: sample.sample_kind === "INITIAL" ? null : toNumber(sample.host_cpu_percent),
  }));
}

export interface HistogramBar {
  label: string;
  count: number;
  share: number;
}

const edge = (value: number) => value.toLocaleString("en-US");

/** Histogram buckets trimmed to the occupied range, each with its height relative to the tallest. */
export function histogramBars(histogram: HistogramBucket[]): HistogramBar[] {
  const first = histogram.findIndex((bucket) => bucket.count > 0);
  if (first === -1) return [];
  const last = histogram.length - 1 - [...histogram].reverse().findIndex((bucket) => bucket.count > 0);
  const occupied = histogram.slice(first, last + 1);
  const tallest = Math.max(...occupied.map((bucket) => bucket.count));
  return occupied.map((bucket) => ({
    label: bucket.upper_ms === null ? `over ${edge(bucket.lower_ms)}` : `${edge(bucket.lower_ms)} to ${edge(bucket.upper_ms)}`,
    count: bucket.count,
    share: bucket.count / tallest,
  }));
}
