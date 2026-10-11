import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { useExperimentDetail, useLatencyBreakdown } from "../api/queries";
import type { ExperimentDetail, ExperimentDetailResponse } from "../api/types";
import { AdvisorFindings } from "../components/AdvisorFindings";
import { EvidenceGap, EvidenceKey } from "../components/EvidenceGap";
import { pairValidationMetrics } from "../components/evidence";
import { LatencyBreakdown } from "../components/LatencyBreakdown";
import { RunFigures } from "../components/RunFigures";
import { Section } from "../components/Section";
import { Segmented } from "../components/Segmented";
import { EmptyState, ErrorState, Placeholder } from "../components/States";
import { TELEMETRY_VIEWS, TelemetryChart, type TelemetryView } from "../components/TelemetryChart";
import { formatDateTime, formatInteger, formatNumber, formatPercent } from "../lib/format";
import { describeRun } from "../lib/runSummary";
import { telemetrySeries } from "../lib/workload";

const BackLink = () => (
  <Link to="/experiments" className="text-graphite underline decoration-rule-strong underline-offset-4 hover:text-paper hover:decoration-paper">
    All experiments
  </Link>
);

function Telemetry({ detail }: { detail: ExperimentDetailResponse }) {
  const [view, setView] = useState<TelemetryView>("lockWaits");
  const series = useMemo(() => telemetrySeries(detail.telemetry), [detail.telemetry]);
  return (
    <Section title="During the run" note="Sampled from PostgreSQL and the host while the workload ran." aside={series.length > 1 ? <Segmented label="Measurement plotted" options={TELEMETRY_VIEWS} value={view} onChange={setView} /> : undefined}>
      {series.length > 1 ? <TelemetryChart series={series} view={view} /> : <EmptyState title="This run has no telemetry">It was started without the collector, so only its workload figures were recorded.</EmptyState>}
    </Section>
  );
}

function Latency({ id }: { id: string }) {
  const latency = useLatencyBreakdown(id);
  return (
    <Section title="Latency by operation" note="Service time of each operation, measured inside the worker that ran it.">
      {latency.isPending && <Placeholder className="h-48 w-full" label="Loading the latency breakdown" />}
      {latency.isError && <ErrorState title="The latency breakdown could not be read" message={latency.error.message} onRetry={() => latency.refetch()} />}
      {latency.isSuccess && (latency.data.count > 0 ? <LatencyBreakdown breakdown={latency.data} /> : <EmptyState title="No operations were recorded for this run">The run has no stored events.</EmptyState>)}
    </Section>
  );
}

function Record({ run }: { run: ExperimentDetail }) {
  const { seed, burstiness, account_skew } = run.configuration;
  const rows: [string, string][] = [
    ["Operations requested", formatInteger(run.requested_operations)],
    ["Completed", formatInteger(run.completed_operations)],
    ["Failed", formatInteger(run.failed_operations)],
    ["Deadlocks", formatInteger(run.db_deadlocks_delta)],
    ["Sessions blocked, peak", formatInteger(run.blocked_sessions_max)],
    ["Active connections, peak", run.max_connections ? `${formatInteger(run.active_connections_max)} of ${formatInteger(run.max_connections)}` : formatInteger(run.active_connections_max)],
    ["Cache hit ratio", formatPercent(run.db_cache_hit_ratio, 2)],
    ["Host memory", formatPercent(run.host_memory_avg_percent)],
    ["Telemetry samples", formatInteger(run.telemetry_sample_count)],
    ["Seed", formatInteger(seed)],
    ["Burstiness", formatNumber(burstiness, 2)],
    ["Hot-account skew", formatNumber(account_skew, 2)],
  ];
  return (
    <Section title="The record" note={run.mine ? "Counts and settings stored with this run. Only you can see this run." : "Counts and settings stored with this run."}>
      <dl className="m-0 grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-3 lg:grid-cols-4">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-graphite">{label}</dt>
            <dd className="num m-0 mt-1 text-base">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 font-mono text-xs text-pencil">{run.experiment_id}</p>
    </Section>
  );
}

function CheckedPrediction({ detail }: { detail: ExperimentDetailResponse }) {
  const validation = detail.validations.find((item) => item.validation_status === "COMPLETED");
  const rows = validation ? pairValidationMetrics(validation) : [];
  if (rows.length === 0) return null;
  return (
    <Section title="The prediction this run checked" note={`Made before the run and stored ${formatDateTime(validation!.created_at)}.`} aside={<EvidenceKey />}>
      <div className="max-w-3xl">
        <EvidenceGap rows={rows} />
      </div>
    </Section>
  );
}

export function RunDetail() {
  const { id = "" } = useParams();
  const detail = useExperimentDetail(id);

  if (detail.isPending) {
    return (
      <div aria-busy="true">
        <Placeholder className="mb-5 h-5 w-40" label="Loading the run" />
        <Placeholder className="mb-10 h-24 w-full max-w-2xl" label="Loading" />
        <Placeholder className="h-80 w-full" label="Loading" />
      </div>
    );
  }
  if (detail.isError) {
    return (
      <>
        <p className="mb-6">
          <BackLink />
        </p>
        <ErrorState title="This run could not be read" message={detail.error.message} onRetry={() => detail.refetch()} />
      </>
    );
  }

  const run = detail.data.experiment;
  const summary = describeRun(run);
  return (
    <>
      <header className="mb-14 sm:mb-16">
        <p className="num mb-5 flex flex-wrap gap-x-6 gap-y-1 text-graphite">
          <BackLink />
          <span>Started {formatDateTime(run.started_at)}</span>
        </p>
        <h1 className="serif max-w-[26ch] text-lede leading-[1.08] text-balance">{summary.headline}</h1>
        <p className="mb-10 mt-5 max-w-[62ch] text-base text-graphite">{summary.detail}</p>
        <RunFigures run={run} />
      </header>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-14">
        <Telemetry detail={detail.data} />
        <Latency id={id} />
        {run.status === "COMPLETED" && <AdvisorFindings id={id} />}
        <CheckedPrediction detail={detail.data} />
        <Record run={run} />
      </div>
    </>
  );
}
