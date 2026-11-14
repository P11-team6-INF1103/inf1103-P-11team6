import pytest

import logic_manager as lm
from logic_manager import LogicManager
from logic_rules import constants
from logic_rules.constants import SYSTEMIC_INCIDENT_COUNT
from logic_rules.log_only_rule import LogOnlyRule
from logic_rules.outcome_rule import OutcomeRule
from logic_rules.pending_review_rule import PendingReviewRule
from logic_rules.photo_mismatch_rule import PhotoMismatchRule
from logic_rules.stop_work_rule import StopWorkRule
from logic_rules.systemic_risk_rule import SystemicRiskRule
from models.incident import Incident
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


def test_scoring_tables_fit_together(logic):
    # Every treatment that adds points has a label for its reason, and "died" is handled separately.
    for treatment, points in logic._INJURY_POINTS.items():
        assert points >= 0
        assert (treatment in logic._INJURY_LABELS) == (points > 0), treatment
    assert "died" not in logic._INJURY_POINTS
    assert set(logic._ESCALATED_OUTCOMES) <= set(constants.OUTCOME_ACTIONS)
    assert set(logic._POOR_LIGHT_LEVELS) == {"low_light", "dark"}
    assert logic._TYPE_A_HAZARDS and all(isinstance(hazard, str) for hazard in logic._TYPE_A_HAZARDS)


def test_weather_relevance_is_whole_word(logic):
    for text in ("Worker slipped on wet floor", "Heavy RAIN all morning", "It was windy on the roof",
                 "flooding in the basement", "Lightning struck the crane"):
        assert logic.is_weather_relevant({"description": text}), text
    for text in ("Hit by a window frame", "Trainee injured at the constraint review",
                 "Shot-blasting dust", "Freshly mopped floor", "Photo taken", "Sweet drink spilled"):
        assert not logic.is_weather_relevant({"description": text}), text
    assert not logic.is_weather_relevant({})


def test_time_of_day_season_and_lighting(logic):
    assert logic.get_time_of_day("2026-09-27T12:00:00") == "day"
    assert logic.get_time_of_day("2026-09-27T18:30:00") == "dusk_dawn"
    assert logic.get_time_of_day("2026-09-27T23:00:00") == "night"
    assert logic.get_time_of_day("garbage") == "day" and logic.get_time_of_day(None) == "day"
    assert logic.get_monsoon_season("2026-01-10T00:00:00") == "northeast_monsoon"
    assert logic.get_monsoon_season("2026-07-10T00:00:00") == "southwest_monsoon"
    assert logic.get_monsoon_season("2026-11-10T00:00:00") == "inter_monsoon"
    assert logic.get_monsoon_season("garbage") == "inter_monsoon"
    assert logic.get_monsoon_season(None) == "inter_monsoon"
    assert logic.classify_lighting_condition("day", "clear") == "daylight"
    assert logic.classify_lighting_condition("day", "rain") == "low_light"
    assert logic.classify_lighting_condition("night", "rain") == "dark"


def test_monsoon_season_boundaries(logic):
    # Northeast: December to mid-March; southwest: June to September; anything else is inter-monsoon.
    for date, season in (("2026-12-01", "northeast_monsoon"), ("2026-03-15", "northeast_monsoon"),
                         ("2026-03-16", "inter_monsoon"), ("2026-05-31", "inter_monsoon"),
                         ("2026-06-01", "southwest_monsoon"), ("2026-09-30", "southwest_monsoon"),
                         ("2026-10-01", "inter_monsoon"), ("2026-11-30", "inter_monsoon")):
        assert logic.get_monsoon_season(date + "T12:00:00") == season, date


def test_injury_score_starts_from_what_happened_to_the_person(logic):
    assert logic._score_injury({"injury_treatment": "died"}) == (5, ["Someone died (set to 5)"])
    assert logic._score_injury({"injury_treatment": "first_aid"}) == (2, ["Minor injury, first aid only (+1)"])
    assert logic._score_injury({"injury_treatment": "hospital"}) == (3, ["Serious injury, hospital treatment (+2)"])
    hurt_not_described = (2, ["Someone was hurt, but how badly wasn't described (+1)"])
    assert logic._score_injury({"injury": True, "injury_treatment": "unspecified"}) == hurt_not_described
    assert logic._score_injury({"injury": True}) == hurt_not_described  # missing treatment counts as unspecified
    for nobody_hurt in ({"injury": False, "injury_treatment": "none"}, {}, {"injury_treatment": "banana"}):
        assert logic._score_injury(nobody_hurt) == (1, []), nobody_hurt


