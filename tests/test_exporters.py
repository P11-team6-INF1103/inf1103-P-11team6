# Lennart
import csv
import io
import json
import os
from datetime import date

import pytest

from ai_clients.response_cache import ResponseCache
from ai_manager import AIManager
from data_manager import DataManager
from exporters.constants import COLUMNS
from exporters.csv_incident_exporter import CsvIncidentExporter
from exporters.exporter_factory import ExporterFactory
from exporters.incident_exporter import IncidentExporter
from exporters.json_incident_exporter import JsonIncidentExporter
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from models.incident import Incident
from tests.api_helpers import log_in
from tests.doubles.fake_gemini import FakeGemini
from tests.doubles.fake_search import FakeSearch
from tests.doubles.fake_weather import FakeWeather
from web_api import WebApi


def scored(description="Scaffold plank fell from level 4 near a worker", location="Site B", injury=True):
    incident = Incident(description, location, "safety_officer", injury, "2026-10-21T21:40:00")
    incident.update({"hazard_type": "fall_from_height", "severity_estimate": 4, "outcome": "stop_work_review",
                     "likelihood_recurrence": "high", "ppe_status": "not_worn",
                     "severity_reasons": ["Someone was injured", "Working at height"],
                     "review_prevention_actions": ["Inspect scaffolds daily", "Tie down planks"]})
    return incident


def read_csv(text):
    return list(csv.reader(io.StringIO(text)))


# --- The exporters ---

def test_csv_has_a_header_and_one_row_per_incident():
    rows = read_csv(CsvIncidentExporter().export([scored(), scored("Cut hand on a saw", "Site A", False)]))
    assert rows[0] == list(COLUMNS) and len(rows) == 3
    first = dict(zip(COLUMNS, rows[1]))
    assert first["number"] == "1" and first["version"] == "1" and first["injury"] == "yes"
    assert first["severity"] == "4" and first["outcome"] == "stop_work_review" and first["hazard"] == "fall_from_height"
    assert first["severity_reasons"] == "Someone was injured | Working at height"
    assert first["prevention_actions"] == "Inspect scaffolds daily | Tie down planks"
    assert dict(zip(COLUMNS, rows[2]))["number"] == "2" and dict(zip(COLUMNS, rows[2]))["injury"] == "no"


def test_csv_keeps_commas_quotes_and_line_breaks_inside_one_cell():
    text = 'Plank fell, "narrowly" missed a worker\nand hit a pipe'
    rows = read_csv(CsvIncidentExporter().export([scored(text)]))
    assert len(rows) == 2 and dict(zip(COLUMNS, rows[1]))["description"] == text


@pytest.mark.parametrize("risky", ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"])
def test_csv_stops_a_spreadsheet_from_running_text_as_a_formula(risky):
    cell = dict(zip(COLUMNS, read_csv(CsvIncidentExporter().export([scored(risky)]))[1]))["description"]
    assert cell == "'" + risky


def test_csv_leaves_numbers_and_an_unassessed_incident_alone():
    bare = Incident("Worker slipped", "Site A", "officer", False, "2026-10-21T10:00:00")  # the AI never scored it
    row = dict(zip(COLUMNS, read_csv(CsvIncidentExporter().export([bare]))[1]))
    assert row["severity"] == "" and row["outcome"] == "" and row["severity_reasons"] == "" and row["description"] == "Worker slipped"


def test_json_keeps_lists_as_lists_and_unscored_fields_as_null():
    bare = Incident("Worker slipped", "Site A", "officer", False, "2026-10-21T10:00:00")
    rows = json.loads(JsonIncidentExporter().export([scored(), bare]))
    assert rows[0]["severity"] == 4 and rows[0]["severity_reasons"] == ["Someone was injured", "Working at height"]
    assert rows[1]["severity"] is None and rows[1]["severity_reasons"] == [] and list(rows[0]) == list(COLUMNS)


def test_an_empty_export_is_still_a_valid_file():
    assert read_csv(CsvIncidentExporter().export([])) == [list(COLUMNS)]
    assert json.loads(JsonIncidentExporter().export([])) == []


def test_every_exporter_can_stand_in_for_the_base_class():
    incidents = [scored()]
    for exporter in (CsvIncidentExporter(), JsonIncidentExporter()):
        assert isinstance(exporter, IncidentExporter)
        assert isinstance(exporter.export(incidents), str) and exporter.export(incidents)
        assert exporter.file_name(date(2026, 11, 13)) == f"incidents_2026-11-13.{exporter.extension}"
        assert exporter.rows(incidents) == IncidentExporter.rows(exporter, incidents)


def test_a_new_format_is_only_a_new_subclass():
    class LineExporter(IncidentExporter):
        extension = "txt"
        content_type = "text/plain"

        def export(self, incidents):
            return "\n".join(f"{row['number']} {row['location']}" for row in self.rows(incidents))

    assert LineExporter().export([scored(), scored(location="Site C")]) == "1 Site B\n2 Site C"
    with pytest.raises(TypeError):
        IncidentExporter()  # the base class cannot be used on its own


def test_factory_picks_by_name_or_file_ending_and_rejects_the_rest():
    assert ExporterFactory.names() == ("csv", "json")
    assert isinstance(ExporterFactory.create(" CSV "), CsvIncidentExporter)
    assert isinstance(ExporterFactory.for_path("out/report.json"), JsonIncidentExporter)
    for bad in ("xml", "", "csv2"):
        with pytest.raises(ValueError, match="Unknown export format"):
            ExporterFactory.create(bad)
    with pytest.raises(ValueError):
        ExporterFactory.for_path("incidents")


# --- Through the app: the terminal menu, the command line and the web route ---

def build(tmp_path, count=2):
    ai = AIManager(FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                            LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path / "data")), ResponseCache())
    for n in range(count):
        app.process_incident(Incident(f"Scaffold plank fell near worker number {n}", f"Site {n}", "officer", True,
                                      f"2026-10-2{n + 1}T10:00:00"), interactive=False)
    return app


