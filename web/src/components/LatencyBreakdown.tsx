import type { LatencyBreakdown as Breakdown } from "../api/types";
import { formatInteger, formatNumber, scenarioLabel } from "../lib/format";
import { histogramBars } from "../lib/workload";

const HEAD = "px-3 pb-2.5 font-normal first:pl-0 last:pr-0";
const CELL = "px-3 py-3 first:pl-0 last:pr-0";

/** How many operations fell in each latency band. Bars are filled: these are measured counts. */
function Histogram({ breakdown }: { breakdown: Breakdown }) {
  const bars = histogramBars(breakdown.histogram);
  return (
    <figure className="m-0">
      <figcaption className="mb-3 text-xs text-graphite">Operations by latency (ms)</figcaption>
      <ul className="m-0 grid list-none gap-1.5 p-0">
        {bars.map((bar) => (
          <li key={bar.label} className="num grid grid-cols-[6.5rem_minmax(0,1fr)_3.5rem] items-center gap-3">
            <span className="text-graphite">{bar.label}</span>
            <span className="h-4 bg-slate" aria-hidden="true">
              <span className="block h-full bg-signal" style={{ width: `${bar.share * 100}%` }} />
            </span>
            <span className="text-right">{formatInteger(bar.count)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

function OperationsTable({ breakdown }: { breakdown: Breakdown }) {
  const anyQueueWait = breakdown.operations.some((item) => item.average_queue_wait_ms !== null);
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] border-collapse">
        <caption className="sr-only">Latency by operation type</caption>
        <thead>
          <tr className="border-b border-rule-strong text-xs text-graphite">
            <th scope="col" className={`${HEAD} text-left`}>Operation</th>
            <th scope="col" className={`${HEAD} text-right`}>Count</th>
            <th scope="col" className={`${HEAD} text-right`}>Failed</th>
            <th scope="col" className={`${HEAD} text-right`}>Average (ms)</th>
            <th scope="col" className={`${HEAD} text-right`}>P95 (ms)</th>
            <th scope="col" className={`${HEAD} text-right`}>Slowest (ms)</th>
            {anyQueueWait && <th scope="col" className={`${HEAD} text-right`}>Waited for a worker (ms)</th>}
          </tr>
        </thead>
        <tbody className="num">
          {breakdown.operations.map((item) => (
            <tr key={item.operation} className="border-b border-rule">
              <td className={CELL}>{scenarioLabel(item.operation)}</td>
              <td className={`${CELL} text-right`}>{formatInteger(item.count)}</td>
              <td className={`${CELL} text-right ${item.failed ? "font-medium text-red" : ""}`}>{formatInteger(item.failed)}</td>
              <td className={`${CELL} text-right`}>{formatNumber(item.average_latency_ms)}</td>
              <td className={`${CELL} text-right`}>{formatNumber(item.p95_latency_ms)}</td>
              <td className={`${CELL} text-right`}>{formatNumber(item.max_latency_ms)}</td>
              {anyQueueWait && <td className={`${CELL} text-right`}>{formatNumber(item.average_queue_wait_ms, 2)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LatencyBreakdown({ breakdown }: { breakdown: Breakdown }) {
  return (
    <div className="grid gap-x-14 gap-y-10 wide:grid-cols-[minmax(0,4fr)_minmax(0,7fr)]">
      <Histogram breakdown={breakdown} />
      <OperationsTable breakdown={breakdown} />
    </div>
  );
}
