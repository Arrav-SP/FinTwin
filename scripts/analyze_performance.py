from __future__ import annotations
import argparse, json
from pathlib import Path
from backend.app.optimization import analyze_experiment, save_csv

parser = argparse.ArgumentParser(description="Analyze measured FinTwin performance and generate advisory recommendations.")
parser.add_argument("--experiment-id", required=True); parser.add_argument("--format", choices=("json", "csv"), default="json"); parser.add_argument("--output", type=Path)
args = parser.parse_args(); result = analyze_experiment(args.experiment_id)
if args.format == "csv":
    if not args.output: raise SystemExit("--output is required for CSV format")
    save_csv(result, args.output)
else:
    payload = json.dumps(result, indent=2, default=str)
    if args.output: args.output.write_text(payload, encoding="utf-8")
    print(payload)

