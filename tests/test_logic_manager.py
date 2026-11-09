import logic_manager as lm
from tests._suite import suite_from


def test_severity_and_outcome_constants_fit_together():
    assert sorted(lm.SEVERITY_LEVELS) == list(range(1, lm.MAX_SEVERITY + 1))
    for name, description in lm.SEVERITY_LEVELS.values():
        assert name and description
    assert 1 < lm.INJURY_MIN_SEVERITY < lm.HIGH_SEVERITY <= lm.MAX_SEVERITY
    assert lm.SYSTEMIC_INCIDENT_COUNT >= 1
    assert set(lm.OUTCOME_ACTIONS) == {"stop_work_review", "systemic_escalation", "log_only", "pending_review"}
    assert all(action for action in lm.OUTCOME_ACTIONS.values())


def test_scoring_tables_fit_together():
    # Every treatment that adds points has a label for its reason, and "died" is handled separately.
    for treatment, points in lm._INJURY_POINTS.items():
        assert points >= 0
        assert (treatment in lm._INJURY_LABELS) == (points > 0), treatment
    assert "died" not in lm._INJURY_POINTS
    assert set(lm._ESCALATED_OUTCOMES) <= set(lm.OUTCOME_ACTIONS)
    assert set(lm._POOR_LIGHT_LEVELS) == {"low_light", "dark"}
    assert lm._TYPE_A_HAZARDS and all(isinstance(hazard, str) for hazard in lm._TYPE_A_HAZARDS)


def test_weather_relevance_is_whole_word():
    for text in ("Worker slipped on wet floor", "Heavy RAIN all morning", "It was windy on the roof",
                 "flooding in the basement", "Lightning struck the crane"):
        assert lm.is_weather_relevant({"description": text}), text
    for text in ("Hit by a window frame", "Trainee injured at the constraint review",
                 "Shot-blasting dust", "Freshly mopped floor", "Photo taken", "Sweet drink spilled"):
        assert not lm.is_weather_relevant({"description": text}), text
    assert not lm.is_weather_relevant({})


def test_time_of_day_season_and_lighting():
    assert lm.get_time_of_day("2026-09-27T12:00:00") == "day"
    assert lm.get_time_of_day("2026-09-27T18:30:00") == "dusk_dawn"
    assert lm.get_time_of_day("2026-09-27T23:00:00") == "night"
    assert lm.get_time_of_day("garbage") == "day" and lm.get_time_of_day(None) == "day"
    assert lm.get_monsoon_season("2026-01-10T00:00:00") == "northeast_monsoon"
    assert lm.get_monsoon_season("2026-07-10T00:00:00") == "southwest_monsoon"
    assert lm.get_monsoon_season("2026-11-10T00:00:00") == "inter_monsoon"
    assert lm.get_monsoon_season("garbage") == "inter_monsoon"
    assert lm.get_monsoon_season(None) == "inter_monsoon"
    assert lm.classify_lighting_condition("day", "clear") == "daylight"


def test_monsoon_season_boundaries():
    # Northeast: December to mid-March; southwest: June to September; anything else is inter-monsoon.
    for date, season in (("2026-12-01", "northeast_monsoon"), ("2026-03-15", "northeast_monsoon"),
                         ("2026-03-16", "inter_monsoon"), ("2026-05-31", "inter_monsoon"),
                         ("2026-06-01", "southwest_monsoon"), ("2026-09-30", "southwest_monsoon"),
                         ("2026-10-01", "inter_monsoon"), ("2026-11-30", "inter_monsoon")):
        assert lm.get_monsoon_season(date + "T12:00:00") == season, date


def test_injury_score_starts_from_what_happened_to_the_person():
    assert lm._score_injury({"injury_treatment": "died"}) == (5, ["Someone died (set to 5)"])
    assert lm._score_injury({"injury_treatment": "first_aid"}) == (2, ["Minor injury, first aid only (+1)"])
    assert lm._score_injury({"injury_treatment": "hospital"}) == (3, ["Serious injury, hospital treatment (+2)"])
    hurt_not_described = (2, ["Someone was hurt, but how badly wasn't described (+1)"])
    assert lm._score_injury({"injury": True, "injury_treatment": "unspecified"}) == hurt_not_described
    assert lm._score_injury({"injury": True}) == hurt_not_described  # missing treatment counts as unspecified
    for nobody_hurt in ({"injury": False, "injury_treatment": "none"}, {}, {"injury_treatment": "banana"}):
        assert lm._score_injury(nobody_hurt) == (1, []), nobody_hurt


