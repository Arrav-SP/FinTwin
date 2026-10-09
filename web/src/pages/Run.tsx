import { Link } from "react-router";
import { JobRunner } from "../components/JobRunner";
import { PageIntro } from "../components/Section";

const LINK = "text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper";

export function Run() {
  return (
    <>
      <PageIntro title="Run a workload">Send banking operations at PostgreSQL at a set rate and record how it responds.</PageIntro>
      <JobRunner
        kind="workload"
        action="Start the run"
        working="Running"
        note="This writes to the database: deposits, transfers and payments change account balances. Runs are queued one at a time so they cannot disturb each other."
        done={(job) =>
          job.result?.experiment_id ? (
            <Link to={`/experiments/${job.result.experiment_id}`} className={LINK}>
              Read what the run found
            </Link>
          ) : null
        }
      />
    </>
  );
}
