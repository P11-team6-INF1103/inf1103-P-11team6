import json
import os
import shutil

from ai_clients.gemini_client import GeminiClient
from ai_clients.groq_search_client import GroqSearchClient
from ai_clients.response_cache import ResponseCache
from ai_clients.weather_client import WeatherClient
from ai_manager import AIManager
from ai_steps.hazard_flag_step import HazardFlagStep
from ai_steps.photo_analysis_step import PhotoAnalysisStep
from data_manager import DataManager
from db.database_unavailable import DatabaseUnavailable
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from tests.fakes import HAZARD_REPLY, PHOTO_REPLY, FakeGemini, FakeSearch, FakeWeather

TESTS = os.path.dirname(__file__)
SAMPLE_PHOTO = os.path.join(TESTS, "sample_photo.png")


def build_app(tmp_path, gemini=None):
    cache = ResponseCache()
    ai = AIManager(gemini or FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    return IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                             LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path)), cache)


def test_full_pipeline_with_photo_saves_a_scored_incident(tmp_path):
    app = build_app(tmp_path)
    incident = Incident("Scaffold plank fell from level 4 near a worker", "Site B", "officer", True,
                        "2026-10-21T21:40:00", IncidentPhoto.from_file(SAMPLE_PHOTO))
    result = app.process_incident(incident, interactive=False)
    assert result.get("outcome") == "stop_work_review"
    assert "Safety gear status taken from the photo (not worn)" in result.get("photo_evidence_used")
    saved = DataManager(str(tmp_path)).load_records()
    assert len(saved) == 1 and saved[0].get("photo_file") == "sample_photo.png"
    assert os.path.exists(saved[0].get("photo_saved_path"))


def test_ai_rejects_gibberish_and_nothing_is_saved(tmp_path, capsys):
    gemini = FakeGemini(replies={id(HazardFlagStep.SCHEMA): {**HAZARD_REPLY, "is_valid_incident": False,
                                                             "invalid_reason": "This is test text."}})
    app = build_app(tmp_path, gemini)
    assert app.process_incident(Incident("testing testing hello", "Site A", "x", False), False) is None
    assert "This is test text." in capsys.readouterr().out
    assert DataManager(str(tmp_path)).load_records() == []


def test_mismatched_photo_is_routed_to_photo_review(tmp_path):
    gemini = FakeGemini(replies={
        id(HazardFlagStep.SCHEMA): {**HAZARD_REPLY, "hazard_category": "other", "injury_treatment": "none",
                                    "elevated_places": [], "ppe_status": "worn"},
        id(PhotoAnalysisStep.SCHEMA): {**PHOTO_REPLY, "photo_matches_description": False,
                                       "photo_shows_height": False, "photo_ppe_status": "unspecified"},
    })
    app = build_app(tmp_path, gemini)
    incident = Incident("Loose cable found across the walkway", "Site C", "officer", False,
                        "2026-10-21T10:00:00", IncidentPhoto.from_file(SAMPLE_PHOTO))
    assert app.process_incident(incident, False).get("outcome") == "photo_review"


def test_batch_without_api_keys_still_finishes_with_manual_review(tmp_path, capsys):
    shutil.copy(os.path.join(TESTS, "sample_batch.json"), tmp_path / "batch.json")
    shutil.copy(SAMPLE_PHOTO, tmp_path / "sample_photo.png")
    cache = ResponseCache()
    ai = AIManager(GeminiClient(cache), GroqSearchClient(cache), WeatherClient(cache), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                            LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path / "data")), cache)
    assert app.run_batch(str(tmp_path / "batch.json")) == 0
    out = capsys.readouterr().out
    assert "Total incidents: 3" in out and "With a photo: 1" in out and "Skipped: Item 4" in out
    saved = json.loads((tmp_path / "data" / "incidents.json").read_text(encoding="utf-8"))
    assert {r["outcome"] for r in saved} == {"pending_review"}


