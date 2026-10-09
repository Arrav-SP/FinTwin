import type { ReactNode } from "react";
import type { Experiment } from "../api/types";
import { formatNumber, type Numeric, toNumber } from "../lib/format";
import { deliveredShare } from "../lib/runSummary";

function Figure({ label, value, unit, digits = 1, tone = "", children, className = "" }: { label: string; value: Numeric; unit?: string; digits?: number; tone?: string; children?: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <dt className="text-xs text-graphite">{label}</dt>
      <dd className="m-0 mt-2">
        <span className={`num text-figure font-medium leading-none tracking-tight ${tone}`}>{formatNumber(value, digits)}</span>
        {unit && <span className="ml-1.5 text-graphite">{unit}</span>}
        {children}
      </dd>
    </div>
  );
}

/** Delivered throughput drawn against the rate that was asked for. */
function DeliveryMeter({ run }: { run: Experiment }) {
  const share = deliveredShare(run.actual_tps, run.configuration.target_tps);
  if (share === null) return null;
  const percent = Math.round(share * 100);
  return (
    <div className="mt-3 max-w-xs">
      <div className="relative h-1.5 bg-slate" role="img" aria-label={`${percent}% of the requested rate was delivered`}>
        <div className="absolute inset-y-0 left-0 bg-signal" style={{ width: `${share * 100}%` }} />
        <div className="absolute -inset-y-1 right-0 w-px bg-paper" />
      </div>
      <p className="num mt-2 text-xs text-graphite">
        {percent}% of the {run.configuration.target_tps} TPS requested
      </p>
    </div>
  );
}

/** The measured figures of one run. Throughput leads because it is what the run was asked to deliver. */
export function RunFigures({ run }: { run: Experiment }) {
  const waits = toNumber(run.lock_wait_count_max);
  return (
    <dl className="m-0 grid grid-cols-2 gap-x-8 gap-y-8 sm:grid-cols-4 lg:grid-cols-[minmax(0,1.6fr)_repeat(4,minmax(0,1fr))]">
      <Figure label="Delivered throughput" value={run.actual_tps} unit="TPS" className="col-span-2 sm:col-span-4 lg:col-span-1">
        <DeliveryMeter run={run} />
      </Figure>
      <Figure label="Average latency" value={run.average_latency_ms} unit="ms" />
      <Figure label="P95 latency" value={run.p95_latency_ms} unit="ms" />
      <Figure label="Host CPU" value={run.host_cpu_avg_percent} unit="%" />
      <Figure label="Lock requests waiting, peak" value={run.lock_wait_count_max} digits={0} tone={waits ? "text-amber" : ""} />
    </dl>
  );
}
