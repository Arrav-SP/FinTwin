import { formatNumber, formatPercent } from "../lib/format";
import { type EvidenceRow, gapGeometry, TARGET_LABELS } from "./evidence";

const ROW = "grid grid-cols-[minmax(0,1fr)_3.5rem_3.75rem_3.75rem] items-baseline gap-x-3 sm:grid-cols-[minmax(0,1fr)_4.5rem_4.5rem_4.75rem] sm:gap-x-4";
const HOLLOW = "border-[1.5px] border-dashed border-paper bg-ink";

export function EvidenceKey() {
  return (
    <div className="flex items-center gap-5 text-xs text-graphite">
      <span className="flex items-center gap-2">
        <span className={`size-3 rounded-full ${HOLLOW}`} aria-hidden="true" />
        Predicted
      </span>
      <span className="flex items-center gap-2">
        <span className="size-3 rounded-full bg-signal" aria-hidden="true" />
        Measured
      </span>
    </div>
  );
}

function Track({ row }: { row: EvidenceRow }) {
  const { predictedX, measuredX } = gapGeometry(row.predicted, row.measured, 100);
  const coincide = Math.abs(predictedX - measuredX) < 1.5;
  return (
    <div className="relative mx-1.5 h-6" aria-hidden="true">
      <div className="absolute inset-x-0 top-1/2 h-px bg-rule" />
      <div className="absolute left-0 top-1/2 h-2.5 w-px -translate-y-1/2 bg-rule-strong" />
      <div className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-pencil" style={{ left: `${Math.min(predictedX, measuredX)}%`, width: `${Math.abs(predictedX - measuredX)}%` }} />
      <span data-marker="measured" className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-signal ${coincide ? "size-2" : "size-3"}`} style={{ left: `${measuredX}%` }} />
      <span data-marker="predicted" className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full ${coincide ? "size-[1.125rem] border-[1.5px] border-dashed border-paper" : `size-3 ${HOLLOW}`}`} style={{ left: `${predictedX}%` }} />
    </div>
  );
}

/**
 * One row per metric, with a track on its own scale starting at zero: a hollow marker where the model said
 * the value would be, a filled one where it was measured. The distance is the miss.
 */
export function EvidenceGap({ rows }: { rows: EvidenceRow[] }) {
  return (
    <div>
      <div className={`${ROW} border-b border-rule pb-2 text-xs text-graphite`} aria-hidden="true">
        <span>Metric</span>
        <span className="text-right">Predicted</span>
        <span className="text-right">Measured</span>
        <span className="text-right">Error</span>
      </div>
      <ul className="m-0 list-none p-0">
        {rows.map((row) => {
          const { label, unit } = TARGET_LABELS[row.key];
          const digits = row.key === "lock_wait_count_max" ? 0 : 1;
          return (
            <li key={row.key} className={`${ROW} border-b border-rule pb-2.5 pt-3.5`}>
              <span>
                {label}
                {unit && <span className="text-graphite"> ({unit})</span>}
              </span>
              <span className="num text-right">
                <span className="sr-only">predicted </span>
                {formatNumber(row.predicted, digits)}
              </span>
              <span className="num text-right font-medium text-signal">
                <span className="sr-only">measured </span>
                {formatNumber(row.measured, digits)}
              </span>
              <span className={`num text-right ${row.percentageError === null ? "text-xs text-graphite" : ""}`}>
                <span className="sr-only">error </span>
                {row.percentageError === null ? "not defined" : formatPercent(row.percentageError)}
              </span>
              <div className="col-span-4 mt-2.5">
                <Track row={row} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
