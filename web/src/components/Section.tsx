import type { ReactNode } from "react";

/**
 * A titled region separated from its neighbours by a rule and space, not by a box.
 * The serif title names what the reader is looking at; the note says how to read it.
 */
export function Section({ title, note, aside, children, className = "" }: { title: string; note?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`border-t border-rule pt-5 ${className}`}>
      <header className="mb-5 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-[60ch]">
          <h2 className="serif text-lg leading-tight">{title}</h2>
          {note && <p className="mt-1.5 text-graphite">{note}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}
