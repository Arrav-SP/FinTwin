import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet } from "./client";

afterEach(() => vi.unstubAllGlobals());

const respond = (status: number, body: unknown) =>
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })));

describe("apiGet", () => {
  it("returns the parsed body on success", async () => {
    respond(200, { status: "ok" });
    await expect(apiGet("/api/health")).resolves.toEqual({ status: "ok" });
  });
  it("raises the server's own explanation on failure", async () => {
    respond(503, { detail: "Database unavailable" });
    const error = (await apiGet("/api/health").catch((reason: unknown) => reason)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(503);
    expect(error.message).toBe("Database unavailable");
  });
  it("explains an unreachable server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const error = (await apiGet("/api/health").catch((reason: unknown) => reason)) as ApiError;
    expect(error.message).toMatch(/cannot reach the FinTwin server/i);
  });
});
