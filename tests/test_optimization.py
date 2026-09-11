from backend.app.optimization import analyze_metrics


def test_high_cpu_and_tail_latency_recommendations():
    result = analyze_metrics({"host_cpu_avg_percent": 90, "average_latency_ms": 20, "p95_latency_ms": 80, "lock_wait_count_max": 0})
    categories = {item["category"] for item in result["recommendations"]}
    assert {"CPU", "LATENCY"} <= categories
    assert result["validation_required"] is True


def test_healthy_metrics_return_no_recommendation():
    result = analyze_metrics({"host_cpu_avg_percent": 20, "host_memory_avg_percent": 40, "db_cache_hit_ratio": 99, "average_latency_ms": 10, "p95_latency_ms": 14, "lock_wait_count_max": 0})
    assert result["recommendations"] == []
    assert result["overall_status"] == "NORMAL"


def test_lock_recommendation_contains_evidence():
    result = analyze_metrics({"lock_wait_count_max": 4})
    recommendation = result["recommendations"][0]
    assert recommendation["category"] == "LOCKING"
    assert recommendation["evidence"]["lock_wait_count_max"] == 4
