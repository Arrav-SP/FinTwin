from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.database import engine
from backend.app.main import app
from backend.app.services.transfer_service import TransferError, transfer_funds

pytestmark = pytest.mark.usefixtures("require_postgres")


def test_required_tables_and_seed_counts():
    with engine.connect() as connection:
        tables = {row[0] for row in connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))}
        assert {"branches", "customers", "accounts", "merchants", "transactions", "loans"} <= tables
        assert connection.execute(text("SELECT COUNT(*) FROM branches")).scalar_one() == 100
        assert connection.execute(text("SELECT COUNT(*) FROM customers")).scalar_one() == 1000
        assert connection.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one() == 1500


def test_successful_transfer_is_atomic():
    with engine.begin() as connection:
        source, destination = connection.execute(text("SELECT account_id FROM accounts ORDER BY account_id LIMIT 2")).scalars().all()
        connection.execute(text("UPDATE accounts SET balance = CASE WHEN account_id = :source THEN 10000 WHEN account_id = :destination THEN 5000 END WHERE account_id IN (:source, :destination)"), {"source": source, "destination": destination})
    result = transfer_funds(source, destination, Decimal("1000.00"))
    with engine.connect() as connection:
        balances = connection.execute(text("SELECT account_id, balance FROM accounts WHERE account_id IN (:source, :destination)"), {"source": source, "destination": destination}).mappings().all()
        assert {row["account_id"]: row["balance"] for row in balances} == {source: Decimal("9000.00"), destination: Decimal("6000.00")}
        assert connection.execute(text("SELECT COUNT(*) FROM transactions WHERE reference_id = :reference"), {"reference": result.reference_id}).scalar_one() == 1


def test_insufficient_balance_rolls_back():
    with engine.begin() as connection:
        source, destination = connection.execute(text("SELECT account_id FROM accounts ORDER BY account_id LIMIT 2 OFFSET 2")).scalars().all()
        connection.execute(text("UPDATE accounts SET balance = CASE WHEN account_id = :source THEN 500 WHEN account_id = :destination THEN 5000 END WHERE account_id IN (:source, :destination)"), {"source": source, "destination": destination})
        before = connection.execute(text("SELECT account_id, balance FROM accounts WHERE account_id IN (:source, :destination) ORDER BY account_id"), {"source": source, "destination": destination}).all()
    try:
        transfer_funds(source, destination, Decimal("1000.00"))
    except TransferError as exc:
        assert str(exc) == "Insufficient balance"
    else:
        raise AssertionError("Expected insufficient-balance transfer to fail")
    with engine.connect() as connection:
        after = connection.execute(text("SELECT account_id, balance FROM accounts WHERE account_id IN (:source, :destination) ORDER BY account_id"), {"source": source, "destination": destination}).all()
        assert after == before


def test_api_endpoints():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok", "database": "connected"}
    summary = client.get("/api/database/summary")
    assert summary.status_code == 200
    assert summary.json()["branches"] == 100

