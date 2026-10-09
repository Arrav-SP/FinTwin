import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Predict } from "./Predict";

afterEach(() => vi.unstubAllGlobals());

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const SCENARIOS = { scenarios: [{ scenario: "NORMAL_DAY", operation_mix: {} }], limits: { max_concurrency: 64, max_target_tps: 1000, max_duration_seconds: 600 } };
const MODELS = [{ target: "actual_tps", algorithm: "linear_regression", training_samples: 5, test_samples: 2, metrics: { mae: 0.3, rmse: 0.5, r2: 0.9 }, scenario_values: ["NORMAL_DAY"], numeric_ranges: { concurrency: [4, 12], target_tps: [10, 30], duration_seconds: [10, 10] }, trained_at: "2026-09-11T21:00:00Z" }];

function renderPredict(prediction: () => Response, models: unknown = MODELS) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/scenarios") return json(200, SCENARIOS);
    if (url === "/api/models") return json(200, models);
    if (url === "/api/predictions" && init?.method === "POST") return prediction();
    return json(404, { detail: "Not found" });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <Predict />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

describe("Predict", () => {
  it("sends the described workload and shows the estimates as predictions", async () => {
    const fetchMock = renderPredict(() =>
      json(200, { workload: { scenario: "NORMAL_DAY", concurrency: 50, target_tps: 20, duration_seconds: 10, account_skew: 0 }, predictions: { predicted_actual_tps: 25.92, predicted_average_latency_ms: 9.46 }, warnings: ["concurrency=50 is outside the training range 4.0–12.0"] }),
    );
    fireEvent.change(await screen.findByLabelText("Workers"), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Predict" }));

    expect(await screen.findByText("Predicted throughput")).toBeInTheDocument();
    expect(screen.getByText("25.9")).toBeInTheDocument();
    expect(screen.getByText("outside 4 to 12")).toBeInTheDocument();
    expect(screen.getByText("inside 10 to 30")).toBeInTheDocument();
    expect(screen.getByText("concurrency=50 is outside the training range 4.0–12.0")).toBeInTheDocument();

    const sent = JSON.parse(fetchMock.mock.calls.find(([url]) => url === "/api/predictions")![1]!.body as string);
    expect(sent).toMatchObject({ scenario: "NORMAL_DAY", concurrency: 50 });
  });

  it("says that a setting the models never saw is ignored", async () => {
    renderPredict(() => json(200, { workload: { scenario: "NORMAL_DAY", concurrency: 8, target_tps: 20, duration_seconds: 10, account_skew: 1.5 }, predictions: { predicted_actual_tps: 20 }, warnings: [] }));
    fireEvent.click(await screen.findByRole("button", { name: "Predict" }));
    expect(await screen.findByText(/trained before this setting existed/)).toBeInTheDocument();
  });

  it("shows the server's reason when no prediction can be made", async () => {
    renderPredict(() => json(409, { detail: "No trained model artifacts exist." }));
    fireEvent.click(await screen.findByRole("button", { name: "Predict" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No trained model artifacts exist.");
  });

  it("explains how to train when there are no models, instead of offering a form", async () => {
    renderPredict(() => json(200, {}), []);
    expect(await screen.findByText("No model has been trained yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Predict" })).not.toBeInTheDocument();
  });
});
