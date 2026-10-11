from __future__ import annotations

"""A lasting copy of what happens on a public server whose own disk is wiped on every restart.

The container's PostgreSQL stays the database that workloads run against and that the API reads.
After each run the site's own rows (runs made by signed-in people, their summaries, telemetry,
validations, run allowances) and any models trained on the site are pushed to a second database,
the archive. When the server starts again, they are copied back. The recorded reference runs are
never archived: they ship with the image.

Every function here fails quietly (logged, returns a falsy value): an unreachable archive must
never stop a run. Whatever was not pushed is pushed by the next successful sync.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from .config import get_settings
from .database import engine as local_engine
from .database import initialize_schema

log = logging.getLogger("fintwin.archive")

# The free archive database holds 1 GB; an archived run takes roughly 10 kB with its details.
MAX_ARCHIVED_RUNS = 20_000
FINISHED = "status IN ('COMPLETED', 'FAILED')"
MODELS = Path("artifacts/models")


@lru_cache
def _archive_engine() -> Engine | None:
    url = get_settings().archive_url.strip()
    if not url:
        return None
    # Hosting dashboards hand out postgres:// or postgresql:// addresses; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
    target = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=0, connect_args={"connect_timeout": 15})
    initialize_schema(target_engine=target)
    return target


def engine() -> Engine | None:
    """The archive, or None when none is configured."""
    return _archive_engine()


_tables: dict[tuple[int, str], Table] = {}


def _table(target: Engine, name: str) -> Table:
    key = (id(target), name)
    if key not in _tables:
        _tables[key] = Table(name, MetaData(), autoload_with=target)
    return _tables[key]


def _copy(source: Engine, dest: Engine, name: str, where: str, params: dict | None = None, key: str | None = None, omit: tuple[str, ...] = ()) -> int:
    """Copy the rows of one table that match `where`.

    `omit` leaves out columns the destination assigns itself (numeric ids, which the two databases
    hand out independently). With `key`, rows the destination already has are skipped.
    """
    src, dst = _table(source, name), _table(dest, name)
    with source.connect() as connection:
        rows = connection.execute(select(src).where(text(where)), params or {}).mappings().all()
    if not rows:
        return 0
    columns = [column.name for column in dst.columns if column.name in src.columns and column.name not in omit]
    values = [{column: row[column] for column in columns} for row in rows]
    with dest.begin() as connection:
        for start in range(0, len(values), 500):
            statement = insert(dst).values(values[start:start + 500])
            connection.execute(statement.on_conflict_do_nothing(index_elements=[key]) if key else statement)
    return len(values)


def _ids(target: Engine, sql: str, params: dict | None = None) -> set[str]:
    with target.connect() as connection:
        return {str(row[0]) for row in connection.execute(text(sql), params or {})}


def _transfer(source: Engine, dest: Engine, runs_where: str, validations_where: str) -> int:
    """Copy runs the destination lacks, with their summaries and telemetry, then validations and allowance rows."""
    runs = sorted(_ids(source, f"SELECT experiment_id FROM experiment_runs WHERE {runs_where}") - _ids(dest, "SELECT experiment_id FROM experiment_runs"))
    if runs:
        match = {"ids": runs}
        _copy(source, dest, "experiment_runs", "experiment_id::text = ANY(:ids)", match, key="experiment_id")
        _copy(source, dest, "experiment_summaries", "experiment_id::text = ANY(:ids)", match, key="experiment_id")
        # Telemetry has no key of its own across databases; it is copied exactly once, with its run.
        _copy(source, dest, "telemetry_samples", "experiment_id::text = ANY(:ids)", match, omit=("telemetry_id",))
    validations = sorted(_ids(source, f"SELECT validation_id FROM validation_experiments WHERE {validations_where}") - _ids(dest, "SELECT validation_id FROM validation_experiments"))
    if validations:
        _copy(source, dest, "validation_experiments", "validation_id::text = ANY(:ids)", {"ids": validations}, key="validation_id")
    usage = sorted(_ids(source, "SELECT usage_key FROM usage_log") - _ids(dest, "SELECT usage_key FROM usage_log"))
    if usage:
        _copy(source, dest, "usage_log", "usage_key::text = ANY(:ids)", {"ids": usage}, key="usage_key", omit=("usage_id",))
    return len(runs)


def sync() -> bool:
    """Push every finished site run, validation and allowance row that the archive does not have yet."""
    try:
        target = engine()
        if target is None:
            return False
        _transfer(local_engine, target, f"started_by IS NOT NULL AND {FINISHED}", "started_by IS NOT NULL AND validation_status IN ('COMPLETED', 'FAILED')")
        return True
    except Exception:
        log.exception("Archive sync failed; it will be retried after the next run")
        return False


def restore() -> int:
    """Copy everything archived back into the local database. Returns the number of runs restored."""
    try:
        target = engine()
        if target is None:
            return 0
        runs = _transfer(target, local_engine, "TRUE", "TRUE")
        restore_models(MODELS)
        return runs
    except Exception:
        log.exception("Archive restore failed; the site starts with the reference data only")
        return 0


def save_models(directory: Path = MODELS) -> bool:
    """Store a model set trained on the site, so it survives the next restart."""
    try:
        target = engine()
        if target is None:
            return False
        with target.begin() as connection:
            for metadata_path in sorted(directory.glob("*.json")):
                artifact = metadata_path.with_suffix(".joblib")
                if not artifact.exists():
                    continue
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                connection.execute(text("""
                    INSERT INTO model_store (target, trained_at, metadata, artifact)
                    VALUES (:target, :trained_at, CAST(:metadata AS JSONB), :artifact)
                    ON CONFLICT (target) DO UPDATE SET trained_at = EXCLUDED.trained_at, metadata = EXCLUDED.metadata, artifact = EXCLUDED.artifact
                """), {"target": metadata_path.stem, "trained_at": metadata.get("trained_at"), "metadata": json.dumps(metadata), "artifact": artifact.read_bytes()})
        return True
    except Exception:
        log.exception("Saving the models to the archive failed")
        return False


def restore_models(directory: Path = MODELS) -> int:
    """Write the archived models into `directory`. Returns how many were written; none means none were trained here."""
    target = engine()
    if target is None:
        return 0
    with target.connect() as connection:
        rows = connection.execute(text("SELECT target, metadata, artifact FROM model_store")).mappings().all()
    if not rows:
        return 0
    directory.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (directory / f"{row['target']}.joblib").write_bytes(bytes(row["artifact"]))
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"])
        (directory / f"{row['target']}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return len(rows)


def forget(login: str) -> bool:
    try:
        target = engine()
        if target is None:
            return False
        with target.begin() as connection:
            connection.execute(text("DELETE FROM validation_experiments WHERE started_by = :login"), {"login": login})
            connection.execute(text("DELETE FROM experiment_runs WHERE started_by = :login"), {"login": login})
            connection.execute(text("DELETE FROM usage_log WHERE login = :login"), {"login": login})
        return True
    except Exception:
        log.exception("Deleting a person's runs from the archive failed")
        return False


def is_full() -> bool:
    try:
        target = engine()
        if target is None:
            return False
        with target.connect() as connection:
            return connection.execute(text("SELECT COUNT(*) FROM experiment_runs")).scalar_one() >= MAX_ARCHIVED_RUNS
    except Exception:
        log.exception("Could not read the archive's size")
        return False
