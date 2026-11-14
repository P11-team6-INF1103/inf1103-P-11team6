import json
import os
import shutil

import pytest

from io_helpers.input_validator import InputValidator
from io_helpers.report_printer import ReportPrinter
from io_manager import IOManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from models.incident import Incident

SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")


# Daniel
@pytest.fixture
def io():
    return IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS)


def type_answers(monkeypatch, answers):
    replies = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))


# Sufi
def test_validator_rules():
    assert InputValidator.check_description("Worker slipped on a wet floor") is None
    assert "too short" in InputValidator.check_description("fell")
    assert "mostly words" in InputValidator.check_description("1234567890 !!!!")
    assert "repeated" in InputValidator.check_description("aaaa aaaa aaaa")
    assert InputValidator.check_location("Site A - Block 3") is None
    assert InputValidator.check_location("12345") is not None
    assert InputValidator.check_role("site_supervisor") is None
    assert InputValidator.check_role("x") is not None


def test_clean_path_handles_quotes_and_dragged_in_paths():
    assert InputValidator.clean_path(" '/tmp/my photo.png' ") == "/tmp/my photo.png"
    assert InputValidator.clean_path("/tmp/my\\ photo.png") == "/tmp/my photo.png"


# Daniel
def test_incident_input_re_asks_until_valid_and_attaches_photo(monkeypatch, io):
    type_answers(monkeypatch, ["bad", "Worker fell from a ladder at the loading bay", "Site A",
                               "site_supervisor", "maybe", "yes", "/nope/missing.png", SAMPLE_PHOTO, "send"])
    incident = io.get_incident_input()
    assert incident.description == "Worker fell from a ladder at the loading bay" and incident.injury is True
    assert incident.has_photo() and incident.photo.file_name == "sample_photo.png"


def test_photo_can_be_skipped(monkeypatch, io):
    type_answers(monkeypatch, [""])
    assert io.ask_for_photo() is None


def test_enter_twice_goes_back_to_the_menu(monkeypatch, io):
    type_answers(monkeypatch, ["", ""])
    assert io.get_incident_input() is None


def test_menu_rejects_bad_choices_and_ctrl_d_exits(monkeypatch, io):
    type_answers(monkeypatch, ["9", "abc", "2"])
    assert io.get_menu_choice() == "2"

    def closed(prompt=""):
        raise EOFError
    monkeypatch.setattr("builtins.input", closed)
    assert io.get_menu_choice() == "7"


def test_batch_file_validation(tmp_path, io):
    path = tmp_path / "batch.json"
    shutil.copy(SAMPLE_PHOTO, tmp_path / "scene.png")
    path.write_text(json.dumps([
        {"description": "Worker slipped on a wet floor", "location": "Site A", "reporter_role": "supervisor",
         "injury": "yes", "photo_path": "scene.png"},
        {"description": "???", "location": "Site A", "reporter_role": "supervisor", "injury": True},
        {"description": "Crane swung too close to workers", "location": "Site A", "reporter_role": "supervisor",
         "injury": False, "photo_path": "missing.png"},
        "not an object",
    ]), encoding="utf-8")
    incidents, problems = io.read_incident_file(str(path))
    assert len(incidents) == 1 and incidents[0].has_photo() and incidents[0].injury is True
    assert len(problems) == 3 and "photo_path" in problems[1]
    assert io.read_incident_file(str(tmp_path / "nothing.json"))[0] == []


# Darrel
def test_report_shows_photo_section_and_friendly_errors(capsys):
    incident = Incident("Plank fell from scaffold", "Site B", "officer", False, "2026-10-21T21:40:00")
    incident.update({"photo_file": "scene.png", "photo_analysed": True, "photo_summary": "A scaffold.",
                     "photo_hazards_seen": ["no helmet"], "photo_matches_description": False,
                     "photo_evidence_used": ["The photo shows work at height"], "severity_estimate": 4,
                     "outcome": "stop_work_review", "hazard_type": "fall_from_height",
                     "web_search_error": "GROQ_API_KEY is not set"})
    ReportPrinter(SEVERITY_LEVELS, OUTCOME_ACTIONS).print_incident(incident)
    out = capsys.readouterr().out
    assert "WHAT THE PHOTO SHOWS" in out and "does not seem to match" in out
    assert "STOP WORK" in out and "API key looks missing" in out


def test_summary_counts_photos(capsys, io):
    a = Incident("Worker slipped on wet floor", "Site A", "officer", True, "2026-10-20T09:00:00")
    a.update({"outcome": "log_only", "hazard_type": "fall", "severity_estimate": 2, "photo_file": "a.png"})
    b = Incident("Forklift hit cement bags", "Site B", "officer", False, "2026-10-21T09:00:00")
    b.update({"outcome": "pending_review", "hazard_type": "unassessed", "assessment_error": "down"})
    io.display_summary([a, b], interactive=False)
    out = capsys.readouterr().out
    assert "Total incidents: 2" in out and "With a photo: 1" in out and "[photo]" in out


DESCRIPTION = "Worker fell from a ladder at the loading bay"


def test_undo_takes_back_the_last_answer_and_redo_puts_it_back(monkeypatch, io, capsys):
    type_answers(monkeypatch, [DESCRIPTION, "Site A", "/undo", "Site B", "site_supervisor", "/undo", "/redo",
                               "no", "", "send"])
    incident = io.get_incident_input()
    assert incident.location == "Site B" and incident.get("reporter_role") == "site_supervisor"
    assert incident.injury is False
    assert "Undid 'Location'" in capsys.readouterr().out


def test_undo_with_nothing_to_undo_and_redo_with_nothing_to_redo(monkeypatch, io, capsys):
    type_answers(monkeypatch, ["/undo", "/redo", DESCRIPTION, "Site C", "officer", "no", "", "send"])
    assert io.get_incident_input().location == "Site C"
    out = capsys.readouterr().out
    assert "Nothing to undo." in out and "Nothing to redo." in out


def test_review_screen_can_cancel_and_nothing_is_returned(monkeypatch, io, capsys):
    type_answers(monkeypatch, [DESCRIPTION, "Site A", "officer", "yes", "", "cancel"])
    assert io.get_incident_input() is None
    assert "Nothing is sent to the AI or saved until you choose 'send'" in capsys.readouterr().out


def test_review_screen_edit_changes_one_answer(monkeypatch, io):
    type_answers(monkeypatch, [DESCRIPTION, "Site A", "officer", "yes", "", "edit", "2", "Site Z", "send"])
    assert io.get_incident_input().location == "Site Z"


def test_commands_are_ignored_outside_the_incident_form(monkeypatch, io, capsys):
    type_answers(monkeypatch, ["/undo", "yes"])
    assert io._ask_yes_no("Delete? ") is True


def test_edit_form_shows_old_values_and_photo_choices(monkeypatch, io, capsys):
    incident = Incident(DESCRIPTION, "Site A", "officer", False)
    incident.update({"photo_file": "old.png"})
    type_answers(monkeypatch, ["edit", "3", "foreman", "edit", "5", "none", "send"])
    draft = io.get_incident_edit(incident)
    assert draft["fields"]["reporter_role"] == "foreman" and draft["photo"] is None
    out = capsys.readouterr().out
    assert "(was: officer)" in out and "(was: old.png)" in out
