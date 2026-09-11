from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.validation import run_validation
from backend.app.workload import Scenario, WorkloadConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a FinTwin prediction against a real PostgreSQL workload.")
    parser.add_argument("--scenario", choices=[item.value for item in Scenario], default=Scenario.NORMAL_DAY.value)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--target-tps", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--telemetry-interval", type=float, default=1.0)
    parser.add_argument("--model-dir", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_validation(WorkloadConfig(Scenario(args.scenario), args.concurrency, args.target_tps, args.duration, seed=args.seed), args.model_dir, args.telemetry_interval)
    payload = json.dumps(result, indent=2, default=str)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    if result["validation_status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
