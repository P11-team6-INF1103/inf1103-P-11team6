import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

import data_manager as dm
from data_stores.db_json import DbJson
from data_stores.document_store import DocumentStore
from data_stores.json_file import JsonFile
from database import Database
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from tests._suite import suite_from, temp_data_dir


def _write(folder, name, text):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(text)


def _files(folder):
    return sorted(os.listdir(folder))


def test_missing_file_means_empty_and_no_problem():
    with temp_data_dir():
        assert dm.load_records() == [] and dm.check_records_file() is None


def test_corrupt_file_is_set_aside_not_overwritten():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", "{not json")
        assert "corrupt" in dm.check_records_file()
        assert dm.load_records() == []
        assert dm.save_record({"location": "A"}) is True
        names = _files(folder)
        backups = [n for n in names if ".corrupt-" in n]
        assert len(backups) == 1, names
        with open(os.path.join(folder, backups[0]), encoding="utf-8") as f:
            assert f.read() == "{not json"
        assert dm.load_records() == [{"location": "A"}]


def test_load_corrupt_without_prior_check_also_keeps_backup():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", "\x00\x01 garbage")
        assert dm.load_records() == []
        assert any(".corrupt-" in n for n in _files(folder))


def test_wrong_shape_file_is_set_aside():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", '{"a": 1}')
        assert dm.load_records() == []
        assert any(".corrupt-" in n for n in _files(folder))


def test_non_object_entries_are_dropped_and_queries_do_not_crash():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", json.dumps([1, "x", None, {"location": "A", "timestamp": "2026-09-27T10:00:00", "outcome": "log_only"}]))
        assert len(dm.load_records()) == 1
        assert len(dm.query_by_location("A", 30, as_of="2026-09-28T00:00:00")) == 1
        assert dm.query_by_location("A", 30, records=[1, None, "x"]) == []


def test_unreadable_file_is_not_overwritten_by_save():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", json.dumps([{"location": "old"}]))
        real_open = open

        def locked(path, mode="r", *args, **kwargs):
            if "r" in mode and str(path).endswith("incidents.json"):
                raise PermissionError("locked by another program")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", locked):
            assert dm.save_record({"location": "new"}) is False
        assert dm.load_records() == [{"location": "old"}]


def test_unsaveable_record_returns_false_and_keeps_file():
    circular = {}
    circular["self"] = circular
    with temp_data_dir() as folder:
        assert dm.save_record({"location": "old"}) is True
        for bad in ({1: "a", "b": 2}, {(1, 2): "x"}, circular):
            assert dm.save_record(bad) is False
        assert dm.load_records() == [{"location": "old"}]
        assert _files(folder) == ["incidents.json"]


def test_unwritable_location_returns_false_instead_of_crashing():
    with tempfile.NamedTemporaryFile() as blocker, \
            mock.patch.dict(os.environ, {"INCIDENT_DATA_DIR": os.path.join(blocker.name, "sub")}):
        assert dm.save_record({"a": 1}) is False
        assert dm.save_ai_cache({"k": "v"}) is False
        assert dm.load_records() == []


def test_roundtrip_filter_and_order():
    with temp_data_dir():
        for stamp, place in (("2026-09-01T10:00:00", "A"), ("2026-09-20T10:00:00", "A"),
                             ("2026-09-25T10:00:00", "B"), ("2026-09-26T10:00:00", "A")):
            assert dm.save_record({"location": place, "timestamp": stamp, "outcome": "log_only"})
        assert len(dm.load_records()) == 4
        hits = dm.query_by_location("A", 30, as_of="2026-09-27T00:00:00")
        assert [h["timestamp"] for h in hits] == ["2026-09-26T10:00:00", "2026-09-20T10:00:00", "2026-09-01T10:00:00"]
        assert len(dm.query_by_location("A", 10, as_of="2026-09-27T00:00:00")) == 2
        assert set(hits[0]) == {"location", "timestamp", "outcome"}


def test_ai_cache_roundtrip_and_corruption():
    with temp_data_dir() as folder:
        assert dm.load_ai_cache() == {}
        assert dm.save_ai_cache({"k": "v"}) is True and dm.load_ai_cache() == {"k": "v"}
        _write(folder, "ai_cache.json", "[1]")
        assert dm.load_ai_cache() == {}


def load_tests(loader, tests, pattern):
    return suite_from(globals())

def test_delete_record_removes_only_the_chosen_incident():
    with temp_data_dir():
        for name in ("A", "B", "C"):
            dm.save_record({"location": name})
        assert dm.delete_record(1) is True
        assert dm.load_records() == [{"location": "A"}, {"location": "C"}]


def test_delete_record_out_of_range_changes_nothing():
    with temp_data_dir():
        dm.save_record({"location": "A"})
        assert dm.delete_record(5) is False
        assert dm.delete_record(-1) is False
        assert dm.load_records() == [{"location": "A"}]


def test_delete_record_on_missing_file_returns_false():
    with temp_data_dir():
        assert dm.delete_record(0) is False


def test_delete_record_on_corrupt_file_returns_false():
    with temp_data_dir() as folder:
        _write(folder, "incidents.json", "{not json")
        assert dm.delete_record(0) is False


def test_document_store_is_an_interface_with_three_methods():
    with pytest.raises(TypeError):
        DocumentStore()

    class ReadOnly(DocumentStore):  # leaves out write and delete
        def read(self):
            return [], None

    with pytest.raises(TypeError):
        ReadOnly()

    class InMemory(DocumentStore):
        def __init__(self):
            self.value = []

        def read(self):
            return self.value, None

        def write(self, data):
            self.value = data
            return True

        def delete(self):
            self.value = []
            return True

    store = InMemory()
    assert store.write([{"a": 1}]) is True and store.read() == ([{"a": 1}], None)
    assert store.delete() is True and store.read() == ([], None)


def test_json_file_round_trip_and_missing_file():
    with temp_data_dir() as folder:
        tmp_path = Path(folder)
        store = JsonFile(str(tmp_path / "sub" / "items.json"), list)
        assert isinstance(store, DocumentStore) and store.path.endswith("items.json")
        assert store.read() == ([], None)  # missing: empty, no complaint
        assert store.write([{"b": 2, "a": 1}]) is True  # creates the folder
        assert store.read() == ([{"a": 1, "b": 2}], None)
        assert JsonFile(str(tmp_path / "cache.json"), dict).read() == ({}, None)


def test_json_file_sets_aside_corrupt_and_wrong_shape_files():
    with temp_data_dir() as folder:
        tmp_path = Path(folder)
        for text, message in (("{not json", "was corrupt"), ('{"a": 1}', "had the wrong format")):
            path = tmp_path / "items.json"
            path.write_text(text, encoding="utf-8")
            data, problem = JsonFile(str(path), list).read()
            assert data == [] and message in problem and "kept as items.json.corrupt-" in problem
            backups = [p for p in tmp_path.iterdir() if ".corrupt-" in p.name]
            assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == text  # original kept, not lost
            assert not path.exists()
            backups[0].unlink()


def test_json_file_unreadable_file_is_reported_and_left_alone():
    with temp_data_dir() as folder:
        tmp_path = Path(folder)
        path = tmp_path / "items.json"
        path.write_text("[1]", encoding="utf-8")
        with mock.patch("builtins.open", side_effect=PermissionError("locked")):
            data, problem = JsonFile(str(path), list).read()
        assert data == [] and problem.startswith("could not read items.json")
        assert path.read_text(encoding="utf-8") == "[1]"  # not set aside: it may be fine once unlocked


def test_json_file_write_failure_returns_false_and_leaves_no_temp_file():
    with temp_data_dir() as folder:
        tmp_path = Path(folder)
        circular = {}
        circular["self"] = circular
        store = JsonFile(str(tmp_path / "items.json"), dict)
        assert store.write({"ok": True}) is True
        assert store.write(circular) is False and store.write({(1, 2): "x"}) is False
        assert store.read() == ({"ok": True}, None)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["items.json"]
        blocker = tmp_path / "blocker"
        blocker.write_text("", encoding="utf-8")
        assert JsonFile(str(blocker / "sub" / "items.json"), list).write([]) is False  # folder cannot be made


def test_json_file_delete():
    with temp_data_dir() as folder:
        tmp_path = Path(folder)
        store = JsonFile(str(tmp_path / "items.json"), list)
        assert store.delete() is True  # nothing to delete is fine
        store.write([1])
        assert store.delete() is True and store.read() == ([], None)
        store.write([1])
        with mock.patch("os.remove", side_effect=PermissionError("locked")):
            assert store.delete() is False
        assert store.read() == ([1], None)


def test_db_json_round_trip_in_the_documents_table():
    with temp_data_dir() as folder:
        database = Database(os.path.join(folder, "app.db"))
        store = DbJson(database, "ai_cache", dict)
        assert isinstance(store, DocumentStore)
        assert store.read() == ({}, None)  # no row yet: empty, no complaint
        assert store.write({"k": "v"}) is True and store.read() == ({"k": "v"}, None)
        assert store.write({"k": "new"}) is True and store.read() == ({"k": "new"}, None)  # replaces, one row
        assert DbJson(database, "site_plan", dict).read() == ({}, None)  # each name is its own document
        assert store.delete() is True and store.read() == ({}, None)
        assert store.delete() is True  # nothing to delete is fine


def test_db_json_reports_corrupt_and_wrong_shape_rows():
    with temp_data_dir() as folder:
        database = Database(os.path.join(folder, "app.db"))
        with database.connect() as connection:
            connection.execute("INSERT INTO documents (name, data) VALUES (?, ?)", ("broken", "{not json"))
            connection.execute("INSERT INTO documents (name, data) VALUES (?, ?)", ("a_list", "[1, 2]"))
        data, problem = DbJson(database, "broken", dict).read()
        assert data == {} and problem == "broken was corrupt in the database"
        data, problem = DbJson(database, "a_list", dict).read()
        assert data == {} and problem == "a_list had the wrong format"


def test_db_json_never_raises_when_the_database_is_down():
    class DeadDatabase:
        def connect(self):
            raise ConnectionError("server unreachable")

    store = DbJson(DeadDatabase(), "ai_cache", dict)
    data, problem = store.read()
    assert data == {} and problem.startswith("could not read ai_cache")
    assert store.write({"k": "v"}) is False and store.delete() is False
    circular = {}
    circular["self"] = circular
    with temp_data_dir() as folder:
        assert DbJson(Database(os.path.join(folder, "app.db")), "x", dict).write(circular) is False


def test_json_file_and_db_json_are_interchangeable():
    # The same steps give the same results whichever DocumentStore is used (Liskov substitution).
    with temp_data_dir() as folder:
        stores = [JsonFile(os.path.join(folder, "cache.json"), dict),
                  DbJson(Database(os.path.join(folder, "app.db")), "cache", dict)]
        for store in stores:
            assert store.read() == ({}, None)
            assert store.write({"b": 2, "a": 1}) is True
            assert store.read() == ({"a": 1, "b": 2}, None)
            assert store.delete() is True and store.read() == ({}, None)


def test_data_manager_folder_and_storage_mode():
    with temp_data_dir() as folder:
        assert dm.DataManager.default_folder() == folder  # INCIDENT_DATA_DIR wins
        local = dm.DataManager()
        assert local.uses_database is False
        assert local.database_path == os.path.join(folder, "app.db")
        assert local.database.path == local.database_path  # SQLite opened on first use
        assert local.database is local.database  # and only once
        shared_db = Database(os.path.join(folder, "shared.db"))
        shared = dm.DataManager(os.path.join(folder, "other"), shared_database=shared_db)
        assert shared.uses_database is True and shared.database is shared_db
    with mock.patch.dict(os.environ, {"INCIDENT_DATA_DIR": ""}):
        assert dm.DataManager.default_folder() == os.path.join(os.path.dirname(dm.__file__), "data")


def test_data_manager_log_path():
    with temp_data_dir() as folder:
        target = os.path.join(folder, "new")
        assert dm.DataManager(target).get_log_path() == os.path.join(target, "app.log")
        assert os.path.isdir(target)  # the folder is created
        blocker = os.path.join(folder, "blocker")
        _write(folder, "blocker", "")
        assert dm.DataManager(os.path.join(blocker, "sub")).get_log_path() is None  # folder cannot be made
        assert dm.DataManager(folder, shared_database=Database(os.path.join(folder, "s.db"))).get_log_path() is None


def test_data_manager_checks_the_incidents_file():
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        assert manager.check_records_file() is None  # missing is fine
        _write(folder, "incidents.json", "{not json")
        assert "was corrupt" in manager.check_records_file()
        assert manager.check_records_file() is None  # it was set aside, so now it is missing
        shared = dm.DataManager(folder, shared_database=Database(os.path.join(folder, "s.db")))
        _write(folder, "incidents.json", "{not json")
        assert shared.check_records_file() is None  # no local file is used in database mode


def test_data_manager_reads_record_dicts_and_refuses_an_unreadable_file():
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        assert manager._read_record_dicts() == []
        _write(folder, "incidents.json", json.dumps([{"a": 1}, 2, "x", None, {"b": 2}]))
        assert manager._read_record_dicts() == [{"a": 1}, {"b": 2}]  # non-objects dropped
        with mock.patch("builtins.open", side_effect=PermissionError("locked")):
            assert manager._read_record_dicts() is None  # exists but unreadable: callers must not overwrite it


def _incident(description, location="Site A", timestamp="2026-10-20T10:00:00", **fields):
    incident = Incident(description, location, "supervisor", False, timestamp)
    incident.update(fields)
    return incident


def _managers(folder):
    # The same DataManager calls, once with local files and once with a shared database.
    return [dm.DataManager(os.path.join(folder, "local")),
            dm.DataManager(os.path.join(folder, "shared"), shared_database=Database(os.path.join(folder, "s.db")))]


def test_save_load_replace_and_delete_incidents_in_both_modes():
    with temp_data_dir() as folder:
        for manager in _managers(folder):
            assert manager.load_records() == []
            assert manager.save_record(_incident("first", outcome="log_only")) is True
            assert manager.save_record(_incident("second", location="Site B")) is True
            loaded = manager.load_records()
            assert all(isinstance(item, Incident) for item in loaded)
            assert [item.description for item in loaded] == ["first", "second"]  # save order kept
            assert loaded[0].get("outcome") == "log_only" and loaded[1].location == "Site B"
            assert manager.replace_record(0, _incident("first, edited")) is True
            assert [item.description for item in manager.load_records()] == ["first, edited", "second"]
            assert manager.delete_record(0) is True
            assert [item.description for item in manager.load_records()] == ["second"]
            for bad_index in (-1, 1, 5):
                assert manager.replace_record(bad_index, _incident("x")) is False
                assert manager.delete_record(bad_index) is False
            assert [item.description for item in manager.load_records()] == ["second"]  # nothing changed
        assert not os.path.exists(os.path.join(folder, "shared", "incidents.json"))  # database mode uses no file


def test_broken_saved_incidents_are_skipped_not_fatal():
    with temp_data_dir() as folder:
        local, shared = _managers(folder)
        good = _incident("good").to_dict()
        os.makedirs(os.path.join(folder, "local"))
        _write(os.path.join(folder, "local"), "incidents.json", json.dumps([good, {"description": "no location"}, 3]))
        assert [item.description for item in local.load_records()] == ["good"]
        with shared.database.connect() as connection:
            for data in (json.dumps(good), "{not json", json.dumps({"description": "no location"})):
                connection.execute("INSERT INTO incidents (timestamp, location, data) VALUES (?, ?, ?)", ("t", "l", data))
        assert [item.description for item in shared.load_records()] == ["good"]


def test_save_never_overwrites_an_unreadable_incidents_file():
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        manager.save_record(_incident("kept"))
        real_open = open

        def locked(path, mode="r", *args, **kwargs):
            if "r" in mode and str(path).endswith("incidents.json"):
                raise PermissionError("locked by another program")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch("builtins.open", locked):
            assert manager.save_record(_incident("new")) is False
            assert manager.replace_record(0, _incident("new")) is False
            assert manager.delete_record(0) is False
        assert [item.description for item in manager.load_records()] == ["kept"]
        _write(folder, "incidents.json", "{not json")  # a corrupt file is set aside, then saving starts afresh
        assert manager.save_record(_incident("after corrupt")) is True
        assert [item.description for item in manager.load_records()] == ["after corrupt"]
        assert any(".corrupt-" in name for name in os.listdir(folder))


def test_shared_database_outage_gives_empty_and_false_not_an_error():
    class DeadDatabase:
        def connect(self):
            raise ConnectionError("server unreachable")

    with temp_data_dir() as folder:
        manager = dm.DataManager(folder, shared_database=DeadDatabase())
        assert manager.load_records() == []
        assert manager.save_record(_incident("x")) is False
        assert manager.replace_record(0, _incident("x")) is False and manager.delete_record(0) is False


_PNG = b"\x89PNG\r\n\x1a\n" + b"fake image data"


def test_photo_is_kept_in_the_photos_folder_and_loads_again():
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        photo = IncidentPhoto.from_bytes("site.png", _PNG)
        path = manager.store_photo(photo)
        assert path == os.path.join(folder, "photos", photo.fingerprint() + ".png")
        with open(path, "rb") as f:
            assert f.read() == _PNG
        loaded = manager.load_photo(_incident("with photo", photo_saved_path=path))
        assert loaded.content == _PNG and loaded.mime_type == "image/png"
        assert manager.load_photo(_incident("no photo")) is None
        assert manager.read_photo("db:" + photo.fingerprint()) is None  # local mode keeps no photos in a database
        _write(os.path.join(folder, "photos"), "broken.png", "not an image")
        assert manager.load_photo(_incident("x", photo_saved_path=os.path.join(folder, "photos", "broken.png"))) is None
        os.remove(path)
        assert manager.load_photo(_incident("x", photo_saved_path=path)) is None  # file gone: no photo, no error


def test_photo_is_kept_in_the_shared_database_and_loads_again():
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder, shared_database=Database(os.path.join(folder, "s.db")))
        photo = IncidentPhoto.from_bytes("site.png", _PNG)
        reference = manager.store_photo(photo)
        assert reference == "db:" + photo.fingerprint()
        assert manager.store_photo(photo) == reference  # the same photo again is stored once
        assert manager.read_photo(reference) == (_PNG, "image/png")
        loaded = manager.load_photo(_incident("x", photo_saved_path=reference, photo_file="site.png"))
        assert loaded.content == _PNG and loaded.file_name == "site.png"
        assert manager.read_photo("db:unknown") is None and manager.read_photo("some/file.png") is None
        assert manager.load_photo(_incident("x", photo_saved_path="db:unknown")) is None
        assert not os.path.exists(os.path.join(folder, "photos"))  # no photo files in database mode