def test_condition_points_each_come_with_a_reason(logic):
    assert logic._score_conditions({}, False) == (0, [])
    assert logic._score_conditions({"ppe_status": "worn"}, False) == (-1, ["Safety gear (PPE) was worn (-1)"])
    assert logic._score_conditions({"hazard_category": "vehicular"}, False) == (
        1, ["One of MOM's highest-risk hazard types (+1)"])
    # Machinery without safety gear counts twice: once for the pair, once for the missing PPE.
    change, reasons = logic._score_conditions({"heavy_machinery_present": True, "ppe_status": "not_worn"}, False)
    assert change == 2 and len(reasons) == 2
    # Rain is read from the incident itself, and only counts with height or machinery.
    change, reasons = logic._score_conditions({"working_at_height": True, "condition": "rain"}, False)
    assert change == 2 and "Raining during work at height or with machinery (+1)" in reasons
    assert logic._score_conditions({"condition": "rain"}, False) == (0, [])
    assert logic._score_conditions({}, True) == (1, ["A similar past incident on our sites was escalated (+1)"])
    change, reasons = logic._score_conditions({"lighting_condition": "dark"}, False)
    assert change == 1 and all(reason.endswith(")") for reason in reasons)


def test_recurrence_level_tiers(logic):
    calm = {"lighting_condition": "daylight"}
    assert logic._recurrence_level(1, calm, [], False) == "low"
    # Medium: poor lighting, or at least one earlier incident at this place.
    assert logic._recurrence_level(1, {"lighting_condition": "low_light"}, [], False) == "medium"
    assert logic._recurrence_level(1, {"lighting_condition": "dark"}, [], False) == "medium"
    assert logic._recurrence_level(1, calm, [{}], False) == "medium"
    # High: severity at the stop-work level, the systemic number of earlier incidents, or an escalated look-alike.
    assert logic._recurrence_level(lm.HIGH_SEVERITY, calm, [], False) == "high"
    assert logic._recurrence_level(1, calm, [{}] * lm.SYSTEMIC_INCIDENT_COUNT, False) == "high"
    assert logic._recurrence_level(1, calm, [], True) == "high"
    # High beats medium when both apply.
    assert logic._recurrence_level(lm.HIGH_SEVERITY, {"lighting_condition": "dark"}, [{}], False) == "high"
    assert logic._recurrence_level(lm.HIGH_SEVERITY - 1, {}, [], False) == "low"


def test_derive_context_and_apply_lighting(logic):
    incident = make(description="wet floor", timestamp="2026-09-27T20:44:10")
    logic.derive_context(incident)
    ctx = incident.to_dict()
    assert ctx["weather_relevant"] is True and ctx["time_of_day"] == "night"
    assert ctx["monsoon_season"] == "southwest_monsoon"
    lit = logic.apply_lighting({**ctx, "condition": "rain"})
    assert lit["lighting_condition"] == "dark"
    assert "lighting_condition" not in ctx

def test_apply_weather_turns_rainfall_into_a_condition(logic):
    assert logic.apply_weather({"precipitation_mm": 0.3})["condition"] == "rain"
    assert logic.apply_weather({"precipitation_mm": 0})["condition"] == "clear"
    assert logic.apply_weather({"condition": None})["condition"] is None
    assert logic.apply_weather({"condition": "rain"})["condition"] == "rain"


def test_apply_lighting_copes_with_missing_or_unknown_values(logic):
    assert logic.apply_lighting({})["lighting_condition"] == "daylight"
    assert logic.apply_lighting({"time_of_day": None, "condition": None})["lighting_condition"] == "daylight"
    assert logic.apply_lighting({"time_of_day": "midnight", "condition": "fog"})["lighting_condition"] == "daylight"
    assert logic.apply_lighting({"time_of_day": "dusk_dawn", "condition": "rain"})["lighting_condition"] == "dark"