def test_condition_points_each_come_with_a_reason():
    assert lm._score_conditions({}, False) == (0, [])
    assert lm._score_conditions({"ppe_status": "worn"}, False) == (-1, ["Safety gear (PPE) was worn (-1)"])
    assert lm._score_conditions({"hazard_category": "vehicular"}, False) == (
        1, ["One of MOM's highest-risk hazard types (+1)"])
    # Machinery without safety gear counts twice: once for the pair, once for the missing PPE.
    change, reasons = lm._score_conditions({"heavy_machinery_present": True, "ppe_status": "not_worn"}, False)
    assert change == 2 and len(reasons) == 2
    # Rain is read from the incident itself, and only counts with height or machinery.
    change, reasons = lm._score_conditions({"working_at_height": True, "condition": "rain"}, False)
    assert change == 2 and "Raining during work at height or with machinery (+1)" in reasons
    assert lm._score_conditions({"condition": "rain"}, False) == (0, [])
    assert lm._score_conditions({}, True) == (1, ["A similar past incident on our sites was escalated (+1)"])
    change, reasons = lm._score_conditions({"lighting_condition": "dark"}, False)
    assert change == 1 and all(reason.endswith(")") for reason in reasons)


def test_rain_on_the_record_adds_a_point_at_height():
    # Reference scoring case: "rain during work at height adds a point on top of the height point".
    calm = {"hazard_category": "other", "injury_treatment": "none", "working_at_height": True,
            "heavy_machinery_present": False, "ppe_status": "unspecified", "lighting_condition": "daylight",
            "similar_incidents": None, "context_flags_error": None, "injury": False, "condition": "rain"}
    result = lm.assess_severity(calm, None, [])
    assert result["severity_estimate"] == 3 and result["likelihood_recurrence"] == "low"
    assert lm.decide_outcome(result, []) == "log_only"
    assert lm.classify_lighting_condition("day", "rain") == "low_light"
    assert lm.classify_lighting_condition("night", "rain") == "dark"


def test_derive_context_and_apply_lighting():
    ctx = lm.derive_context({"description": "wet floor", "timestamp": "2026-09-27T20:44:10"})
    assert ctx["weather_relevant"] is True and ctx["time_of_day"] == "night"
    assert ctx["monsoon_season"] == "southwest_monsoon"
    lit = lm.apply_lighting({**ctx, "condition": "rain"})
    assert lit["lighting_condition"] == "dark"
    assert "lighting_condition" not in ctx

def test_apply_weather_turns_rainfall_into_a_condition():
    assert lm.apply_weather({"precipitation_mm": 0.3})["condition"] == "rain"
    assert lm.apply_weather({"precipitation_mm": 0})["condition"] == "clear"
    assert lm.apply_weather({"condition": None})["condition"] is None
    assert lm.apply_weather({"condition": "rain"})["condition"] == "rain"


def test_apply_lighting_copes_with_missing_or_unknown_values():
    assert lm.apply_lighting({})["lighting_condition"] == "daylight"
    assert lm.apply_lighting({"time_of_day": None, "condition": None})["lighting_condition"] == "daylight"
    assert lm.apply_lighting({"time_of_day": "midnight", "condition": "fog"})["lighting_condition"] == "daylight"
    assert lm.apply_lighting({"time_of_day": "dusk_dawn", "condition": "rain"})["lighting_condition"] == "dark"

def _enriched(**changes):
    base = {"hazard_category": "fall_from_height", "injury_treatment": "hospital", "injury": True,
            "working_at_height": True, "heavy_machinery_present": False, "ppe_status": "not_worn",
            "lighting_condition": "dark", "similar_incidents": None, "context_flags_error": None}
    base.update(changes)
    return base

