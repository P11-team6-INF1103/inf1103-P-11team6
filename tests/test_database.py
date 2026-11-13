# Lennart
import sys

import pytest

import migrate_to_database
from data_manager import DataManager
from database import Database
from db.database_unavailable import DatabaseUnavailable
from db.postgres_connection import PostgresConnection
from models.incident import Incident
from tests.doubles.dead_pool import DeadPool
from tests.doubles.fake_pool import FakePool
from tests.doubles.recording_connection import RecordingConnection
from workflow import WorkflowStore


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


def test_migration_copies_local_data_once(tmp_path, monkeypatch, capsys):
    local = DataManager(str(tmp_path / "local"))
    for stamp, place in (("2026-10-01T09:00:00", "Site A"), ("2026-10-02T09:00:00", "Site B")):
        local.save_record(Incident("Plank fell", place, "site_supervisor", False, stamp))
    WorkflowStore(local.database).set_priority("2026-10-01T09:00:00", 2)

    target = str(tmp_path / "remote.db")
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(tmp_path / "local"))
    monkeypatch.setenv("DATABASE_URL", target)
    monkeypatch.setattr(migrate_to_database, "load_dotenv", lambda: None)  # never read the real .env
    monkeypatch.setattr(sys, "argv", ["migrate_to_database.py"])
    assert migrate_to_database.Migration.main() == 0
    assert migrate_to_database.Migration.main() == 0  # a second run adds nothing

    remote = DataManager(str(tmp_path / "unused"), Database(target))
    assert [i.location for i in remote.load_records()] == ["Site A", "Site B"]
    with remote.database.connect() as connection:
        priorities = [r["priority"] for r in connection.execute("SELECT priority FROM incident_workflow").fetchall()]
    assert priorities == [2]
    assert "already has some" in capsys.readouterr().out


def test_migration_stops_with_a_message_when_there_is_no_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(migrate_to_database, "load_dotenv", lambda: None)
    monkeypatch.setattr(sys, "argv", ["migrate_to_database.py"])
    assert migrate_to_database.Migration.main() == 1
    assert "DATABASE_URL is not set" in capsys.readouterr().out
