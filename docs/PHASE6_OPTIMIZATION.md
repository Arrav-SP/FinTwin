# Phase 6 — Intelligent Optimization Recommendations

Phase 6 is an advisory, rule-based optimization layer. It consumes measured Phase 3 summaries and optionally query statistics. It does not modify PostgreSQL, create indexes, rewrite SQL, change configuration, or claim causal improvements.

Rules use documented defaults: host CPU >= 80% indicates potential CPU pressure, memory >= 85% indicates potential memory pressure, cache hit ratio < 95% indicates poor cache behavior, P95/average latency >= 2 indicates tail-latency pressure, and any ungranted lock count indicates possible lock contention. Thresholds are configurable through `Thresholds`.

Run an assessment:

```powershell
python scripts/analyze_performance.py --experiment-id <UUID> --format json
python scripts/analyze_performance.py --experiment-id <UUID> --format csv --output artifacts/recommendations.csv
```

Recommendations contain category, severity, evidence, recommended action, expected benefit, coverage status, and a validation requirement. Query analysis is optional; if `pg_stat_statements` is unavailable the engine continues and emits a warning. Candidate index creation is intentionally not automated. Model-derived what-if results remain advisory and are not causal proof.
