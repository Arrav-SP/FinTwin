import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";
import { SIGN_IN_PATH, useJob, useJobs, useScenarios, useSession, useSubmitJob } from "../api/queries";
import type { Job, JobKind, RunLimits, WorkloadInput } from "../api/types";
import { scenarioLabel } from "../lib/format";
import { jobProgress } from "../lib/jobs";
import { EmptyState, ErrorState, Placeholder } from "./States";
import { DEFAULT_WORKLOAD, WorkloadForm } from "./WorkloadForm";

const isActive = (job: Job | undefined) => job?.status === "queued" || job?.status === "running";

function useNow(ticking: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!ticking) return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [ticking]);
  return now;
}

function Progress({ job }: { job: Job }) {
  const now = useNow(isActive(job));
  const { message, fraction } = jobProgress(job, now);
  const { scenario, concurrency, target_tps } = job.request.workload;
  return (
    <div className="max-w-xl" role="status">
      <p className="serif text-lg">{message}</p>
      <p className="num mt-1.5 text-graphite">
        {scenarioLabel(scenario)}, {concurrency} workers at {target_tps} TPS
      </p>
      {isActive(job) && (
        <div className="relative mt-4 h-1.5 bg-slate" aria-hidden="true">
          {fraction === null ? <div className="absolute inset-y-0 left-0 w-1/5 animate-pulse bg-rule-strong motion-reduce:animate-none" /> : <div className="absolute inset-y-0 left-0 bg-paper transition-[width] duration-500 ease-linear" style={{ width: `${fraction * 100}%` }} />}
        </div>
      )}
    </div>
  );
}

const LINK = "text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper";

/** On a public server a visitor who is not signed in sees why, not a form the server would refuse. */
function SignInFirst({ available, limits }: { available: boolean; limits: RunLimits }) {
  return (
    <EmptyState title="Sign in to run a workload here">
      <p className="max-w-[62ch]">
        Anyone can read the recorded runs and use Predict and What if. Running a workload loads the shared database, so it needs a sign-in and is limited to {limits.max_concurrency} workers, {limits.max_target_tps} TPS and {limits.max_duration_seconds} seconds.
      </p>
      <p className="mt-3 max-w-[62ch]">What you run is visible only to you. Its measurements, without your name, are used to retrain the site's models.</p>
      <p className="mt-4">
        {available ? (
          <a href={SIGN_IN_PATH} target="_top" className={LINK}>
            Sign in with GitHub
          </a>
        ) : (
          "Sign-in has not been set up on this server."
        )}
      </p>
    </EmptyState>
  );
}

/**
 * Describe a workload, start it as a background job, and follow it to its outcome.
 * A job that is still running when the page is reopened is picked up again.
 */
export function JobRunner({ kind, action, working, note, done }: { kind: JobKind; action: string; working: string; note: string; done: (job: Job) => ReactNode }) {
  const queryClient = useQueryClient();
  const scenarios = useScenarios();
  const jobs = useJobs();
  const session = useSession();
  const submit = useSubmitJob();
  const [workload, setWorkload] = useState<WorkloadInput>(DEFAULT_WORKLOAD);
  const [startedId, setStartedId] = useState<string>();

  const resumedId = jobs.data?.find((job) => job.kind === kind && isActive(job))?.job_id;
  const job = useJob(startedId ?? resumedId).data;
  const busy = submit.isPending || isActive(job);

  const finished = job?.status === "completed" || job?.status === "failed";
  useEffect(() => {
    if (finished) for (const key of ["experiments", "validations", "validation-summary", "jobs", "session"]) queryClient.invalidateQueries({ queryKey: [key] });
  }, [finished, queryClient]);

  if (scenarios.isPending || session.isPending) return <Placeholder className="h-40 w-full" label="Loading scenarios" />;
  if (scenarios.isError) return <ErrorState title="The form could not be prepared" message={scenarios.error.message} onRetry={() => scenarios.refetch()} />;

  // A server that does not answer the session question is a private one: no restrictions.
  const restricted = session.data?.public === true ? session.data : undefined;
  if (restricted && !restricted.signed_in) return <SignInFirst available={restricted.sign_in_available} limits={restricted.run_limits} />;
  const catalogue = restricted ? { ...scenarios.data, limits: restricted.run_limits } : scenarios.data;
  const spent = restricted?.runs_left === 0;
  const allowance = !restricted ? "" : spent ? ` You have used today's ${restricted.runs_per_day} runs; the allowance refills over the next 24 hours.` : ` ${restricted.runs_left} of ${restricted.runs_per_day} runs left today.`;

  return (
    <>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit.mutate({ kind, workload }, { onSuccess: (created) => setStartedId(created.job_id) });
        }}
      >
        <WorkloadForm id={kind} value={workload} onChange={setWorkload} catalogue={catalogue} />
        <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3">
          <button type="submit" className="primary" disabled={busy || spent}>
            {busy ? working : action}
          </button>
          <p className="max-w-[52ch] text-xs text-graphite">
            {note}
            {allowance}
          </p>
        </div>
      </form>
      <div className="mt-10" aria-live="polite">
        {submit.isError && <ErrorState title="The run was not started" message={submit.error.message} />}
        {job && (
          <div className="border-l-2 border-rule-strong pl-5">
            <Progress job={job} />
            {job.status === "failed" && <p className="mt-3 max-w-[62ch] text-red">{job.error}</p>}
            {job.status === "completed" && <div className="mt-4">{done(job)}</div>}
          </div>
        )}
      </div>
    </>
  );
}
