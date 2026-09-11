from __future__ import annotations

import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text
from .database import engine


@dataclass(frozen=True)
class Thresholds:
    cpu_high: float = 80.0
    memory_high: float = 85.0
    cache_low: float = 95.0
    connection_utilization_high: float = 0.8
    tail_ratio_high: float = 2.0


def analyze_metrics(metrics: dict, thresholds: Thresholds = Thresholds()) -> dict:
    bottlenecks, recommendations = [], []

    def add(category, severity, title, description, evidence, action, benefit, status="HIGH_EVIDENCE"):
        rec = {"recommendation_id": f"REC-{len(recommendations)+1:03d}", "category": category, "severity": severity, "title": title, "description": description, "evidence": evidence, "recommended_action": action, "expected_benefit": benefit, "coverage_status": status, "requires_validation": True}
        recommendations.append(rec)
        bottlenecks.append({"category": category, "severity": severity, "title": title, "evidence": evidence})

    cpu = metrics.get("host_cpu_avg_percent")
    if cpu is not None and cpu >= thresholds.cpu_high:
        add("CPU", "HIGH", "Potential CPU pressure", f"Host CPU averaged {cpu:.2f}%.", {"host_cpu_avg_percent": cpu}, "Investigate expensive queries and workload concurrency before increasing intensity.", "Potential reduction in CPU pressure; validate with a controlled experiment.")
    memory = metrics.get("host_memory_avg_percent")
    if memory is not None and memory >= thresholds.memory_high:
        add("MEMORY", "HIGH", "Potential memory pressure", f"Host memory averaged {memory:.2f}%.", {"host_memory_avg_percent": memory}, "Inspect host/container memory availability and PostgreSQL memory configuration.", "Potential reduction in memory pressure; validation required.")
    active, maximum = metrics.get("active_connections_max"), metrics.get("max_connections")
    if active is not None and maximum and active / maximum >= thresholds.connection_utilization_high:
        add("CONCURRENCY", "HIGH", "Connection pressure", f"Active connections reached {active} of {maximum}.", {"active_connections_max": active, "max_connections": maximum}, "Review connection pooling, burstiness, and client concurrency.", "Potentially fewer connection waits; do not change pool settings automatically.")
    locks = metrics.get("lock_wait_count_max", 0) or 0
    if locks > 0:
        add("LOCKING", "HIGH", "Lock contention detected", f"Un granted lock count reached {locks}.", {"lock_wait_count_max": locks}, "Investigate transaction duration and concurrent account-update access patterns.", "Potentially lower lock waiting; controlled validation required.")
    avg, p95 = metrics.get("average_latency_ms"), metrics.get("p95_latency_ms")
    if avg and p95 and p95 / avg >= thresholds.tail_ratio_high:
        add("LATENCY", "MEDIUM", "Tail latency pressure", f"P95 latency is {p95:.2f} ms versus {avg:.2f} ms average.", {"average_latency_ms": avg, "p95_latency_ms": p95, "ratio": p95 / avg}, "Investigate contention, bursts, and expensive query classes.", "Potentially lower tail latency; validate with repeated experiments.")
    cache = metrics.get("db_cache_hit_ratio")
    if cache is not None and cache < thresholds.cache_low:
        add("QUERY", "MEDIUM", "Poor cache behavior", f"Cache hit ratio was {cache:.2f}%.", {"db_cache_hit_ratio": cache}, "Inspect query access patterns and buffer/cache behavior.", "Potentially fewer disk reads; validation required.")
    if not recommendations:
        return {"overall_status": "NORMAL", "bottlenecks": [], "recommendations": [], "validation_required": False, "summary": "No significant bottlenecks detected under this workload."}
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    recommendations.sort(key=lambda item: severity_order[item["severity"]], reverse=True)
    return {"overall_status": "ELEVATED", "bottlenecks": bottlenecks, "recommendations": recommendations, "validation_required": True, "summary": f"{len(recommendations)} evidence-based recommendation(s) require human review."}


def analyze_experiment(experiment_id: str, thresholds: Thresholds = Thresholds()) -> dict:
    with engine.connect() as connection:
        row = connection.execute(text("SELECT e.experiment_id, e.scenario, e.configuration, e.actual_tps, e.average_latency_ms, e.p95_latency_ms, s.* FROM experiment_runs e LEFT JOIN experiment_summaries s USING (experiment_id) WHERE e.experiment_id = :id"), {"id": experiment_id}).mappings().first()
        if row is None: raise ValueError(f"Experiment not found: {experiment_id}")
        query_stats = []
        try:
            query_stats = [dict(item) for item in connection.execute(text("SELECT queryid, calls, total_exec_time, mean_exec_time, rows, shared_blks_read, shared_blks_hit FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20")).mappings().all()]
        except Exception:
            query_stats = []
    metrics = dict(row)
    result = analyze_metrics(metrics, thresholds)
    result.update({"experiment_id": experiment_id, "scenario": row["scenario"], "metrics": {key: value for key, value in metrics.items() if key not in ("configuration", "experiment_id")}, "query_statistics_available": bool(query_stats), "query_statistics": query_stats, "generated_at": datetime.now(timezone.utc).isoformat()})
    if not query_stats: result["warnings"] = ["Query-level analysis unavailable because pg_stat_statements is not enabled or accessible."]
    return result


def save_csv(result: dict, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["recommendation_id", "category", "severity", "title", "description", "evidence", "recommended_action", "expected_benefit", "coverage_status", "requires_validation"], extrasaction="ignore")
        writer.writeheader(); writer.writerows(result["recommendations"])
