import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Sweep } from "../api/types";
import { formatNumber } from "../lib/format";
import type { Range } from "../lib/workload";

export const SWEEP_VIEWS = [
  { key: "predicted_actual_tps", label: "Throughput", axis: "Predicted throughput (TPS)", unit: "TPS" },
  { key: "predicted_average_latency_ms", label: "Average latency", axis: "Predicted average latency (ms)", unit: "ms" },
  { key: "predicted_p95_latency_ms", label: "P95 latency", axis: "Predicted P95 latency (ms)", unit: "ms" },
  { key: "predicted_host_cpu_avg_percent", label: "Host CPU", axis: "Predicted host CPU (%)", unit: "%" },
] as const;

export type SweepView = (typeof SWEEP_VIEWS)[number]["key"];

export const PARAMETER_LABELS = { concurrency: "Workers", target_tps: "Requested rate (TPS)" } as const;
export const PARAMETER_PHRASES = { concurrency: "the number of workers", target_tps: "the requested rate" } as const;

const AXIS_TICK = { fill: "var(--color-graphite)", fontSize: 13 };

interface Point {
  x: number;
  value: number;
}

function HollowDot({ cx, cy }: { cx?: number; cy?: number }) {
  if (cx === undefined || cy === undefined) return null;
  return <circle cx={cx} cy={cy} r={4.5} fill="var(--color-ink)" stroke="var(--color-paper)" strokeWidth={1.5} strokeDasharray="2.4 2" />;
}

function SweepTooltip({ active, payload, unit, parameter }: { active?: boolean; payload?: { payload: Point }[]; unit: string; parameter: string }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="border border-rule-strong bg-well px-3.5 py-2.5 text-xs shadow-lg shadow-black/30">
      <p className="num text-sm font-medium">
        {formatNumber(point.value)} {unit} predicted
      </p>
      <p className="num mt-1 text-graphite">
        {parameter}: {formatNumber(point.x, 0)}
      </p>
    </div>
  );
}

/**
 * Model predictions across a range of one setting. Dashed line and hollow points: nothing here was measured.
 * The shaded band is the range of that setting the models were trained on.
 */
export function SweepChart({ sweep, view, trained }: { sweep: Sweep; view: SweepView; trained?: Range }) {
  const { axis, unit } = SWEEP_VIEWS.find((item) => item.key === view)!;
  const parameter = PARAMETER_LABELS[sweep.parameter];
  const points: Point[] = sweep.results.flatMap((result) => {
    const value = result.predictions[view];
    return typeof value === "number" ? [{ x: Number(result.configuration[sweep.parameter]), value }] : [];
  });
  const xs = points.map((point) => point.x);
  const low = Math.min(...xs, trained?.[0] ?? Infinity);
  const high = Math.max(...xs, trained?.[1] ?? -Infinity);
  const pad = (high - low) * 0.04 || 1;

  return (
    <figure className="m-0">
      <div className="h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 12, right: 16, bottom: 28, left: 8 }}>
            <CartesianGrid stroke="var(--color-rule)" strokeWidth={0.75} vertical={false} />
            {trained && <ReferenceArea x1={trained[0]} x2={trained[1]} fill="var(--color-slate)" fillOpacity={0.9} stroke="none" ifOverflow="hidden" />}
            <XAxis type="number" dataKey="x" domain={[low - pad, high + pad]} ticks={xs} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--color-rule-strong)" }} label={{ value: parameter, position: "insideBottom", offset: -18, fill: "var(--color-graphite)", fontSize: 13 }} />
            <YAxis domain={[0, "auto"]} tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} label={{ value: axis, angle: -90, position: "insideLeft", offset: 4, fill: "var(--color-graphite)", fontSize: 13, style: { textAnchor: "middle" } }} />
            <Tooltip content={<SweepTooltip unit={unit} parameter={parameter} />} cursor={{ stroke: "var(--color-rule-strong)" }} isAnimationActive={false} />
            <Line type="linear" dataKey="value" stroke="var(--color-paper)" strokeWidth={1.5} strokeDasharray="5 5" dot={<HollowDot />} activeDot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-graphite">
        <span className="flex items-center gap-2">
          <span className="size-3 rounded-full border-[1.5px] border-dashed border-paper" aria-hidden="true" />
          Predicted, not measured
        </span>
        {trained && (
          <span className="flex items-center gap-2">
            <span className="h-3 w-6 bg-slate" aria-hidden="true" />
            Range the models were trained on ({formatNumber(trained[0], 0)} to {formatNumber(trained[1], 0)})
          </span>
        )}
      </figcaption>
    </figure>
  );
}
