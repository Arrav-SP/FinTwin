from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def check_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_schema(schema_path: Path | None = None) -> None:
    path = schema_path or Path(__file__).resolve().parents[2] / "database" / "schema.sql"
    statements = [statement.strip() for statement in path.read_text(encoding="utf-8").split(";") if statement.strip()]
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)

