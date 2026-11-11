# Lennart
import pytest

from database import Database
from db.database_unavailable import DatabaseUnavailable
from db.postgres_connection import PostgresConnection
from tests.doubles.dead_pool import DeadPool
from tests.doubles.fake_pool import FakePool
from tests.doubles.recording_connection import RecordingConnection


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


def test_the_postgres_adapter_turns_question_marks_into_placeholders():
    inner = RecordingConnection()
    assert PostgresConnection(inner).execute("SELECT * FROM documents WHERE name = ? AND data = ?", ("a", "b")) == "cursor"
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
