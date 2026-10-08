"""logic_manager: context rules moved from ai_manager, plus severity/outcome."""

import logic_manager as lm
from tests._suite import suite_from


def test_weather_relevance_is_whole_word():
    for text in ("Worker slipped on wet floor", "Heavy RAIN all morning", "It was windy on the roof",
                 "flooding in the basement", "Lightning struck the crane"):
        assert lm.is_weather_relevant({"description": text}), text
    for text in ("Hit by a window frame", "Trainee injured at the constraint review",
                 "Shot-blasting dust", "Freshly mopped floor", "Photo taken", "Sweet drink spilled"):
        assert not lm.is_weather_relevant({"description": text}), text
    assert not lm.is_weather_relevant({})


def test_time_of_day_and_season_and_lighting():
    assert lm.get_time_of_day("2026-09-27T12:00:00") == "day"
    assert lm.get_time_of_day("2026-09-27T18:30:00") == "dusk_dawn"
    assert lm.get_time_of_day("2026-09-27T23:00:00") == "night"
    assert lm.get_time_of_day("garbage") == "day" and lm.get_time_of_day(None) == "day"
    assert lm.get_monsoon_season("2026-01-10T00:00:00") == "northeast_monsoon"
    assert lm.get_monsoon_season("2026-07-10T00:00:00") == "southwest_monsoon"
    assert lm.get_monsoon_season("2026-11-10T00:00:00") == "inter_monsoon"
    assert lm.get_monsoon_season("garbage") == "inter_monsoon"  # never depends on today's date
    assert lm.classify_lighting_condition("day", "clear") == "daylight"
    assert lm.classify_lighting_condition("day", "rain") == "low_light"
    assert lm.classify_lighting_condition("night", "rain") == "dark"


def test_derive_context_and_apply_lighting():
    ctx = lm.derive_context({"description": "wet floor", "timestamp": "2026-09-27T20:44:10"})
    assert ctx["weather_relevant"] is True and ctx["time_of_day"] == "night"
    assert ctx["monsoon_season"] == "southwest_monsoon"
    lit = lm.apply_lighting({**ctx, "condition": "rain"})
    assert lit["lighting_condition"] == "dark"
    assert "lighting_condition" not in ctx


def _enriched(**changes):
    base = {"hazard_category": "fall_from_height", "injury_severity": "serious", "injury": True,
            "working_at_height": True, "heavy_machinery_present": False, "ppe_status": "not_worn",
            "lighting_condition": "dark", "similar_incidents": None, "context_flags_error": None}
    base.update(changes)
    return base


def test_severity_and_outcome_rules():
    worst = lm.assess_severity(_enriched(injury_severity="fatal"), {}, [])
    assert worst["severity_estimate"] == 5 and lm.decide_outcome(worst, []) == "stop_work_review"
    mild = lm.assess_severity(_enriched(hazard_category="fall", injury_severity="none", injury=False,
                                         working_at_height=False, ppe_status="worn",
                                         lighting_condition="daylight"), {}, [])
    assert mild["severity_estimate"] == 1 and lm.decide_outcome(mild, []) == "log_only"
    three = [{"outcome": "log_only"}] * 3
    assert lm.decide_outcome(mild, three) == "systemic_escalation"


def test_multi_condition_rule_uses_ai_fields():
    record = {"severity_estimate": 2, "injury": True, "likelihood_recurrence": "high"}
    assert lm.is_high_severity(record)
    assert not lm.is_high_severity({**record, "injury": False})
    assert not lm.is_high_severity({**record, "likelihood_recurrence": "low"})


def test_failed_ai_extraction_routes_to_manual_review():
    result = lm.assess_severity(_enriched(hazard_category=None, context_flags_error="down"), {}, [])
    assert result["assessment_error"] and result["severity_estimate"] == 0
    assert lm.decide_outcome(result, []) == "pending_review"


def load_tests(loader, tests, pattern):
    return suite_from(globals())