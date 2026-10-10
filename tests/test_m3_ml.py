import json

import pytest

pytest.importorskip("sklearn")

from backend.app.ml import train
from backend.app.ml.dataset import TARGETS, rows_to_frame
from backend.app.workload.config import DEFAULT_MIXES, Scenario
from scripts.run_campaign import campaign_plan


def run_row(scenario="NORMAL_DAY", concurrency=4, target_tps=20.0, skew=0.0, latency=10.0, tps=None, current=True, status="COMPLETED"):
    configuration = {"concurrency": concurrency, "target_tps": target_tps, "duration_seconds": 8, "burstiness": 0.0, "operation_mix": DEFAULT_MIXES[Scenario(scenario)], "seed": 42}
    if current:
        configuration["account_skew"] = skew
    return {
        "experiment_id": f"{scenario}-{concurrency}-{target_tps}-{skew}-{latency}", "scenario": scenario, "configuration": configuration, "status": status,
        "actual_tps": target_tps if tps is None else tps, "average_latency_ms": latency, "p95_latency_ms": latency * 2,
        "host_cpu_avg_percent": 20.0, "lock_wait_count_max": 0,
    }


def synthetic_rows():
    """Latency rises with requested rate and differs by scenario; two repeats per configuration."""
    rows = []
    for scenario, base in (("NORMAL_DAY", 8.0), ("SALARY_DAY", 12.0), ("HIGH_CONCURRENCY_TRANSFER", 16.0)):
        for workers, rate in ((4, 20.0), (8, 60.0), (16, 150.0), (32, 300.0)):
            for repeat in (0, 1):
                rows.append(run_row(scenario, workers, rate, latency=base + rate / 10 + repeat * 0.4))
    return rows


def test_frame_marks_runs_made_with_the_current_timing():
    frame = rows_to_frame([run_row(current=True), run_row(current=False, latency=11)])
    assert frame["current_timing"].tolist() == [True, False]
    assert frame["account_skew"].tolist() == [0.0, 0.0]


def test_training_rows_exclude_earlier_timing_and_unfinished_runs():
    frame = rows_to_frame([run_row(), run_row(current=False, latency=11), run_row(status="FAILED", latency=12)])
    usable = train.training_rows(frame)
    assert len(usable) == 1
    assert usable.iloc[0]["current_timing"]


def test_throughput_baseline_is_the_requested_rate():
    frame = rows_to_frame(synthetic_rows())
    predicted = train.baseline_predictions(frame.iloc[:4], frame.iloc[4:8], "actual_tps")
    assert predicted.tolist() == frame.iloc[4:8]["target_tps"].tolist()


def test_other_baselines_are_the_scenario_mean_seen_in_training():
    frame = rows_to_frame([run_row("NORMAL_DAY", latency=10), run_row("NORMAL_DAY", 8, 60.0, latency=20), run_row("SALARY_DAY", latency=40)])
    test = rows_to_frame([run_row("NORMAL_DAY", 16, 150.0, latency=99), run_row("MONTH_END", latency=99)])
    predicted = train.baseline_predictions(frame, test, "average_latency_ms")
    assert predicted[0] == pytest.approx(15.0)
    assert predicted[1] == pytest.approx((10 + 20 + 40) / 3)  # unseen scenario falls back to the overall mean


def test_repeat_spread_is_the_typical_variation_between_identical_runs():
    frame = rows_to_frame([run_row(latency=10), run_row(latency=12), run_row("SALARY_DAY", latency=30)])
    assert train.repeat_spread(frame, "average_latency_ms") == pytest.approx(2 ** 0.5)
    assert train.repeat_spread(frame.iloc[2:], "average_latency_ms") is None


def test_training_cross_validates_against_a_baseline_and_refits_on_every_run(monkeypatch, tmp_path):
    frame = rows_to_frame(synthetic_rows())
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    results = train.train_models(tmp_path)

    assert set(results) == set(TARGETS)
    latency = json.loads((tmp_path / "average_latency_ms.json").read_text(encoding="utf-8"))
    assert latency["training_samples"] == len(frame)
    assert latency["configurations"] == 12
    assert latency["cv_folds"] == 4
    assert set(latency["candidates"]) == {"linear_regression", "random_forest", "gradient_boosting"}
    assert latency["metrics"]["mae"] == latency["candidates"][latency["algorithm"]]["mae"]
    assert latency["metrics"]["mae"] <= min(item["mae"] for item in latency["candidates"].values())
    assert latency["baseline"]["mae"] > latency["metrics"]["mae"]  # a rate-dependent latency beats the scenario mean
    assert latency["repeat_spread"] == pytest.approx(0.4 / 2 ** 0.5, rel=1e-6)
    assert "account_skew" in latency["numeric_ranges"]
    assert (tmp_path / "average_latency_ms.joblib").exists()


