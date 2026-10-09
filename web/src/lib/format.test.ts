import { describe, expect, it } from "vitest";
import { formatInteger, formatNumber, formatPercent, scenarioLabel, shortId, toNumber } from "./format";

describe("toNumber", () => {
  it("parses the decimal strings the API returns", () => {
    expect(toNumber("37.6572")).toBe(37.6572);
    expect(toNumber(12)).toBe(12);
  });
  it("treats missing and non-numeric values as absent, never as zero", () => {
    expect(toNumber(null)).toBeNull();
    expect(toNumber(undefined)).toBeNull();
    expect(toNumber("")).toBeNull();
    expect(toNumber("n/a")).toBeNull();
  });
});

describe("formatting", () => {
  it("shows a dash for a missing measurement", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatInteger(undefined)).toBe("—");
    expect(formatPercent(null)).toBe("—");
  });
  it("keeps a real zero as zero", () => {
    expect(formatNumber(0)).toBe("0.0");
    expect(formatInteger("0")).toBe("0");
  });
  it("rounds to the requested precision", () => {
    expect(formatNumber("18.8324")).toBe("18.8");
    expect(formatNumber(274.7316, 0)).toBe("275");
    expect(formatPercent(49.7494)).toBe("49.7%");
  });
  it("turns scenario codes into readable names", () => {
    expect(scenarioLabel("HIGH_CONCURRENCY_TRANSFER")).toBe("High concurrency transfer");
  });
  it("shortens identifiers", () => {
    expect(shortId("1be70501-efd7-4e99-8262-7c402b8c2004")).toBe("1be70501");
    expect(shortId(null)).toBe("—");
  });
});
