import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { Target } from "../api/types";
import { formatNumber, scenarioLabel } from "../lib/format";
import type { ValidationPoint } from "../lib/jobs";
import { TARGET_LABELS } from "./evidence";

const AXIS_TICK = { fill: "var(--color-graphite)", fontSize: 13 };

function HollowDot({ cx, cy }: { cx?: number; cy?: number }) {
  if (cx === undefined || cy === undefined) return null;
  return <circle cx={cx} cy={cy} r={5} fill="var(--color-ink)" stroke="var(--color-paper)" strokeWidth={1.5} strokeDasharray="2.4 2" />;
}

function PointTooltip({ active, payload, unit }: { active?: boolean; payload?: { payload: ValidationPoint }[]; unit: string }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="border border-rule-strong bg-well px-3.5 py-2.5 text-xs shadow-lg shadow-black/30">
      <p className="num text-sm">
        Predicted {formatNumber(point.predicted)} {unit}
      </p>
      <p className="num text-sm font-medium text-signal">
        Measured {formatNumber(point.measured)} {unit}
      </p>
      <p className="mt-1.5 text-graphite">{scenarioLabel(point.scenario)}</p>
    </div>
  );
}

/**
 * Every checked prediction for one metric: measured value across, predicted value up.
 * A point on the diagonal was predicted exactly; above it the model overestimated, below it underestimated.
 */
export function AccuracyChart({ points, target }: { points: ValidationPoint[]; target: Target }) {
  const { label, unit } = TARGET_LABELS[target];
  const top = Math.max(...points.flatMap((point) => [point.predicted, point.measured]), 0) * 1.12 || 1;
  const suffix = unit ? ` (${unit})` : "";
  return (
    <figure className="m-0">
      <div className="h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 12, right: 16, bottom: 28, left: 8 }}>
            <CartesianGrid stroke="var(--color-rule)" strokeWidth={0.75} />
            <XAxis type="number" dataKey="measured" domain={[0, top]} tickFormatter={(value: number) => formatNumber(value, 0)} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--color-rule-strong)" }} label={{ value: `Measured ${label.toLowerCase()}${suffix}`, position: "insideBottom", offset: -18, fill: "var(--color-graphite)", fontSize: 13 }} />
            <YAxis type="number" dataKey="predicted" domain={[0, top]} tickFormatter={(value: number) => formatNumber(value, 0)} tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} label={{ value: `Predicted${suffix}`, angle: -90, position: "insideLeft", offset: 4, fill: "var(--color-graphite)", fontSize: 13, style: { textAnchor: "middle" } }} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: top, y: top }]} stroke="var(--color-signal)" strokeWidth={1.5} ifOverflow="hidden" />
            <Tooltip content={<PointTooltip unit={unit} />} cursor={{ stroke: "var(--color-rule-strong)" }} isAnimationActive={false} />
            <Scatter data={points} shape={<HollowDot />} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-graphite">
        <span className="flex items-center gap-2">
          <span className="size-3 rounded-full border-[1.5px] border-dashed border-paper" aria-hidden="true" />
          One checked prediction
        </span>
        <span className="flex items-center gap-2">
          <span className="w-6 border-t-[1.5px] border-signal" aria-hidden="true" />
          Where an exact prediction would sit
        </span>
      </figcaption>
    </figure>
  );
}
