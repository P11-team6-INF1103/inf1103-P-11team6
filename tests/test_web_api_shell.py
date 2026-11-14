# Lennart
from database import Database
from models.incident import Incident
from web_api import WebApi, create_app


class _StubApp:
    # Stands in for IncidentTriageApp: the incidents it holds and the database the workflow rows live in.
    def __init__(self, database: Database, records: list[Incident] | None = None) -> None:
        self.database = database
        self.records = records or []
        self.started = False

    def start_up(self) -> None:
        self.started = True

    def reload_records(self) -> list[Incident]:
        return self.records


def _incident(description: str = "Scaffold plank fell near a worker", location: str = "Site B") -> Incident:
    return Incident(description, location, "safety_officer", False)


def _client(tmp_path, records: list[Incident] | None = None, origins: list[str] | None = None):
    app = _StubApp(Database(str(tmp_path / "web.db")), records)
    api = WebApi(app, origins or ["http://localhost:5173"], 50)
    return api.flask.test_client(), app


def test_the_app_is_started_when_the_api_is_built(tmp_path):
    _, app = _client(tmp_path)
    assert app.started is True


def test_health_reports_how_many_incidents_are_loaded(tmp_path):
    client, _ = _client(tmp_path, [_incident(), _incident(location="Site C")])
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "incidents": 2}


def test_meta_gives_the_labels_the_terminal_app_uses(tmp_path):
    client, _ = _client(tmp_path)
    body = client.get("/api/meta").get_json()
    assert body["severity_levels"]["5"]["name"] == "Critical"
    assert body["priority_levels"]["1"] == "Urgent"
    assert set(body) == {"severity_levels", "outcome_actions", "outcome_names", "hazard_names", "priority_levels"}


def test_cors_allows_only_the_configured_origin(tmp_path):
    client, _ = _client(tmp_path, origins=["https://workplacelogging.netlify.app"])
    allowed = client.get("/api/health", headers={"Origin": "https://workplacelogging.netlify.app"})
    other = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://workplacelogging.netlify.app"
    assert "Access-Control-Allow-Origin" not in other.headers


def test_list_gives_each_incident_its_number_and_workflow_fields(tmp_path):
    client, _ = _client(tmp_path, [_incident(), _incident(location="Site C")])
    body = client.get("/api/incidents").get_json()
    assert [row["id"] for row in body] == [1, 2]
    assert body[1]["location"] == "Site C"
    assert {"priority", "priority_name", "resolved", "problems", "has_photo"} <= set(body[0])


def test_list_is_empty_when_nothing_is_saved(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/api/incidents").get_json() == []


def test_get_returns_one_incident_with_its_history(tmp_path):
    client, _ = _client(tmp_path, [_incident()])
    response = client.get("/api/incidents/1")
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == 1 and body["history"] == []


def test_get_of_a_missing_number_is_a_404(tmp_path):
    client, _ = _client(tmp_path, [_incident()])
    for number in (0, 2):
        response = client.get(f"/api/incidents/{number}")
        assert response.status_code == 404
        assert response.get_json() == {"errors": [f"No incident #{number}."]}


def test_create_app_hands_over_the_flask_server_of_the_environment_api(tmp_path, monkeypatch):
    api = WebApi(_StubApp(Database(str(tmp_path / "web.db"))), ["http://localhost:5173"])
    monkeypatch.setattr(WebApi, "from_environment", classmethod(lambda cls: api))
    assert create_app() is api.flask
