import { afterEach, describe, expect, it, vi } from "vitest";
import { applyTheme, readTheme } from "./theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  vi.restoreAllMocks();
});

describe("theme", () => {
  it("is dark until the person chooses otherwise", () => {
    expect(readTheme()).toBe("dark");
    localStorage.setItem("fintwin-theme", "sepia");
    expect(readTheme()).toBe("dark");
  });

  it("applies a choice to the document and remembers it", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(readTheme()).toBe("light");
  });

  it("still applies a choice when the browser refuses to store it", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
