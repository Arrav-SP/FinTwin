import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Validation } from "./Validation";

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

const check = (id: string) => ({
  validation_id: id,
  scenario: "NORMAL_DAY",
  workload_configuration: { concurrency: 12, target_tps: 100 },
  validation_status: "COMPLETED",
  predicted_metrics: { predicted_average_latency_ms: 6.3, predicted_actual_tps: 99.9 },
  actual_metrics: { average_latency_ms: 6.4, actual_tps: 100 },
  error_metrics: { average_latency_ms: { absolute_error: 0.1, percentage_error: 1.6 }, actual_tps: { absolute_error: 0.1, percentage_error: 0.1 } },
  actual_experiment_id: null,
  error_message: null,
  created_at: "2026-10-10T08:05:00Z",
});

const accuracy = { count: 1, mae: 0.1, rmse: 0.1, r2: null, mape: 1.6 };

function renderValidation(current: { checks: unknown[]; earlier: number }) {
  const requested: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      requested.push(url);
      const all = url.includes("scope=all");
      if (url.startsWith("/api/validation/summary")) {
        const count = all ? current.checks.length + current.earlier : current.checks.length;
        return json({ validation_count: count, pending_or_failed_count: 0, earlier_count: all ? 0 : current.earlier, overall: count ? { average_latency_ms: { ...accuracy, count } } : {} });
      }
      if (url.startsWith("/api/validation")) return json(all ? [...current.checks, ...Array.from({ length: current.earlier }, (_, index) => check(`old-${index}`))] : current.checks);
      if (url.startsWith("/api/scenarios")) return json({ scenarios: [{ scenario: "NORMAL_DAY", operation_mix: { BALANCE_CHECK: 1 } }], limits: { max_concurrency: 64, max_target_tps: 1000, max_duration_seconds: 600 } });
      return json([]);
    }),
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <Validation />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return requested;
}

describe("Validation", () => {
  it("judges the models now in use, and says how many earlier checks it leaves out", async () => {
    const requested = renderValidation({ checks: [check("new-1"), check("new-2")], earlier: 7 });
    expect(await screen.findByText("Across 2 completed checks of the models now in use. 7 earlier checks tested models that have since been replaced.")).toBeInTheDocument();
    expect(requested).toContain("/api/validation/summary?scope=current");
    expect(requested).toContain("/api/validation?scope=current&limit=1000");
    expect(screen.getByRole("button", { name: "Current models" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows every check on request", async () => {
    const requested = renderValidation({ checks: [check("new-1"), check("new-2")], earlier: 7 });
    fireEvent.click(await screen.findByRole("button", { name: "All checks" }));
    expect(await screen.findByText("Across 9 completed checks, including those of models that have since been replaced.")).toBeInTheDocument();
    expect(requested).toContain("/api/validation/summary?scope=all");
  });

  it("says so when the current models have not been checked yet but earlier ones were", async () => {
    renderValidation({ checks: [], earlier: 7 });
    expect(await screen.findByText("The models now in use have not been checked yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All checks" })).toBeInTheDocument();
  });
});
