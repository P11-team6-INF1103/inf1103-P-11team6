import json
from unittest import mock

import ai_manager

_GOOD_FLAGS = {
    "hazard_category": "fall_from_height", "injury_severity": "serious",
    "working_at_height": True, "height_estimate_m": 10,
    "heavy_machinery_present": False, "ppe_status": "not_worn",
}


def _incident(description="Worker fell from scaffolding", weather_relevant=False):
    return {"description": description, "location": "Site A", "reporter_role": "site_supervisor",
            "injury": True, "timestamp": "2026-09-27T20:44:10",
            "weather_relevant": weather_relevant, "time_of_day": "night",
            "monsoon_season": "southwest_monsoon"}


def _flags_for(reply):
    ai_manager.load_response_cache({})
    return mock.patch.object(ai_manager, "_call_gemini", return_value=json.dumps(reply))


def test_flags_ai_can_reject_text_that_is_not_a_safety_incident():
    reply = dict(_GOOD_FLAGS, hazard_category="other", is_valid_incident=False,
                 invalid_reason="It is random text, not an incident.")
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=object()), _flags_for(reply):
        result = ai_manager.extract_hazard_context_flags("asdf qwerty banana")
    assert result["is_valid_incident"] is False
    assert "random text" in result["invalid_reason"]


def test_flags_treat_a_reply_without_the_new_field_or_an_ai_outage_as_valid():
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=object()), _flags_for(_GOOD_FLAGS):
        result = ai_manager.extract_hazard_context_flags("Worker fell")
    assert result["is_valid_incident"] is True and result["invalid_reason"] is None
    with mock.patch.object(ai_manager, "_get_gemini_client", return_value=None):
        assert ai_manager.extract_hazard_context_flags("Worker fell")["is_valid_incident"] is True
