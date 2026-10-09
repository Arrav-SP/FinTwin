import { useMemo, useState } from "react";
import { useExperiments } from "../api/queries";
import type { RunStatus } from "../api/types";
import { RunsTable } from "../components/RunsTable";
import { PageIntro, Section } from "../components/Section";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { scenarioLabel } from "../lib/format";

const FIELD = "min-h-9 rounded-control border border-rule-strong bg-well px-3 placeholder:text-pencil";

const PageTitle = () => <PageIntro title="Experiments">Every workload run against PostgreSQL, newest first.</PageIntro>;

export function Experiments() {
  const experiments = useExperiments();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<RunStatus | "">("");

  const runs = experiments.data;
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (runs ?? []).filter((run) => (!status || run.status === status) && (!needle || `${run.experiment_id} ${scenarioLabel(run.scenario)}`.toLowerCase().includes(needle)));
  }, [runs, search, status]);

  if (experiments.isPending) {
    return (
      <>
        <PageTitle />
        <Placeholder className="h-96 w-full" label="Loading runs" />
      </>
    );
  }
  if (experiments.isError) {
    return (
      <>
        <PageTitle />
        <ErrorState title="The runs could not be read" message={experiments.error.message} onRetry={() => experiments.refetch()} />
      </>
    );
  }
  if (experiments.data.length === 0) {
    return (
      <>
        <PageTitle />
        <EmptyState title="No workload has been run yet">
          Start one with <Command>python scripts/run_workload.py --scenario NORMAL_DAY</Command>
        </EmptyState>
      </>
    );
  }

  const filters = (
    <div className="flex flex-wrap gap-3">
      <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Scenario or run ID" aria-label="Filter by scenario or run ID" className={`${FIELD} w-56`} />
      <select value={status} onChange={(event) => setStatus(event.target.value as RunStatus | "")} aria-label="Filter by status" className={FIELD}>
        <option value="">Any status</option>
        <option value="COMPLETED">Completed</option>
        <option value="RUNNING">Running</option>
        <option value="FAILED">Failed</option>
      </select>
    </div>
  );

  return (
    <>
      <PageTitle />
      <Section title={visible.length === experiments.data.length ? `${visible.length} runs` : `${visible.length} of ${experiments.data.length} runs`} aside={filters}>
        {visible.length === 0 ? <EmptyState title="No run matches these filters">Clear the search or choose another status.</EmptyState> : <RunsTable runs={visible} caption="Workload runs matching the current filters" />}
      </Section>
    </>
  );
}
