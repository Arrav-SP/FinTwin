# FinTwin Phase 1 Database Design

Phase 1 uses six normalized PostgreSQL entities: `branches`, `customers`, `accounts`, `merchants`, `transactions`, and `loans`. Each table has a single-attribute primary key and foreign keys enforce the documented relationships. `transactions.from_account_id` and `transactions.to_account_id` are two separate many-to-one relationships to `accounts`, representing sender and receiver roles.

The design targets 3NF: attributes are atomic, there are no repeating groups or partial dependencies, and non-key attributes describe only their table's key. The principal functional dependencies are `branch_id -> branch attributes`, `customer_id -> customer attributes`, `account_id -> account attributes`, `merchant_id -> merchant attributes`, `transaction_id -> transaction attributes`, and `loan_id -> loan attributes`.

Customer and Account are separate because one customer may own multiple accounts; combining them would duplicate customer information. Transaction is central because future workloads will query and simulate transfers, deposits, withdrawals, and payments. Synthetic data is used because real banking data is private and inappropriate for this project.

The selected six entities provide meaningful relational complexity while keeping Phase 1 focused on validating the database foundation. Cards, employees, card transactions, and loan payments are intentionally deferred.

Foreign-key indexes are included for common joins and access paths. PostgreSQL already indexes primary keys and unique constraints. Indexes improve reads but add storage and write-maintenance costs, so later phases can measure their trade-offs.

## Atomic transfers

`transfer_funds` opens one database transaction, locks both account rows with `SELECT ... FOR UPDATE` in ascending account-ID order, validates status/currency/balance, updates both balances, and inserts the successful transaction record before commit. Any validation or SQL error causes the context manager to roll back the entire unit. This demonstrates atomicity, consistency through constraints, isolation through row locks, and durability after commit.

