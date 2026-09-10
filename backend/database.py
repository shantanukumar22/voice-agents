from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
ENV_FILE = Path(__file__).resolve().parent / ".env"
_pool: ConnectionPool | None = None

# Local development fallback. Existing process/deployment variables always win.
load_dotenv(ENV_FILE, override=False)


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is required for the shared PostgreSQL database")
    if not value.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL")
    return value


def open_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # Hosted Postgres (Supabase / poolers) drop idle sessions. Validate on
        # checkout and recycle before the server does, so a dead connection
        # is replaced instead of surfacing as a 500 on the next request.
        _pool = ConnectionPool(
            conninfo=database_url(),
            min_size=int(os.getenv("DATABASE_POOL_MIN_SIZE", "1")),
            max_size=int(os.getenv("DATABASE_POOL_MAX_SIZE", "10")),
            timeout=10,
            max_idle=float(os.getenv("DATABASE_POOL_MAX_IDLE", "180")),
            max_lifetime=float(os.getenv("DATABASE_POOL_MAX_LIFETIME", "1800")),
            check=ConnectionPool.check_connection,
            kwargs={
                "row_factory": dict_row,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
            open=False,
        )
        _pool.open(wait=True, timeout=10)
    return _pool


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not open")
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def migrate(pool: ConnectionPool | None = None) -> None:
    active_pool = pool or get_pool()
    with active_pool.connection() as connection:
        with connection.transaction():
            connection.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version TEXT PRIMARY KEY,
                       applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                   )"""
            )
        applied = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in applied:
                continue
            with connection.transaction():
                connection.execute(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (%s)",
                    (migration.name,),
                )


def main() -> None:
    pool = open_pool()
    try:
        migrate(pool)
        print("PostgreSQL migrations applied successfully.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
