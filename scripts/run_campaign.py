from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

from backend.app.workload import Scenario, WorkloadConfig

# (workers, requested TPS): from a lightly loaded database to well past what it can deliver.
LOAD_LEVELS = ((4, 20.0), (8, 60.0), (16, 150.0), (32, 300.0), (48, 600.0))
# Uniform account choice, and a Zipf-like skew that sends many operations to a few hot accounts.
ACCOUNT_SKEWS = (0.0, 1.2)


def campaign_plan(repetitions: int, duration: float, seed: int) -> list[WorkloadConfig]:
    """Every scenario at every load level and skew, once per repetition.

    Each repetition is shuffled, so slow drift in the machine or the database is spread
    across configurations instead of lining up with one scenario or one load level.
    """
    order = random.Random(seed)
    plan: list[WorkloadConfig] = []
    for repetition in range(repetitions):
        grid = [WorkloadConfig(scenario, workers, rate, duration, seed=seed + repetition, account_skew=skew) for scenario in Scenario for workers, rate in LOAD_LEVELS for skew in ACCOUNT_SKEWS]
        order.shuffle(grid)
        plan.extend(grid)
    return plan


def random_plan(runs: int, duration: float, seed: int) -> list[WorkloadConfig]:
    """Workloads with workers and requested rate drawn from continuous ranges.

    A grid gives a model only a handful of distinct loads to learn from. Drawing each run's load
    at random (log-uniformly, so light and heavy loads are equally represented) fills in the
    space between the grid's levels. Scenarios are cycled so each gets an equal share.
    """
    rng = random.Random(seed)
    scenarios = list(Scenario)
    plan = []
    for index in range(runs):
        workers = round(math.exp(rng.uniform(math.log(2), math.log(64))))
        rate = round(math.exp(rng.uniform(math.log(10), math.log(600))), 1)
        plan.append(WorkloadConfig(scenarios[index % len(scenarios)], workers, rate, duration, seed=seed + index, account_skew=rng.choice((0.0, 0.6, 1.2))))
    rng.shuffle(plan)
    return plan


def main() -> None:
    from backend.app.telemetry import TelemetryCollector
    from backend.app.workload import WorkloadRunner

    parser = argparse.ArgumentParser(description="Run the FinTwin experiment campaign: a shuffled grid of workloads with repetitions.")
    parser.add_argument("--design", choices=("grid", "random"), default="grid", help="grid: fixed load levels with repetitions; random: loads drawn from continuous ranges")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--runs", type=int, default=100, help="number of runs for the random design")
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--telemetry-interval", type=float, default=1.0)
    parser.add_argument("--settle", type=float, default=1.0, help="seconds to wait between runs so one run's tail does not load the next")
    parser.add_argument("--output", type=Path, default=Path("artifacts/campaign.json"))
    args = parser.parse_args()

    plan = campaign_plan(args.repetitions, args.duration, args.seed) if args.design == "grid" else random_plan(args.runs, args.duration, args.seed)
    started = time.monotonic()
    records = []
    for index, config in enumerate(plan, start=1):
        label = f"{config.scenario.value} workers={config.concurrency} tps={config.target_tps:g} skew={config.account_skew:g}"
        try:
            result = WorkloadRunner(config).run(TelemetryCollector(args.telemetry_interval))
            records.append({"experiment_id": str(result.experiment_id), "scenario": config.scenario.value, "concurrency": config.concurrency, "target_tps": config.target_tps, "account_skew": config.account_skew, "actual_tps": result.actual_tps, "average_latency_ms": result.average_latency_ms, "failed_operations": result.failed_operations})
            outcome = f"{result.actual_tps:.1f} TPS, {result.average_latency_ms:.1f} ms, {result.failed_operations} failed"
        except Exception as exc:  # one failed run must not end the campaign; it is recorded and skipped
            records.append({"scenario": config.scenario.value, "concurrency": config.concurrency, "target_tps": config.target_tps, "account_skew": config.account_skew, "error": str(exc)[:500]})
            outcome = f"FAILED: {exc}"
        print(f"[{index}/{len(plan)}] {time.monotonic() - started:6.0f}s  {label}: {outcome}", flush=True)
        time.sleep(args.settle)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"design": args.design, "repetitions": args.repetitions, "duration_seconds": args.duration, "seed": args.seed, "runs": records}, indent=2), encoding="utf-8")
    failed = sum(1 for record in records if "error" in record)
    print(f"Campaign finished: {len(records) - failed} runs recorded, {failed} failed, {time.monotonic() - started:.0f}s. Written to {args.output}.")


if __name__ == "__main__":
    main()
