from __future__ import annotations

import json
import random
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import text

from ..database import engine
from ..services.transfer_service import TransferError, transfer_funds
from ..telemetry.metrics import summarize_latencies
from .config import WorkloadConfig


@dataclass(frozen=True)
class OperationResult:
    operation: str
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class WorkloadResult:
    experiment_id: UUID
    scenario: str
    requested_operations: int
    completed_operations: int
    successful_operations: int
    failed_operations: int
    actual_tps: float
    average_latency_ms: float
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None
    started_at: datetime
    completed_at: datetime


class WorkloadRunner:
    """Execute a bounded banking workload using SQLAlchemy's connection pool."""

    def __init__(self, config: WorkloadConfig):
        self.config = config
        self.random = random.Random(config.seed)

    def run(self, telemetry_collector=None) -> WorkloadResult:
        experiment_id = uuid4()
        started_at = datetime.now(timezone.utc)
        started_clock = perf_counter()
        self._create_experiment(experiment_id, started_at)
        if telemetry_collector is not None:
            telemetry_collector.start(experiment_id)
        requested = max(1, round(self.config.target_tps * self.config.duration_seconds))
        futures: list[Future[OperationResult]] = []
        with ThreadPoolExecutor(max_workers=self.config.concurrency, thread_name_prefix="fintwin-worker") as executor:
            for index in range(requested):
                target_offset = index / self.config.target_tps
                remaining = target_offset - (perf_counter() - started_clock)
                if remaining > 0:
                    time.sleep(remaining)
                operation = self.random.choices(tuple(self.config.operation_mix), weights=tuple(self.config.operation_mix.values()), k=1)[0]
                futures.append(executor.submit(self._execute_operation, experiment_id, operation, self.config.seed + index))
        results = [future.result() for future in as_completed(futures)]
        completed_at = datetime.now(timezone.utc)
        elapsed = max(perf_counter() - started_clock, 1e-9)
        successful = sum(result.success for result in results)
        latency = summarize_latencies(result.latency_ms for result in results)
        result = WorkloadResult(experiment_id, self.config.scenario.value, requested, len(results), successful, len(results) - successful, len(results) / elapsed, latency["average_latency_ms"] or 0.0, latency["p50_latency_ms"], latency["p95_latency_ms"], latency["p99_latency_ms"], started_at, completed_at)
        self._complete_experiment(result)
        if telemetry_collector is not None:
            telemetry_collector.stop()
            telemetry_collector.finalize(result)
        return result

    def _create_experiment(self, experiment_id: UUID, started_at: datetime) -> None:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO experiment_runs (experiment_id, scenario, configuration, started_at, status)
                VALUES (:experiment_id, :scenario, CAST(:configuration AS JSONB), :started_at, 'RUNNING')
            """), {"experiment_id": experiment_id, "scenario": self.config.scenario.value, "configuration": self._configuration_json(), "started_at": started_at})

    def _complete_experiment(self, result: WorkloadResult) -> None:
        with engine.begin() as connection:
            connection.execute(text("""
                UPDATE experiment_runs
                SET completed_at = :completed_at, status = 'COMPLETED', requested_operations = :requested,
                    completed_operations = :completed, successful_operations = :successful,
                    failed_operations = :failed, actual_tps = :actual_tps,
                    average_latency_ms = :average_latency, p50_latency_ms = :p50,
                    p95_latency_ms = :p95, p99_latency_ms = :p99, error_rate = :error_rate
                WHERE experiment_id = :experiment_id
            """), {"completed_at": result.completed_at, "requested": result.requested_operations, "completed": result.completed_operations, "successful": result.successful_operations, "failed": result.failed_operations, "actual_tps": result.actual_tps, "average_latency": result.average_latency_ms, "p50": result.p50_latency_ms, "p95": result.p95_latency_ms, "p99": result.p99_latency_ms, "error_rate": result.failed_operations / result.completed_operations if result.completed_operations else 0, "experiment_id": result.experiment_id})

    def _execute_operation(self, experiment_id: UUID, operation: str, seed: int) -> OperationResult:
        started = perf_counter()
        try:
            rng = random.Random(seed)
            if operation == "TRANSFER":
                source, destination = self._account_pair(rng)
                transfer_funds(source, destination, Decimal(rng.randrange(1, 25)))
            elif operation == "BALANCE_CHECK":
                self._read_balance(rng)
            elif operation == "RECENT_TRANSACTIONS":
                self._read_transactions(rng)
            elif operation == "DEPOSIT":
                self._change_balance(rng, Decimal(rng.randrange(1, 100)), deposit=True)
            elif operation == "WITHDRAWAL":
                self._change_balance(rng, Decimal(rng.randrange(1, 25)), deposit=False)
            elif operation == "PAYMENT":
                self._payment(rng)
            elif operation == "LOAN_PROCESSING":
                self._loan_aggregation()
            else:
                raise ValueError(f"Unsupported operation: {operation}")
            result = OperationResult(operation, (perf_counter() - started) * 1000, True)
        except Exception as exc:
            result = OperationResult(operation, (perf_counter() - started) * 1000, False, str(exc))
        self._record_event(experiment_id, result)
        return result

    def _account_pair(self, rng: random.Random) -> tuple[int, int]:
        with engine.connect() as connection:
            ids = connection.execute(text("SELECT account_id FROM accounts WHERE status = 'ACTIVE' ORDER BY account_id LIMIT 1000")).scalars().all()
        if len(ids) < 2:
            raise RuntimeError("At least two active accounts are required")
        source, destination = rng.sample(ids, 2)
        return source, destination

    def _read_balance(self, rng: random.Random) -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT balance FROM accounts WHERE account_id = :account_id"), {"account_id": self._account_pair(rng)[0]}).scalar_one_or_none()

    def _read_transactions(self, rng: random.Random) -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT transaction_id, amount FROM transactions WHERE from_account_id = :account_id OR to_account_id = :account_id ORDER BY transaction_time DESC LIMIT 20"), {"account_id": self._account_pair(rng)[0]}).all()

    def _change_balance(self, rng: random.Random, amount: Decimal, deposit: bool) -> None:
        account_id = self._account_pair(rng)[0]
        with engine.begin() as connection:
            row = connection.execute(text("SELECT balance FROM accounts WHERE account_id = :account_id FOR UPDATE"), {"account_id": account_id}).scalar_one()
            if not deposit and row < amount:
                raise TransferError("Insufficient balance")
            operator = "+" if deposit else "-"
            connection.execute(text(f"UPDATE accounts SET balance = balance {operator} :amount WHERE account_id = :account_id"), {"amount": amount, "account_id": account_id})
            insert = "INSERT INTO transactions (to_account_id, amount, transaction_type, description, reference_id, channel, status) VALUES (:account_id, :amount, 'DEPOSIT', 'Workload deposit', :reference_id, 'ONLINE', 'SUCCESS')" if deposit else "INSERT INTO transactions (from_account_id, amount, transaction_type, description, reference_id, channel, status) VALUES (:account_id, :amount, 'WITHDRAWAL', 'Workload withdrawal', :reference_id, 'ATM', 'SUCCESS')"
            connection.execute(text(insert), {"account_id": account_id, "amount": amount, "reference_id": f"WL-{uuid4().hex}"})

    def _payment(self, rng: random.Random) -> None:
        account_id = self._account_pair(rng)[0]
        with engine.begin() as connection:
            merchant_id = connection.execute(text("SELECT merchant_id FROM merchants WHERE status = 'ACTIVE' ORDER BY RANDOM() LIMIT 1")).scalar_one()
            amount = Decimal(rng.randrange(1, 50))
            balance = connection.execute(text("SELECT balance FROM accounts WHERE account_id = :account_id FOR UPDATE"), {"account_id": account_id}).scalar_one()
            if balance < amount:
                raise TransferError("Insufficient balance")
            connection.execute(text("UPDATE accounts SET balance = balance - :amount WHERE account_id = :account_id"), {"amount": amount, "account_id": account_id})
            connection.execute(text("INSERT INTO transactions (from_account_id, merchant_id, amount, transaction_type, description, reference_id, channel, status) VALUES (:account_id, :merchant_id, :amount, 'PAYMENT', 'Workload merchant payment', :reference_id, 'POS', 'SUCCESS')"), {"account_id": account_id, "merchant_id": merchant_id, "amount": amount, "reference_id": f"WL-{uuid4().hex}"})

    def _loan_aggregation(self) -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT branch_id, COUNT(*), SUM(principal_amount) FROM loans GROUP BY branch_id ORDER BY branch_id")).all()

    def _record_event(self, experiment_id: UUID, result: OperationResult) -> None:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO workload_events (experiment_id, operation, latency_ms, success, error_message, recorded_at) VALUES (:experiment_id, :operation, :latency_ms, :success, :error_message, :recorded_at)"), {"experiment_id": experiment_id, "operation": result.operation, "latency_ms": result.latency_ms, "success": result.success, "error_message": result.error, "recorded_at": datetime.now(timezone.utc)})

    def _configuration_json(self) -> str:
        return json.dumps({"concurrency": self.config.concurrency, "target_tps": self.config.target_tps, "duration_seconds": self.config.duration_seconds, "operation_mix": dict(self.config.operation_mix), "seed": self.config.seed, "burstiness": self.config.burstiness})