def test_menu_runs_summary_then_exits(tmp_path, monkeypatch, capsys):
    app = build_app(tmp_path)
    answers = iter(["2", "7"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    app.run()
    assert "No incidents logged yet." in capsys.readouterr().out


def test_failed_save_is_reported(tmp_path, monkeypatch, capsys):
    app = build_app(tmp_path)
    monkeypatch.setattr(DataManager, "save_record", lambda self, incident: False)
    app.process_incident(Incident("Worker slipped on wet floor", "Site A", "x", True), interactive=False)
    assert "could not save this incident" in capsys.readouterr().out


# Edit, undo and re-analyse
LOW_RISK = {**HAZARD_REPLY, "hazard_category": "other", "injury_treatment": "none",
            "elevated_places": [], "ppe_status": "worn"}


def logged_app(tmp_path, gemini=None):
    app = build_app(tmp_path, gemini)
    app.process_incident(Incident("Worker slipped on a wet floor in the canteen", "Site A", "officer", False,
                                  "2026-10-21T10:00:00"), interactive=False)
    return app


def test_edit_saves_a_new_version_and_keeps_the_old_one(tmp_path):
    gemini = FakeGemini(replies={id(HazardFlagStep.SCHEMA): LOW_RISK})
    app = logged_app(tmp_path, gemini)
    assert app.records[0].get("outcome") == "log_only" and app.records[0].version == 1
    gemini.replies[id(HazardFlagStep.SCHEMA)] = HAZARD_REPLY
    result = app.edit_incident(0, {"description": "Worker fell from the level 4 scaffold edge", "injury": True})
    assert result.status == "updated"
    now = DataManager(str(tmp_path)).load_records()
    assert len(now) == 1 and now[0].version == 2 and now[0].get("outcome") == "stop_work_review"
    assert now[0].history[0]["version"] == 1 and now[0].history[0]["outcome"] == "log_only"
    assert result.previous.get("outcome") == "log_only"
    assert now[0].timestamp == "2026-10-21T10:00:00"


def test_text_only_edit_renames_without_running_the_ai(tmp_path):
    gemini = FakeGemini()
    app = logged_app(tmp_path, gemini)
    calls = len(gemini.calls)
    outcome = app.records[0].get("outcome")
    result = app.edit_incident_text(0, {"location": "Site A level 2", "injury": False})
    assert result.status == "updated" and len(gemini.calls) == calls
    now = DataManager(str(tmp_path)).load_records()[0]
    assert now.location == "Site A level 2" and now.version == 2 and now.get("outcome") == outcome
    assert now.history[0]["location"] == "Site A"
    assert app.edit_incident_text(0, {"location": "Site A level 2"}).status == "unchanged"
    assert app.edit_incident_text(0, {"injury": True}).status == "failed"


def test_edit_with_nothing_changed_skips_the_ai(tmp_path):
    gemini = FakeGemini()
    app = logged_app(tmp_path, gemini)
    calls = len(gemini.calls)
    result = app.edit_incident(0, {"description": "Worker slipped on a wet floor in the canteen"})
    assert result.status == "unchanged" and len(gemini.calls) == calls and app.records[0].version == 1


def test_edit_keeps_the_old_version_when_the_ai_fails(tmp_path):
    gemini = FakeGemini()
    app = logged_app(tmp_path, gemini)
    old = app.records[0].to_dict()
    gemini.error = RuntimeError("quota exceeded")
    result = app.edit_incident(0, {"location": "Site Z"})
    assert result.status == "failed"
    assert DataManager(str(tmp_path)).load_records()[0].to_dict() == old


def test_edit_rejected_by_the_ai_keeps_the_old_version(tmp_path):
    gemini = FakeGemini()
    app = logged_app(tmp_path, gemini)
    gemini.replies[id(HazardFlagStep.SCHEMA)] = {**HAZARD_REPLY, "is_valid_incident": False,
                                                 "invalid_reason": "Test text."}
    result = app.edit_incident(0, {"description": "testing testing hello there"})
    assert result.status == "rejected" and result.message == "Test text."
    assert app.records[0].version == 1


def test_edited_incident_is_not_counted_as_a_repeat_at_its_location(tmp_path):
    app = build_app(tmp_path, FakeGemini(replies={id(HazardFlagStep.SCHEMA): LOW_RISK}))
    for n in range(3):
        app.process_incident(Incident(f"Worker slipped on wet floor number {n}", "Site A", "officer", False,
                                      f"2026-10-2{n + 1}T10:00:00"), interactive=False)
    # Three earlier incidents at Site A would normally make a fourth one a systemic escalation.
    assert app.records[2].get("outcome") == "log_only"  # only two others when it was logged
    result = app.edit_incident(2, {"description": "Worker slipped on a wet floor again"})
    assert result.status == "updated" and result.incident.get("outcome") == "log_only"


def test_edit_photo_add_keep_and_remove(tmp_path):
    app = logged_app(tmp_path)
    result = app.edit_incident(0, {}, IncidentPhoto.from_file(SAMPLE_PHOTO))
    assert result.status == "updated" and result.incident.get("photo_analysed") is True
    assert os.path.exists(result.incident.get("photo_saved_path"))
    # Changing only the text keeps the photo and analyses it again from the saved copy.
    result = app.edit_incident(0, {"location": "Site B"})
    assert result.incident.get("photo_file") == "sample_photo.png" and result.incident.get("photo_analysed") is True
    assert app.edit_incident(0, {}, IncidentPhoto.from_file(SAMPLE_PHOTO)).status == "unchanged"
    result = app.edit_incident(0, {}, None)
    assert result.status == "updated" and not result.incident.get("photo_file") and result.incident.version == 4


def test_revert_copies_an_old_version_in_as_the_newest(tmp_path):
    gemini = FakeGemini(replies={id(HazardFlagStep.SCHEMA): LOW_RISK})
    app = logged_app(tmp_path, gemini)
    gemini.replies[id(HazardFlagStep.SCHEMA)] = HAZARD_REPLY
    app.edit_incident(0, {"injury": True})
    result = app.revert_incident(0, 1)
    now = DataManager(str(tmp_path)).load_records()[0]
    assert result.status == "updated" and now.version == 3 and now.get("reverted_from") == 1
    assert now.description == "Worker slipped on a wet floor in the canteen" and now.get("outcome") == "log_only"
    assert [v["version"] for v in now.history] == [1, 2]
    assert app.revert_incident(0, 9).status == "failed"


def test_edit_menu_edits_and_shows_the_old_and_new_insight(tmp_path, monkeypatch, capsys):
    gemini = FakeGemini(replies={id(HazardFlagStep.SCHEMA): LOW_RISK})
    app = logged_app(tmp_path, gemini)
    gemini.replies[id(HazardFlagStep.SCHEMA)] = HAZARD_REPLY
    # pick incident 1, edit, change answer 4 (injury) to yes, keep the photo, send, then go back out.
    answers = iter(["1", "1", "edit", "4", "yes", "send", "", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    app.edit_saved_incident()
    out = capsys.readouterr().out
    assert "WHAT CHANGED" in out and "LOG ONLY -> STOP WORK" in out and "(was: No)" in out
    assert app.records[0].version == 2


# --- Storage choice: the app must start for an assessor who has no database ---

def _database_down(url):
    raise DatabaseUnavailable("could not open the database (PoolTimeout)")


def test_without_a_database_url_the_app_keeps_incidents_in_local_files():
    data, notice = IncidentTriageApp.open_storage(None)
    assert not data.uses_database and "local files" in notice


def test_with_a_database_that_opens_there_is_nothing_to_tell_the_user(tmp_path):
    data, notice = IncidentTriageApp.open_storage(str(tmp_path / "triage.db"))
    assert data.uses_database and notice is None


def test_a_database_that_is_down_falls_back_to_local_files_and_hides_the_password(monkeypatch):
    monkeypatch.setattr("main.Database", _database_down)
    data, notice = IncidentTriageApp.open_storage("postgresql://user:secret@host/db")
    assert not data.uses_database and "PoolTimeout" in notice and "secret" not in notice


def test_create_still_starts_when_the_database_is_down_and_says_so(monkeypatch, capsys):
    monkeypatch.setattr("main.load_dotenv", lambda: None)  # never read the real .env
    monkeypatch.setattr("main.Database", _database_down)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@host/db")
    app = IncidentTriageApp.create()
    app.start_up()
    out = capsys.readouterr().out
    assert "Warning: could not open the database" in out and "Loaded 0 saved incident(s)." in out


def test_command_line_batch_runs_with_no_database_url_and_no_keys(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("main.load_dotenv", lambda: None)  # never read the real .env
    shutil.copy(os.path.join(TESTS, "sample_batch.json"), tmp_path / "batch.json")
    shutil.copy(SAMPLE_PHOTO, tmp_path / "sample_photo.png")
    assert IncidentTriageApp.cli(["--batch", str(tmp_path / "batch.json")]) == 0
    out = capsys.readouterr().out
    assert "DATABASE_URL is not set" in out and "Total incidents: 3" in out and "INCIDENT SUMMARY" in out
