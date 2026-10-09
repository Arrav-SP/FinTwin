import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Job } from "../api/types";
import { Run } from "./Run";

afterEach(() => vi.unstubAllGlobals());

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const SCENARIOS = { scenarios: [{ scenario: "NORMAL_DAY", operation_mix: {} }], limits: { max_concurrency: 64, max_target_tps: 1000, max_duration_seconds: 600 } };

const job = (overrides: Partial<Job>): Job => ({
  job_id: "job-1",
  kind: "workload",
  status: "running",
  request: { kind: "workload", workload: { scenario: "NORMAL_DAY", concurrency: 8, target_tps: 20, duration_seconds: 10, account_skew: 0 } },
  submitted_at: new Date().toISOString(),
  started_at: new Date().toISOString(),
  finished_at: null,
  result: null,
  error: null,
  ...overrides,
});

function renderRun({ existing = [] as Job[], polled, submitted = json(202, job({})) }: { existing?: Job[]; polled: Job; submitted?: Response }) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/scenarios") return json(200, SCENARIOS);
    if (url === "/api/jobs" && init?.method === "POST") return submitted;
    if (url === "/api/jobs") return json(200, existing);
    if (url === "/api/jobs/job-1") return json(200, polled);
    return json(404, { detail: "Not found" });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <Run />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

describe("Run", () => {
  it("starts a background job and links to the run once it has finished", async () => {
    const fetchMock = renderRun({ polled: job({ status: "completed", finished_at: new Date().toISOString(), result: { experiment_id: "exp-9" } }) });
    fireEvent.click(await screen.findByRole("button", { name: "Start the run" }));

    const link = await screen.findByRole("link", { name: "Read what the run found" });
    expect(link).toHaveAttribute("href", "/experiments/exp-9");
    const sent = JSON.parse(fetchMock.mock.calls.find(([url, init]) => url === "/api/jobs" && init?.method === "POST")![1]!.body as string);
    expect(sent).toMatchObject({ kind: "workload", workload: { scenario: "NORMAL_DAY", concurrency: 8 } });
  });

  it("shows the reason when the run fails and offers no link", async () => {
    renderRun({ polled: job({ status: "failed", finished_at: new Date().toISOString(), error: "PostgreSQL is not reachable" }) });
    fireEvent.click(await screen.findByRole("button", { name: "Start the run" }));
    expect(await screen.findByText("PostgreSQL is not reachable")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Read what the run found" })).not.toBeInTheDocument();
  });

  it("picks up a run that is already in progress and blocks a second start", async () => {
    renderRun({ existing: [job({})], polled: job({}) });
    expect(await screen.findByText(/^Running, \d+ s of about 10 s$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Running" })).toBeDisabled();
  });

  it("reports the server's reason when the job is refused", async () => {
    renderRun({ polled: job({}), submitted: json(422, { detail: "concurrency must not exceed 64" }) });
    fireEvent.click(await screen.findByRole("button", { name: "Start the run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("concurrency must not exceed 64");
  });
});
