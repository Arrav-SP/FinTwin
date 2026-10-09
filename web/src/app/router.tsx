import { createBrowserRouter } from "react-router";
import { Experiments } from "../pages/Experiments";
import { Overview } from "../pages/Overview";
import { AppShell } from "./AppShell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: "experiments", element: <Experiments /> },
    ],
  },
]);
