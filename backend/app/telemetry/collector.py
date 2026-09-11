from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from sqlalchemy import text
from ..database import engine
from .metrics import counter_delta

logger = logging.getLogger(__name__)


class TelemetryCollector:
    def __init__(self, interval_seconds: float = 1.0):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = None
        self.experiment_id = None
        self.initial = {}
        self.final = {}
        self.errors = 0

    def start(self, experiment_id):
        self.experiment_id = experiment_id
        self.initial = self._capture_store("INITIAL")
        self.thread = threading.Thread(target=self._loop, name="fintwin-telemetry", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=max(5, self.interval_seconds * 3))
        self.final = self._capture_store("FINAL")

    def finalize(self, result):
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT * FROM telemetry_samples WHERE experiment_id = :id ORDER BY captured_at"), {"id": self.experiment_id}).mappings().all()
        host_cpu = [float(row["host_cpu_percent"]) for row in rows if row["host_cpu_percent"] is not None]
        host_memory = [float(row["host_memory_percent"]) for row in rows if row["host_memory_percent"] is not None]
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO experiment_summaries (experiment_id, error_rate, p50_latency_ms, p95_latency_ms, p99_latency_ms, active_connections_max, blocked_sessions_max, lock_wait_count_max, db_xact_commit_delta, db_xact_rollback_delta, db_deadlocks_delta, db_cache_hit_ratio, host_cpu_avg_percent, host_memory_avg_percent, db_size_before_bytes, db_size_after_bytes, telemetry_sample_count, telemetry_error_count, generated_at)
                VALUES (:id, :error_rate, :p50, :p95, :p99, :active, :blocked, :locks, :commits, :rollbacks, :deadlocks, :cache, :cpu, :memory, :before_size, :after_size, :samples, :errors, :generated)
                ON CONFLICT (experiment_id) DO UPDATE SET generated_at = EXCLUDED.generated_at
            """), {"id": self.experiment_id, "error_rate": result.failed_operations / result.completed_operations if result.completed_operations else 0, "p50": result.p50_latency_ms, "p95": result.p95_latency_ms, "p99": result.p99_latency_ms, "active": max((r["active_connections"] for r in rows if r["active_connections"] is not None), default=None), "blocked": max((r["blocked_sessions"] for r in rows if r["blocked_sessions"] is not None), default=None), "locks": max((r["lock_wait_count"] for r in rows if r["lock_wait_count"] is not None), default=None), "commits": counter_delta(self.initial.get("xact_commit"), self.final.get("xact_commit")), "rollbacks": counter_delta(self.initial.get("xact_rollback"), self.final.get("xact_rollback")), "deadlocks": counter_delta(self.initial.get("deadlocks"), self.final.get("deadlocks")), "cache": self.final.get("cache_hit_ratio"), "cpu": sum(host_cpu) / len(host_cpu) if host_cpu else None, "memory": sum(host_memory) / len(host_memory) if host_memory else None, "before_size": self.initial.get("database_size_bytes"), "after_size": self.final.get("database_size_bytes"), "samples": len(rows), "errors": self.errors, "generated": datetime.now(timezone.utc)})

    def _loop(self):
        while not self.stop_event.wait(self.interval_seconds):
            self._capture_store("SAMPLE")

    def _capture_store(self, kind):
        try:
            snapshot = self._capture()
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO telemetry_samples (experiment_id, sample_kind, captured_at, active_connections, idle_connections, waiting_connections, max_connections, xact_commit, xact_rollback, blks_read, blks_hit, tup_inserted, tup_updated, tup_deleted, deadlocks, lock_count, lock_wait_count, blocked_sessions, database_size_bytes, cache_hit_ratio, host_cpu_percent, host_memory_percent) VALUES (:experiment_id, :sample_kind, :captured_at, :active_connections, :idle_connections, :waiting_connections, :max_connections, :xact_commit, :xact_rollback, :blks_read, :blks_hit, :tup_inserted, :tup_updated, :tup_deleted, :deadlocks, :lock_count, :lock_wait_count, :blocked_sessions, :database_size_bytes, :cache_hit_ratio, :host_cpu_percent, :host_memory_percent)"), {"experiment_id": self.experiment_id, "sample_kind": kind, **snapshot})
            return snapshot
        except Exception as exc:
            self.errors += 1
            logger.warning("Telemetry sample failed: %s", str(exc)[:200])
            return {}

    def _capture(self):
        with engine.connect() as connection:
            activity = connection.execute(text("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE state = 'active') AS active, COUNT(*) FILTER (WHERE state = 'idle') AS idle, COUNT(*) FILTER (WHERE wait_event_type IS NOT NULL) AS waiting, COUNT(*) FILTER (WHERE wait_event_type = 'Lock') AS blocked FROM pg_stat_activity")).mappings().one()
            database = connection.execute(text("SELECT xact_commit, xact_rollback, blks_read, blks_hit, tup_inserted, tup_updated, tup_deleted, deadlocks FROM pg_stat_database WHERE datname = current_database()")).mappings().one()
            locks = connection.execute(text("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE NOT granted) AS waiting FROM pg_locks")).mappings().one()
            size = connection.execute(text("SELECT pg_database_size(current_database())")).scalar_one()
            maximum = connection.execute(text("SELECT current_setting('max_connections')::INTEGER")).scalar_one()
        blocks = int(database["blks_hit"] or 0) + int(database["blks_read"] or 0)
        cpu, memory = self._host_metrics()
        return {"captured_at": datetime.now(timezone.utc), "active_connections": activity["active"], "idle_connections": activity["idle"], "waiting_connections": activity["waiting"], "max_connections": maximum, "xact_commit": database["xact_commit"], "xact_rollback": database["xact_rollback"], "blks_read": database["blks_read"], "blks_hit": database["blks_hit"], "tup_inserted": database["tup_inserted"], "tup_updated": database["tup_updated"], "tup_deleted": database["tup_deleted"], "deadlocks": database["deadlocks"], "lock_count": locks["total"], "lock_wait_count": locks["waiting"], "blocked_sessions": activity["blocked"], "database_size_bytes": size, "cache_hit_ratio": (float(database["blks_hit"]) / blocks * 100) if blocks else None, "host_cpu_percent": cpu, "host_memory_percent": memory}

    @staticmethod
    def _host_metrics():
        try:
            import psutil
            return float(psutil.cpu_percent(None)), float(psutil.virtual_memory().percent)
        except ImportError:
            return None, None