def _enriched(injury=True, **changes):
    base = {"hazard_category": "fall_from_height", "injury_treatment": "hospital",
            "working_at_height": True, "heavy_machinery_present": False, "ppe_status": "not_worn",
            "lighting_condition": "dark", "similar_incidents": None, "context_flags_error": None}
    base.update(changes)
    return make(injury=injury, **base)

def test_worst_case_scores_5_and_stops_work(logic):
    incident = _enriched(injury_treatment="died")
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 5
    assert logic.decide_outcome(incident, []) == "stop_work_review"


def test_mild_case_logs_only_and_three_earlier_incidents_escalate(logic):
    incident = _enriched(injury=False, hazard_category="fall", injury_treatment="none",
                         working_at_height=False, ppe_status="worn", lighting_condition="daylight")
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 1
    assert logic.decide_outcome(incident, []) == "log_only"
    assert logic.decide_outcome(incident, [{}] * 3) == "systemic_escalation"


def test_anyone_injured_scores_at_least_3(logic):
    safe_but_hurt = {"hazard_category": "fall", "injury_treatment": "first_aid", "working_at_height": False,
                     "ppe_status": "worn", "lighting_condition": "daylight"}
    for treatment in ("first_aid", "none", "unspecified"):
        incident = _enriched(**{**safe_but_hurt, "injury_treatment": treatment})
        logic.assess_severity(incident, [])
        assert incident.get("severity_estimate") == 3
        assert any("injured" in r for r in incident.get("severity_reasons"))
    uninjured = _enriched(injury=False, **{**safe_but_hurt, "injury_treatment": "none"})
    logic.assess_severity(uninjured, [])
    assert uninjured.get("severity_estimate") == 1


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


def test_sample_ai_reply_gives_the_expected_severity_recurrence_and_outcome(logic):
    for name, ai_reply, injured, earlier, severity, recurrence, outcome in SCORING_CASES:
        history = [{}] * earlier
        incident = make(injury=injured, **{**CALM_AI_REPLY, **ai_reply})
        logic.assess_severity(incident, history)
        assert incident.get("severity_estimate") == severity, name
        assert incident.get("likelihood_recurrence") == recurrence, name
        assessed = incident.to_dict()
        assert assessed["assessment_error"] is None and assessed["severity_reasons"] is not None, name
        assert logic.decide_outcome(incident, history) == outcome, name


def test_every_severity_reason_is_listed_so_the_score_can_be_explained(logic):
    incident = make(**{**CALM_AI_REPLY, "injury_treatment": "hospital",
                       "hazard_category": "vehicular", "ppe_status": "not_worn"})
    logic.assess_severity(incident, [])
    reasons = incident.get("severity_reasons")
    assert any("hospital" in r.lower() for r in reasons) and any("highest-risk" in r for r in reasons)
    assert any("not worn" in r for r in reasons) and all(r.endswith(")") for r in reasons)


def test_a_missing_hazard_category_is_never_scored_as_if_it_were_safe(logic):
    incident = make(**{**CALM_AI_REPLY, "hazard_category": None})
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 0 and incident.get("likelihood_recurrence") == "unknown"
    assert "hazard_category missing" in incident.get("assessment_error")


def test_multi_condition_rule_uses_ai_fields(logic):
    record = {"severity_estimate": 2, "injury": True, "likelihood_recurrence": "high"}
    assert logic.is_high_severity(record)
    assert not logic.is_high_severity({**record, "injury": False})
    assert not logic.is_high_severity({**record, "likelihood_recurrence": "low"})


def test_failed_ai_extraction_routes_to_manual_review(logic):
    incident = _enriched(hazard_category=None, context_flags_error="AI down")
    logic.assess_severity(incident, [])
    assert incident.get("assessment_error") and incident.get("severity_estimate") == 0
    assert logic.decide_outcome(incident, []) == "pending_review"


