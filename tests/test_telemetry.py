from backend.app.telemetry.metrics import counter_delta, percentile, summarize_latencies
import pytest


def test_latency_percentiles():
    result = summarize_latencies([1, 2, 3, 4, 100])
    assert result["average_latency_ms"] == 22
    assert result["p50_latency_ms"] == 3
    assert result["p95_latency_ms"] == pytest.approx(80.8)
    assert percentile([], 95) is None


def test_counter_delta():
    assert counter_delta(100, 125) == 25
    assert counter_delta(None, 10) is None
