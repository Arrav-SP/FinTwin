import { useAssessment } from "../api/queries";
import type { Recommendation } from "../api/types";
import { formatNumber } from "../lib/format";
import { evidenceLabel } from "../lib/jobs";
import { Section } from "./Section";
import { ErrorState, Placeholder } from "./States";

const SEVERITY: Record<Recommendation["severity"], string> = { CRITICAL: "Critical", HIGH: "High", MEDIUM: "Medium", LOW: "Low", INFO: "Note" };

function Finding({ item }: { item: Recommendation }) {
  return (
    <li className="grid gap-x-10 gap-y-3 border-b border-rule py-5 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div>
        <p className="text-xs text-amber">{SEVERITY[item.severity]} severity</p>
        <p className="mt-1 text-base">{item.title}</p>
        <dl className="num m-0 mt-3 grid gap-1 text-graphite">
          {Object.entries(item.evidence).map(([field, value]) => (
            <div key={field} className="flex justify-between gap-6">
              <dt>{evidenceLabel(field)}</dt>
              <dd className="m-0 text-paper">{formatNumber(value, 2)}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="max-w-[62ch]">
        <p>{item.description}</p>
        <p className="mt-2 text-graphite">{item.recommended_action}</p>
      </div>
    </li>
  );
}

/** What the rule-based advisor found in this run's measurements. It suggests where to look; it changes nothing. */
export function AdvisorFindings({ id }: { id: string }) {
  const assessment = useAssessment(id);
  return (
    <Section title="What the advisor found" note="Fixed thresholds applied to this run's measurements. Each finding is a place to look, not a change to make.">
      {assessment.isPending && <Placeholder className="h-32 w-full" label="Loading the advisor's findings" />}
      {assessment.isError && <ErrorState title="The advisor could not assess this run" message={assessment.error.message} onRetry={() => assessment.refetch()} />}
      {assessment.isSuccess && (
        <>
          {assessment.data.recommendations.length === 0 ? (
            <p className="max-w-[62ch]">No measurement crossed a threshold in this run.</p>
          ) : (
            <ul className="m-0 list-none border-t border-rule p-0">
              {assessment.data.recommendations.map((item) => (
                <Finding key={item.recommendation_id} item={item} />
              ))}
            </ul>
          )}
          {assessment.data.warnings?.map((warning) => (
            <p key={warning} className="mt-4 max-w-[70ch] text-xs text-graphite">
              {warning}
            </p>
          ))}
        </>
      )}
    </Section>
  );
}
