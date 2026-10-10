# FinTwin interface

The interface lives in `web/`: React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, React Router and Recharts. It is built to static files in `web/dist`, which the FastAPI server serves at `http://127.0.0.1:8000/` beside the API. The design rules are in `web/DESIGN.md`; read that before changing anything visual.

The first interface (`frontend/`, plain HTML and JavaScript) is no longer served. `docs/UI_RESULTS.md` describes it and is kept as history.

## Commands

```powershell
npm --prefix web install
npm --prefix web run build      # needed before the server can show the interface
npm --prefix web run dev        # development server on port 5173, proxies /api to port 8000
npm --prefix web test
npm --prefix web run typecheck
```

## Pages

| Address | Page | Shows |
|---|---|---|
| `/` | Overview | The latest run as a sentence, its measured figures, every run plotted as requested against delivered, the latest check of a prediction |
| `/experiments` | Experiments | Every run |
| `/experiments/:id` | Run | Telemetry over time, latency by operation, advisor findings, prediction beside measurement where one exists |
| `/run` | Run a workload | Starts a workload as a background job |
| `/predict` | Predict | Estimates for a workload, with range warnings |
| `/what-if` | What if | A sweep of workers or requested rate |
| `/validation` | Validation | Predict, run, compare; accuracy of the current models, with earlier checks on request |
| `/models` | Models | Each model's error beside the no-model baseline and run-to-run variation; trained ranges |

## Data flow

Every value on screen comes from the API through the typed client in `web/src/api/`. Nothing is hard-coded or simulated. A missing value is shown as a dash, a failed request shows the server's own message, and an empty list says what to do next. Long work (a run or a validation) is submitted to `POST /api/jobs` and polled until it finishes.

## The one visual rule

A measured value is drawn filled in the signal colour. A predicted value is drawn hollow and dashed. Nothing else uses the signal colour as a fill.