def test_training_is_refused_without_enough_current_runs(monkeypatch, tmp_path):
    frame = rows_to_frame([run_row(current=False, latency=value) for value in range(10, 30)])
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    with pytest.raises(ValueError, match="Insufficient"):
        train.train_models(tmp_path)


def test_campaign_plan_covers_the_grid_once_per_repetition_in_shuffled_order():
    plan = campaign_plan(repetitions=2, duration=8, seed=7)
    configurations = {(c.scenario, c.concurrency, c.target_tps, c.account_skew) for c in plan}
    assert len(plan) == 2 * len(configurations)
    assert {c.scenario for c in plan} == set(Scenario)
    first_pass = plan[: len(configurations)]
    assert len({(c.scenario, c.concurrency, c.target_tps, c.account_skew) for c in first_pass}) == len(configurations)
    assert [c.scenario for c in first_pass] != sorted(c.scenario for c in first_pass)  # not run scenario by scenario
    assert campaign_plan(repetitions=2, duration=8, seed=7) == plan
    assert len({c.seed for c in plan}) == 2  # each repetition has its own seed


# ---------------------------------------------------------------- interpolation between load settings

from backend.app.ml.models import build_model  # noqa: E402
from scripts.run_campaign import random_plan  # noqa: E402


def test_frame_carries_a_key_for_the_load_setting():
    frame = rows_to_frame([run_row(concurrency=8, target_tps=60.0), run_row("SALARY_DAY", 8, 60.0), run_row(concurrency=16, target_tps=150.0)])
    assert frame["load_key"].nunique() == 2


def test_models_are_scored_on_load_settings_they_never_saw(monkeypatch, tmp_path):
    """Latency here is a straight line in the requested rate. Tree models can only repeat rates they
    were trained on, so when whole rates are held out the linear model has to win."""
    frame = rows_to_frame(synthetic_rows())
    monkeypatch.setattr(train, "load_experiments", lambda: (frame, 0))
    latency = train.train_models(tmp_path)["average_latency_ms"]
    assert latency["held_out"] == "load settings"
    assert latency["cv_folds"] == 4  # four load settings in the synthetic data
    assert latency["algorithm"] == "linear_regression"
    assert latency["candidates"]["random_forest"]["mae"] > latency["candidates"]["linear_regression"]["mae"]


def test_throughput_model_scales_with_a_requested_rate_it_has_not_seen():
    rows = [run_row(scenario, workers, rate, tps=min(rate, 280.0)) for scenario in ("NORMAL_DAY", "SALARY_DAY") for workers, rate in ((4, 20.0), (8, 60.0), (16, 150.0), (32, 300.0), (48, 600.0))]
    frame = rows_to_frame(rows)
    model = build_model("random_forest", "actual_tps")
    model.fit(frame, frame["actual_tps"])
    unseen = rows_to_frame([run_row("NORMAL_DAY", 12, 100.0)])
    assert model.predict(unseen)[0] == pytest.approx(100.0, rel=0.05)


def test_random_plan_spreads_load_instead_of_repeating_a_few_levels():
    plan = random_plan(runs=60, duration=8, seed=11)
    assert len(plan) == 60
    assert {c.scenario for c in plan} == set(Scenario)
    assert all(2 <= c.concurrency <= 64 and 10 <= c.target_tps <= 600 for c in plan)
    assert len({c.target_tps for c in plan}) > 50
    assert len({c.concurrency for c in plan}) > 15
    assert random_plan(runs=60, duration=8, seed=11) == plan


# ---------------------------------------------------------------- runs the machine interrupted

from datetime import datetime, timedelta  # noqa: E402


def timed_row(elapsed_seconds, **kwargs):
    started = datetime(2026, 10, 10, 12, 0, 0)
    return {**run_row(**kwargs), "started_at": started, "completed_at": started + timedelta(seconds=elapsed_seconds)}


def test_runs_that_took_far_longer_than_requested_are_not_training_data():
    """A run of 8 requested seconds that lasted half an hour was suspended with the machine, not slow."""
    frame = rows_to_frame([timed_row(8.1), timed_row(12.5, latency=11), timed_row(1886.5, latency=61281.0), run_row(latency=13)])
    assert frame["interrupted"].tolist() == [False, False, True, False]
    assert len(train.training_rows(frame)) == 3
