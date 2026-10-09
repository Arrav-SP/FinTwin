import type { ReactNode } from "react";

/** A quiet placeholder shaped like the content it stands in for. */
export function Placeholder({ className = "", label }: { className?: string; label: string }) {
  return <div role="status" aria-label={label} className={`animate-pulse rounded-control bg-slate motion-reduce:animate-none ${className}`} />;
}

export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="max-w-[64ch] border-l-2 border-red py-1 pl-5">
      <p className="serif text-lg">{title}</p>
      <p className="mt-2 text-graphite">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="control mt-4">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="max-w-[64ch] border-l-2 border-rule-strong py-1 pl-5">
      <p className="serif text-lg">{title}</p>
      <div className="mt-2 text-graphite">{children}</div>
    </div>
  );
}

export function Command({ children }: { children: string }) {
  return <code className="rounded-control bg-slate px-1.5 py-0.5 font-mono text-xs text-paper">{children}</code>;
}
