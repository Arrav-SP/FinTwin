from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from backend.app.workload import Scenario, WorkloadConfig, WorkloadRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible FinTwin banking workload against PostgreSQL.")
    parser.add_argument("--scenario", choices=[scenario.value for scenario in Scenario], default=Scenario.NORMAL_DAY.value)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--target-tps", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    config = WorkloadConfig(Scenario(args.scenario), args.concurrency, args.target_tps, args.duration, seed=args.seed)
    print(json.dumps(asdict(WorkloadRunner(config).run()), default=str, indent=2))


if __name__ == "__main__":
    main()

