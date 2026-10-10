import { describe, expect, it } from "vitest";
import type { ModelCard } from "../api/types";
import { describeTraining } from "../components/Predicted";
import { verdict } from "./Models";

const model = (overrides: Partial<ModelCard>): ModelCard => ({
  target: "average_latency_ms",
  algorithm: "gradient_boosting",
  training_samples: 140,
  test_samples: 140,
  metrics: { mae: 4, rmse: 6, r2: 0.8 },
  scenario_values: ["NORMAL_DAY"],
  numeric_ranges: {},
  trained_at: "2026-10-10T05:00:00Z",
  ...overrides,
});

describe("verdict", () => {
  it("credits a model only when it clearly misses by less than predicting without one", () => {
    expect(verdict(model({ baseline: { mae: 10, rmse: 12, r2: 0 } }))).toBe("Better than no model");
    expect(verdict(model({ baseline: { mae: 4.1, rmse: 12, r2: 0 } }))).toBe("No better than no model");
    expect(verdict(model({ baseline: { mae: 2, rmse: 3, r2: 0.9 } }))).toBe("Worse than no model");
  });
  it("does not judge a model that was never compared", () => {
    expect(verdict(model({}))).toBe("Not compared");
  });
});

describe("describeTraining", () => {
  it("describes cross-validated models by runs, workloads and folds", () => {
    expect(describeTraining(model({ configurations: 70, cv_folds: 5 }))).toMatch(/^Models fitted on 140 runs of 70 workloads, .+\. Error estimated by 5-fold cross-validation/);
  });
  it("says that each fold holds out whole load settings when the models were scored that way", () => {
    expect(describeTraining(model({ configurations: 176, cv_folds: 5, held_out: "load settings" }))).toMatch(/each fold holding out every run at a set of loads, so a model is always scored at a load it was not trained on\.$/);
  });
  it("describes earlier models by their single held-out split", () => {
    expect(describeTraining(model({ training_samples: 5, test_samples: 2 }))).toMatch(/^Models fitted on 5 runs and checked on 2 held back/);
  });
});
