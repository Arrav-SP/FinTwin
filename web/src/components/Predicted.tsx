import type { ModelCard } from "../api/types";
import { formatDateTime, formatNumber } from "../lib/format";
import { type Range, rangeCheck } from "../lib/workload";
import { TARGET_LABELS } from "./evidence";

const ORDER = ["actual_tps", "average_latency_ms", "p95_latency_ms", "host_cpu_avg_percent", "lock_wait_count_max"] as const;
const PREDICTED_LABELS: Record<(typeof ORDER)[number], string> = {
  actual_tps: "Predicted throughput",
  average_latency_ms: "Predicted average latency",
  p95_latency_ms: "Predicted P95 latency",
  host_cpu_avg_percent: "Predicted host CPU",
  lock_wait_count_max: "Predicted lock waits",
};

/** Predicted figures. The dashed rule under each marks it as an estimate, not a measurement. */
export function PredictedFigures({ predictions }: { predictions: Record<string, number> }) {
  return (
    <dl className="m-0 grid grid-cols-2 gap-x-8 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
      {ORDER.filter((key) => typeof predictions[`predicted_${key}`] === "number").map((key) => {
        const { unit } = TARGET_LABELS[key];
        return (
          <div key={key}>
            <dt className="text-xs text-graphite">{PREDICTED_LABELS[key]}</dt>
            <dd className="m-0 mt-2 border-b border-dashed border-paper pb-3">
              <span className="num text-figure font-medium leading-none tracking-tight">{formatNumber(predictions[`predicted_${key}`], key === "lock_wait_count_max" ? 0 : 1)}</span>
              {unit && <span className="ml-1.5 text-graphite">{unit}</span>}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

const INPUTS: { feature: string; label: string }[] = [
  { feature: "concurrency", label: "Workers" },
  { feature: "target_tps", label: "Requested rate (TPS)" },
  { feature: "duration_seconds", label: "Duration (s)" },
  { feature: "account_skew", label: "Hot-account skew" },
];

/** Each input set against the range the models saw in training. Outside it, a prediction is an extrapolation. */
export function TrainedRange({ workload, ranges }: { workload: Record<string, number | string>; ranges: Record<string, Range> }) {
  return (
    <ul className="m-0 grid list-none gap-x-10 gap-y-5 p-0 md:grid-cols-2">
      {INPUTS.map(({ feature, label }) => {
        const value = Number(workload[feature]);
        const range = ranges[feature];
        if (!range) {
          return (
            <li key={feature}>
              <p>
                {label}: <span className="num">{formatNumber(value, 1)}</span>
              </p>
              <p className="mt-1 text-xs text-amber">The models were trained before this setting existed, so they ignore it.</p>
            </li>
          );
        }
        const { inside, fraction } = rangeCheck(value, range);
        return (
          <li key={feature}>
            <p className="flex justify-between gap-4">
              <span>
                {label}: <span className="num font-medium">{formatNumber(value, 1)}</span>
              </span>
              <span className={`num text-xs ${inside ? "text-graphite" : "text-amber"}`}>
                {inside ? "inside" : "outside"} {formatNumber(range[0], 0)} to {formatNumber(range[1], 0)}
              </span>
            </p>
            <div className="relative mt-3 h-4" aria-hidden="true">
              <div className="absolute inset-x-0 top-1/2 h-px bg-rule" />
              <div className="absolute inset-x-[20%] top-1/2 h-1.5 -translate-y-1/2 bg-rule-strong" />
              <span className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-dashed bg-ink ${inside ? "border-paper" : "border-amber"}`} style={{ left: `${inside ? 20 + fraction * 60 : fraction === 0 ? 8 : 92}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Where the estimates come from, in the models' own recorded terms. */
export function ModelProvenance({ models }: { models: ModelCard[] }) {
  if (models.length === 0) return null;
  const { training_samples, test_samples, trained_at } = models[0];
  return (
    <p className="text-xs text-graphite">
      Models fitted on {training_samples} runs and checked on {test_samples} held back, {formatDateTime(trained_at)}.
    </p>
  );
}

export function Cautions({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="border-l-2 border-amber py-1 pl-5">
      <p className="text-xs text-graphite">The model reported</p>
      <ul className="m-0 mt-1.5 list-none p-0">
        {[...warnings].sort((a, b) => a.localeCompare(b, "en", { numeric: true })).map((warning) => (
          <li key={warning} className="num">
            {warning}
          </li>
        ))}
      </ul>
    </div>
  );
}
