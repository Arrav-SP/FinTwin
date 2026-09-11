from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

from .database import engine
from .telemetry import TelemetryCollector
from .workload import WorkloadConfig, WorkloadRunner, Scenario


VALIDATION_TARGETS = (
    "average_latency_ms",
    "p95_latency_ms",
    "actual_tps",
    "host_cpu_avg_percent",
    "lock_wait_count_max",
)


def prediction_key(target: str) -> str:
    return f"predicted_{target}"


def error_for(predicted: float | None, actual: float | None) -> dict[str, float | None]:
    """Return safe absolute and percentage errors for one measured target."""
    if predicted is None or actual is None:
        return {"absolute_error": None, "percentage_error": None}
    absolute = abs(float(predicted) - float(actual))
    percentage = None if float(actual) == 0 else absolute / abs(float(actual)) * 100
    return {"absolute_error": absolute, "percentage_error": percentage}


def calculate_errors(predicted: dict[str, Any], actual: dict[str, Any]) -> dict[str, dict[str, float | None]]:
    return {
        target: error_for(predicted.get(prediction_key(target), predicted.get(target)), actual.get(target))
        for target in VALIDATION_TARGETS
        if predicted.get(prediction_key(target), predicted.get(target)) is not None and actual.get(target) is not None
    }


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for target in VALIDATION_TARGETS:
        pairs = [(r.get("predicted_metrics", {}).get(prediction_key(target)), r.get("actual_metrics", {}).get(target)) for r in records]
        pairs = [(float(p), float(a)) for p, a in pairs if p is not None and a is not None]
        if not pairs:
            continue
        errors = [p - a for p, a in pairs]
        absolute = [abs(error) for error in errors]
        percentage = [abs(error) / abs(a) * 100 for error, (_, a) in zip(errors, pairs) if a != 0]
        actual_mean = sum(a for _, a in pairs) / len(pairs)
        ss_total = sum((a - actual_mean) ** 2 for _, a in pairs)
        ss_residual = sum(error ** 2 for error in errors)
        result[target] = {
            "count": len(pairs),
            "mae": sum(absolute) / len(absolute),
            "rmse": math.sqrt(sum(error ** 2 for error in errors) / len(errors)),
            "r2": 1 - ss_residual / ss_total if ss_total else None,
            "mape": sum(percentage) / len(percentage) if percentage else None,
        }
    return result


def summarize_validations(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [record for record in records if record.get("validation_status") == "COMPLETED"]
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    by_concurrency: dict[str, list[dict[str, Any]]] = {}
    by_tps: dict[str, list[dict[str, Any]]] = {}
    for record in completed:
        config = record.get("workload_configuration") or {}
        by_scenario.setdefault(record.get("scenario", "UNKNOWN"), []).append(record)
        concurrency = config.get("concurrency")
        tps = config.get("target_tps")
        if concurrency is not None:
            by_concurrency.setdefault(str(concurrency), []).append(record)
        if tps is not None:
            by_tps.setdefault(str(tps), []).append(record)
    return {
        "validation_count": len(completed),
        "pending_or_failed_count": len(records) - len(completed),
        "overall": _aggregate(completed),
        "by_scenario": {key: _aggregate(value) for key, value in by_scenario.items()},
        "by_concurrency": {key: _aggregate(value) for key, value in by_concurrency.items()},
        "by_tps": {key: _aggregate(value) for key, value in by_tps.items()},
        "error_distribution": [record.get("error_metrics", {}) for record in completed],
    }


def _configuration(config: WorkloadConfig) -> dict[str, Any]:
    return {"scenario": config.scenario.value, "concurrency": config.concurrency, "target_tps": config.target_tps, "duration_seconds": config.duration_seconds, "operation_mix": dict(config.operation_mix), "seed": config.seed, "burstiness": config.burstiness}


def _json(value: Any) -> str:
    return json.dumps(value, default=str)


def _insert(validation_id: UUID, prediction_id: UUID, config: WorkloadConfig) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO validation_experiments (validation_id, prediction_id, scenario, workload_configuration, prediction_timestamp, validation_status)
            VALUES (:validation_id, :prediction_id, :scenario, CAST(:configuration AS JSONB), :timestamp, 'PENDING')
        """), {"validation_id": validation_id, "prediction_id": prediction_id, "scenario": config.scenario.value, "configuration": _json(_configuration(config)), "timestamp": datetime.now(timezone.utc)})


def _update(validation_id: UUID, **values: Any) -> None:
    json_columns = {"predicted_metrics", "actual_metrics", "error_metrics", "model_version"}
    assignments = ", ".join(f"{key} = CAST(:{key} AS JSONB)" if key in json_columns else f"{key} = :{key}" for key in values)
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE validation_experiments SET {assignments} WHERE validation_id = :validation_id"), {**values, "validation_id": validation_id})


def _actual_metrics(experiment_id: UUID) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT e.actual_tps, e.average_latency_ms, e.p95_latency_ms,
                   s.host_cpu_avg_percent, s.lock_wait_count_max
            FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id)
            WHERE e.experiment_id = :id
        """), {"id": experiment_id}).mappings().one()
    return {key: (float(value) if value is not None else None) for key, value in row.items()}


def run_validation(config: WorkloadConfig, model_dir: Path = Path("artifacts/models"), telemetry_interval: float = 1.0) -> dict[str, Any]:
    """Predict, execute the same configuration, and compare only real measurements."""
    validation_id, prediction_id = uuid4(), uuid4()
    _insert(validation_id, prediction_id, config)
    try:
        _update(validation_id, validation_status="RUNNING")
        # Keep the base API importable when the optional native ML stack is not installed.
        from .ml.predict import predict_performance

        prediction = predict_performance({"scenario": config.scenario.value, "concurrency": config.concurrency, "target_tps": config.target_tps, "duration_seconds": config.duration_seconds, "operation_mix": dict(config.operation_mix), "burstiness": config.burstiness}, model_dir)
        _update(validation_id, predicted_metrics=_json(prediction["predictions"]), model_version=_json({"model_dir": str(model_dir), "warnings": prediction.get("warnings", [])}))
        result = WorkloadRunner(config).run(TelemetryCollector(telemetry_interval))
        actual = _actual_metrics(result.experiment_id)
        errors = calculate_errors(prediction["predictions"], actual)
        completed = datetime.now(timezone.utc)
        _update(validation_id, actual_experiment_id=result.experiment_id, execution_timestamp=result.started_at, actual_metrics=_json(actual), error_metrics=_json(errors), validation_status="COMPLETED", completed_at=completed, error_message=None)
        return get_validation(str(validation_id))
    except Exception as exc:
        _update(validation_id, validation_status="FAILED", error_message=str(exc)[:2000], completed_at=datetime.now(timezone.utc))
        return get_validation(str(validation_id))


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("workload_configuration", "model_version", "predicted_metrics", "actual_metrics", "error_metrics"):
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    return row


def get_validation(validation_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM validation_experiments WHERE validation_id = :id"), {"id": validation_id}).mappings().first()
    if row is None:
        raise ValueError(f"Validation not found: {validation_id}")
    return _decode(dict(row))


def list_validations(limit: int = 100) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT * FROM validation_experiments ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}).mappings().all()
    return [_decode(dict(row)) for row in rows]


def validation_summary() -> dict[str, Any]:
    return summarize_validations(list_validations(10000))
