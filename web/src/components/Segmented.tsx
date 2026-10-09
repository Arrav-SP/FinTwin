/** A small set of mutually exclusive views. Buttons, not tabs: the content below is one chart re-plotted. */
export function Segmented<Key extends string>({ label, options, value, onChange }: { label: string; options: readonly { key: Key; label: string }[]; value: Key; onChange: (key: Key) => void }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-x-5 gap-y-1">
      {options.map((option) => {
        const selected = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.key)}
            className={`cursor-pointer border-0 border-b-2 bg-transparent px-0 pb-1 pt-1 transition-colors ${selected ? "border-paper text-paper" : "border-transparent text-graphite hover:text-paper"}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
