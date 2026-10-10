import pytest

pytest.importorskip("sklearn")

from backend.app.ml import study
from backend.app.ml.dataset import rows_to_frame
from tests.test_m3_ml import run_row


def rising_rows():
    """Latency rises with the requested rate; throughput saturates at 280. Two repeats per configuration."""
    rows = []
    for scenario, base in (("NORMAL_DAY", 8.0), ("SALARY_DAY", 12.0)):
        for workers, rate in ((2, 10.0), (4, 20.0), (6, 40.0), (8, 60.0), (12, 100.0), (16, 150.0), (24, 220.0), (32, 300.0), (40, 450.0), (48, 600.0)):
            for repeat in (0, 1):
                rows.append(run_row(scenario, workers, rate, latency=base + rate / 10 + repeat * 0.4, tps=min(rate, 280.0)))
    return rows_to_frame(rows)


def test_learning_curve_reports_held_out_error_for_each_training_size():
    frame = rising_rows()
    curve = study.learning_curve(frame, "average_latency_ms", "linear_regression", sizes=(8, 16, 500), repeats=2, seed=1)
    assert [point["runs"] for point in curve] == [8, 16, 32]  # a size larger than a training fold is capped at the fold
    assert all(point["mae"] >= 0 and point["fits"] > 0 for point in curve)
    assert curve[-1]["mae"] <= curve[0]["mae"] + 1e-9
    assert study.learning_curve(frame, "average_latency_ms", "linear_regression", sizes=(8, 16, 500), repeats=2, seed=1) == curve


def test_learning_curve_reports_training_on_everything_as_one_point_when_folds_differ_in_size():
    frame = rising_rows().iloc[:-1]  # one run fewer, so the folds no longer leave equal numbers to train on
    curve = study.learning_curve(frame, "average_latency_ms", "linear_regression", sizes=(8, 500), repeats=1, seed=1)
    assert len(curve) == 2
    assert curve[-1]["fits"] == 5  # one fit per fold, all under the same point


def test_error_by_band_splits_held_out_error_by_requested_rate_and_counts_every_run_once():
    frame = rising_rows()
    bands = study.error_by_band(frame, "actual_tps", "random_forest", edges=(50, 350))
    assert [band["band"] for band in bands] == ["under 50 TPS", "50 to 350 TPS", "350 TPS and over"]
    assert sum(band["runs"] for band in bands) == len(frame)
    assert bands[0]["baseline_mae"] == 0  # below saturation the requested rate is exactly what was delivered
    assert bands[2]["baseline_mae"] > 100  # above it, the requested rate is far off


def test_transfer_scores_a_model_on_runs_from_a_different_design():
    frame = rising_rows()
    grid = frame[frame["target_tps"].isin([20.0, 60.0, 150.0, 300.0, 600.0])]
    between = frame[~frame.index.isin(grid.index) & (frame["target_tps"] < 280)]
    raw = study.transfer(grid, between, "actual_tps", "random_forest", rate_share=False)
    share = study.transfer(grid, between, "actual_tps", "random_forest", rate_share=True)
    assert raw["test_runs"] == len(between)
    assert share["mae"] < raw["mae"]  # a tree on raw throughput repeats the grid's rates; the share model does not
    assert raw["baseline_mae"] == 0


def test_noise_floor_reports_spread_and_relative_spread_between_identical_runs():
    floor = study.noise_floor(rising_rows(), "average_latency_ms")
    assert floor["repeated_configurations"] == 20
    assert floor["spread"] == pytest.approx(0.4 / 2 ** 0.5, rel=1e-6)
    assert 0 < floor["relative_spread_percent"] < 10
