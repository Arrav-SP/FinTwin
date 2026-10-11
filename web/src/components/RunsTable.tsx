import { Link } from "react-router";
import type { Experiment } from "../api/types";
import { formatDateTime, formatInteger, formatNumber, scenarioLabel, shortId, toNumber } from "../lib/format";
import { deliveredShare } from "../lib/runSummary";

const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";

function Delivered({ run }: { run: Experiment }) {
  const share = deliveredShare(run.actual_tps, run.configuration.target_tps);
  return (
    <span className="inline-flex items-center justify-end gap-3">
      {share !== null && (
        <span className="relative hidden h-1 w-14 bg-slate sm:block" aria-hidden="true">
          <span className={`absolute inset-y-0 left-0 ${share < 0.95 ? "bg-amber" : "bg-signal"}`} style={{ width: `${share * 100}%` }} />
        </span>
      )}
      <span className="w-12">{formatNumber(run.actual_tps)}</span>
    </span>
  );
}

/** The run log. Units live in the column heads so the cells stay clean columns of figures. */
export function RunsTable({ runs, caption }: { runs: Experiment[]; caption: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Started</th>
            <th scope="col" className={`${HEAD} text-left`}>Scenario</th>
            <th scope="col" className={`${HEAD} text-right`}>Workers</th>
            <th scope="col" className={`${HEAD} text-right`}>Requested (TPS)</th>
            <th scope="col" className={`${HEAD} text-right`}>Delivered (TPS)</th>
            <th scope="col" className={`${HEAD} text-right`}>Average (ms)</th>
            <th scope="col" className={`${HEAD} text-right`}>P95 (ms)</th>
            <th scope="col" className={`${HEAD} text-right`}>Lock waits</th>
            <th scope="col" className={`${HEAD} text-right`}>Run</th>
          </tr>
        </thead>
        <tbody className="num">
          {runs.map((run) => {
            const waits = toNumber(run.lock_wait_count_max);
            return (
              <tr key={run.experiment_id} className="border-b border-rule transition-colors hover:bg-slate/50">
                <td className={`${CELL} whitespace-nowrap text-graphite`}>{formatDateTime(run.started_at)}</td>
                <td className={CELL}>
                  <Link to={`/experiments/${run.experiment_id}`} className="text-paper underline decoration-rule-strong underline-offset-4 hover:decoration-paper">
                    {scenarioLabel(run.scenario)}
                  </Link>
                  {run.mine && <span className="ml-2 text-xs text-graphite">yours</span>}
                  {run.status !== "COMPLETED" && <span className={`ml-2 text-xs ${run.status === "FAILED" ? "text-red" : "text-amber"}`}>{run.status === "FAILED" ? "failed" : "running"}</span>}
                </td>
                <td className={`${CELL} text-right`}>{formatInteger(run.configuration.concurrency)}</td>
                <td className={`${CELL} text-right`}>{formatNumber(run.configuration.target_tps, 0)}</td>
                <td className={`${CELL} text-right`}>
                  <Delivered run={run} />
                </td>
                <td className={`${CELL} text-right`}>{formatNumber(run.average_latency_ms)}</td>
                <td className={`${CELL} text-right`}>{formatNumber(run.p95_latency_ms)}</td>
                <td className={`${CELL} text-right ${waits ? "font-medium text-amber" : ""}`}>{formatInteger(run.lock_wait_count_max)}</td>
                <td className={`${CELL} text-right font-mono text-xs text-pencil`}>{shortId(run.experiment_id)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
