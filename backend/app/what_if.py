from __future__ import annotations
import csv, json
from copy import deepcopy
from pathlib import Path
from .ml.predict import predict_performance
from .workload.config import DEFAULT_MIXES, Scenario

def normalize_workload(config: dict) -> dict:
    result = deepcopy(config)
    result["scenario"] = Scenario(result["scenario"]).value
    for field in ("concurrency", "target_tps", "duration_seconds"):
        if float(result.get(field, 0)) <= 0: raise ValueError(f"{field} must be greater than zero")
    result.setdefault("duration_seconds", 10.0); result.setdefault("burstiness", 0.0)
    result.setdefault("operation_mix", dict(DEFAULT_MIXES[Scenario(result["scenario"])]))
    if abs(sum(result["operation_mix"].values()) - 1.0) > 1e-6 or any(value < 0 for value in result["operation_mix"].values()): raise ValueError("operation_mix values must be non-negative and sum to 1")
    return result

def compare_workloads(baseline: dict, modified: dict) -> dict:
    baseline, modified = normalize_workload(baseline), normalize_workload(modified)
    base, changed = predict_performance(baseline), predict_performance(modified)
    deltas = {}
    for metric, base_value in base["predictions"].items():
        new_value = changed["predictions"].get(metric)
        if new_value is not None: deltas[metric] = {"baseline": base_value, "modified": new_value, "absolute_change": new_value - base_value, "percentage_change": None if base_value == 0 else (new_value - base_value) / abs(base_value) * 100}
    percentages = [abs(item["percentage_change"]) for item in deltas.values() if item["percentage_change"] is not None]
    assessment = "HIGH_IMPACT" if percentages and max(percentages) >= 20 else "MEDIUM_IMPACT" if percentages and max(percentages) >= 5 else "LOW_IMPACT"
    return {"baseline": baseline, "modified": modified, "baseline_prediction": base["predictions"], "modified_prediction": changed["predictions"], "deltas": deltas, "assessment": assessment, "warnings": sorted(set(base.get("warnings", []) + changed.get("warnings", [])))}

def sweep_workload(baseline: dict, parameter: str, values: list) -> list[dict]:
    if parameter not in ("concurrency", "target_tps") or not values or len(set(values)) != len(values): raise ValueError("parameter must be concurrency/target_tps with non-empty unique values")
    results = []
    for value in values:
        configuration = normalize_workload({**baseline, parameter: value}); prediction = predict_performance(configuration)
        results.append({"configuration": configuration, "predictions": prediction["predictions"], "warnings": prediction.get("warnings", [])})
    return results

def sensitivity_analysis(baseline: dict, parameter: str, values: list) -> dict:
    results = sweep_workload(baseline, parameter, values); change = results[-1]["configuration"][parameter] - results[0]["configuration"][parameter]
    if len(results) < 2 or change == 0: raise ValueError("at least two distinct values are required")
    sensitivity = {metric: (results[-1]["predictions"][metric] - results[0]["predictions"][metric]) / change for metric in results[0]["predictions"] if metric in results[-1]["predictions"]}
    return {"parameter": parameter, "values": values, "model_derived_sensitivity": sensitivity, "results": results, "warnings": sorted({warning for result in results for warning in result["warnings"]})}

def save_json(result: dict, path: Path) -> None: path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

def save_csv(results: list[dict], path: Path) -> None:
    rows = [{**item["configuration"], **item["predictions"], "warnings": " | ".join(item["warnings"])} for item in results]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row})); writer.writeheader(); writer.writerows(rows)

