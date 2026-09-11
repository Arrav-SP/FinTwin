from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text

from backend.app.database import engine, initialize_schema

SEED = 42
COUNTS = {"branches": 100, "customers": 1000, "accounts": 1500, "merchants": 100, "transactions": 5000, "loans": 200}


def seed_database() -> dict[str, int]:
    rng = random.Random(SEED)
    initialize_schema()
    with engine.begin() as connection:
        for table in COUNTS:
            connection.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))

        branch_rows = [{"name": f"FinTwin Branch {i:03d}", "code": f"FT{i:04d}", "address": f"{i} Synthetic Road", "city": f"City {i % 20:02d}", "state": f"State {i % 10:02d}", "ifsc": f"FTWB000{i:04d}", "phone": f"90000{i:05d}"} for i in range(1, COUNTS["branches"] + 1)]
        connection.execute(text("INSERT INTO branches (branch_name, branch_code, address, city, state, ifsc_code, phone) VALUES (:name, :code, :address, :city, :state, :ifsc, :phone)"), branch_rows)
        branch_ids = [row[0] for row in connection.execute(text("SELECT branch_id FROM branches ORDER BY branch_id"))]

        customer_rows = []
        for i in range(1, COUNTS["customers"] + 1):
            customer_rows.append({"name": f"Synthetic Customer {i:04d}", "dob": date(1960, 1, 1) + timedelta(days=rng.randrange(18000)), "gender": rng.choice(("FEMALE", "MALE", "NON_BINARY", "UNSPECIFIED")), "email": f"customer{i:04d}@example.test", "phone": f"91000{i:05d}", "address": f"{i} Sample Avenue", "city": f"City {i % 20:02d}", "state": f"State {i % 10:02d}", "kyc": "VERIFIED", "branch": rng.choice(branch_ids)})
        connection.execute(text("INSERT INTO customers (full_name, date_of_birth, gender, email, phone, address, city, state, kyc_status, branch_id) VALUES (:name, :dob, :gender, :email, :phone, :address, :city, :state, :kyc, :branch)"), customer_rows)
        customer_ids = [row[0] for row in connection.execute(text("SELECT customer_id FROM customers ORDER BY customer_id"))]

        account_rows = []
        for i in range(1, COUNTS["accounts"] + 1):
            account_rows.append({"customer": rng.choice(customer_ids), "branch": rng.choice(branch_ids), "number": f"FTIN{i:012d}", "type": rng.choice(("SAVINGS", "CURRENT")), "balance": Decimal(rng.randrange(500, 200000)), "open_date": date(2020, 1, 1) + timedelta(days=rng.randrange(2200))})
        connection.execute(text("INSERT INTO accounts (customer_id, branch_id, account_number, account_type, balance, open_date, status) VALUES (:customer, :branch, :number, :type, :balance, :open_date, 'ACTIVE')"), account_rows)
        account_rows_db = connection.execute(text("SELECT account_id, balance FROM accounts ORDER BY account_id")).mappings().all()
        account_ids = [row["account_id"] for row in account_rows_db]

        merchant_rows = [{"name": f"Synthetic Merchant {i:03d}", "category": rng.choice(("GROCERY", "TRAVEL", "DINING", "UTILITIES")), "mcc": f"{rng.randrange(1000, 10000):04d}", "city": f"City {i % 20:02d}", "state": f"State {i % 10:02d}", "online": rng.choice((True, False))} for i in range(1, COUNTS["merchants"] + 1)]
        connection.execute(text("INSERT INTO merchants (name, category, mcc_code, city, state, is_online, status) VALUES (:name, :category, :mcc, :city, :state, :online, 'ACTIVE')"), merchant_rows)
        merchant_ids = [row[0] for row in connection.execute(text("SELECT merchant_id FROM merchants ORDER BY merchant_id"))]

        transaction_rows = []
        for i in range(1, COUNTS["transactions"] + 1):
            tx_type = rng.choice(("TRANSFER", "DEPOSIT", "WITHDRAWAL", "PAYMENT"))
            source = rng.choice(account_ids)
            destination = rng.choice([a for a in account_ids if a != source]) if tx_type == "TRANSFER" else None
            transaction_rows.append({"source": source if tx_type in ("TRANSFER", "WITHDRAWAL", "PAYMENT") else None, "destination": destination if tx_type == "TRANSFER" else (source if tx_type == "DEPOSIT" else None), "merchant": rng.choice(merchant_ids) if tx_type == "PAYMENT" else None, "amount": Decimal(rng.randrange(10, 5000)), "type": tx_type, "ref": f"SEED-{i:06d}", "channel": rng.choice(("BRANCH", "ATM", "ONLINE", "MOBILE", "POS"))})
        connection.execute(text("INSERT INTO transactions (from_account_id, to_account_id, merchant_id, amount, transaction_type, description, reference_id, channel, status) VALUES (:source, :destination, :merchant, :amount, :type, 'Deterministic synthetic seed transaction', :ref, :channel, 'SUCCESS')"), transaction_rows)

        loan_rows = [{"customer": (account_rows[i % len(account_rows)]["customer"]), "account": account_ids[i % len(account_ids)], "branch": rng.choice(branch_ids), "type": rng.choice(("PERSONAL", "HOME", "EDUCATION", "VEHICLE")), "principal": Decimal(rng.randrange(10000, 1000000)), "rate": Decimal("7.5000"), "tenure": rng.choice((12, 24, 36, 60)), "start": date(2024, 1, 1), "end": date(2029, 1, 1)} for i in range(COUNTS["loans"])]
        connection.execute(text("INSERT INTO loans (customer_id, account_id, branch_id, loan_type, principal_amount, interest_rate, tenure_months, start_date, end_date, status) VALUES (:customer, :account, :branch, :type, :principal, :rate, :tenure, :start, :end, 'ACTIVE')"), loan_rows)

    return COUNTS.copy()


if __name__ == "__main__":
    print(seed_database())