def test_apply_hazard_rules_decides_height_and_machinery_from_the_ais_lists(logic):
    both = logic.apply_hazard_rules({"equipment_mentioned": ["Tower Crane", "hammer"],
                                  "elevated_places": ["roof"]})
    assert both["working_at_height"] is True and both["heavy_machinery_present"] is True
    for name in ("excavator", "forklift", "generator", "conveyor belt", "dump truck", "piling rig",
                 "scissor lift", "concrete pump", "bobcat", "dumper", "pile driver", "telehandler",
                 "skid steer", "road roller", "mobile crane"):
        assert logic.apply_hazard_rules({"equipment_mentioned": [name]})["heavy_machinery_present"], name
    light = logic.apply_hazard_rules({"equipment_mentioned": ["hammer", "ladder", "drill", "paint roller",
                                                           "lifting sling", "angle grinder"],
                                   "elevated_places": []})
    assert light["working_at_height"] is False and light["heavy_machinery_present"] is False
    for odd in (None, "crane", [None, 5, " "], {}):
        result = logic.apply_hazard_rules({"equipment_mentioned": odd, "elevated_places": odd})
        assert result["working_at_height"] is False and result["heavy_machinery_present"] is False, odd
    source = {"equipment_mentioned": ["crane"]}
    logic.apply_hazard_rules(source)
    assert "heavy_machinery_present" not in source

def test_screen_incident_decides_accept_or_reject_from_the_ai_flag(logic):
    rejected = logic.screen_incident({"is_valid_incident": False, "invalid_reason": " It is random text. "})
    assert rejected == (False, "It is random text.")
    accepted, reason = logic.screen_incident({"is_valid_incident": False, "invalid_reason": None})
    assert accepted is False and "workplace safety incident" in reason
    for record in ({"is_valid_incident": True}, {"is_valid_incident": None}, {}, None, "x"):
        assert logic.screen_incident(record) == (True, None), record


# Sufi
@pytest.fixture
def logic():
    return LogicManager(LogicManager.default_rules())


def make(description="Worker fell from scaffold", injury=True, timestamp="2026-10-20T23:00:00", **fields):
    incident = Incident(description, "Site A", "supervisor", injury, timestamp)
    incident.update(fields)
    return incident


# Sample enriched record, as if the AI had replied (no live API).
def enriched(injury=True, **changes):
    fields = {"hazard_category": "fall_from_height", "injury_treatment": "hospital",
              "working_at_height": True, "heavy_machinery_present": False, "ppe_status": "not_worn",
              "lighting_condition": "dark", "similar_incidents": None, "context_flags_error": None}
    fields.update(changes)
    return make(injury=injury, **fields)


# Sufi
def test_multi_condition_rule_uses_two_ai_fields():
    rule = StopWorkRule()
    assert rule.applies(make(injury=True, severity_estimate=2, likelihood_recurrence="high"), [])
    assert not rule.applies(make(injury=False, severity_estimate=2, likelihood_recurrence="high"), [])
    assert not rule.applies(make(injury=True, severity_estimate=2, likelihood_recurrence="low"), [])


# Sufi
def test_screening_rejects_only_when_ai_says_not_an_incident(logic):
    rejected = make(is_valid_incident=False, invalid_reason="gibberish")
    assert logic.screen_incident(rejected) == (False, "gibberish")
    unknown = make(is_valid_incident=None)
    assert logic.screen_incident(unknown) == (True, None)


# Sufi
# --- New feature: photo evidence ---

def test_photo_fills_in_ppe_height_and_machinery(logic):
    incident = make(photo_analysed=True, ppe_status="unspecified", photo_ppe_status="not_worn",
                    working_at_height=False, photo_shows_height=True,
                    heavy_machinery_present=False, photo_shows_machinery=True)
    logic.apply_photo_evidence(incident)
    assert incident.get("ppe_status") == "not_worn"
    assert incident.get("working_at_height") and incident.get("heavy_machinery_present")
    assert len(incident.get("photo_evidence_used")) == 3


def test_description_wins_over_photo_when_it_is_explicit(logic):
    incident = make(photo_analysed=True, ppe_status="worn", photo_ppe_status="not_worn")
    logic.apply_photo_evidence(incident)
    assert incident.get("ppe_status") == "worn" and incident.get("photo_evidence_used") == []


