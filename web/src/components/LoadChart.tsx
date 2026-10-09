import { useMemo } from "react";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { Experiment } from "../api/types";
import { formatDateTime, formatNumber, scenarioLabel, toNumber } from "../lib/format";
import { usesCurrentTiming } from "../lib/runSummary";
import { logDomain, logTicks } from "../lib/scale";

export const LOAD_VIEWS = [
  { key: "actual_tps", label: "Throughput", axis: "Delivered rate (TPS)", unit: "TPS", timingSensitive: false },
  { key: "average_latency_ms", label: "Average latency", axis: "Average latency (ms)", unit: "ms", timingSensitive: true },
  { key: "p95_latency_ms", label: "P95 latency", axis: "P95 latency (ms)", unit: "ms", timingSensitive: true },
] as const;

export type LoadView = (typeof LOAD_VIEWS)[number]["key"];

interface Point {
  id: string;
  requested: number;
  value: number;
  scenario: string;
  workers: number | undefined;
  startedAt: string;
  current: boolean;
  latest: boolean;
}

const AXIS_TICK = { fill: "var(--color-graphite)", fontSize: 13 };

function Dot({ cx, cy, payload, hollowEarlier }: { cx?: number; cy?: number; payload?: Point; hollowEarlier: boolean }) {
  if (cx === undefined || cy === undefined || !payload) return null;
  const earlier = hollowEarlier && !payload.current;
  return (
    <g>
      {payload.latest && <circle cx={cx} cy={cy} r={11} fill="none" stroke="var(--color-paper)" strokeWidth={1} />}
      {earlier ? <circle cx={cx} cy={cy} r={4.5} fill="var(--color-ink)" stroke="var(--color-pencil)" strokeWidth={1.5} /> : <circle cx={cx} cy={cy} r={5} fill="var(--color-signal)" fillOpacity={0.82} />}
    </g>
  );
}

function PointTooltip({ active, payload, unit }: { active?: boolean; payload?: { payload: Point }[]; unit: string }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="border border-rule-strong bg-well px-3.5 py-2.5 text-xs shadow-lg shadow-black/30">
      <p className="num text-sm font-medium">
        {formatNumber(point.value)} {unit}
      </p>
      <p className="mt-1.5">{scenarioLabel(point.scenario)}</p>
      <p className="num text-graphite">
        {point.workers ?? "—"} workers, {formatNumber(point.requested, 0)} TPS requested
      </p>
      <p className="num text-graphite">{formatDateTime(point.startedAt)}</p>
    </div>
  );
}

/**
 * Every completed run placed by the rate it was asked for (the input) against what was
 * measured (the response). Both axes are logarithmic because runs span 10 to 400 TPS.
 */
export function LoadChart({ experiments, view }: { experiments: Experiment[]; view: LoadView }) {
  const { axis, unit, timingSensitive } = LOAD_VIEWS.find((item) => item.key === view)!;

  const points = useMemo<Point[]>(() => {
    const completed = experiments.filter((run) => run.status === "COMPLETED");
    const latestId = completed[0]?.experiment_id;
    // Drawn oldest first, so current-runner points and the latest run sit on top of earlier ones.
    return [...completed].reverse().flatMap((run) => {
      const requested = toNumber(run.configuration.target_tps);
      const value = toNumber(run[view]);
      if (requested === null || value === null || requested <= 0 || value <= 0) return [];
      return [{ id: run.experiment_id, requested, value, scenario: run.scenario, workers: run.configuration.concurrency, startedAt: run.started_at, current: usesCurrentTiming(run), latest: run.experiment_id === latestId }];
    });
  }, [experiments, view]);

  const isThroughput = view === "actual_tps";
  const xDomain = logDomain(points.map((point) => point.requested));
  const valueDomain = logDomain(points.map((point) => point.value));
  if (!xDomain || !valueDomain) return null;
  // On the throughput view both axes share one scale, so the diagonal means "delivered what was asked".
  const yDomain = isThroughput ? xDomain : valueDomain;
  const hasEarlier = timingSensitive && points.some((point) => !point.current);

  return (
    <figure className="m-0">
      <div className="h-[340px] sm:h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 12, right: 16, bottom: 28, left: 8 }}>
            <CartesianGrid stroke="var(--color-rule)" strokeWidth={0.75} />
            <XAxis type="number" dataKey="requested" scale="log" domain={xDomain} ticks={logTicks(xDomain)} allowDataOverflow tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--color-rule-strong)" }} label={{ value: "Requested rate (TPS)", position: "insideBottom", offset: -18, fill: "var(--color-graphite)", fontSize: 13 }} />
            <YAxis type="number" dataKey="value" scale="log" domain={yDomain} ticks={logTicks(yDomain)} allowDataOverflow tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} label={{ value: axis, angle: -90, position: "insideLeft", offset: 4, fill: "var(--color-graphite)", fontSize: 13, style: { textAnchor: "middle" } }} />
            {isThroughput && <ReferenceLine segment={[{ x: xDomain[0], y: xDomain[0] }, { x: xDomain[1], y: xDomain[1] }]} stroke="var(--color-pencil)" strokeDasharray="5 5" ifOverflow="hidden" />}
            <Tooltip content={<PointTooltip unit={unit} />} cursor={{ stroke: "var(--color-rule-strong)" }} isAnimationActive={false} />
            <Scatter data={points} shape={(props: object) => <Dot {...props} hollowEarlier={timingSensitive} />} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-graphite">
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-signal" aria-hidden="true" />
          One completed run
        </span>
        <span className="flex items-center gap-2">
          <span className="size-4 rounded-full border border-paper" aria-hidden="true" />
          Latest run
        </span>
        {isThroughput && (
          <span className="flex items-center gap-2">
            <span className="w-6 border-t border-dashed border-pencil" aria-hidden="true" />
            Delivered equals requested
          </span>
        )}
        {hasEarlier && (
          <span className="flex items-center gap-2">
            <span className="size-2.5 rounded-full border-[1.5px] border-pencil" aria-hidden="true" />
            Timed by the earlier runner, which included an account lookup
          </span>
        )}
      </figcaption>
    </figure>
  );
}
