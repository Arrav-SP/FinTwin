import pytest

from backend.app.workload.config import Scenario, WorkloadConfig


def test_workload_has_at_least_five_realistic_scenarios():
    assert len(Scenario) >= 5
    assert {Scenario.NORMAL_DAY, Scenario.SALARY_DAY, Scenario.MONTH_END, Scenario.FESTIVAL_SPIKE, Scenario.HIGH_CONCURRENCY_TRANSFER} <= set(Scenario)


def test_workload_configuration_is_deterministic_and_validates_mix():
    config = WorkloadConfig(scenario=Scenario.SALARY_DAY, concurrency=8, target_tps=25, duration_seconds=2)
    assert config.operation_mix["DEPOSIT"] == 0.35
    assert config.seed == 42
    with pytest.raises(ValueError, match="sum to 1"):
        WorkloadConfig(operation_mix={"TRANSFER": 0.5})


@pytest.mark.parametrize("field", ["concurrency", "target_tps", "duration_seconds"])
def test_workload_rejects_non_positive_limits(field):
    values = {"concurrency": 1, "target_tps": 1.0, "duration_seconds": 1.0}
    values[field] = 0
    with pytest.raises(ValueError):
        WorkloadConfig(**values)

