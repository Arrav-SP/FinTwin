import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../api/types";
import { AppShell } from "../app/AppShell";
import { Experiments } from "./Experiments";
import { Run } from "./Run";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const SCENARIOS = { scenarios: [{ scenario: "NORMAL_DAY", operation_mix: {} }], limits: { max_concurrency: 64, max_target_tps: 1000, max_duration_seconds: 600 } };
const PRIVATE: Session = { public: false, sign_in_available: false, signed_in: false, login: null, can_run: true, run_limits: SCENARIOS.limits, runs_per_day: null, runs_left: null };
const VISITOR: Session = { public: true, sign_in_available: true, signed_in: false, login: null, can_run: false, run_limits: { max_concurrency: 16, max_target_tps: 100, max_duration_seconds: 10 }, runs_per_day: 10, runs_left: null };
const MEMBER: Session = { ...VISITOR, signed_in: true, login: "octocat", can_run: true, runs_left: 7 };

const run = (id: string, mine: boolean) => ({
  experiment_id: id, scenario: "NORMAL_DAY", configuration: { concurrency: 4, target_tps: 10, duration_seconds: 2 }, started_at: "2026-10-11T08:00:00Z", completed_at: "2026-10-11T08:00:02Z",
  status: "COMPLETED", actual_tps: 10, average_latency_ms: 8, p50_latency_ms: 7, p95_latency_ms: 12, p99_latency_ms: 15, successful_operations: 20, failed_operations: 0, host_cpu_avg_percent: 12, lock_wait_count_max: 0, telemetry_sample_count: 3, mine,
});

function renderAt(path: string, session: Session) {
  const calls: { url: string; method: string }[] = [];
  let current = session;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET" });
      if (url === "/api/auth/forget") return json(200, { deleted_runs: 1 });
      if (url === "/api/auth/logout") {
        current = VISITOR;
        return new Response(null, { status: 204 });
      }
      if (url === "/api/auth/me") return json(200, current);
      if (url === "/api/scenarios") return json(200, SCENARIOS);
      if (url === "/api/jobs") return json(200, []);
      if (url.startsWith("/api/experiments")) return json(200, [run("11111111-aaaa", true), run("22222222-bbbb", false)]);
      return json(200, {});
    }),
  );
  const router = createMemoryRouter(
    [{ path: "/", element: <AppShell />, children: [{ index: true, element: <p>Overview page</p> }, { path: "run", element: <Run /> }, { path: "experiments", element: <Experiments /> }] }],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return calls;
}

describe("a private server", () => {
  it("shows the run form to anyone and nothing about accounts", async () => {
    renderAt("/run", PRIVATE);
    expect(await screen.findByRole("button", { name: "Start the run" })).toBeEnabled();
    expect(screen.getByText("1 to 64")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/public demonstration/i)).not.toBeInTheDocument();
  });
});

describe("a public server, not signed in", () => {
  it("explains why running needs a sign-in, and offers it, instead of showing a form that would be refused", async () => {
    renderAt("/run", VISITOR);
    expect(await screen.findByText("Sign in to run a workload here")).toBeInTheDocument();
    expect(screen.getByText(/16 workers, 100 TPS and 10 seconds/)).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText(/What you run is visible only to you/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start the run" })).not.toBeInTheDocument();
    const main = within(screen.getByRole("main"));
    expect(main.getByRole("link", { name: "Sign in with GitHub" })).toHaveAttribute("href", "/api/auth/login");
  });

  it("says so plainly when the server has no sign-in set up", async () => {
    renderAt("/run", { ...VISITOR, sign_in_available: false });
    expect(await screen.findByText(/Sign-in has not been set up on this server/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
  });

  it("tells every visitor what kind of site this is", async () => {
    renderAt("/", VISITOR);
    const footer = within(await screen.findByRole("contentinfo"));
    expect(await footer.findByText(/Public demonstration on shared hardware/)).toBeInTheDocument();
    expect(footer.getByText(/Runs you make are visible only to you/)).toBeInTheDocument();
    expect(footer.getByText(/without your name, to retrain the models/)).toBeInTheDocument();
    expect(footer.queryByRole("button", { name: "Delete my runs" })).not.toBeInTheDocument();
  });
});

describe("a public server, signed in", () => {
  it("shows the form with the public limits and the runs left today", async () => {
    renderAt("/run", MEMBER);
    expect(await screen.findByRole("button", { name: "Start the run" })).toBeEnabled();
    expect(screen.getByText("1 to 16")).toBeInTheDocument();
    expect(screen.getByText("up to 100")).toBeInTheDocument();
    expect(screen.getByText(/7 of 10 runs left today/)).toBeInTheDocument();
  });

  it("stops offering runs when today's allowance is used", async () => {
    renderAt("/run", { ...MEMBER, runs_left: 0 });
    expect(await screen.findByRole("button", { name: "Start the run" })).toBeDisabled();
    expect(screen.getByText(/You have used today's 10 runs/)).toBeInTheDocument();
  });

  it("names the account in the header and signs out on request", async () => {
    const calls = renderAt("/", MEMBER);
    const header = within(screen.getByRole("banner"));
    expect(await header.findByText("octocat")).toBeInTheDocument();
    fireEvent.click(header.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(calls).toContainEqual({ url: "/api/auth/logout", method: "POST" }));
    expect(await header.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/api/auth/login");
  });

  it("deletes this person's runs only after they confirm", async () => {
    const calls = renderAt("/", MEMBER);
    const footer = within(screen.getByRole("contentinfo"));
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    fireEvent.click(await footer.findByRole("button", { name: "Delete my runs" }));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(calls).not.toContainEqual({ url: "/api/auth/forget", method: "POST" });

    confirm.mockReturnValue(true);
    fireEvent.click(footer.getByRole("button", { name: "Delete my runs" }));
    await waitFor(() => expect(calls).toContainEqual({ url: "/api/auth/forget", method: "POST" }));
  });

  it("marks this person's runs in the list", async () => {
    renderAt("/experiments", MEMBER);
    const rows = await screen.findAllByRole("row");
    expect(rows.filter((row) => within(row).queryByText("yours")).length).toBe(1);
  });

  it("can narrow the experiments to the runs this person started", async () => {
    renderAt("/experiments", MEMBER);
    expect(await screen.findByText("2 runs")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mine" }));
    expect(await screen.findByText("1 of 2 runs")).toBeInTheDocument();
  });
});

describe("experiments for someone not signed in", () => {
  it("offers no filter for runs that could not be theirs", async () => {
    renderAt("/experiments", VISITOR);
    expect(await screen.findByText("2 runs")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mine" })).not.toBeInTheDocument();
  });
});
