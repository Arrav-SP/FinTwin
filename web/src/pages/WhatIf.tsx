import { useState } from "react";
import { useModels, useScenarios, useSweep } from "../api/queries";
import type { Sweep, SweepParameter, WorkloadInput } from "../api/types";
import { Cautions, ModelProvenance } from "../components/Predicted";
import { PageIntro, Section } from "../components/Section";
import { Segmented } from "../components/Segmented";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { PARAMETER_LABELS, PARAMETER_PHRASES, SWEEP_VIEWS, SweepChart, type SweepView } from "../components/SweepChart";
import { DEFAULT_WORKLOAD, WorkloadForm } from "../components/WorkloadForm";
import { formatNumber } from "../lib/format";
import { sweepValues, trainingRanges } from "../lib/workload";

const Intro = () => <PageIntro title="What if the load changes">Hold a workload fixed, vary one setting, and see what the models expect across the range. Nothing is run.</PageIntro>;

const STEPS = 7;
const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";

function SweepTable({ sweep }: { sweep: Sweep }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse">
        <caption className="sr-only">Predicted response at each value</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>{PARAMETER_LABELS[sweep.parameter]}</th>
            {SWEEP_VIEWS.map((view) => (
              <th key={view.key} scope="col" className={`${HEAD} text-right`}>
                {view.label} ({view.unit})
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="num">
          {sweep.results.map((result) => (
            <tr key={result.configuration[sweep.parameter]} className="border-b border-rule">
              <td className={CELL}>{formatNumber(result.configuration[sweep.parameter], 0)}</td>
              {SWEEP_VIEWS.map((view) => (
                <td key={view.key} className={`${CELL} text-right`}>
                  {formatNumber(result.predictions[view.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function WhatIf() {
  const scenarios = useScenarios();
  const models = useModels();
  const sweep = useSweep();
  const [workload, setWorkload] = useState<WorkloadInput>(DEFAULT_WORKLOAD);
  const [parameter, setParameter] = useState<SweepParameter>("target_tps");
  const [from, setFrom] = useState(10);
  const [to, setTo] = useState(100);
  const [view, setView] = useState<SweepView>("predicted_actual_tps");

  if (scenarios.isPending || models.isPending) {
    return (
      <>
        <Intro />
        <Placeholder className="h-40 w-full" label="Loading scenarios and models" />
      </>
    );
  }
  if (scenarios.isError || models.isError) {
    const failed = scenarios.isError ? scenarios : models;
    return (
      <>
        <Intro />
        <ErrorState title="The form could not be prepared" message={failed.error!.message} onRetry={() => failed.refetch()} />
      </>
    );
  }
  if (models.data.length === 0) {
    return (
      <>
        <Intro />
        <EmptyState title="No model has been trained yet">
          Run several workloads, then train with <Command>python scripts/train_models.py</Command>
        </EmptyState>
      </>
    );
  }

  const limit = parameter === "concurrency" ? scenarios.data.limits.max_concurrency : scenarios.data.limits.max_target_tps;
  const values = sweepValues(parameter, from, to, STEPS);
  const ranges = trainingRanges(models.data);

  return (
    <>
      <Intro />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (values.length >= 2) sweep.mutate({ baseline: workload, parameter, values });
        }}
      >
        <WorkloadForm id="whatif" value={workload} onChange={setWorkload} catalogue={scenarios.data} />
        <fieldset className="m-0 mt-8 border-0 border-t border-rule p-0 pt-6">
          <legend className="serif float-left mb-5 w-full p-0 text-lg">Vary one setting</legend>
          <div className="clear-both grid grid-cols-2 gap-x-5 gap-y-5 md:grid-cols-[minmax(0,1.6fr)_repeat(4,minmax(0,1fr))]">
            <div className="col-span-2 md:col-span-1">
              <label htmlFor="whatif-parameter" className="mb-1.5 block text-xs text-graphite">
                Setting to vary
              </label>
              <select id="whatif-parameter" className="field" value={parameter} onChange={(event) => setParameter(event.target.value as SweepParameter)}>
                <option value="target_tps">{PARAMETER_LABELS.target_tps}</option>
                <option value="concurrency">{PARAMETER_LABELS.concurrency}</option>
              </select>
            </div>
            <div>
              <label htmlFor="whatif-from" className="mb-1.5 block text-xs text-graphite">
                From
              </label>
              <input id="whatif-from" className="field num" type="number" required min={1} max={limit} step="any" value={Number.isNaN(from) ? "" : from} onChange={(event) => setFrom(event.target.valueAsNumber)} />
            </div>
            <div>
              <label htmlFor="whatif-to" className="mb-1.5 block text-xs text-graphite">
                To
              </label>
              <input id="whatif-to" className="field num" type="number" required min={1} max={limit} step="any" value={Number.isNaN(to) ? "" : to} onChange={(event) => setTo(event.target.valueAsNumber)} />
            </div>
          </div>
          <p className="num mt-3 text-xs text-pencil">{values.length >= 2 ? `Predicts at ${values.join(", ")}. The value in the form above is replaced by each of these.` : "Choose two different ends for the range."}</p>
        </fieldset>
        <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
          <button type="submit" className="primary" disabled={sweep.isPending || values.length < 2}>
            {sweep.isPending ? "Predicting" : "Predict the range"}
          </button>
          <ModelProvenance models={models.data} />
        </div>
      </form>

      <div className="mt-14" aria-live="polite">
        {sweep.isError && <ErrorState title="No prediction was made" message={sweep.error.message} />}
        {sweep.isSuccess && (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-14">
            <Section title={`Predicted response as ${PARAMETER_PHRASES[sweep.data.parameter]} changes`} note="Estimates from the models at each value. Nothing was run against the database." aside={<Segmented label="Prediction plotted" options={SWEEP_VIEWS} value={view} onChange={setView} />}>
              <SweepChart sweep={sweep.data} view={view} trained={ranges[sweep.data.parameter]} />
              {sweep.data.warnings.length > 0 && (
                <div className="mt-8">
                  <Cautions warnings={sweep.data.warnings} />
                </div>
              )}
            </Section>
            <Section title="The figures">
              <SweepTable sweep={sweep.data} />
            </Section>
          </div>
        )}
      </div>
    </>
  );
}