def test_severity_and_outcome_rules():
    worst = lm.assess_severity(_enriched(injury_treatment="died"), {}, [])
    assert worst["severity_estimate"] == 5 and lm.decide_outcome(worst, []) == "stop_work_review"
    mild = lm.assess_severity(_enriched(hazard_category="fall", injury_treatment="none", injury=False,
                                         working_at_height=False, ppe_status="worn",
                                         lighting_condition="daylight"), {}, [])
    assert mild["severity_estimate"] == 1 and lm.decide_outcome(mild, []) == "log_only"
    three = [{"outcome": "log_only"}] * 3
    assert lm.decide_outcome(mild, three) == "systemic_escalation"


def test_any_injury_scores_at_least_the_injury_minimum():
    calm = dict(hazard_category="fall", working_at_height=False, ppe_status="worn", lighting_condition="daylight")
    for injury, treatment in ((True, "unspecified"), (True, "none"), (False, "first_aid"), (False, "hospital")):
        result = lm.assess_severity(_enriched(**calm, injury=injury, injury_treatment=treatment), {}, [])
        assert result["severity_estimate"] == lm.INJURY_MIN_SEVERITY, (injury, treatment)
        assert f"Someone was injured, so severity is at least {lm.INJURY_MIN_SEVERITY}" in result["severity_reasons"]
    uninjured = lm.assess_severity(_enriched(**calm, injury=False, injury_treatment="none"), {}, [])
    assert uninjured["severity_estimate"] == 1
    assert not any("at least" in reason for reason in uninjured["severity_reasons"])


def test_multi_condition_rule_uses_ai_fields():
    record = {"severity_estimate": 2, "injury": True, "likelihood_recurrence": "high"}
    assert lm.is_high_severity(record)
    assert not lm.is_high_severity({**record, "injury": False})
    assert not lm.is_high_severity({**record, "likelihood_recurrence": "low"})


def test_failed_ai_extraction_routes_to_manual_review():
    result = lm.assess_severity(_enriched(hazard_category=None, context_flags_error="down"), {}, [])
    assert result["assessment_error"] and result["severity_estimate"] == 0
    assert lm.decide_outcome(result, []) == "pending_review"


def test_apply_hazard_rules_decides_height_and_machinery_from_the_ais_lists():
    both = lm.apply_hazard_rules({"equipment_mentioned": ["Tower Crane", "hammer"],
                                  "elevated_places": ["roof"]})
    assert both["working_at_height"] is True and both["heavy_machinery_present"] is True
    for name in ("excavator", "forklift", "generator", "conveyor belt", "dump truck", "piling rig",
                 "scissor lift", "concrete pump", "bobcat", "dumper", "pile driver", "telehandler",
                 "skid steer", "road roller", "mobile crane"):
        assert lm.apply_hazard_rules({"equipment_mentioned": [name]})["heavy_machinery_present"], name
    light = lm.apply_hazard_rules({"equipment_mentioned": ["hammer", "ladder", "drill", "paint roller",
                                                           "lifting sling", "angle grinder"],
                                   "elevated_places": []})
    assert light["working_at_height"] is False and light["heavy_machinery_present"] is False
    for odd in (None, "crane", [None, 5, " "], {}):
        result = lm.apply_hazard_rules({"equipment_mentioned": odd, "elevated_places": odd})
        assert result["working_at_height"] is False and result["heavy_machinery_present"] is False, odd
    source = {"equipment_mentioned": ["crane"]}
    lm.apply_hazard_rules(source)
    assert "heavy_machinery_present" not in source

def test_screen_incident_decides_accept_or_reject_from_the_ai_flag():
    rejected = lm.screen_incident({"is_valid_incident": False, "invalid_reason": " It is random text. "})
    assert rejected == {"accepted": False, "reject_reason": "It is random text."}
    no_reason = lm.screen_incident({"is_valid_incident": False, "invalid_reason": None})
    assert not no_reason["accepted"] and "workplace safety incident" in no_reason["reject_reason"]
    for record in ({"is_valid_incident": True}, {"is_valid_incident": None}, {}, None, "x"):
        assert lm.screen_incident(record) == {"accepted": True, "reject_reason": None}, record

def load_tests(loader, tests, pattern):
    return suite_from(globals())