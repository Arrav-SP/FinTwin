import type { ReactNode } from "react";

/** The opening of a page that is a tool, not a finding: a serif title and one line on what it does. */
export function PageIntro({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-10">
      <h1 className="serif text-lede leading-[1.08]">{title}</h1>
      {children && <p className="mt-4 max-w-[62ch] text-base text-graphite">{children}</p>}
    </header>
  );
}

/**
 * A titled region separated from its neighbours by a rule and space, not by a box.
 * The serif title names what the reader is looking at; the note says how to read it.
 */
export function Section({ title, note, aside, children, className = "" }: { title: string; note?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 border-t border-rule pt-5 ${className}`}>
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
