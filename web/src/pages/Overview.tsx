import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { useExperiments, useValidationSummary, useValidations } from "../api/queries";
import type { Experiment } from "../api/types";
import { EvidenceGap, EvidenceKey } from "../components/EvidenceGap";
import { pairValidationMetrics } from "../components/evidence";
import { LOAD_VIEWS, LoadChart, type LoadView } from "../components/LoadChart";
import { RunFigures } from "../components/RunFigures";
import { RunsTable } from "../components/RunsTable";
import { Section } from "../components/Section";
import { Segmented } from "../components/Segmented";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { formatDateTime, formatPercent, scenarioLabel } from "../lib/format";
import { describeRun } from "../lib/runSummary";

const RECENT_RUNS = 6;

function RefreshControl({ updatedAt }: { updatedAt: number }) {
  const queryClient = useQueryClient();
  const fetching = useIsFetching() > 0;
  return (
    <div className="flex items-center gap-4 text-xs text-graphite">
      {updatedAt > 0 && <span className="num hidden sm:inline">Read at {new Date(updatedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>}
      <button type="button" className="control text-sm text-paper" onClick={() => queryClient.invalidateQueries()} aria-busy={fetching}>
        {fetching ? "Reading" : "Read again"}
      </button>
    </div>
  );
}

/** The page opens with what the latest run found, in words, before any figure. */
function LatestRun({ run, updatedAt }: { run: Experiment; updatedAt: number }) {
  const summary = describeRun(run);
  return (
    <header className="mb-14 sm:mb-16">
      <div className="mb-5 flex items-center justify-between gap-4">
        <p className="num text-graphite">Latest run, {formatDateTime(run.started_at)}</p>
        <RefreshControl updatedAt={updatedAt} />
      </div>
      <h1 className="serif max-w-[26ch] text-lede leading-[1.08] text-balance">{summary.headline}</h1>
      <p className="mb-10 mt-5 max-w-[62ch] text-base text-graphite">{summary.detail}</p>
      <RunFigures run={run} />
    </header>
  );
}

function PredictionCheck() {
  const validations = useValidations();
  const summary = useValidationSummary();
  if (validations.isPending) return <Placeholder className="h-64" label="Loading checked predictions" />;
  if (validations.isError) return <ErrorState title="Checked predictions could not be read" message={validations.error.message} onRetry={() => validations.refetch()} />;

  const latest = validations.data.find((item) => item.validation_status === "COMPLETED");
  const rows = latest ? pairValidationMetrics(latest) : [];
  if (!latest || rows.length === 0) {
    return (
      <EmptyState title="No prediction has been checked yet">
        Predict a workload, run it, and compare the two with <Command>python scripts/validate_prediction.py</Command>
      </EmptyState>
    );
  }
  const count = summary.data?.validation_count;
  const latencyError = summary.data?.overall.average_latency_ms?.mape;
  const { concurrency, target_tps } = latest.workload_configuration;
  return (
    <>
      <EvidenceGap rows={rows} />
      <p className="mt-4 text-xs text-graphite">
        {scenarioLabel(latest.scenario)}, {concurrency ?? "—"} workers at {target_tps ?? "—"} TPS, checked {formatDateTime(latest.created_at)}.
        {count != null && (
          <>
            {" "}
            {count} {count === 1 ? "prediction has" : "predictions have"} been checked in all
            {latencyError != null ? `; average latency missed by ${formatPercent(latencyError)} on average.` : "."}
          </>
        )}
      </p>
    </>
  );
}

function OverviewSkeleton() {
  return (
    <div aria-busy="true">
      <Placeholder className="mb-5 h-5 w-48" label="Loading the latest run" />
      <Placeholder className="mb-3 h-12 w-full max-w-2xl" label="Loading" />
      <Placeholder className="mb-10 h-12 w-full max-w-xl" label="Loading" />
      <Placeholder className="mb-16 h-24 w-full" label="Loading measured figures" />
      <Placeholder className="h-96 w-full" label="Loading runs" />
    </div>
  );
}

export function Overview() {
  const experiments = useExperiments();
  const [view, setView] = useState<LoadView>("actual_tps");

  if (experiments.isPending) return <OverviewSkeleton />;
  if (experiments.isError) return <ErrorState title="The runs could not be read" message={experiments.error.message} onRetry={() => experiments.refetch()} />;

  const runs = experiments.data;
  const latest = runs.find((run) => run.status === "COMPLETED") ?? runs[0];
  if (!latest) {
    return (
      <EmptyState title="No workload has been run yet">
        Start one with <Command>python scripts/run_workload.py --scenario NORMAL_DAY</Command>
      </EmptyState>
    );
  }

  return (
    <>
      <LatestRun run={latest} updatedAt={experiments.dataUpdatedAt} />
      <div className="grid gap-x-14 gap-y-14 wide:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Section
          title="What was asked against what came back"
          note="Each point is one completed run, placed by the rate it was asked for and what was measured."
          aside={<Segmented label="Measurement plotted" options={LOAD_VIEWS} value={view} onChange={setView} />}
        >
          <LoadChart experiments={runs} view={view} />
        </Section>
        <Section title="Prediction against measurement" note="The most recent prediction that was then run for real." aside={<EvidenceKey />}>
          <PredictionCheck />
        </Section>
      </div>
      <Section
        title="Run log"
        className="mt-14"
        aside={
          <Link to="/experiments" className="text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper">
            All {runs.length} runs
          </Link>
        }
      >
        <RunsTable runs={runs.slice(0, RECENT_RUNS)} caption={`The ${RECENT_RUNS} most recent workload runs`} />
      </Section>
    </>
  );
}
