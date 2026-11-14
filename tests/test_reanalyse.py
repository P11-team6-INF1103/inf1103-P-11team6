from ai_clients.response_cache import ResponseCache
from ai_manager import AIManager
from ai_steps.hazard_flag_step import HazardFlagStep
from data_manager import DataManager
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from models.incident import Incident
from tests.fakes import HAZARD_REPLY, FakeGemini, FakeSearch, FakeWeather

LOW_RISK = {**HAZARD_REPLY, "hazard_category": "other", "injury_treatment": "none",
            "elevated_places": [], "ppe_status": "worn"}
HAZARD = id(HazardFlagStep.SCHEMA)
TEXT = "Worker slipped on a wet floor in the canteen"


class CachingGemini(FakeGemini):
    # A FakeGemini that reads and writes the cache the way the real GeminiClient does, to count real AI calls.
    def __init__(self, cache: ResponseCache, replies: dict | None = None) -> None:
        super().__init__(replies)
        self.cache = cache
        self.real_calls = 0

    def ask_json(self, prompt, schema, photo=None, subject=None):
        key = ResponseCache.make_key("fake", prompt)
        cached = self.cache.lookup(key)
        if cached is not None:
            return cached
        self.real_calls += 1
        reply = super().ask_json(prompt, schema, photo, subject)
        self.cache.remember(key, reply)
        return reply


def build(tmp_path, gemini=None, cache=None):
    cache = cache or ResponseCache()
    ai = AIManager(gemini or FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                            LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path)), cache)
    app.process_incident(Incident(TEXT, "Site A", "officer", False, "2026-10-21T10:00:00"), interactive=False)
    return app


def test_reanalyse_runs_the_ai_again_with_no_change_and_keeps_the_old_version(tmp_path):
    gemini = FakeGemini(replies={HAZARD: LOW_RISK})
    app = build(tmp_path, gemini)
    assert app.records[0].get("outcome") == "log_only"
    calls = len(gemini.calls)
    gemini.replies[HAZARD] = HAZARD_REPLY  # the AI now sees it differently
    result = app.reanalyse_incident(0)
    assert result.status == "updated" and len(gemini.calls) > calls
    now = DataManager(str(tmp_path)).load_records()
    assert len(now) == 1 and now[0].version == 2 and now[0].get("reanalysed") is True
    assert now[0].get("outcome") == "stop_work_review" and now[0].history[0]["outcome"] == "log_only"
    assert result.previous.get("outcome") == "log_only"
    assert (now[0].description, now[0].location, now[0].timestamp) == (TEXT, "Site A", "2026-10-21T10:00:00")


def test_an_edit_with_nothing_changed_skips_the_ai_but_reanalyse_does_not(tmp_path):
    gemini = FakeGemini()
    app = build(tmp_path, gemini)
    calls = len(gemini.calls)
    assert app.edit_incident(0, {"description": TEXT}).status == "unchanged" and len(gemini.calls) == calls
    assert app.reanalyse_incident(0).status == "updated" and len(gemini.calls) > calls


def test_reanalyse_after_a_wording_only_edit_replaces_the_analysis_that_was_kept(tmp_path):
    gemini = FakeGemini(replies={HAZARD: LOW_RISK})
    app = build(tmp_path, gemini)
    app.edit_incident_text(0, {"description": "Worker fell from the level 4 scaffold edge"})
    assert app.records[0].get("text_only_edit") is True and app.records[0].get("outcome") == "log_only"
    gemini.replies[HAZARD] = HAZARD_REPLY
    result = app.reanalyse_incident(0)
    assert result.status == "updated" and result.incident.version == 3
    assert result.incident.description == "Worker fell from the level 4 scaffold edge"
    assert result.incident.get("outcome") == "stop_work_review" and not result.incident.get("text_only_edit")
    assert [v["version"] for v in result.incident.history] == [1, 2]


def test_reanalyse_skips_the_saved_replies_but_a_normal_run_uses_them(tmp_path):
    cache = ResponseCache()
    gemini = CachingGemini(cache)
    app = build(tmp_path, gemini, cache)
    first = gemini.real_calls
    assert first > 0
    app.edit_incident(0, {"location": "Site Z"})  # same description, so the hazard reply comes from the cache
    asked_by_edit = gemini.real_calls - first
    before = gemini.real_calls
    app.reanalyse_incident(0)
    assert gemini.real_calls - before > asked_by_edit  # every step asked the AI again, none read the cache
    before = gemini.real_calls
    app.edit_incident(0, {"location": "Site Y"})
    assert gemini.real_calls - before == asked_by_edit  # the cache works again after a re-analyse


def test_reanalyse_keeps_the_old_version_when_the_ai_fails(tmp_path):
    gemini = FakeGemini()
    app = build(tmp_path, gemini)
    old = app.records[0].to_dict()
    gemini.error = RuntimeError("quota exceeded")
    result = app.reanalyse_incident(0)
    assert result.status == "failed" and DataManager(str(tmp_path)).load_records()[0].to_dict() == old


def test_reanalyse_keeps_the_old_version_when_the_ai_now_rejects_the_text(tmp_path):
    gemini = FakeGemini()
    app = build(tmp_path, gemini)
    gemini.replies[HAZARD] = {**HAZARD_REPLY, "is_valid_incident": False, "invalid_reason": "Test text."}
    result = app.reanalyse_incident(0)
    assert result.status == "rejected" and result.message == "Test text." and app.records[0].version == 1


def test_reanalyse_of_an_unknown_incident_fails_cleanly(tmp_path):
    app = build(tmp_path)
    assert app.reanalyse_incident(5).status == "failed" and app.reanalyse_incident(-1).status == "failed"


def test_edit_menu_offers_reanalyse_and_shows_the_old_and_new_insight(tmp_path, monkeypatch, capsys):
    gemini = FakeGemini(replies={HAZARD: LOW_RISK})
    app = build(tmp_path, gemini)
    gemini.replies[HAZARD] = HAZARD_REPLY
    answers = iter(["1", "2", "3", ""])  # incident 1, Re-analyse, then the version history, then back
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    app.edit_saved_incident()
    out = capsys.readouterr().out
    assert "Re-analyse: ask the AI again" in out and "WHAT CHANGED" in out and "LOG ONLY -> STOP WORK" in out
    assert app.records[0].version == 2
