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

    from backend.app import archive
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
    restored = archive.restore()  # site runs and site-trained models, when an archive is configured
    if restored:
        print(f"Restored {restored} runs from the archive.", flush=True)
    for name in install_bundled():  # only where no models exist, so site-trained models win
        print(f"Installed shipped file: {name}", flush=True)
    archive.sync()


if __name__ == "__main__":
    import uvicorn

    prepare()
    # Hosts such as Render say which port to listen on through PORT.
    uvicorn.run("backend.app.main:app", host=os.environ.get("FINTWIN_HOST", "0.0.0.0"), port=int(os.environ.get("PORT") or os.environ.get("FINTWIN_PORT", "8000")))
