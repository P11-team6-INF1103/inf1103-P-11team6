# Lennart
from database import Database
from models.incident import Incident
from web_api import WebApi


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
