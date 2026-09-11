import argparse
import json

from backend.app.ml.predict import predict_performance


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--concurrency", required=True, type=int)
    parser.add_argument("--target-tps", required=True, type=float)
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()
    print(json.dumps(predict_performance({"scenario": args.scenario, "concurrency": args.concurrency, "target_tps": args.target_tps, "duration_seconds": args.duration}), indent=2))