def test_photo_storage_failures_give_none_not_an_error():
    class DeadDatabase:
        def connect(self):
            raise ConnectionError("server unreachable")

    photo = IncidentPhoto.from_bytes("site.png", _PNG)
    with temp_data_dir() as folder:
        _write(folder, "blocker", "")
        assert dm.DataManager(os.path.join(folder, "blocker")).store_photo(photo) is None  # folder cannot be made
        down = dm.DataManager(folder, shared_database=DeadDatabase())
        assert down.store_photo(photo) is None and down.read_photo("db:" + photo.fingerprint()) is None


def test_ai_cache_round_trip_in_both_modes():
    with temp_data_dir() as folder:
        local, shared = _managers(folder)
        for manager in (local, shared):
            assert manager.load_ai_cache() == {}
            assert manager.save_ai_cache({"prompt-key": "reply"}) is True
            assert manager.load_ai_cache() == {"prompt-key": "reply"}
        assert os.path.exists(os.path.join(folder, "local", "ai_cache.json"))
        assert not os.path.exists(os.path.join(folder, "shared", "ai_cache.json"))  # kept in the database instead
        _write(os.path.join(folder, "local"), "ai_cache.json", "[1]")  # wrong shape
        assert local.load_ai_cache() == {}


def test_query_by_location_window_order_and_bad_timestamps():
    records = [_incident("old", timestamp="2026-09-01T10:00:00"),
               _incident("mid", timestamp="2026-09-20T10:00:00"),
               _incident("other site", location="Site B", timestamp="2026-09-25T10:00:00"),
               _incident("new", timestamp="2026-09-26T10:00:00"),
               _incident("bad time", timestamp="garbage")]
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        hits = manager.query_by_location("Site A", 30, as_of="2026-09-27T00:00:00", records=records)
        assert [item.description for item in hits] == ["new", "mid", "old"]  # newest first, bad time skipped
        assert all(isinstance(item, Incident) for item in hits)
        assert [item.description for item in manager.query_by_location(
            "Site A", 10, as_of="2026-09-27T00:00:00", records=records)] == ["new", "mid"]
        assert manager.query_by_location("Nowhere", 30, records=records) == []
        for incident in records:
            manager.save_record(incident)
        saved = manager.query_by_location("Site A", 30, as_of="2026-09-27T00:00:00")  # reads the saved records
        assert [item.description for item in saved] == ["new", "mid", "old"]
        # An unreadable as_of falls back to now, so these September records are outside a 1-day window.
        assert manager.query_by_location("Site A", 1, as_of="not a date", records=records) == []


def test_list_locations_counts_and_sorts_by_name():
    records = [_incident("a", location="site b"), _incident("b", location="Site A"),
               _incident("c", location="site b"), _incident("d", location="Crane yard")]
    with temp_data_dir() as folder:
        manager = dm.DataManager(folder)
        assert manager.list_locations(records) == [("Crane yard", 1), ("Site A", 1), ("site b", 2)]
        assert manager.list_locations() == []
        manager.save_record(records[0])
        assert manager.list_locations() == [("site b", 1)]
