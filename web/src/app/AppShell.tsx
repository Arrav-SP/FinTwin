import { NavLink, Outlet } from "react-router";
import { useSystemStatus } from "../api/queries";
import type { ComponentState } from "../api/types";

const NAVIGATION = [
  { to: "/", label: "Overview", end: true },
  { to: "/experiments", label: "Experiments", end: false },
  { to: "/run", label: "Run", end: false },
  { to: "/predict", label: "Predict", end: false },
  { to: "/what-if", label: "What if", end: false },
  { to: "/validation", label: "Validation", end: false },
  { to: "/models", label: "Models", end: false },
];

const HEALTHY: ComponentState[] = ["connected", "active", "ready"];
const STATE_TEXT: Record<ComponentState, string> = {
  connected: "connected",
  offline: "offline",
  active: "collecting",
  awaiting_data: "no samples yet",
  unavailable: "unavailable",
  ready: "loaded",
};

/** The mark is the design rule in miniature: a solid measured trace over a dashed predicted one. */
function Wordmark() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5 text-paper no-underline" aria-label="FinTwin, overview">
      <svg width="26" height="22" viewBox="0 0 26 22" aria-hidden="true">
        <path d="M1 14 L8 7 L14 11 L25 2" fill="none" stroke="var(--color-signal)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M1 20 L8 14 L14 17 L25 9" fill="none" stroke="var(--color-paper)" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="0.5 4" />
      </svg>
      <span className="serif text-lg leading-none">FinTwin</span>
    </NavLink>
  );
}

function SystemStatus() {
  const { data, isError } = useSystemStatus();
  const parts: [string, ComponentState | undefined][] = [
    ["PostgreSQL", isError ? "offline" : data?.database],
    ["Telemetry", isError ? "unavailable" : data?.telemetry],
    ["Models", isError ? "unavailable" : data?.ml_models],
  ];
  return (
    <ul className="m-0 flex list-none items-center gap-5 p-0 text-xs text-graphite" aria-label="System status">
      {parts.map(([name, state], index) => {
        const healthy = state !== undefined && HEALTHY.includes(state);
        return (
          <li key={name} className={`items-center gap-2 whitespace-nowrap ${index === 0 ? "flex" : "hidden lg:flex"}`}>
            <span className={`size-2 shrink-0 rounded-full ${state === undefined ? "bg-pencil" : healthy ? "bg-signal" : "bg-red"}`} aria-hidden="true" />
            <span className="max-sm:sr-only">
              {name} <span className={healthy || state === undefined ? "" : "text-red"}>{state === undefined ? "checking" : STATE_TEXT[state]}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function AppShell() {
  return (
    <>
      <a href="#content" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-20 focus:bg-paper focus:px-3 focus:py-2 focus:text-ink">
        Skip to content
      </a>
      <header className="sticky top-0 z-10 border-b border-rule bg-ink/95 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-x-5 px-5 sm:gap-x-8 sm:px-8">
          <Wordmark />
          <nav aria-label="Sections" className="flex h-full min-w-0 items-stretch gap-4 overflow-x-auto whitespace-nowrap [scrollbar-width:none] sm:gap-6">
            {NAVIGATION.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex items-center border-b-2 pt-0.5 no-underline transition-colors ${isActive ? "border-paper text-paper" : "border-transparent text-graphite hover:text-paper"}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto shrink-0">
            <SystemStatus />
          </div>
        </div>
      </header>
      <main id="content" className="mx-auto max-w-[1320px] px-5 pb-20 pt-10 sm:px-8 sm:pt-14">
        <Outlet />
      </main>
    </>
  );
}
