import { useModels } from "../api/queries";
import type { ModelCard } from "../api/types";
import { TARGET_LABELS } from "../components/evidence";
import { PageIntro, Section } from "../components/Section";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { formatDateTime, formatNumber, scenarioLabel } from "../lib/format";
import { evidenceLabel } from "../lib/jobs";

const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";
const ALGORITHMS: Record<string, string> = { linear_regression: "Linear regression", random_forest: "Random forest", gradient_boosting: "Gradient boosting" };
const INPUT_LABELS: Record<string, string> = { concurrency: "Workers", target_tps: "Requested rate (TPS)", duration_seconds: "Duration (s)", burstiness: "Burstiness", account_skew: "Hot-account skew" };

const Intro = () => <PageIntro title="The models">One model per predicted metric. Each was the best of three candidates on runs it had not seen.</PageIntro>;

function ModelTable({ models }: { models: ModelCard[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse">
        <caption className="sr-only">The chosen model and its held-out error for each metric</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Predicts</th>
            <th scope="col" className={`${HEAD} text-left`}>Chosen model</th>
            <th scope="col" className={`${HEAD} text-right`}>Typical miss</th>
            <th scope="col" className={`${HEAD} text-right`}>RMSE</th>
            <th scope="col" className={`${HEAD} text-right`}>R²</th>
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
                <td className={`${CELL} text-right`}>{formatNumber(model.metrics.rmse, 2)}</td>
                <td className={`${CELL} text-right`}>{formatNumber(model.metrics.r2, 2)}</td>
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
      <div className="grid gap-14">
        <Section title="Error on runs held back from training" note={`Fitted on ${first.training_samples} runs and tested on ${first.test_samples}, ${formatDateTime(first.trained_at)}. With so few test runs these figures are indications, not measurements of accuracy.`}>
          <ModelTable models={models.data} />
        </Section>
        <Section title="What the models have seen" note="Predictions for workloads outside these ranges are extrapolations.">
          <TrainedOn model={first} />
        </Section>
      </div>
    </>
  );
}
