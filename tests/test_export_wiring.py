# Lennart
import json
import os

import pytest

from ai_clients.response_cache import ResponseCache
from ai_manager import AIManager
from data_manager import DataManager
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from models.incident import Incident
from tests.fakes import FakeGemini, FakeSearch, FakeWeather
from web_api import WebApi


def build_app(tmp_path, saved=0):
    ai = AIManager(FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai, LogicManager(LogicManager.default_rules()),
                            DataManager(str(tmp_path / "data")), ResponseCache())
    for number in range(saved):
        app._data.save_record(Incident(f"Scaffold plank fell near worker {number}", "Site B", "safety_officer", False,
                                       f"2026-10-2{number}T10:00:00"))
    return app


def test_export_text_returns_the_exporter_and_every_saved_incident(tmp_path):
    exporter, text = build_app(tmp_path, saved=2).export_text("json")
    assert exporter.content_type.startswith("application/json")
    assert len(json.loads(text)) == 2


def test_export_text_rejects_an_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        build_app(tmp_path, saved=1).export_text("xml")


def test_export_to_file_picks_the_format_from_the_file_ending(tmp_path):
    path = tmp_path / "out.csv"
    assert build_app(tmp_path, saved=2).export_to_file(str(path)) == 2
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3  # header and two rows
    with pytest.raises(ValueError):
        build_app(tmp_path, saved=1).export_to_file(str(tmp_path / "out.xml"))


def test_run_export_returns_zero_on_success_and_one_when_it_fails(tmp_path, capsys):
    app = build_app(tmp_path, saved=1)
    assert app.run_export(str(tmp_path / "all.json")) == 0
    assert app.run_export(str(tmp_path / "all.xml")) == 1
    assert "Export failed" in capsys.readouterr().out


def test_menu_option_six_asks_for_a_format_and_writes_the_file(tmp_path, monkeypatch, capsys):
    app = build_app(tmp_path, saved=1)
    answers = iter(["2", str(tmp_path / "menu.json")])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    app.export_incidents()
    assert json.loads((tmp_path / "menu.json").read_text(encoding="utf-8"))
    assert "Exported 1 incident(s)" in capsys.readouterr().out


def test_menu_option_six_with_nothing_saved_says_so(tmp_path, capsys):
    build_app(tmp_path).export_incidents()
    assert "No incidents to export." in capsys.readouterr().out


def test_export_choice_goes_back_on_enter_and_asks_before_replacing_a_file(tmp_path, monkeypatch):
    io = IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS)
    defaults = {"csv": "incidents.csv", "json": "incidents.json"}
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert io.get_export_choice(defaults) is None
    existing = tmp_path / "taken.csv"
    existing.write_text("old")
    answers = iter(["1", str(existing), "no"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert io.get_export_choice(defaults) is None
    assert existing.read_text() == "old" and os.path.exists(existing)


def test_export_route_downloads_csv_by_default_and_json_on_request(tmp_path):
    client = WebApi(build_app(tmp_path, saved=2), ["http://localhost:5173"], 50).flask.test_client()
    csv_reply = client.get("/api/incidents/export")
    assert csv_reply.status_code == 200
    assert csv_reply.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in csv_reply.headers["Content-Disposition"] and ".csv" in csv_reply.headers["Content-Disposition"]
    json_reply = client.get("/api/incidents/export?format=json")
    assert len(json.loads(json_reply.get_data(as_text=True))) == 2


def test_export_route_refuses_an_unknown_format(tmp_path):
    client = WebApi(build_app(tmp_path, saved=1), ["http://localhost:5173"], 50).flask.test_client()
    reply = client.get("/api/incidents/export?format=xml")
    assert reply.status_code == 422 and reply.get_json()["errors"]
