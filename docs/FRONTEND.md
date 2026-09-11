# FinTwin Product UI

## Running the interface

Start the FastAPI application and open `http://127.0.0.1:8000/`.

```powershell
$env:PYTHONPATH = (Get-Location).Path
uvicorn backend.app.main:app --reload
```

The interface is implemented with static HTML, CSS, and JavaScript under `frontend/` and is served by FastAPI. It deliberately has no new frontend build tooling or runtime dependencies.

## Pages and live API data

| Page | Data source |
|---|---|
| Dashboard | Health, system status, real experiment history, and persisted validation data |
| Experiments | `GET /api/experiments` and `GET /api/experiments/{id}` |
| Prediction | `POST /api/predictions` using the existing Phase 4 model artifacts |
| What-If Analysis | `POST /api/what-if` using the existing Phase 5 engine |
| Optimization | `GET /api/recommendations/{experiment_id}` using the existing Phase 6 engine |
| Validation | `GET /api/validation`, `GET /api/validation/summary`, and deliberate `POST /api/validation` execution |

Predicted values are labelled `PREDICTED`; PostgreSQL workload observations are labelled `ACTUAL`. Empty metrics remain unavailable rather than being replaced with zeroes or placeholder performance values. The validation form explicitly warns that it starts a real workload run and waits for the chosen duration.

## Design and accessibility

The UI uses a dark technical/fintech visual system, responsive sidebar navigation, readable status indicators, keyboard-focusable controls, semantic buttons/forms/tables, responsive layouts, loading skeletons, and error/empty states. Charts are generated from measured experiment data using an inline SVG implementation to avoid an unnecessary dependency.
