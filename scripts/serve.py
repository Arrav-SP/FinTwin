from __future__ import annotations

import os
import time


def wait_for_database(timeout: float = 300.0) -> None:
    """PostgreSQL may still be starting, or loading the shipped data on its first start."""
    from backend.app.database import check_connection

    deadline = time.monotonic() + timeout
    while True:
        try:
            check_connection()
            return
        except Exception as exc:
            if time.monotonic() > deadline:
                raise SystemExit(f"PostgreSQL did not become available within {timeout:.0f} s: {exc}") from exc
            time.sleep(2)


def prepare() -> None:
    """Make a fresh installation usable: schema, banking data if there is none, shipped models."""
    from sqlalchemy import text

    from backend.app.bundled import install_bundled
    from backend.app.database import engine, initialize_schema

    wait_for_database()
    initialize_schema()
    with engine.connect() as connection:
        branches = connection.execute(text("SELECT COUNT(*) FROM branches")).scalar_one()
    if branches == 0:
        from scripts.seed_database import seed_database

        print("Empty database: loading the synthetic banking data.", flush=True)
        seed_database()
    for name in install_bundled():
        print(f"Installed shipped file: {name}", flush=True)


if __name__ == "__main__":
    import uvicorn

    prepare()
    uvicorn.run("backend.app.main:app", host=os.environ.get("FINTWIN_HOST", "0.0.0.0"), port=int(os.environ.get("FINTWIN_PORT", "8000")))
