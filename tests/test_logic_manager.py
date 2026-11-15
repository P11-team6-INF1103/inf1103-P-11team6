import pytest

from ai_manager import AIManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SYSTEMIC_INCIDENT_COUNT
from logic_rules.log_only_rule import LogOnlyRule
from logic_rules.outcome_rule import OutcomeRule
from logic_rules.pending_review_rule import PendingReviewRule
from logic_rules.photo_mismatch_rule import PhotoMismatchRule
from logic_rules.stop_work_rule import StopWorkRule
from logic_rules.systemic_risk_rule import SystemicRiskRule
from models.incident import Incident
from tests.doubles.fake_gemini import FakeGemini
from tests.doubles.fake_search import FakeSearch
from tests.doubles.fake_weather import FakeWeather


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


# Darrel
def test_weather_relevance_is_whole_word(logic):
    assert logic.is_weather_relevant(make("Worker slipped on wet floor"))
    assert logic.is_weather_relevant(make("Lightning struck the crane"))
    assert not logic.is_weather_relevant(make("Hit by a window frame"))
    assert not logic.is_weather_relevant(make("Shot-blasting dust in the room"))


# Daniel
def test_time_of_day_season_and_lighting():
    assert LogicManager.get_time_of_day("2026-09-27T12:00:00") == "day"
    assert LogicManager.get_time_of_day("2026-09-27T18:30:00") == "dusk_dawn"
    assert LogicManager.get_time_of_day("garbage") == "day"
    assert LogicManager.get_monsoon_season("2026-01-10T00:00:00") == "northeast_monsoon"
    assert LogicManager.get_monsoon_season("2026-07-10T00:00:00") == "southwest_monsoon"
    assert LogicManager.get_monsoon_season(None) == "inter_monsoon"
    assert LogicManager.classify_lighting_condition("day", "rain") == "low_light"
    assert LogicManager.classify_lighting_condition("night", "rain") == "dark"


# Darrel
def test_derive_context_plans_the_lookups(logic):
    incident = make("Worker slipped on wet floor", timestamp="2026-09-27T20:44:10")
    logic.derive_context(incident)
    assert incident.get("run_weather") is True and incident.get("run_similar") is False
    assert incident.get("time_of_day") == "night"


# Darrel
def test_site_conditions_from_ai_lists(logic):
    incident = make(equipment_mentioned=["Tower Crane"], elevated_places=["roof"], precipitation_mm=0.5,
                    time_of_day="day")
    logic.apply_site_conditions(incident)
    assert incident.get("condition") == "rain" and incident.get("lighting_condition") == "low_light"
    assert incident.get("working_at_height") and incident.get("heavy_machinery_present")
    plain = make(equipment_mentioned=["hammer"], elevated_places=[])
    logic.apply_site_conditions(plain)
    assert not plain.get("working_at_height") and not plain.get("heavy_machinery_present")


# Daniel
def test_worst_case_scores_5_and_stops_work(logic):
    incident = enriched(injury_treatment="died")
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 5
    assert logic.decide_outcome(incident, []) == "stop_work_review"


def test_mild_case_logs_only_and_three_earlier_incidents_escalate(logic):
    incident = enriched(injury=False, hazard_category="fall", injury_treatment="none", working_at_height=False,
                        ppe_status="worn", lighting_condition="daylight")
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 1
    assert logic.decide_outcome(incident, []) == "log_only"
    assert logic.decide_outcome(incident, [object()] * 3) == "systemic_escalation"


# Sufi
def test_multi_condition_rule_uses_two_ai_fields():
    rule = StopWorkRule()
    assert rule.applies(make(injury=True, severity_estimate=2, likelihood_recurrence="high"), [])
    assert not rule.applies(make(injury=False, severity_estimate=2, likelihood_recurrence="high"), [])
    assert not rule.applies(make(injury=True, severity_estimate=2, likelihood_recurrence="low"), [])


# Daniel
def test_anyone_injured_scores_at_least_3():
    logic = LogicManager(LogicManager.default_rules())
    safe_but_hurt = {"hazard_category": "fall", "injury_treatment": "first_aid", "working_at_height": False,
                     "ppe_status": "worn", "lighting_condition": "daylight"}
    for treatment in ("first_aid", "none", "unspecified"):
        incident = enriched(injury=True, **{**safe_but_hurt, "injury_treatment": treatment})
        logic.assess_severity(incident, [])
        assert incident.get("severity_estimate") == 3
        assert any("injured" in r for r in incident.get("severity_reasons"))
    uninjured = enriched(injury=False, **{**safe_but_hurt, "injury_treatment": "none"})
    logic.assess_severity(uninjured, [])
    assert uninjured.get("severity_estimate") == 1


