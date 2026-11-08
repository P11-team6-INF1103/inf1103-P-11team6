# Lennart
from contextlib import contextmanager
from typing import ClassVar

import pytest
from psycopg_pool import PoolTimeout

from database import Database, DatabaseUnavailable, _PostgresConnection


def test_sqlite_database_creates_every_table_and_can_be_opened_twice(tmp_path):
    path = str(tmp_path / "app.db")
    Database(path)
    database = Database(path)  # opening an existing database again is safe
    with database.connect() as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    assert {"incidents", "incident_workflow", "documents", "photos"} <= {r["name"] for r in rows}
    assert not {"users", "sessions"} & {r["name"] for r in rows}  # there are no accounts
    assert not database.is_postgres and database.path == path


def test_a_failed_block_is_rolled_back_and_a_finished_one_is_committed(tmp_path):
    database = Database(str(tmp_path / "app.db"))
    with database.connect() as connection:
        connection.execute("INSERT INTO documents (name, data) VALUES (?, ?)", ("kept", "{}"))
    with pytest.raises(RuntimeError), database.connect() as connection:
        connection.execute("INSERT INTO documents (name, data) VALUES (?, ?)", ("lost", "{}"))
        raise RuntimeError("boom")
    with database.connect() as connection:
        names = [r["name"] for r in connection.execute("SELECT name FROM documents").fetchall()]
    assert names == ["kept"]


class RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return "cursor"


class FakePool:
    instances: ClassVar[list] = []
    check_connection = staticmethod(lambda connection: None)

    def __init__(self, target, **options):
        self.target, self.options, self.closed = target, options, False
        self.recorder = RecordingConnection()
        FakePool.instances.append(self)

    @contextmanager
    def connection(self):
        yield self.recorder

    def close(self):
        self.closed = True


def test_the_postgres_adapter_turns_question_marks_into_placeholders():
    inner = RecordingConnection()
    assert _PostgresConnection(inner).execute("SELECT * FROM documents WHERE name = ? AND data = ?", ("a", "b")) == "cursor"
    assert inner.calls == [("SELECT * FROM documents WHERE name = %s AND data = %s", ("a", "b"))]


def test_postgres_startup_builds_the_schema(monkeypatch):
    monkeypatch.setattr("psycopg_pool.ConnectionPool", FakePool)  # no server is contacted
    database = Database("postgresql://user:secret@host/db")
    pool = FakePool.instances[-1]
    statements = [sql for sql, _params in pool.recorder.calls]
    assert database.is_postgres and pool.target == "postgresql://user:secret@host/db"
    assert pool.options["kwargs"]["prepare_threshold"] is None  # Neon's pooler needs statements that are not prepared
    assert any("CREATE TABLE IF NOT EXISTS incidents" in s and "BIGSERIAL" in s for s in statements)
    assert not any("users" in s for s in statements)
    assert database.IntegrityError[0].__name__ == "UniqueViolation"
    assert pool.options["timeout"] == Database.CONNECT_WAIT_SECONDS  # a dead server must not hang start-up
    database.close()
    assert pool.closed


class DeadPool(FakePool):
    # A Postgres server that never answers: the pool gives up waiting for a connection.
    @contextmanager
    def connection(self):
        raise PoolTimeout("couldn't get a connection after 10.00 sec")
        yield  # pragma: no cover


def test_an_unreachable_postgres_server_gives_a_clean_error_and_closes_the_pool(monkeypatch):
    monkeypatch.setattr("psycopg_pool.ConnectionPool", DeadPool)
    with pytest.raises(DatabaseUnavailable) as error:
        Database("postgresql://user:secret@host/db")
    assert "PoolTimeout" in str(error.value) and "secret" not in str(error.value)  # the password is never shown
    assert DeadPool.instances[-1].closed


def test_an_unwritable_sqlite_location_gives_a_clean_error(tmp_path):
    blocker = tmp_path / "plain_file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(DatabaseUnavailable):
        Database(str(blocker / "inside" / "app.db"))
