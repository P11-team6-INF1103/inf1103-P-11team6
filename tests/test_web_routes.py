# Lennart
from database import Database
from models.edit_result import EditResult
from models.incident import Incident
from web_api import WebApi


class _StubApp:
    # Stands in for IncidentTriageApp: it keeps the incidents and records which re-runs were asked for.
    def __init__(self, database: Database, records: list[Incident]) -> None:
        self.database = database
        self.records = records
        self.reanalysed: list[int] = []
        self.result = EditResult("updated", records[0] if records else None)

    def start_up(self) -> None:
        pass

    def reload_records(self) -> list[Incident]:
        return self.records

    def reanalyse_incident(self, index: int) -> EditResult:
        self.reanalysed.append(index)
        return self.result


def _client(tmp_path, post_limit: int = 50):
    records = [Incident("Scaffold plank fell near a worker", "Site B", "safety_officer", False)]
    app = _StubApp(Database(str(tmp_path / "routes.db")), records)
    api = WebApi(app, ["http://localhost:5173"], post_limit)
    return api.flask.test_client(), app


def test_every_method_and_path_the_dashboard_uses_is_registered(tmp_path):
    client, _ = _client(tmp_path)
    registered = {(rule.rule, method) for rule in client.application.url_map.iter_rules() for method in rule.methods}
    expected = {("/api/incidents", "POST"), ("/api/incidents/<int:number>", "PATCH"),
                ("/api/incidents/<int:number>", "DELETE"), ("/api/incidents/<int:number>/revert", "POST"),
                ("/api/incidents/<int:number>/reanalyse", "POST"), ("/api/incidents/<int:number>/photo", "GET"),
                ("/api/site-plan", "GET"), ("/api/site-plan", "PUT"), ("/api/site-plan", "DELETE"),
                ("/api/site-plan/read", "POST")}
    assert expected <= registered


def test_reanalyse_runs_the_ai_again_on_the_chosen_incident(tmp_path):
    client, app = _client(tmp_path)
    response = client.post("/api/incidents/1/reanalyse")
    assert response.status_code == 200
    assert response.get_json()["status"] == "updated"
    assert app.reanalysed == [0]


def test_reanalyse_of_an_unknown_number_is_a_404_and_runs_nothing(tmp_path):
    client, app = _client(tmp_path)
    response = client.post("/api/incidents/9/reanalyse")
    assert response.status_code == 404
    assert app.reanalysed == []


def test_reanalyse_failure_keeps_the_old_version_and_gives_502(tmp_path):
    client, app = _client(tmp_path)
    app.result = EditResult("failed", None, app.records[0], "The AI could not assess it.")
    response = client.post("/api/incidents/1/reanalyse")
    assert response.status_code == 502
    assert response.get_json()["kept_version"] == app.records[0].version


def test_reanalyse_is_rate_limited_per_connection(tmp_path):
    client, app = _client(tmp_path, post_limit=1)
    assert client.post("/api/incidents/1/reanalyse").status_code == 200
    assert client.post("/api/incidents/1/reanalyse").status_code == 429
    assert app.reanalysed == [0]