def test_photo_evidence_raises_the_severity(logic):
    without = enriched(ppe_status="unspecified", lighting_condition="daylight", injury_treatment="none")
    with_photo = enriched(ppe_status="unspecified", lighting_condition="daylight", injury_treatment="none",
                          photo_analysed=True, photo_ppe_status="not_worn")
    logic.apply_photo_evidence(with_photo)
    logic.assess_severity(without, [])
    logic.assess_severity(with_photo, [])
    assert with_photo.get("severity_estimate") == without.get("severity_estimate") + 1


def test_unanalysed_photo_changes_nothing(logic):
    incident = make(photo_analysed=False, ppe_status="unspecified", photo_ppe_status="not_worn")
    logic.apply_photo_evidence(incident)
    assert incident.get("ppe_status") == "unspecified"


def test_mismatched_photo_goes_to_photo_review_but_stop_work_still_wins(logic):
    low = enriched(injury=False, hazard_category="other", injury_treatment="none", working_at_height=False,
                   ppe_status="worn", lighting_condition="daylight", photo_matches_description=False)
    logic.assess_severity(low, [])
    assert logic.decide_outcome(low, []) == "photo_review"
    high = enriched(injury_treatment="died", photo_matches_description=False)
    logic.assess_severity(high, [])
    assert logic.decide_outcome(high, []) == "stop_work_review"


# --- SOLID evidence: OCP and LSP ---

def test_every_rule_is_an_outcome_rule_and_can_be_swapped():
    for rule in LogicManager.default_rules():
        assert isinstance(rule, OutcomeRule)
        assert isinstance(rule.applies(make(), []), bool) and isinstance(rule.outcome, str)
    only_log = LogicManager([LogOnlyRule()])
    assert only_log.decide_outcome(make(assessment_error="x"), []) == "log_only"


def test_a_new_rule_can_be_added_without_changing_logic_manager():
    class NightShiftRule(OutcomeRule):
        @property
        def outcome(self):
            return "night_shift_review"

        def applies(self, incident, history):
            return incident.get("time_of_day") == "night"

    logic = LogicManager([PendingReviewRule(), NightShiftRule(), SystemicRiskRule(), LogOnlyRule()])
    assert logic.decide_outcome(make(time_of_day="night"), []) == "night_shift_review"
    assert logic.decide_outcome(make(time_of_day="day"), []) == "log_only"
    assert PhotoMismatchRule().outcome == "photo_review"


def test_outcome_rule_cannot_be_created_directly():
    with pytest.raises(TypeError):
        OutcomeRule()


# Sufi
def test_the_systemic_threshold_is_exactly_three_earlier_incidents():
    rule = SystemicRiskRule()
    assert SYSTEMIC_INCIDENT_COUNT == 3
    assert not rule.applies(make(), [object()] * (SYSTEMIC_INCIDENT_COUNT - 1))
    assert rule.applies(make(), [object()] * SYSTEMIC_INCIDENT_COUNT)


# Sufi
def test_rules_are_asked_in_priority_order(logic):
    broken = make(assessment_error="AI down", severity_estimate=5, photo_matches_description=False)
    assert logic.decide_outcome(broken, [object()] * 3) == "pending_review"  # a person must look before anything else
    severe = make(severity_estimate=5, photo_matches_description=False)
    assert logic.decide_outcome(severe, [object()] * 3) == "stop_work_review"  # Rule 1 before the photo and Rule 2
    mismatch = make(severity_estimate=1, photo_matches_description=False)
    assert logic.decide_outcome(mismatch, [object()] * 3) == "photo_review"  # the photo before Rule 2


# Sufi
def test_with_no_rules_the_outcome_is_manual_review_not_a_crash():
    assert LogicManager([]).decide_outcome(make(), []) == "pending_review"


# Sufi
def test_a_missing_or_wrong_typed_ai_value_never_breaks_a_rule():
    for fields in ({}, {"severity_estimate": None}, {"likelihood_recurrence": None}):
        assert not StopWorkRule().applies(make(injury=True, **fields), [])  # no usable AI value: no stop-work, no error
    assert not PhotoMismatchRule().applies(make(photo_matches_description=None), [])
    assert not PhotoMismatchRule().applies(make(), [])


def load_tests(loader, tests, pattern):
    return suite_from(globals())