def type_answers(monkeypatch, answers):
    queue = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(queue))


def test_menu_option_writes_the_chosen_file(tmp_path, monkeypatch, capsys):
    app = build(tmp_path)
    target = tmp_path / "out.csv"
    type_answers(monkeypatch, ["1", str(target)])
    app.export_incidents()
    rows = read_csv(target.read_text(encoding="utf-8"))
    assert len(rows) == 3 and rows[1][3] == "Site 0" and f"Exported 2 incident(s) to {target}" in capsys.readouterr().out
    assert "\r\n" in target.read_bytes().decode()  # a proper CSV line ending


def test_menu_option_uses_the_default_name_for_the_format(tmp_path, monkeypatch):
    app = build(tmp_path)
    monkeypatch.chdir(tmp_path)
    type_answers(monkeypatch, ["2", ""])
    app.export_incidents()
    assert os.path.isfile(tmp_path / f"incidents_{date.today().isoformat()}.json")


def test_menu_option_asks_before_replacing_a_file_and_can_be_cancelled(tmp_path, monkeypatch, capsys):
    app = build(tmp_path)
    target = tmp_path / "out.csv"
    target.write_text("keep me")
    type_answers(monkeypatch, ["1", str(target), "no"])
    app.export_incidents()
    assert target.read_text() == "keep me" and "Nothing was exported" in capsys.readouterr().out
    type_answers(monkeypatch, ["1", str(target), "yes"])
    app.export_incidents()
    assert target.read_text(encoding="utf-8").startswith("number,")
    type_answers(monkeypatch, [""])  # Enter at the format question goes back
    app.export_incidents()


def test_menu_option_reports_a_folder_that_cannot_be_written(tmp_path, monkeypatch, capsys):
    app = build(tmp_path)
    type_answers(monkeypatch, ["1", str(tmp_path / "missing" / "out.csv")])
    app.export_incidents()
    assert "Could not write" in capsys.readouterr().out


def test_menu_option_with_no_incidents_says_so(tmp_path, capsys):
    build(tmp_path, count=0).export_incidents()
    assert "No incidents to export." in capsys.readouterr().out


def test_command_line_export_picks_the_format_from_the_file_ending(tmp_path, capsys):
    app = build(tmp_path)
    assert app.run_export(str(tmp_path / "all.json")) == 0
    assert len(json.loads((tmp_path / "all.json").read_text(encoding="utf-8"))) == 2
    assert app.run_export(str(tmp_path / "all.xml")) == 1 and "Unknown export format" in capsys.readouterr().out
    assert app.run_export(str(tmp_path / "missing" / "all.csv")) == 1


def test_web_route_downloads_csv_by_default_and_json_on_request(tmp_path):
    client = log_in(WebApi(build(tmp_path), ["http://localhost:5173"], 50).flask.test_client())
    response = client.get("/api/incidents/export")
    assert response.status_code == 200 and response.mimetype == "text/csv"
    assert f'filename="incidents_{date.today().isoformat()}.csv"' in response.headers["Content-Disposition"]
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert len(read_csv(response.get_data(as_text=True))) == 3
    as_json = client.get("/api/incidents/export?format=json")
    assert as_json.mimetype == "application/json" and len(as_json.get_json()) == 2
    assert client.get("/api/incidents/1").status_code == 200  # the export route does not hide the numbered routes


def test_web_route_rejects_an_unknown_format(tmp_path):
    client = log_in(WebApi(build(tmp_path), ["http://localhost:5173"], 50).flask.test_client())
    response = client.get("/api/incidents/export?format=xml")
    assert response.status_code == 422 and "Unknown export format" in response.get_json()["errors"][0]
