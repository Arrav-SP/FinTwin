from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text

from ..database import engine

RATIOS = ("BALANCE_CHECK", "RECENT_TRANSACTIONS", "TRANSFER", "DEPOSIT", "WITHDRAWAL", "PAYMENT", "LOAN_PROCESSING")
TARGETS = ("average_latency_ms", "p95_latency_ms", "actual_tps", "host_cpu_avg_percent", "lock_wait_count_max")


@dataclass(frozen=True)
class DatasetReport:
    total_experiments: int
    completed_experiments: int
    usable_experiments: int
    unique_configurations: int
    unique_scenarios: int
    telemetry_samples: int
    missing_targets: dict[str, int]


def load_experiments() -> pd.DataFrame:
    import pandas as pd
    query = text("""
        SELECT e.experiment_id, e.scenario, e.configuration, e.status,
               e.started_at, e.completed_at, e.requested_operations,
               e.completed_operations, e.successful_operations, e.failed_operations,
               e.actual_tps, e.average_latency_ms, e.p50_latency_ms, e.p95_latency_ms,
               e.p99_latency_ms, s.host_cpu_avg_percent, s.host_memory_avg_percent,
               s.lock_wait_count_max, s.active_connections_max,
               s.db_size_before_bytes, s.db_cache_hit_ratio
        FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id)
        ORDER BY e.started_at
    """)
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(query).mappings().all()]
        telemetry_count = connection.execute(text("SELECT COUNT(*) FROM telemetry_samples")).scalar_one()
    records = []
    for row in rows:
        configuration = row.pop("configuration") or {}
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        row["concurrency"] = configuration.get("concurrency")
        row["target_tps"] = configuration.get("target_tps")
        row["duration_seconds"] = configuration.get("duration_seconds")
        row["burstiness"] = configuration.get("burstiness", 0.0)
        mix = configuration.get("operation_mix", {})
        for operation in RATIOS:
            row[f"{operation.lower()}_ratio"] = mix.get(operation, 0.0)
        row["configuration_key"] = json.dumps({key: row[key] for key in ("scenario", "concurrency", "target_tps", "duration_seconds", "burstiness", *[f"{op.lower()}_ratio" for op in RATIOS])}, sort_keys=True)
        records.append(row)
    return pd.DataFrame(records), telemetry_count


def quality_report(frame: pd.DataFrame, telemetry_count: int) -> DatasetReport:
    completed = frame[frame["status"] == "COMPLETED"] if not frame.empty else frame
    usable = completed.dropna(subset=[target for target in TARGETS if target in completed]) if not completed.empty else completed
    missing = {target: int(completed[target].isna().sum()) for target in TARGETS if target in completed}
    return DatasetReport(len(frame), len(completed), len(usable), int(completed["configuration_key"].nunique()) if not completed.empty else 0, int(completed["scenario"].nunique()) if not completed.empty else 0, telemetry_count, missing)
