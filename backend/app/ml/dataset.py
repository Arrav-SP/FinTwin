from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text

from ..database import engine

RATIOS = ("BALANCE_CHECK", "RECENT_TRANSACTIONS", "TRANSFER", "DEPOSIT", "WITHDRAWAL", "PAYMENT", "LOAN_PROCESSING")
TARGETS = ("average_latency_ms", "p95_latency_ms", "actual_tps", "host_cpu_avg_percent", "lock_wait_count_max")
CONFIGURATION_FIELDS = ("scenario", "concurrency", "target_tps", "duration_seconds", "burstiness", "account_skew", *[f"{operation.lower()}_ratio" for operation in RATIOS])


@dataclass(frozen=True)
class DatasetReport:
    total_experiments: int
    completed_experiments: int
    usable_experiments: int
    unique_configurations: int
    unique_scenarios: int
    telemetry_samples: int
    missing_targets: dict[str, int]


# A saturated run overruns its requested duration by about half while its queue drains.
# Several times longer means the machine was suspended mid-run, and its numbers measure the pause.
INTERRUPTED_FACTOR = 3.0


def _interrupted(started_at, completed_at, duration_seconds) -> bool:
    if started_at is None or completed_at is None or not duration_seconds:
        return False
    return (completed_at - started_at).total_seconds() > INTERRUPTED_FACTOR * float(duration_seconds)


def rows_to_frame(rows) -> pd.DataFrame:
    """One row per experiment, with the stored configuration expanded into feature columns."""
    import pandas as pd

    records = []
    for source in rows:
        row = dict(source)
        configuration = row.pop("configuration", None) or {}
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        row["concurrency"] = configuration.get("concurrency")
        row["target_tps"] = configuration.get("target_tps")
        row["duration_seconds"] = configuration.get("duration_seconds")
        row["burstiness"] = configuration.get("burstiness", 0.0)
        row["account_skew"] = configuration.get("account_skew", 0.0)
        # The runner has stored account_skew since it stopped timing an account lookup inside every
        # operation. Runs without it measured latency differently and must not be mixed with the rest.
        row["current_timing"] = "account_skew" in configuration
        row["interrupted"] = _interrupted(row.get("started_at"), row.get("completed_at"), row["duration_seconds"])
        mix = configuration.get("operation_mix", {})
        for operation in RATIOS:
            row[f"{operation.lower()}_ratio"] = mix.get(operation, 0.0)
        # Runs that share workers and requested rate, whatever the scenario. Held out together in evaluation.
        row["load_key"] = f"{row['concurrency']}|{row['target_tps']}"
        row["configuration_key"] = json.dumps({key: row[key] for key in CONFIGURATION_FIELDS}, sort_keys=True)
        records.append(row)
    frame = pd.DataFrame(records)
    for column in TARGETS:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_experiments() -> pd.DataFrame:
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
        rows = connection.execute(query).mappings().all()
        telemetry_count = connection.execute(text("SELECT COUNT(*) FROM telemetry_samples")).scalar_one()
    return rows_to_frame(rows), telemetry_count


def quality_report(frame: pd.DataFrame, telemetry_count: int) -> DatasetReport:
    completed = frame[frame["status"] == "COMPLETED"] if not frame.empty else frame
    usable = completed.dropna(subset=[target for target in TARGETS if target in completed]) if not completed.empty else completed
    missing = {target: int(completed[target].isna().sum()) for target in TARGETS if target in completed}
    return DatasetReport(len(frame), len(completed), len(usable), int(completed["configuration_key"].nunique()) if not completed.empty else 0, int(completed["scenario"].nunique()) if not completed.empty else 0, telemetry_count, missing)
