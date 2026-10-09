import { createBrowserRouter } from "react-router";
import { Experiments } from "../pages/Experiments";
import { Overview } from "../pages/Overview";
import { Predict } from "../pages/Predict";
import { RunDetail } from "../pages/RunDetail";
import { WhatIf } from "../pages/WhatIf";
import { AppShell } from "./AppShell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: "experiments", element: <Experiments /> },
      { path: "experiments/:id", element: <RunDetail /> },
      { path: "predict", element: <Predict /> },
      { path: "what-if", element: <WhatIf /> },
    ],
  },
]);
