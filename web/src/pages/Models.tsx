import { useModels } from "../api/queries";
import type { ModelCard } from "../api/types";
import { TARGET_LABELS } from "../components/evidence";
import { describeTraining, SiteTraining } from "../components/Predicted";
import { PageIntro, Section } from "../components/Section";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { formatNumber, scenarioLabel } from "../lib/format";
import { evidenceLabel } from "../lib/jobs";

const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";
const ALGORITHMS: Record<string, string> = { linear_regression: "Linear regression", random_forest: "Random forest", gradient_boosting: "Gradient boosting" };
const INPUT_LABELS: Record<string, string> = { concurrency: "Workers", target_tps: "Requested rate (TPS)", duration_seconds: "Duration (s)", burstiness: "Burstiness", account_skew: "Hot-account skew" };

const Intro = () => <PageIntro title="The models">One model per predicted metric. Each was the best of three candidates on runs it had not seen.</PageIntro>;

/** Whether the model earns its place: it has to miss by less than predicting without one. */
export function verdict(model: ModelCard): string {
  if (!model.baseline) return "Not compared";
  if (model.metrics.mae < model.baseline.mae * 0.95) return "Better than no model";
  if (model.metrics.mae > model.baseline.mae * 1.05) return "Worse than no model";
  return "No better than no model";
}

function ModelTable({ models }: { models: ModelCard[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse">
        <caption className="sr-only">The chosen model and its held-out error for each metric</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Predicts</th>
            <th scope="col" className={`${HEAD} text-left`}>Chosen model</th>
            <th scope="col" className={`${HEAD} text-right`}>Typical miss</th>
            <th scope="col" className={`${HEAD} text-right`}>Without a model</th>
            <th scope="col" className={`${HEAD} text-right`}>Between identical runs</th>
            <th scope="col" className={`${HEAD} text-right`}>R²</th>
            <th scope="col" className={`${HEAD} text-left`}>Verdict</th>
          </tr>
        </thead>
        <tbody className="num">
          {models.map((model) => {
            const { label, unit } = TARGET_LABELS[model.target];
            return (
              <tr key={model.target} className="border-b border-rule">
                <td className={CELL}>{label}</td>
                <td className={CELL}>{ALGORITHMS[model.algorithm] ?? model.algorithm}</td>
                <td className={`${CELL} text-right`}>
                  {formatNumber(model.metrics.mae, 2)} {unit}
                </td>
                <td className={`${CELL} text-right`}>{formatNumber(model.baseline?.mae, 2)}</td>
                <td className={`${CELL} text-right`}>{formatNumber(model.repeat_spread, 2)}</td>
                <td className={`${CELL} text-right`}>{formatNumber(model.metrics.r2, 2)}</td>
                <td className={CELL}>{verdict(model)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TrainedOn({ model }: { model: ModelCard }) {
  const ranges = Object.entries(model.numeric_ranges);
  const settings = ranges.filter(([feature]) => !feature.endsWith("_ratio"));
  const mix = ranges.filter(([feature]) => feature.endsWith("_ratio"));
  return (
    <div className="grid gap-x-14 gap-y-10 md:grid-cols-2">
      <div>
        <h3 className="mb-3 text-xs font-normal text-graphite">Settings covered</h3>
        <dl className="m-0 grid gap-2.5">
          {settings.map(([feature, [low, high]]) => (
            <div key={feature} className="flex justify-between gap-6 border-b border-rule pb-2.5">
              <dt>{INPUT_LABELS[feature] ?? evidenceLabel(feature)}</dt>
              <dd className="num m-0">{low === high ? `${formatNumber(low, 0)} only` : `${formatNumber(low, 0)} to ${formatNumber(high, 0)}`}</dd>
            </div>
          ))}
        </dl>
        <h3 className="mb-3 mt-8 text-xs font-normal text-graphite">Scenarios in the data</h3>
        <p>{model.scenario_values.map(scenarioLabel).join(", ")}</p>
      </div>
      <div>
        <h3 className="mb-3 text-xs font-normal text-graphite">Share of each operation covered (%)</h3>
        <dl className="m-0 grid gap-2.5">
          {mix.map(([feature, [low, high]]) => (
            <div key={feature} className="flex justify-between gap-6 border-b border-rule pb-2.5">
              <dt>{scenarioLabel(feature.replace("_ratio", ""))}</dt>
              <dd className="num m-0">
                {formatNumber(low * 100, 0)} to {formatNumber(high * 100, 0)}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

export function Models() {
  const models = useModels();
  if (models.isPending) {
    return (
      <>
        <Intro />
        <Placeholder className="h-72 w-full" label="Loading models" />
      </>
    );
  }
  if (models.isError) {
    return (
      <>
        <Intro />
        <ErrorState title="The models could not be read" message={models.error.message} onRetry={() => models.refetch()} />
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
  const first = models.data[0];
  return (
    <>
      <Intro />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-14">
        <Section title="Error on runs held back from training" note={describeTraining(first)}>
          <SiteTraining model={first} />
          <div className="mt-5">
            <ModelTable models={models.data} />
          </div>
          <p className="mt-3 max-w-[78ch] text-xs text-graphite">Typical miss is the mean absolute error. “Without a model” is the miss from predicting the requested rate for throughput, or the scenario’s average for everything else. “Between identical runs” is how much the same workload varies when repeated, which no model can beat.</p>
        </Section>
        <Section title="What the models have seen" note="Predictions for workloads outside these ranges are extrapolations.">
          <TrainedOn model={first} />
        </Section>
      </div>
    </>
  );
}
