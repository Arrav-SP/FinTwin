from math import ceil


def percentile(values, rank: float):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if not 0 <= rank <= 100:
        raise ValueError("rank must be between 0 and 100")
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(ceil(position), len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_latencies(values):
    values = [float(value) for value in values]
    if not values:
        return {key: None for key in ("average_latency_ms", "min_latency_ms", "max_latency_ms", "p50_latency_ms", "p95_latency_ms", "p99_latency_ms")}
    return {"average_latency_ms": sum(values) / len(values), "min_latency_ms": min(values), "max_latency_ms": max(values), "p50_latency_ms": percentile(values, 50), "p95_latency_ms": percentile(values, 95), "p99_latency_ms": percentile(values, 99)}


def counter_delta(start, end):
    return None if start is None or end is None else end - start

