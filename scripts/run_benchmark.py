from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from backend.app.telemetry import TelemetryCollector
from backend.app.workload import Scenario, WorkloadConfig, WorkloadRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible real-PostgreSQL FinTwin benchmark scenarios.")
    parser.add_argument("--scenarios", nargs="+", default=[Scenario.NORMAL_DAY.value, Scenario.SALARY_DAY.value])
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--target-tps", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--telemetry-interval", type=float, default=1.0)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = []
    for index, scenario in enumerate(args.scenarios):
        config = WorkloadConfig(Scenario(scenario), args.concurrency, args.target_tps, args.duration, seed=args.seed + index)
        result = WorkloadRunner(config).run(TelemetryCollector(args.telemetry_interval))
        record = asdict(result)
        record["experiment_id"] = str(record["experiment_id"])
        record["started_at"] = record["started_at"].isoformat()
        record["completed_at"] = record["completed_at"].isoformat()
        records.append(record)
    if args.format == "csv":
        if not args.output:
            raise SystemExit("--output is required for CSV format")
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
    else:
        payload = json.dumps(records, indent=2)
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        print(payload)


if __name__ == "__main__":
    main()
