import type { ReactNode } from "react";
import type { ScenarioCatalogue, WorkloadInput } from "../api/types";
import { scenarioLabel } from "../lib/format";

export const DEFAULT_WORKLOAD: WorkloadInput = { scenario: "NORMAL_DAY", concurrency: 8, target_tps: 20, duration_seconds: 10, account_skew: 0 };

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-xs text-graphite">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-pencil">{hint}</p>}
    </div>
  );
}

/** The inputs that describe a workload. Limits come from the server so the form and the API cannot disagree. */
export function WorkloadForm({ id, value, onChange, catalogue }: { id: string; value: WorkloadInput; onChange: (next: WorkloadInput) => void; catalogue: ScenarioCatalogue }) {
  const { limits, scenarios } = catalogue;
  const number = (key: keyof WorkloadInput) => (event: React.ChangeEvent<HTMLInputElement>) => onChange({ ...value, [key]: event.target.valueAsNumber });
  const shown = (field: number) => (Number.isNaN(field) ? "" : field);
  return (
    <div className="grid grid-cols-2 gap-x-5 gap-y-5 md:grid-cols-[minmax(0,1.6fr)_repeat(4,minmax(0,1fr))]">
      <div className="col-span-2 md:col-span-1">
        <Field id={`${id}-scenario`} label="Scenario">
          <select id={`${id}-scenario`} className="field" value={value.scenario} onChange={(event) => onChange({ ...value, scenario: event.target.value })}>
            {scenarios.map((item) => (
              <option key={item.scenario} value={item.scenario}>
                {scenarioLabel(item.scenario)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field id={`${id}-workers`} label="Workers" hint={`1 to ${limits.max_concurrency}`}>
        <input id={`${id}-workers`} className="field num" type="number" required min={1} max={limits.max_concurrency} step={1} value={shown(value.concurrency)} onChange={number("concurrency")} />
      </Field>
      <Field id={`${id}-rate`} label="Requested rate (TPS)" hint={`up to ${limits.max_target_tps.toLocaleString("en-US")}`}>
        <input id={`${id}-rate`} className="field num" type="number" required min={0.1} max={limits.max_target_tps} step="any" value={shown(value.target_tps)} onChange={number("target_tps")} />
      </Field>
      <Field id={`${id}-duration`} label="Duration (s)" hint={`up to ${limits.max_duration_seconds}`}>
        <input id={`${id}-duration`} className="field num" type="number" required min={1} max={limits.max_duration_seconds} step="any" value={shown(value.duration_seconds)} onChange={number("duration_seconds")} />
      </Field>
      <Field id={`${id}-skew`} label="Hot-account skew" hint="0 is even, 3 is extreme">
        <input id={`${id}-skew`} className="field num" type="number" required min={0} max={3} step={0.1} value={shown(value.account_skew)} onChange={number("account_skew")} />
      </Field>
    </div>
  );
}
