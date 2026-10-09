import type { Experiment } from "../api/types";
import { type Numeric, scenarioLabel, toNumber } from "./format";

/** A run counts as having held its target when it delivered at least this share of it. */
const HELD_TARGET_SHARE = 0.95;

export interface RunSummary {
  headline: string;
  detail: string;
}

const plural = (count: number, one: string, many: string) => `${count.toLocaleString("en-US")} ${count === 1 ? one : many}`;

/** Delivered throughput as a fraction of the requested rate, capped at 1. Null when either is unknown. */
export function deliveredShare(actual: Numeric, target: Numeric): number | null {
  const delivered = toNumber(actual);
  const requested = toNumber(target);
  if (delivered === null || requested === null || requested <= 0) return null;
  return Math.min(delivered / requested, 1);
}

/**
 * The current runner stores `account_skew` with every run and times an operation without
 * the per-operation account lookup the earlier runner included. Latency from the two is
 * not comparable, so charts need to tell them apart.
 */
export function usesCurrentTiming(run: Experiment): boolean {
  return "account_skew" in run.configuration;
}

/** A plain-language account of one run, built only from values the API returned for it. */
export function describeRun(run: Experiment): RunSummary {
  const name = scenarioLabel(run.scenario);
  const { concurrency, target_tps: target, duration_seconds: duration } = run.configuration;
  const setup = `${concurrency ?? "An unrecorded number of"} workers for ${duration ?? "an unrecorded number of"} s.`;

  if (run.status === "RUNNING") return { headline: `${name} is still running.`, detail: setup };
  if (run.status === "FAILED") return { headline: `${name} stopped before it finished.`, detail: setup };

  const delivered = toNumber(run.actual_tps);
  const share = deliveredShare(delivered, target);
  let headline: string;
  if (delivered === null || share === null) headline = `${name} finished without a recorded throughput.`;
  else if (share < HELD_TARGET_SHARE) headline = `${name} asked for ${target} transactions a second and got ${Math.round(delivered)}.`;
  else headline = `${name} held its target of ${target} transactions a second.`;

  const waits = toNumber(run.lock_wait_count_max);
  const locks = waits === null ? "Lock waits were not recorded." : waits > 0 ? `At the worst moment ${plural(waits, "lock request was", "lock requests were")} waiting.` : "Nothing waited on a lock.";

  const failed = run.failed_operations;
  const failures = failed === null ? "Failures were not recorded." : failed > 0 ? `${plural(failed, "operation", "operations")} failed.` : "No operation failed.";

  return { headline, detail: `${setup} ${locks} ${failures}` };
}
