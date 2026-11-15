# Daniel
from tests.api_helpers import FORM, make_client
from workflow import WorkflowStore


def test_anyone_can_set_priority_resolve_reopen_and_delete(tmp_path):
    client = make_client(tmp_path)
    assert client.post("/api/incidents", data=FORM).status_code == 201
    created = client.get("/api/incidents/1").get_json()
    assert created["priority"] in (1, 2) and created["priority_source"] == "auto" and created["resolved"] is False

    changed = client.put("/api/incidents/1/priority", json={"priority": 4}).get_json()
    assert changed["priority"] == 4 and changed["priority_source"] == "manual"
    assert client.put("/api/incidents/1/priority", json={"priority": 9}).status_code == 422
    back = client.put("/api/incidents/1/priority", json={"priority": None}).get_json()
    assert back["priority_source"] == "auto"

    done = client.post("/api/incidents/1/resolve", json={"note": "Plank secured"}).get_json()
    assert done["resolved"] and done["resolution_note"] == "Plank secured"
    assert client.get("/api/incidents/1").get_json()["resolved"] is True
    assert client.post("/api/incidents/1/reopen").get_json()["resolved"] is False
    assert client.put("/api/incidents/7/priority", json={"priority": 1}).status_code == 404


def test_there_are_no_account_routes(tmp_path):
    client = make_client(tmp_path)
    for path in ("/api/auth/login", "/api/auth/register", "/api/auth/me"):
        assert client.post(path, json={}).status_code in (404, 405)
    assert "login_required" not in client.get("/api/health").get_json()


def test_priority_survives_an_edit_and_is_dropped_on_delete(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/incidents", data=FORM)
    client.put("/api/incidents/1/priority", json={"priority": 3})
    client.patch("/api/incidents/1", data={"location": "Site C"})
    assert client.get("/api/incidents/1").get_json()["priority"] == 3
    assert client.delete("/api/incidents/1").status_code == 200
    client.post("/api/incidents", data=FORM)
    assert client.get("/api/incidents/1").get_json()["priority_source"] == "auto"


def test_suggested_priority():
    assert WorkflowStore.suggested_priority({"severity_estimate": 5}) == 1
    assert WorkflowStore.suggested_priority({"severity_estimate": 4}) == 2
    assert WorkflowStore.suggested_priority({"severity_estimate": 3}) == 3
    assert WorkflowStore.suggested_priority({"severity_estimate": 1, "outcome": "systemic_escalation"}) == 2
    assert WorkflowStore.suggested_priority({"severity_estimate": 1, "outcome": "log_only"}) == 4
    assert WorkflowStore.suggested_priority({"assessment_error": "down"}) == 3
