import { createBrowserRouter } from "react-router";
import { Experiments } from "../pages/Experiments";
import { Models } from "../pages/Models";
import { Overview } from "../pages/Overview";
import { Predict } from "../pages/Predict";
import { Run } from "../pages/Run";
import { RunDetail } from "../pages/RunDetail";
import { Validation } from "../pages/Validation";
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
      { path: "run", element: <Run /> },
      { path: "predict", element: <Predict /> },
      { path: "validation", element: <Validation /> },
      { path: "models", element: <Models /> },
      { path: "what-if", element: <WhatIf /> },
    ],
  },
]);
