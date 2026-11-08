# Lennart
import os
import sqlite3
from contextlib import contextmanager

# Each incident's workflow (priority, resolved) and, when the database is
# shared (Postgres), the incidents themselves. A workflow row points at an incident by its timestamp.
# The two dialects differ only in how an auto-numbered id is written.
_COMMON = """
CREATE TABLE IF NOT EXISTS incident_workflow (
    incident_key    TEXT PRIMARY KEY,
    priority        INTEGER CHECK (priority BETWEEN 1 AND 4),
    resolved        INTEGER NOT NULL DEFAULT 0,
    resolved_at     TEXT,
    resolution_note TEXT,
    updated_at      TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    name TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    location  TEXT,
    data      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
    fingerprint TEXT PRIMARY KEY,
    mime_type   TEXT NOT NULL,
    content     BLOB NOT NULL
);
""" + _COMMON

_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id        BIGSERIAL PRIMARY KEY,
    timestamp TEXT,
    location  TEXT,
    data      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
    fingerprint TEXT PRIMARY KEY,
    mime_type   TEXT NOT NULL,
    content     BYTEA NOT NULL
);
""" + _COMMON


class DatabaseUnavailable(RuntimeError):
    # The database could not be opened (server down, wrong URL, bad password, unwritable file). The message
    # never contains the connection string, so it is safe to show to the user.
    pass


class Database:
    # How long to wait for a Postgres connection before giving up, so a dead server does not hang start-up.
    CONNECT_WAIT_SECONDS = 10

    # Either a SQLite file (give a path) or a Postgres server such as Neon (give a postgresql:// URL).
    # All SQL is written with ? placeholders and works in both. Raises DatabaseUnavailable if it cannot be opened.
    def __init__(self, target: str) -> None:
        self._target = target
        self.is_postgres = target.startswith(("postgresql://", "postgres://"))
        self._pool = None
        try:
            self._open()
        except Exception as error:
            self.close()
            raise DatabaseUnavailable(f"could not open the database ({type(error).__name__})") from error

    # Connects (Postgres) or creates the folder (SQLite), then creates the tables that are missing.
    def _open(self) -> None:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
            self.IntegrityError = (psycopg.errors.UniqueViolation,)
            # prepare_threshold=None: Neon's pooler may hand each statement to a different server connection.
            self._pool = ConnectionPool(self._target, min_size=1, max_size=5, open=True,
                                        timeout=self.CONNECT_WAIT_SECONDS, check=ConnectionPool.check_connection,
                                        kwargs={"row_factory": dict_row, "prepare_threshold": None, "connect_timeout": 15})
            statements = _POSTGRES_SCHEMA
        else:
            self.IntegrityError = (sqlite3.IntegrityError,)
            os.makedirs(os.path.dirname(os.path.abspath(self._target)), exist_ok=True)
            statements = _SQLITE_SCHEMA
        with self.connect() as connection:
            for statement in statements.split(";"):
                if statement.strip():
                    connection.execute(statement)

    @property
    def path(self) -> str:
        return self._target

    # Commits when the block finishes, rolls back if it raises. Yields an object with execute(sql, params).
    @contextmanager
    def connect(self):
        if self._pool is not None:
            with self._pool.connection() as connection:
                yield _PostgresConnection(connection)
            return
        connection = sqlite3.connect(self._target, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()


class _PostgresConnection:
    # Lets the Postgres driver take the same ? placeholders SQLite uses.
    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, sql: str, params: tuple = ()):
        return self._connection.execute(sql.replace("?", "%s"), params)
