# Daniel
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import os

import pytest

from data_manager import DataManager
from data_stores.db_json import DbJson
from data_stores.document_store import DocumentStore
from data_stores.json_file import JsonFile
from models.incident import Incident
from models.incident_photo import IncidentPhoto

SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")


def make(location="Site A", timestamp="2026-10-20T09:00:00", **fields):
    incident = Incident("Worker slipped on wet floor", location, "supervisor", True, timestamp)
    incident.update(fields)
    return incident


def test_missing_file_gives_no_records(tmp_path):
    data = DataManager(str(tmp_path))
    assert data.load_records() == [] and data.check_records_file() is None


def test_save_load_and_delete_round_trip(tmp_path):
    data = DataManager(str(tmp_path))
    assert data.save_record(make(outcome="log_only")) and data.save_record(make("Site B"))
    loaded = data.load_records()
    assert [r.location for r in loaded] == ["Site A", "Site B"] and loaded[0].get("outcome") == "log_only"
    assert data.delete_record(0) and [r.location for r in data.load_records()] == ["Site B"]
    assert not data.delete_record(5)


def test_corrupt_file_is_kept_aside_and_never_crashes(tmp_path):
    (tmp_path / "incidents.json").write_text("{ not json", encoding="utf-8")
    data = DataManager(str(tmp_path))
    assert "corrupt" in data.check_records_file()
    assert data.load_records() == []
    assert any(name.startswith("incidents.json.corrupt-") for name in os.listdir(tmp_path))


def test_wrong_shape_and_broken_entries_are_handled(tmp_path):
    (tmp_path / "incidents.json").write_text('{"a": 1}', encoding="utf-8")
    assert "wrong format" in DataManager(str(tmp_path)).check_records_file()
    (tmp_path / "incidents.json").write_text('[{"description": "only this"}, 5]', encoding="utf-8")
    assert DataManager(str(tmp_path)).load_records() == []


def test_save_refuses_to_overwrite_an_unreadable_file(tmp_path, monkeypatch):
    data = DataManager(str(tmp_path))
    data.save_record(make())
    monkeypatch.setattr(JsonFile, "read", lambda self: ([], "could not read incidents.json"))
    assert data.save_record(make()) is False


def test_write_failure_returns_false(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x", encoding="utf-8")
    assert JsonFile(str(blocker / "incidents.json"), list).write([]) is False


def test_query_by_location_window_and_order(tmp_path):
    records = [make(timestamp="2026-10-01T09:00:00"), make(timestamp="2026-10-19T09:00:00"),
               make("Site B", "2026-10-19T10:00:00"), make(timestamp="bad")]
    found = DataManager(str(tmp_path)).query_by_location("Site A", 30, as_of="2026-10-20T00:00:00",
                                                         records=records)
    assert [r.timestamp for r in found] == ["2026-10-19T09:00:00", "2026-10-01T09:00:00"]
    assert DataManager(str(tmp_path)).list_locations(records) == [("Site A", 3), ("Site B", 1)]


def test_photo_is_copied_into_the_data_folder(tmp_path):
    path = DataManager(str(tmp_path)).store_photo(IncidentPhoto.from_file(SAMPLE_PHOTO))
    assert path.startswith(str(tmp_path / "photos")) and os.path.getsize(path) > 0


def test_ai_cache_round_trip(tmp_path):
    data = DataManager(str(tmp_path))
    assert data.load_ai_cache() == {}
    assert data.save_ai_cache({"k": "v"}) and data.load_ai_cache() == {"k": "v"}


# With a shared database nothing is written to the local data folder: incidents, photos, site plan and cache all go in it.
def test_shared_database_keeps_everything_out_of_the_folder(tmp_path):
    from database import Database
    folder = tmp_path / "local"
    manager = DataManager(str(folder), Database(str(tmp_path / "shared.db")))
    with open(SAMPLE_PHOTO, "rb") as f:
        photo = IncidentPhoto.from_bytes("scene.png", f.read())
    first = Incident("Plank fell", "Site A", "site_supervisor", False, "2026-10-01T09:00:00", photo)
    first.update({"photo_saved_path": manager.store_photo(photo)})
    second = Incident("Slip", "Site B", "site_supervisor", True, "2026-10-02T09:00:00")
    assert manager.save_record(first) and manager.save_record(second)
    assert [i.location for i in manager.load_records()] == ["Site A", "Site B"]

    reference = first.get("photo_saved_path")
    assert reference.startswith("db:") and manager.read_photo(reference)[0] == photo.content
    assert manager.load_photo(first).content == photo.content

    second.update({"severity_estimate": 3})
    assert manager.replace_record(1, second) and manager.load_records()[1].get("severity_estimate") == 3
    assert manager.delete_record(0) and [i.location for i in manager.load_records()] == ["Site B"]
    assert not manager.delete_record(5)
    assert manager.save_ai_cache({"k": 1}) and manager.load_ai_cache() == {"k": 1}
    assert manager.get_log_path() is None
    assert not folder.exists()


# SOLID evidence (Liskov and open/closed): a file and a database row are both a DocumentStore, so they can be swapped.
def test_document_store_cannot_be_created_directly():
    with pytest.raises(TypeError):
        DocumentStore()


def test_a_file_and_a_database_row_behave_the_same_behind_the_interface(tmp_path):
    from database import Database
    stores = [JsonFile(str(tmp_path / "plan.json"), dict), DbJson(Database(str(tmp_path / "app.db")), "plan", dict)]
    for store in stores:
        assert isinstance(store, DocumentStore)
        assert store.read() == ({}, None)  # nothing stored yet: an empty value, no problem reported
        assert store.write({"width_m": 90}) and store.read() == ({"width_m": 90}, None)
        assert store.delete() and store.read() == ({}, None)
        assert store.delete()  # deleting what is already gone is not an error


def test_data_manager_accepts_a_new_kind_of_store_without_changes(tmp_path):
    class MemoryStore(DocumentStore):
        def __init__(self):
            self.value = {}

        def read(self):
            return self.value, None

        def write(self, data):
            self.value = data
            return True

        def delete(self):
            self.value = {}
            return True

    data = DataManager(str(tmp_path))
    data._cache_file = MemoryStore()
    assert data.save_ai_cache({"k": "v"}) and data.load_ai_cache() == {"k": "v"}
    assert not (tmp_path / "ai_cache.json").exists()