# Daniel
def test_failed_ai_extraction_routes_to_manual_review(logic):
    incident = enriched(hazard_category=None, context_flags_error="AI down")
    logic.assess_severity(incident, [])
    assert incident.get("assessment_error") and incident.get("severity_estimate") == 0
    assert logic.decide_outcome(incident, []) == "pending_review"


# Sufi
def test_screening_rejects_only_when_ai_says_not_an_incident(logic):
    assert logic.screen_incident(make(is_valid_incident=False, invalid_reason="gibberish")) == (False, "gibberish")
    assert logic.screen_incident(make(is_valid_incident=None))[0] is True


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


# Daniel
@pytest.mark.parametrize("name, ai_reply, injured, earlier, severity, recurrence, outcome", SCORING_CASES,
                         ids=[case[0] for case in SCORING_CASES])
def test_sample_ai_reply_gives_the_expected_severity_recurrence_and_outcome(
        logic, name, ai_reply, injured, earlier, severity, recurrence, outcome):
    incident = make(injury=injured, **{**CALM_AI_REPLY, **ai_reply})
    history = [object()] * earlier
    logic.assess_severity(incident, history)
    assert incident.get("severity_estimate") == severity
    assert incident.get("likelihood_recurrence") == recurrence
    assert incident.get("assessment_error") is None and incident.get("severity_reasons") is not None
    assert logic.decide_outcome(incident, history) == outcome


# Daniel
def test_every_severity_reason_is_listed_so_the_score_can_be_explained(logic):
    incident = make(injury=True, **{**CALM_AI_REPLY, "injury_treatment": "hospital", "hazard_category": "vehicular",
                                    "ppe_status": "not_worn"})
    logic.assess_severity(incident, [])
    reasons = incident.get("severity_reasons")
    assert any("hospital" in r.lower() for r in reasons) and any("highest-risk" in r for r in reasons)
    assert any("not worn" in r for r in reasons) and all(r.endswith(")") for r in reasons)


# Daniel
def test_a_missing_hazard_category_is_never_scored_as_if_it_were_safe(logic):
    incident = make(**{**CALM_AI_REPLY, "hazard_category": None})
    logic.assess_severity(incident, [])
    assert incident.get("severity_estimate") == 0 and incident.get("likelihood_recurrence") == "unknown"
    assert "hazard_category missing" in incident.get("assessment_error")


# Daniel
# The hard-coded Gemini reply from tests/fakes.py goes through the real AIManager, then the real LogicManager.
def test_hardcoded_ai_reply_flows_through_ai_manager_into_the_logic_manager(logic):
    ai = AIManager(FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    incident = make("Scaffold plank fell from level 4 near a worker", timestamp="2026-10-20T23:00:00")
    logic.derive_context(incident)
    ai.extract_hazards(incident)
    ai.gather_evidence(incident, [])
    logic.apply_site_conditions(incident)
    logic.apply_photo_evidence(incident)
    logic.assess_severity(incident, [])
    assert incident.get("hazard_category") == "fall_from_height" and incident.get("working_at_height") is True
    assert incident.get("severity_estimate") == 5 and logic.decide_outcome(incident, []) == "stop_work_review"


# Daniel
def test_a_failed_ai_call_flows_through_to_manual_review(logic):
    ai = AIManager(FakeGemini(error=ConnectionError("API down")), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    incident = make("Scaffold plank fell from level 4 near a worker")
    ai.extract_hazards(incident)
    logic.assess_severity(incident, [])
    assert incident.get("assessment_error") and logic.decide_outcome(incident, []) == "pending_review"


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


# Darrel
def test_site_conditions_cope_with_dry_weather_and_malformed_ai_lists(logic):
    dry = make(precipitation_mm=0, time_of_day="day", equipment_mentioned=["Excavator"], elevated_places=[])
    logic.apply_site_conditions(dry)
    assert dry.get("condition") == "clear" and dry.get("heavy_machinery_present") is True
    assert dry.get("lighting_condition") == "daylight"
    no_reading = make(time_of_day="day")
    logic.apply_site_conditions(no_reading)
    assert no_reading.get("condition") is None  # no weather reading: nothing is invented
    malformed = make(equipment_mentioned="crane", elevated_places=[5, None, "  "], time_of_day="night")
    logic.apply_site_conditions(malformed)  # a string and junk entries instead of lists of names
    assert malformed.get("heavy_machinery_present") is False and malformed.get("working_at_height") is False
    assert malformed.get("lighting_condition") == "dark"
