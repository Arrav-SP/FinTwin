from backend.app.validation import calculate_errors, summarize_validations


def test_error_calculation_uses_absolute_and_percentage_error():
    result = calculate_errors({"predicted_average_latency_ms": 12, "predicted_actual_tps": 90}, {"average_latency_ms": 10, "actual_tps": 100})
    assert result["average_latency_ms"] == {"absolute_error": 2.0, "percentage_error": 20.0}
    assert result["actual_tps"]["percentage_error"] == 10.0


def test_zero_actual_is_safe_and_missing_values_are_skipped():
    result = calculate_errors({"predicted_lock_wait_count_max": 2, "predicted_actual_tps": 10}, {"lock_wait_count_max": 0, "actual_tps": None})
    assert result["lock_wait_count_max"] == {"absolute_error": 2.0, "percentage_error": None}
    assert "actual_tps" not in result


def test_validation_summary_reports_metrics_by_scenario():
    records = [{"validation_status": "COMPLETED", "scenario": "NORMAL_DAY", "workload_configuration": {"concurrency": 10, "target_tps": 10}, "predicted_metrics": {"predicted_actual_tps": 90}, "actual_metrics": {"actual_tps": 100}, "error_metrics": {"actual_tps": {"percentage_error": 10}}}]
    result = summarize_validations(records)
    assert result["validation_count"] == 1
    assert result["overall"]["actual_tps"]["mae"] == 10
    assert "NORMAL_DAY" in result["by_scenario"]
