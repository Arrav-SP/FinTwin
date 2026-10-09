import { useState } from "react";
import { useModels, usePredict, useScenarios } from "../api/queries";
import type { WorkloadInput } from "../api/types";
import { Cautions, ModelProvenance, PredictedFigures, TrainedRange } from "../components/Predicted";
import { PageIntro, Section } from "../components/Section";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { DEFAULT_WORKLOAD, WorkloadForm } from "../components/WorkloadForm";
import { trainingRanges } from "../lib/workload";

const Intro = () => <PageIntro title="Predict a workload">Describe a workload and the models estimate how PostgreSQL will respond, without running it.</PageIntro>;

export function Predict() {
  const scenarios = useScenarios();
  const models = useModels();
  const predict = usePredict();
  const [workload, setWorkload] = useState<WorkloadInput>(DEFAULT_WORKLOAD);

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

  return (
    <>
      <Intro />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          predict.mutate(workload);
        }}
      >
        <WorkloadForm id="predict" value={workload} onChange={setWorkload} catalogue={scenarios.data} />
        <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
          <button type="submit" className="primary" disabled={predict.isPending}>
            {predict.isPending ? "Predicting" : "Predict"}
          </button>
          <ModelProvenance models={models.data} />
        </div>
      </form>

      <div className="mt-14" aria-live="polite">
        {predict.isError && <ErrorState title="No prediction was made" message={predict.error.message} />}
        {predict.isSuccess && (
          <div className="grid gap-14">
            <Section title="Predicted response" note="Estimates from the models. Nothing was run against the database.">
              <PredictedFigures predictions={predict.data.predictions} />
            </Section>
            <Section title="Inside what the models have seen?" note="A prediction outside the trained range is an extrapolation and should not be relied on.">
              <TrainedRange workload={{ ...predict.data.workload }} ranges={trainingRanges(models.data)} />
              {predict.data.warnings.length > 0 && (
                <div className="mt-8">
                  <Cautions warnings={predict.data.warnings} />
                </div>
              )}
            </Section>
          </div>
        )}
      </div>
    </>
  );
}
