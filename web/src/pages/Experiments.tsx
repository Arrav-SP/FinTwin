import { useMemo, useState } from "react";
import { useExperiments, useSession } from "../api/queries";
import type { RunStatus } from "../api/types";
import { RunsTable } from "../components/RunsTable";
import { PageIntro, Section } from "../components/Section";
import { Segmented } from "../components/Segmented";
import { Command, EmptyState, ErrorState, Placeholder } from "../components/States";
import { scenarioLabel } from "../lib/format";

const FIELD = "min-h-9 rounded-control border border-rule-strong bg-well px-3 placeholder:text-pencil";

const OWNERS = [
  { key: "all", label: "Everyone's" },
  { key: "mine", label: "Mine" },
] as const;

const PageTitle = () => <PageIntro title="Experiments">Every workload run against PostgreSQL, newest first.</PageIntro>;

export function Experiments() {
  const experiments = useExperiments();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<RunStatus | "">("");
  const [owner, setOwner] = useState<"all" | "mine">("all");
  const signedIn = useSession().data?.signed_in === true;

  const runs = experiments.data;
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (runs ?? []).filter((run) => (owner === "all" || run.mine === true) && (!status || run.status === status) && (!needle || `${run.experiment_id} ${scenarioLabel(run.scenario)}`.toLowerCase().includes(needle)));
  }, [runs, search, status, owner]);

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
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
      {signedIn && <Segmented label="Runs shown" options={OWNERS} value={owner} onChange={setOwner} />}
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
        {visible.length === 0 ? <EmptyState title="No run matches these filters">{owner === "mine" ? "You have not started a run yet, or none matches the other filters." : "Clear the search or choose another status."}</EmptyState> : <RunsTable runs={visible} caption="Workload runs matching the current filters" />}
      </Section>
    </>
  );
}
