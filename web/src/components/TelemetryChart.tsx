import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatNumber } from "../lib/format";
import type { TelemetryPoint } from "../lib/workload";

export const TELEMETRY_VIEWS = [
  { key: "lockWaits", label: "Lock requests waiting", axis: "Lock requests waiting", unit: "" },
  { key: "blockedSessions", label: "Blocked sessions", axis: "Sessions blocked on a lock", unit: "" },
  { key: "activeConnections", label: "Active connections", axis: "Active connections", unit: "" },
  { key: "cpu", label: "Host CPU", axis: "Host CPU (%)", unit: "%" },
] as const;

export type TelemetryView = (typeof TELEMETRY_VIEWS)[number]["key"];

const AXIS_TICK = { fill: "var(--color-graphite)", fontSize: 13 };

function SampleTooltip({ active, payload, view }: { active?: boolean; payload?: { payload: TelemetryPoint }[]; view: TelemetryView }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const { label, unit } = TELEMETRY_VIEWS.find((item) => item.key === view)!;
  return (
    <div className="border border-rule-strong bg-well px-3.5 py-2.5 text-xs shadow-lg shadow-black/30">
      <p className="num text-sm font-medium">
        {formatNumber(point[view], view === "cpu" ? 1 : 0)}
        {unit}
      </p>
      <p className="mt-1 text-graphite">{label}</p>
      <p className="num text-graphite">{formatNumber(point.seconds, 1)} s into the run</p>
    </div>
  );
}

/** One sampled measurement across the life of a run. A solid line: these are measurements. */
export function TelemetryChart({ series, view }: { series: TelemetryPoint[]; view: TelemetryView }) {
  const { axis } = TELEMETRY_VIEWS.find((item) => item.key === view)!;
  return (
    <div className="h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 12, right: 16, bottom: 28, left: 8 }}>
          <CartesianGrid stroke="var(--color-rule)" strokeWidth={0.75} vertical={false} />
          <XAxis type="number" dataKey="seconds" domain={[0, "dataMax"]} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: "var(--color-rule-strong)" }} label={{ value: "Seconds into the run", position: "insideBottom", offset: -18, fill: "var(--color-graphite)", fontSize: 13 }} />
          <YAxis allowDecimals={view === "cpu"} domain={[0, "auto"]} tick={AXIS_TICK} tickLine={false} axisLine={false} width={56} label={{ value: axis, angle: -90, position: "insideLeft", offset: 4, fill: "var(--color-graphite)", fontSize: 13, style: { textAnchor: "middle" } }} />
          <Tooltip content={<SampleTooltip view={view} />} cursor={{ stroke: "var(--color-rule-strong)" }} isAnimationActive={false} />
          <Line type="linear" dataKey={view} stroke="var(--color-signal)" strokeWidth={2} dot={{ r: 2.5, fill: "var(--color-signal)", strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
