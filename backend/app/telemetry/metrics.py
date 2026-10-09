from math import ceil


def percentile(values, rank: float):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if not 0 <= rank <= 100:
        raise ValueError("rank must be between 0 and 100")
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(ceil(position), len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_latencies(values):
    values = [float(value) for value in values]
    if not values:
        return {key: None for key in ("average_latency_ms", "min_latency_ms", "max_latency_ms", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms")}
    return {"average_latency_ms": sum(values) / len(values), "min_latency_ms": min(values), "max_latency_ms": max(values), "p50_latency_ms": percentile(values, 50), "p95_latency_ms": percentile(values, 95), "p99_latency_ms": percentile(values, 99)}


def average_excluding_initial(rows, key):
    """Average a sampled column, skipping the INITIAL snapshot taken before the workload starts."""
    values = [float(row[key]) for row in rows if row.get("sample_kind") != "INITIAL" and row.get(key) is not None]
    return sum(values) / len(values) if values else None


# experiment_summaries columns that experiment_runs does not also define.
SUMMARY_COLUMNS = (
    "active_connections_max", "max_connections", "blocked_sessions_max", "lock_wait_count_max",
    "db_xact_commit_delta", "db_xact_rollback_delta", "db_deadlocks_delta", "db_cache_hit_ratio",
    "host_cpu_avg_percent", "host_memory_avg_percent", "db_size_before_bytes", "db_size_after_bytes",
    "telemetry_sample_count", "telemetry_error_count", "generated_at",
)


def summary_select(alias: str = "s") -> str:
    return ", ".join(f"{alias}.{column}" for column in SUMMARY_COLUMNS)


# Upper edges of the latency histogram, in milliseconds (1-2-5 steps); the last bucket is open-ended.
HISTOGRAM_EDGES_MS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)


def latency_breakdown(events) -> dict:
    """Per-operation latency statistics and an overall histogram for one run's events."""
    events = list(events)
    if not events:
        return {"count": 0, "operations": [], "histogram": []}
    grouped: dict[str, list] = {}
    for event in events:
        grouped.setdefault(event["operation"], []).append(event)
    operations = []
    for operation in sorted(grouped):
        rows = grouped[operation]
        latencies = [float(row["latency_ms"]) for row in rows]
        waits = [float(row["queue_wait_ms"]) for row in rows if row["queue_wait_ms"] is not None]
        operations.append({
            "operation": operation,
            "count": len(rows),
            "failed": sum(1 for row in rows if not row["success"]),
            "average_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": percentile(latencies, 50),
            "p95_latency_ms": percentile(latencies, 95),
            "max_latency_ms": max(latencies),
            "average_queue_wait_ms": sum(waits) / len(waits) if waits else None,
        })
    # Buckets are (lower, upper]; the first one also takes a latency of exactly zero.
    histogram, lower = [], 0.0
    all_latencies = [float(event["latency_ms"]) for event in events]
    for upper in (*HISTOGRAM_EDGES_MS, None):
        count = sum(1 for value in all_latencies if (value > lower or lower == 0) and (upper is None or value <= upper))
        histogram.append({"lower_ms": lower, "upper_ms": upper, "count": count})
        lower = upper
    return {"count": len(events), "operations": operations, "histogram": histogram}


def counter_delta(start, end):
    return None if start is None or end is None else end - start

