import { describe, expect, it } from "vitest";
import { gapGeometry, pairValidationMetrics } from "./evidence";

describe("gapGeometry", () => {
  it("places both markers on one scale with headroom", () => {
    const geometry = gapGeometry(10, 20, 200);
    expect(geometry.predictedX).toBeCloseTo(87, 0);
    expect(geometry.measuredX).toBeCloseTo(174, 0);
    expect(geometry.measuredX).toBeLessThan(200);
  });
  it("keeps markers at the origin when both values are zero", () => {
    expect(gapGeometry(0, 0, 200)).toEqual({ predictedX: 0, measuredX: 0 });
  });
});

describe("pairValidationMetrics", () => {
  it("pairs each predicted metric with its measurement and error", () => {
    const rows = pairValidationMetrics({
      predicted_metrics: { predicted_average_latency_ms: 9.46, predicted_actual_tps: 12.15 },
      actual_metrics: { average_latency_ms: 18.83, actual_tps: 10.08 },
      error_metrics: { average_latency_ms: { absolute_error: 9.37, percentage_error: 49.75 } },
    });
    expect(rows.map((row) => row.key)).toEqual(["average_latency_ms", "actual_tps"]);
    expect(rows[0]).toMatchObject({ predicted: 9.46, measured: 18.83, percentageError: 49.75 });
    expect(rows[1].percentageError).toBeNull();
  });
  it("omits metrics that lack either side", () => {
    expect(pairValidationMetrics({ predicted_metrics: { predicted_actual_tps: 12 }, actual_metrics: {}, error_metrics: {} })).toEqual([]);
  });
});
