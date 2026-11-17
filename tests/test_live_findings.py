# Lennart
import pytest

from data_manager import DataManager
from models.incident import Incident
from tests.api_helpers import FORM, make_client
from workflow import WorkflowStore


def three(client):
    for place in ("Site A", "Site B", "Site C"):
        assert client.post("/api/incidents", data={**FORM, "location": place}).status_code == 201
    return client.get("/api/incidents").get_json()


# --- Incident numbers are positions, so a stale page must not change a different incident ---

def test_a_stale_delete_is_refused_and_removes_nothing(tmp_path):
    client = make_client(tmp_path)
    rows = three(client)
    stale = rows[1]["timestamp"]
    assert client.delete(f"/api/incidents/2?timestamp={stale}").status_code == 200  # the first click
    second = client.delete(f"/api/incidents/2?timestamp={stale}")  # a stale page or a second supervisor
    assert second.status_code == 409 and "Refresh the list" in second.get_json()["errors"][0]
    assert [r["location"] for r in client.get("/api/incidents").get_json()] == ["Site A", "Site C"]


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/incidents/1/resolve", {"json": {"note": "x"}}),
    ("post", "/api/incidents/1/reopen", {}),
    ("put", "/api/incidents/1/priority", {"json": {"priority": 1}}),
    ("patch", "/api/incidents/1", {"data": {"location": "Site Z"}}),
    ("post", "/api/incidents/1/revert", {"json": {"version": 1}}),
    ("post", "/api/incidents/1/reanalyse", {}),
    ("delete", "/api/incidents/1", {}),
])
def test_every_change_checks_the_timestamp(tmp_path, method, path, body):
    client = make_client(tmp_path)
    three(client)
    response = getattr(client, method)(path + "?timestamp=1999-01-01T00:00:00", **body)
    assert response.status_code == 409
    assert len(client.get("/api/incidents").get_json()) == 3


def test_the_right_timestamp_or_none_works(tmp_path):
    client = make_client(tmp_path)
    rows = three(client)
    ok = client.post(f"/api/incidents/1/resolve?timestamp={rows[0]['timestamp']}", json={"note": "done"})
    assert ok.status_code == 200 and ok.get_json()["resolved"] is True
    assert client.post("/api/incidents/2/resolve", json={}).status_code == 200  # scripts may leave it out


# --- Locations are one place whatever the case or spacing ---

def make_record(location, day):
    return Incident(description="Scaffold plank fell near a worker", location=location, reporter_role="supervisor",
                    injury=False, timestamp=f"2026-10-{day:02d}T09:00:00")


def test_location_spellings_are_one_place(tmp_path):
    data = DataManager(str(tmp_path))
    records = [make_record("Site B", 1), make_record("site b", 2), make_record(" Site   B ", 3), make_record("Site A", 4)]
    assert data.list_locations(records) == [("Site A", 1), ("Site B", 3)]
    found = data.query_by_location("SITE B", 30, as_of="2026-10-20T00:00:00", records=records)
    assert len(found) == 3
    assert DataManager.location_key(None) == "" and DataManager.location_key("  A  b ") == "a b"


# --- Resolving twice keeps the first note ---

def test_resolving_again_keeps_the_first_note_and_time(tmp_path):
    client = make_client(tmp_path)
    three(client)
    first = client.post("/api/incidents/1/resolve", json={"note": "first"}).get_json()
    second = client.post("/api/incidents/1/resolve", json={"note": "second"}).get_json()
    assert second["resolution_note"] == "first" and second["resolved_at"] == first["resolved_at"]
    client.post("/api/incidents/1/reopen")
    third = client.post("/api/incidents/1/resolve", json={"note": "after reopen"}).get_json()
    assert third["resolution_note"] == "after reopen"


def test_workflow_resolve_is_a_no_op_when_already_resolved(tmp_path):
    from database import Database
    store = WorkflowStore(Database(str(tmp_path / "w.db")))
    store.resolve("k", "one")
    store.resolve("k", "two")
    assert store.all()["k"]["resolution_note"] == "one"


# --- Search filters are checked like the other ones ---

@pytest.mark.parametrize("query", ["status=bogus", "has_photo=maybe"])
def test_bad_search_filters_are_refused(tmp_path, query):
    client = make_client(tmp_path)
    response = client.get(f"/api/incidents/search?q=plank&{query}")
    assert response.status_code == 422 and "must be" in response.get_json()["errors"][0]


@pytest.mark.parametrize("query", ["status=open", "status=resolved", "has_photo=true", "has_photo=false", "has_photo=1"])
def test_good_search_filters_still_work(tmp_path, query):
    client = make_client(tmp_path)
    three(client)
    assert client.get(f"/api/incidents/search?{query}").status_code == 200


# --- Unknown addresses answer in JSON ---

@pytest.mark.parametrize("path", ["/api/incidents/abc", "/api/incidents/-1", "/api/incidents/1.5", "/api/nothing"])
def test_unknown_addresses_answer_in_json(tmp_path, path):
    client = make_client(tmp_path)
    response = client.get(path)
    assert response.status_code == 404 and response.get_json() == {"errors": ["Not found."]}


def test_a_wrong_method_answers_in_json(tmp_path):
    response = make_client(tmp_path).put("/api/health")
    assert response.status_code == 405 and response.get_json() == {"errors": ["That method is not allowed here."]}


# --- Error wording ---

def test_error_messages_do_not_repeat_the_field_name(tmp_path):
    client = make_client(tmp_path)
    response = client.post("/api/incidents", data={**FORM, "description": "ok"})
    assert response.get_json()["errors"] == ["Description is too short. Say what happened in at least 10 characters."]
    response = client.post("/api/incidents", data={**FORM, "injury": "maybe"})
    assert response.get_json()["errors"] == ["Injury must be true or false."]
    response = client.post("/api/incidents", data={k: v for k, v in FORM.items() if k != "location"})
    assert response.get_json()["errors"] == ["Location is missing."]
