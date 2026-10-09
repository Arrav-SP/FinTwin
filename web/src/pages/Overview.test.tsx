import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Overview } from "./Overview";

afterEach(() => vi.unstubAllGlobals());

function renderOverview(respond: (url: string) => Response) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => respond(url)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Overview />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("Overview", () => {
  it("shows placeholders while the runs are being read", () => {
    renderOverview(() => json(200, []));
    expect(screen.getByRole("status", { name: "Loading the latest run" })).toBeInTheDocument();
  });

  it("reports the server's own reason when the runs cannot be read, and offers a retry", async () => {
    renderOverview(() => json(503, { detail: "Database unavailable" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The runs could not be read");
    expect(alert).toHaveTextContent("Database unavailable");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("tells a new user how to start the first run instead of showing empty figures", async () => {
    renderOverview(() => json(200, []));
    expect(await screen.findByText("No workload has been run yet")).toBeInTheDocument();
    expect(screen.getByText(/python scripts\/run_workload\.py/)).toBeInTheDocument();
    expect(screen.queryByText("Delivered throughput")).not.toBeInTheDocument();
  });
});
