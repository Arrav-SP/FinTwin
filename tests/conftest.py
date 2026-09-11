import pytest

from backend.app.database import check_connection


@pytest.fixture(scope="session", autouse=True)
def require_postgres():
    try:
        check_connection()
    except Exception as exc:
        pytest.skip(f"PostgreSQL is required for integration tests: {exc}")

