import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NotFound } from "../pages/NotFound";
import { AppShell } from "./AppShell";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

function renderAt(path: string) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } })));
  const router = createMemoryRouter(
    [{ path: "/", element: <AppShell />, children: [{ index: true, element: <p>Overview page</p> }, { path: "*", element: <NotFound /> }] }],
    { initialEntries: [path] },
  );
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  it("lets the person switch to the light theme and shows which one is on", () => {
    renderAt("/");
    const theme = screen.getByRole("group", { name: "Theme" });
    expect(theme).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
  });

  it("answers an address that is not a page with a way back, inside the usual frame", () => {
    renderAt("/no-such-page");
    expect(screen.getByRole("heading", { level: 1, name: "There is no page at this address" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the overview" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("navigation", { name: "Sections" })).toBeInTheDocument();
  });
});
