# FinTwin Phase 1 — Database Foundation Results

Phase 1 established the PostgreSQL banking database foundation using synthetic data.

## Implemented

- PostgreSQL 16 running in Docker
- Six tables: branches, customers, accounts, merchants, transactions, and loans
- Primary keys, foreign keys, unique constraints, and financial CHECK constraints
- Deterministic seed data
- SQLAlchemy and psycopg database connectivity
- FastAPI health and database-summary endpoints
- Atomic account transfer service with row locking
- Rollback handling for insufficient balances

## Seed data

| Entity | Rows |
|---|---:|
| Branches | 100 |
| Customers | 1,000 |
| Accounts | 1,500 |
| Merchants | 100 |
| Transactions | 5,000 |
| Loans | 200 |

## Verification

The Phase 1 tests verified schema availability, seeded counts, successful transfer commit behavior, insufficient-balance rollback, and API responses. The successful transfer debited the source account by ₹1,000, credited the destination account by ₹1,000, and inserted one transfer record. The failed transfer preserved both balances and inserted no successful transaction.

Phase 1 uses synthetic banking data and is not connected to real financial systems.

