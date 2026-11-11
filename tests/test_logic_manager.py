import logic_manager as lm
from logic_rules import constants
from tests._suite import suite_from


def test_severity_and_outcome_constants_fit_together():
    assert sorted(constants.SEVERITY_LEVELS) == list(range(1, constants.MAX_SEVERITY + 1))
    for name, description in constants.SEVERITY_LEVELS.values():
        assert name and description
    assert 1 < constants.INJURY_MIN_SEVERITY < constants.HIGH_SEVERITY <= constants.MAX_SEVERITY
    assert constants.SYSTEMIC_INCIDENT_COUNT >= 1
    assert set(constants.OUTCOME_ACTIONS) == {"stop_work_review", "photo_review", "systemic_escalation", "log_only",
                                              "pending_review"}
    assert all(action for action in constants.OUTCOME_ACTIONS.values())


# The constants live in logic_rules/constants.py; logic_manager and main.py use those same objects.
def test_logic_manager_uses_the_logic_rules_constants():
    assert lm.SEVERITY_LEVELS is constants.SEVERITY_LEVELS and lm.OUTCOME_ACTIONS is constants.OUTCOME_ACTIONS
    assert (lm.MAX_SEVERITY, lm.INJURY_MIN_SEVERITY, lm.HIGH_SEVERITY, lm.SYSTEMIC_INCIDENT_COUNT) == (
        constants.MAX_SEVERITY, constants.INJURY_MIN_SEVERITY, constants.HIGH_SEVERITY,
        constants.SYSTEMIC_INCIDENT_COUNT)


def test_scoring_tables_fit_together():
    # Every treatment that adds points has a label for its reason, and "died" is handled separately.
    for treatment, points in lm._INJURY_POINTS.items():
        assert points >= 0
        assert (treatment in lm._INJURY_LABELS) == (points > 0), treatment
    assert "died" not in lm._INJURY_POINTS
    assert set(lm._ESCALATED_OUTCOMES) <= set(constants.OUTCOME_ACTIONS)
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
    assert lm.classify_lighting_condition("day", "rain") == "low_light"
    assert lm.classify_lighting_condition("night", "rain") == "dark"


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


def test_recurrence_level_tiers():
    calm = {"lighting_condition": "daylight"}
    assert lm._recurrence_level(1, calm, [], False) == "low"
    # Medium: poor lighting, or at least one earlier incident at this place.
    assert lm._recurrence_level(1, {"lighting_condition": "low_light"}, [], False) == "medium"
    assert lm._recurrence_level(1, {"lighting_condition": "dark"}, [], False) == "medium"
    assert lm._recurrence_level(1, calm, [{}], False) == "medium"
    # High: severity at the stop-work level, the systemic number of earlier incidents, or an escalated look-alike.
    assert lm._recurrence_level(lm.HIGH_SEVERITY, calm, [], False) == "high"
    assert lm._recurrence_level(1, calm, [{}] * lm.SYSTEMIC_INCIDENT_COUNT, False) == "high"
    assert lm._recurrence_level(1, calm, [], True) == "high"
    # High beats medium when both apply.
    assert lm._recurrence_level(lm.HIGH_SEVERITY, {"lighting_condition": "dark"}, [{}], False) == "high"
    assert lm._recurrence_level(lm.HIGH_SEVERITY - 1, {}, [], False) == "low"


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

def test_worst_case_scores_5_and_stops_work():
    incident = lm.assess_severity(_enriched(injury_treatment="died"), None, [])
    assert incident["severity_estimate"] == 5
    assert lm.decide_outcome(incident, []) == "stop_work_review"


def test_mild_case_logs_only_and_three_earlier_incidents_escalate():
    incident = lm.assess_severity(_enriched(injury=False, hazard_category="fall", injury_treatment="none",
                                            working_at_height=False, ppe_status="worn",
                                            lighting_condition="daylight"), None, [])
    assert incident["severity_estimate"] == 1
    assert lm.decide_outcome(incident, []) == "log_only"
    assert lm.decide_outcome(incident, [{}] * 3) == "systemic_escalation"


def test_anyone_injured_scores_at_least_3():
    safe_but_hurt = {"hazard_category": "fall", "injury_treatment": "first_aid", "working_at_height": False,
                     "ppe_status": "worn", "lighting_condition": "daylight"}
    for treatment in ("first_aid", "none", "unspecified"):
        incident = lm.assess_severity(_enriched(injury=True, **{**safe_but_hurt, "injury_treatment": treatment}),
                                      None, [])
        assert incident["severity_estimate"] == 3
        assert any("injured" in r for r in incident["severity_reasons"])
    uninjured = lm.assess_severity(_enriched(injury=False, **{**safe_but_hurt, "injury_treatment": "none"}),
                                   None, [])
    assert uninjured["severity_estimate"] == 1


# --- Hard-coded sample AI replies -> severity, recurrence and outcome (no live API) ---

