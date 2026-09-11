from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.validation import run_validation, validation_summary
from backend.app.workload import Scenario, WorkloadConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a safe, reproducible FinTwin validation suite.")
    parser.add_argument("--scenarios", nargs="+", default=[Scenario.NORMAL_DAY.value, Scenario.SALARY_DAY.value])
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--target-tps", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")
    for scenario in args.scenarios:
        for repetition in range(args.repetitions):
            run_validation(WorkloadConfig(Scenario(scenario), args.concurrency, args.target_tps, args.duration, seed=args.seed + repetition), telemetry_interval=1.0)
    result = validation_summary()
    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
