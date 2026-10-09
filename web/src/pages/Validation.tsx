import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useValidationSummary, useValidations } from "../api/queries";
import { TARGETS, type Target, type Validation as ValidationRecord, type ValidationSummary } from "../api/types";
import { AccuracyChart } from "../components/AccuracyChart";
import { TARGET_LABELS } from "../components/evidence";
import { JobRunner } from "../components/JobRunner";
import { PageIntro, Section } from "../components/Section";
import { Segmented } from "../components/Segmented";
import { EmptyState, ErrorState, Placeholder } from "../components/States";
import { formatDateTime, formatInteger, formatNumber, formatPercent, scenarioLabel } from "../lib/format";
import { validationPoints } from "../lib/jobs";

const LINK = "text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper";
const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";
const CHART_TARGETS = TARGETS.filter((target) => target !== "lock_wait_count_max").map((key) => ({ key, label: TARGET_LABELS[key].label }));

function AccuracyTable({ summary }: { summary: ValidationSummary }) {
  const rows = TARGETS.filter((target) => summary.overall[target]);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse">
        <caption className="sr-only">Prediction error by metric across all completed checks</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Metric</th>
            <th scope="col" className={`${HEAD} text-right`}>Checks</th>
            <th scope="col" className={`${HEAD} text-right`}>Typical miss</th>
            <th scope="col" className={`${HEAD} text-right`}>Typical miss (%)</th>
            <th scope="col" className={`${HEAD} text-right`}>R²</th>
          </tr>
        </thead>
        <tbody className="num">
          {rows.map((target) => {
            const accuracy = summary.overall[target]!;
            const { label, unit } = TARGET_LABELS[target];
            return (
              <tr key={target} className="border-b border-rule">
                <td className={CELL}>{label}</td>
                <td className={`${CELL} text-right`}>{formatInteger(accuracy.count)}</td>
                <td className={`${CELL} text-right`}>
                  {formatNumber(accuracy.mae, 2)} {unit}
                </td>
                <td className={`${CELL} text-right`}>{accuracy.mape === null ? <span className="text-xs text-graphite">not defined</span> : formatPercent(accuracy.mape)}</td>
                <td className={`${CELL} text-right`}>{accuracy.r2 === null ? <span className="text-xs text-graphite">not defined</span> : formatNumber(accuracy.r2, 2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-3 max-w-[70ch] text-xs text-graphite">Typical miss is the mean absolute error. R² is left out when every check used the same workload, and the percentage when the measured value was zero.</p>
    </div>
  );
}

function Checks({ validations }: { validations: ValidationRecord[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse">
        <caption className="sr-only">Every check, newest first</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Checked</th>
            <th scope="col" className={`${HEAD} text-left`}>Workload</th>
            <th scope="col" className={`${HEAD} text-right`}>Average latency miss</th>
            <th scope="col" className={`${HEAD} text-right`}>Throughput miss</th>
            <th scope="col" className={`${HEAD} text-left`}>Outcome</th>
          </tr>
        </thead>
        <tbody className="num">
          {validations.map((item) => {
            const { concurrency, target_tps } = item.workload_configuration;
            const workload = `${scenarioLabel(item.scenario)}, ${concurrency ?? "—"} workers at ${target_tps ?? "—"} TPS`;
            return (
              <tr key={item.validation_id} className="border-b border-rule">
                <td className={`${CELL} whitespace-nowrap text-graphite`}>{formatDateTime(item.created_at)}</td>
                <td className={CELL}>
                  {item.actual_experiment_id ? (
                    <Link to={`/experiments/${item.actual_experiment_id}`} className={LINK}>
                      {workload}
                    </Link>
                  ) : (
                    workload
                  )}
                </td>
                <td className={`${CELL} text-right`}>{formatPercent(item.error_metrics?.average_latency_ms?.percentage_error)}</td>
                <td className={`${CELL} text-right`}>{formatPercent(item.error_metrics?.actual_tps?.percentage_error)}</td>
                <td className={CELL}>{item.validation_status === "COMPLETED" ? "Compared" : item.validation_status === "FAILED" ? <span className="text-red">Failed: {item.error_message ?? "no reason recorded"}</span> : "In progress"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Record() {
  const validations = useValidations();
  const summary = useValidationSummary();
  const [target, setTarget] = useState<Target>("average_latency_ms");
  const points = useMemo(() => validationPoints(validations.data ?? [], target), [validations.data, target]);

  if (validations.isPending || summary.isPending) return <Placeholder className="h-96 w-full" label="Loading checked predictions" />;
  if (validations.isError || summary.isError) {
    const failed = validations.isError ? validations : summary;
    return <ErrorState title="The checks could not be read" message={failed.error!.message} onRetry={() => failed.refetch()} />;
  }
  if (validations.data.length === 0) {
    return (
      <Section title="No prediction has been checked yet">
        <EmptyState title="Start with the form above">Each check stores the prediction first, then runs the workload and compares.</EmptyState>
      </Section>
    );
  }
  return (
    <div className="grid gap-14">
      <div className="grid gap-x-14 gap-y-14 wide:grid-cols-[minmax(0,6fr)_minmax(0,6fr)]">
        <Section title="Predicted against measured" note="Each point is one check. The closer to the line, the better the prediction." aside={<Segmented label="Metric plotted" options={CHART_TARGETS} value={target} onChange={setTarget} />}>
          {points.length > 0 ? <AccuracyChart points={points} target={target} /> : <EmptyState title="No completed check has this metric">Choose another metric.</EmptyState>}
        </Section>
        <Section title="How far off, by metric" note={`Across ${summary.data.validation_count} completed ${summary.data.validation_count === 1 ? "check" : "checks"}.`}>
          <AccuracyTable summary={summary.data} />
        </Section>
      </div>
      <Section title="Every check">
        <Checks validations={validations.data} />
      </Section>
    </div>
  );
}

export function Validation() {
  return (
    <>
      <PageIntro title="Check the model against a real run">The prediction is stored first. Then the same workload is run, and the two are compared.</PageIntro>
      <JobRunner
        kind="validation"
        action="Predict, then run"
        working="Checking"
        note="This runs a real workload against the database and takes as long as the duration you set."
        done={(job) =>
          job.result?.experiment_id ? (
            <Link to={`/experiments/${job.result.experiment_id}`} className={LINK}>
              See the prediction beside the measurement
            </Link>
          ) : null
        }
      />
      <div className="mt-14">
        <Record />
      </div>
    </>
  );
}
