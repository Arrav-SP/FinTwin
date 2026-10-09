import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceGap } from "./EvidenceGap";

const position = (container: HTMLElement, kind: "predicted" | "measured") => parseFloat(container.querySelector<HTMLElement>(`[data-marker="${kind}"]`)!.style.left);

describe("EvidenceGap", () => {
  it("states the predicted value, the measured value and the error for a metric", () => {
    render(<EvidenceGap rows={[{ key: "average_latency_ms", predicted: 9.5, measured: 18.8, percentageError: 49.7 }]} />);
    const row = screen.getByRole("listitem");
    expect(within(row).getByText("Average latency")).toBeInTheDocument();
    expect(within(row).getByText("9.5")).toBeInTheDocument();
    expect(within(row).getByText("18.8")).toBeInTheDocument();
    expect(within(row).getByText("49.7%")).toBeInTheDocument();
  });

  it("places each marker by its own value, whichever is larger", () => {
    const over = render(<EvidenceGap rows={[{ key: "actual_tps", predicted: 12.1, measured: 10.1, percentageError: 20.8 }]} />);
    expect(position(over.container, "predicted")).toBeGreaterThan(position(over.container, "measured"));
    over.unmount();
    const under = render(<EvidenceGap rows={[{ key: "p95_latency_ms", predicted: 14, measured: 44.2, percentageError: 68.2 }]} />);
    expect(position(under.container, "measured")).toBeGreaterThan(position(under.container, "predicted"));
  });

  it("does not invent a percentage when the measured value is zero", () => {
    render(<EvidenceGap rows={[{ key: "lock_wait_count_max", predicted: 0, measured: 0, percentageError: null }]} />);
    expect(screen.getByText("not defined")).toBeInTheDocument();
  });
});
