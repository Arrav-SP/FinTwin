from __future__ import annotations
import argparse, json
from pathlib import Path
from backend.app.what_if import compare_workloads, save_csv, save_json, sensitivity_analysis

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Phase 4 predictions without executing workloads.")
    parser.add_argument("--scenario", default="NORMAL_DAY"); parser.add_argument("--concurrency", type=int, default=50); parser.add_argument("--target-tps", type=float, default=100); parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--change-concurrency", type=int); parser.add_argument("--change-tps", type=float); parser.add_argument("--sweep-concurrency", nargs="+", type=int); parser.add_argument("--sweep-tps", nargs="+", type=float); parser.add_argument("--output-json", type=Path); parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args(); baseline = {"scenario": args.scenario, "concurrency": args.concurrency, "target_tps": args.target_tps, "duration_seconds": args.duration}
    if args.change_concurrency or args.change_tps:
        modified = {**baseline};
        if args.change_concurrency: modified["concurrency"] = args.change_concurrency
        if args.change_tps: modified["target_tps"] = args.change_tps
        result = compare_workloads(baseline, modified)
    elif args.sweep_concurrency or args.sweep_tps:
        parameter, values = ("concurrency", args.sweep_concurrency) if args.sweep_concurrency else ("target_tps", args.sweep_tps); result = sensitivity_analysis(baseline, parameter, values)
        if args.output_csv: save_csv(result["results"], args.output_csv)
    else: result = compare_workloads(baseline, baseline)
    if args.output_json: save_json(result, args.output_json)
    print(json.dumps(result, indent=2, default=str))