# A quiet, fully specified reply; each case below changes only the fields it is about.
CALM_AI_REPLY = {"hazard_category": "other", "injury_treatment": "none", "working_at_height": False,
                 "heavy_machinery_present": False, "ppe_status": "unspecified", "lighting_condition": "daylight",
                 "similar_incidents": None, "context_flags_error": None}

# (name, what the AI said, was anyone hurt, earlier incidents at this place, severity, recurrence, outcome)
SCORING_CASES = [
    ("near miss with PPE worn stays at the floor of 1",
     {"ppe_status": "worn"}, False, 0, 1, "low", "log_only"),
    ("first aid only still scores the injury floor of 3",
     {"injury_treatment": "first_aid"}, True, 0, 3, "low", "log_only"),
    ("hospital treatment is moderate",
     {"injury_treatment": "hospital"}, True, 0, 3, "low", "log_only"),
    ("hurt but not described is lifted to the injury floor of 3",
     {"injury_treatment": "unspecified"}, True, 0, 3, "low", "log_only"),
    ("a MOM Type A hazard with a hospital injury is high and stops work",
     {"injury_treatment": "hospital", "hazard_category": "vehicular"}, True, 0, 4, "high", "stop_work_review"),
    ("darkness makes a minor injury moderate and the repeat risk medium",
     {"injury_treatment": "first_aid", "lighting_condition": "dark"}, True, 0, 3, "medium", "log_only"),
    ("rain during work at height adds a point on top of the height point",
     {"working_at_height": True, "condition": "rain"}, False, 0, 3, "low", "log_only"),
    ("machinery with no safety gear counts twice",
     {"heavy_machinery_present": True, "ppe_status": "not_worn"}, False, 0, 3, "low", "log_only"),
    ("a fatality is always 5",
     {"injury_treatment": "died"}, True, 0, 5, "high", "stop_work_review"),
    ("every factor at once is capped at 5",
     {"injury_treatment": "hospital", "hazard_category": "fall_from_height", "working_at_height": True,
      "ppe_status": "not_worn", "lighting_condition": "dark"}, True, 0, 5, "high", "stop_work_review"),
    ("a similar past incident that was escalated raises recurrence to high",
     {"similar_incidents": [{"outcome": "stop_work_review"}]}, False, 0, 2, "high", "log_only"),
    ("a similar past incident that was only logged changes nothing",
     {"similar_incidents": [{"outcome": "log_only"}]}, False, 0, 1, "low", "log_only"),
    ("Rule 1, second branch: injury plus high recurrence stops work even at severity 3",
     {"injury_treatment": "first_aid"}, True, 3, 3, "high", "stop_work_review"),
    ("Rule 2: three earlier incidents and nobody hurt escalates to management",
     {}, False, 3, 1, "high", "systemic_escalation"),
    ("an AI value outside the known list is ignored, but the injury floor still applies",
     {"injury_treatment": "banana"}, True, 0, 3, "low", "log_only"),
]


def test_sample_ai_reply_gives_the_expected_severity_recurrence_and_outcome():
    for name, ai_reply, injured, earlier, severity, recurrence, outcome in SCORING_CASES:
        history = [{}] * earlier
        incident = lm.assess_severity({**CALM_AI_REPLY, **ai_reply, "injury": injured}, None, history)
        assert incident["severity_estimate"] == severity, name
        assert incident["likelihood_recurrence"] == recurrence, name
        assert incident["assessment_error"] is None and incident["severity_reasons"] is not None, name
        assert lm.decide_outcome(incident, history) == outcome, name


def test_every_severity_reason_is_listed_so_the_score_can_be_explained():
    incident = lm.assess_severity({**CALM_AI_REPLY, "injury": True, "injury_treatment": "hospital",
                                   "hazard_category": "vehicular", "ppe_status": "not_worn"}, None, [])
    reasons = incident["severity_reasons"]
    assert any("hospital" in r.lower() for r in reasons) and any("highest-risk" in r for r in reasons)
    assert any("not worn" in r for r in reasons) and all(r.endswith(")") for r in reasons)


def test_a_missing_hazard_category_is_never_scored_as_if_it_were_safe():
    incident = lm.assess_severity({**CALM_AI_REPLY, "injury": True, "hazard_category": None}, None, [])
    assert incident["severity_estimate"] == 0 and incident["likelihood_recurrence"] == "unknown"
    assert "hazard_category missing" in incident["assessment_error"]


def test_multi_condition_rule_uses_ai_fields():
    record = {"severity_estimate": 2, "injury": True, "likelihood_recurrence": "high"}
    assert lm.is_high_severity(record)
    assert not lm.is_high_severity({**record, "injury": False})
    assert not lm.is_high_severity({**record, "likelihood_recurrence": "low"})


def test_failed_ai_extraction_routes_to_manual_review():
    incident = lm.assess_severity(_enriched(hazard_category=None, context_flags_error="AI down"), None, [])
    assert incident["assessment_error"] and incident["severity_estimate"] == 0
    assert lm.decide_outcome(incident, []) == "pending_review"


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