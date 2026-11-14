# Lennart
import os
import sys

import pytest

import migrate_to_database
from data_manager import DataManager
from data_stores.db_json import DbJson
from database import Database
from db.database_unavailable import DatabaseUnavailable
from db.postgres_connection import PostgresConnection
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from site_plan.site_plan import SitePlan
from tests.doubles.dead_pool import DeadPool
from tests.doubles.fake_pool import FakePool
from tests.doubles.recording_connection import RecordingConnection
from tests.doubles.unreachable_database import UnreachableDatabase
from workflow import WorkflowStore

SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")


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


def test_documents_round_trip_and_bad_content_is_reported_not_raised(tmp_path):
    database = Database(str(tmp_path / "app.db"))
    document = DbJson(database, "site_plan", dict)
    assert document.read() == ({}, None)
    assert document.write({"a": 1}) and document.write({"a": 2})  # the second write replaces the first
    assert document.read() == ({"a": 2}, None)
    with database.connect() as connection:
        connection.execute("UPDATE documents SET data = ? WHERE name = ?", ("{ not json", "site_plan"))
    data, problem = document.read()
    assert data == {} and "corrupt" in problem
    document.write([1, 2])
    data, problem = document.read()
    assert data == {} and "wrong format" in problem
    assert document.delete() and document.read() == ({}, None)


def test_database_photos_are_stored_once_and_read_back(tmp_path):
    manager = DataManager(str(tmp_path / "local"), Database(str(tmp_path / "app.db")))
    photo = IncidentPhoto.from_file(SAMPLE_PHOTO)
    reference = manager.store_photo(photo)
    assert reference.startswith("db:") and manager.store_photo(photo) == reference
    with manager.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) AS n FROM photos").fetchone()["n"] == 1
    assert manager.read_photo(reference) == (photo.content, photo.mime_type)
    assert manager.read_photo("db:unknown") is None and manager.read_photo("/tmp/a.png") is None


def test_an_unreachable_database_never_crashes_the_data_manager(tmp_path):
    manager = DataManager(str(tmp_path / "local"), UnreachableDatabase())
    incident = Incident("Plank fell", "Site A", "site_supervisor", False, "2026-10-01T09:00:00")
    assert manager.load_records() == []
    assert not manager.save_record(incident) and not manager.replace_record(0, incident) and not manager.delete_record(0)
    assert manager.store_photo(IncidentPhoto.from_file(SAMPLE_PHOTO)) is None
    assert manager.read_photo("db:abc") is None and manager.load_site_plan() is None
    assert manager.load_ai_cache() == {} and not manager.save_ai_cache({"k": 1})
    _data, problem = DbJson(manager.database, "site_plan", dict).read()
    assert "could not read" in problem


def test_migration_copies_local_data_once(tmp_path, monkeypatch, capsys):
    local = DataManager(str(tmp_path / "local"))
    for stamp, place in (("2026-10-01T09:00:00", "Site A"), ("2026-10-02T09:00:00", "Site B")):
        local.save_record(Incident("Plank fell", place, "site_supervisor", False, stamp))
    local.save_site_plan(SitePlan.from_dict({"width_m": 90, "depth_m": 56, "elements": [{"type": "gate", "name": "Main gate", "x": 2, "y": 44, "w": 15, "d": 10}]}))
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
    assert remote.load_site_plan() is not None
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
