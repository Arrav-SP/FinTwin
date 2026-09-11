from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

from ..database import engine


class TransferError(ValueError):
    pass


@dataclass(frozen=True)
class TransferResult:
    reference_id: str
    source_account_id: int
    destination_account_id: int
    amount: Decimal


def transfer_funds(source_account_id: int, destination_account_id: int, amount: Decimal) -> TransferResult:
    amount = Decimal(amount)
    if amount <= 0:
        raise TransferError("Transfer amount must be greater than zero")
    if source_account_id == destination_account_id:
        raise TransferError("Source and destination accounts must differ")

    # Lock in deterministic ID order to reduce deadlock risk for concurrent reverse transfers.
    first_id, second_id = sorted((source_account_id, destination_account_id))
    reference_id = f"TR-{uuid4().hex}"
    with engine.begin() as connection:
        rows = connection.execute(
            text("""
                SELECT account_id, balance, status, currency
                FROM accounts
                WHERE account_id IN (:first_id, :second_id)
                ORDER BY account_id
                FOR UPDATE
            """),
            {"first_id": first_id, "second_id": second_id},
        ).mappings().all()
        accounts = {row["account_id"]: row for row in rows}
        if len(accounts) != 2:
            raise TransferError("Both accounts must exist")
        source = accounts[source_account_id]
        destination = accounts[destination_account_id]
        if source["status"] != "ACTIVE" or destination["status"] != "ACTIVE":
            raise TransferError("Both accounts must be active")
        if source["currency"] != destination["currency"]:
            raise TransferError("Accounts must use the same currency")
        if source["balance"] < amount:
            raise TransferError("Insufficient balance")

        connection.execute(text("UPDATE accounts SET balance = balance - :amount WHERE account_id = :account_id"), {"amount": amount, "account_id": source_account_id})
        connection.execute(text("UPDATE accounts SET balance = balance + :amount WHERE account_id = :account_id"), {"amount": amount, "account_id": destination_account_id})
        connection.execute(text("""
            INSERT INTO transactions (
                from_account_id, to_account_id, amount, currency, transaction_type,
                description, reference_id, channel, status
            ) VALUES (:source_id, :destination_id, :amount, :currency, 'TRANSFER',
                      'Phase 1 account transfer', :reference_id, 'ONLINE', 'SUCCESS')
        """), {"source_id": source_account_id, "destination_id": destination_account_id, "amount": amount, "currency": source["currency"], "reference_id": reference_id})
    return TransferResult(reference_id, source_account_id, destination_account_id, amount)

