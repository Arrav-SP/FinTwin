# Slide updates needed (10 October 2026)

The two decks were not edited. This file lists what in them no longer matches the code, and gives text for the slides that are missing. Numbers come from `docs/RESULTS.md`.

## FinTwin_Teacher_Presentation_Enhanced.pptx

| Slide | Says | Should say |
|---|---|---|
| 4 Architecture | React Dashboard, FastAPI, workload engine, PostgreSQL, telemetry, ML | Correct now. Optionally add "background jobs" beside FastAPI |
| 5 Database design | Ten entities, including CARD, CARD_TRANSACTION, LOAN_PAYMENT and EMPLOYEE | Six banking tables: BRANCH, CUSTOMER, ACCOUNT, MERCHANT, TRANSACTION, LOAN. Card payments are TRANSACTION rows of type PAYMENT that reference a MERCHANT. Add: five experiment tables store runs, events, telemetry, summaries and validations |
| 9 Telemetry | CPU "system / process utilisation" | Host CPU only (whole machine). There is no per-process measurement |
| 10 Machine learning | Inputs include "optional pre-execution DB state"; "holdout evaluation" | Inputs: scenario, workers, requested rate, duration, burstiness, hot-account skew, operation mix. Evaluation: 5-fold cross-validation holding out whole load settings, compared with a no-model baseline and with run-to-run variation |
| 11, 12 What-if | Placeholder dashes for latency | Use a real example: high-concurrency transfer, 32 workers, skew 1.2, 300 to 600 TPS. Predicted average latency 8.8 to 107.2 ms, throughput 298.8 to 403.6 TPS |
| 13 Optimization | Six categories including QUERY and INDEX | The six rules are CPU, MEMORY, CONCURRENCY, LOCKING, LATENCY and QUERY (cache hit ratio). There is no index recommendation |
| 14 Validation | No numbers | Add the results table below |
| 17 Demonstration | Steps A to F | Correct. All six steps can now be done from the interface at `http://127.0.0.1:8000/` |

### New slide: results

Title: **What was measured**

- 280 runs, 383,385 operations, loads up to 600 TPS with 64 workers. No deadlocks.
- At 600 TPS the database saturates: 488 TPS delivered on average, latency ten times higher.
- Hot-account skew turns saturation into lock contention: P95 latency 118 ms without skew, 702 ms with it.

| Metric | Model error | No-model error |
|---|---|---|
| Average latency | 3.7 ms | 9.5 ms |
| P95 latency | 14.0 ms | 24.4 ms |
| Throughput | 5.1 TPS | 9.7 TPS |
| Host CPU | 3.8 points | 10.5 points |

Caption: 16 workloads predicted first, then run.

### New slide: limits and one mistake

Title: **Where the models stop working**

- Accurate below about 350 TPS. Above it, P95 latency and lock waits are predicted little better than with no model.
- One machine, runs of eight seconds, burstiness never varied.
- An earlier evaluation looked good and was wrong: models trained on five load levels predicted 60 TPS for a request of 100. A validation run exposed it. The fix was to hold out whole load levels when scoring, and to add runs at random loads.

## FinTwin_DBMS_ER_Relational_Normalization_Guide.pptx

This deck is built on a ten-entity design (it includes EMPLOYEE, CARD, CARD_TRANSACTION and LOAN_PAYMENT) on slides 3 to 8, 15 and 17. The implemented schema in `database/schema.sql` has six banking tables. Either:

- present the deck as the conceptual design and say which six entities were implemented, or
- redraw the ER diagram, relational schema, key map and functional dependencies for the six implemented tables. Section 4 of the report and its Figure 2 give the correct schema, keys and constraints.

Two points in the implemented schema that an examiner may raise are covered in Section 4.3 of the report: `loans` stores both `account_id` and `customer_id`, and `tenure_months` is not tied to the start and end dates.
