import { createBrowserRouter } from "react-router";
import { NotFound, PageFailed } from "../pages/NotFound";
import { AppShell } from "./AppShell";

// Each page is fetched when first visited, so the charting library is downloaded only by
// pages that draw a chart, and separately from the frame around them.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <PageFailed />,
    hydrateFallbackElement: <></>,
    children: [
      { index: true, lazy: async () => ({ Component: (await import("../pages/Overview")).Overview }) },
      { path: "experiments", lazy: async () => ({ Component: (await import("../pages/Experiments")).Experiments }) },
      { path: "experiments/:id", lazy: async () => ({ Component: (await import("../pages/RunDetail")).RunDetail }) },
      { path: "run", lazy: async () => ({ Component: (await import("../pages/Run")).Run }) },
      { path: "predict", lazy: async () => ({ Component: (await import("../pages/Predict")).Predict }) },
      { path: "validation", lazy: async () => ({ Component: (await import("../pages/Validation")).Validation }) },
      { path: "models", lazy: async () => ({ Component: (await import("../pages/Models")).Models }) },
      { path: "what-if", lazy: async () => ({ Component: (await import("../pages/WhatIf")).WhatIf }) },
      { path: "*", element: <NotFound /> },
    ],
  },
]);
