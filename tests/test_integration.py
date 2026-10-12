import main

# Only the AI and weather network calls are replaced with canned answers.
# logic_manager, data_manager and io_manager are the real ones, so a wiring
# mistake in main.py (wrong argument order, a skipped step) fails these tests.


def _flags(**overrides):
    flags = {"hazard_category": "fall_from_height", "injury_treatment": "hospital",
             "equipment_mentioned": [], "elevated_places": ["scaffolding"], "height_estimate_m": 10,
             "ppe_status": "not_worn",
             "is_valid_incident": True, "invalid_reason": None, "context_flags_error": None}
    flags.update(overrides)
    return flags


def _canned_ai(monkeypatch, flags, weather=None):
    monkeypatch.setattr(main.ai_manager, "extract_hazard_context_flags", lambda description: flags)
    monkeypatch.setattr(main.ai_manager, "get_weather", lambda timestamp, location: weather)
    monkeypatch.setattr(main.ai_manager, "find_similar_incidents",
                        lambda record, history, outcome_meanings=None: {"similar_incidents": [], "similar_incidents_error": None})
    monkeypatch.setattr(main.ai_manager, "search_web_for_similar_incidents",
                        lambda record: {"web_industry_context": None, "web_incidents": [], "web_search_error": None})
    monkeypatch.setattr(main.ai_manager, "generate_incident_review",
                        lambda record: {"review_likely_causes": None, "review_prevention_actions": None,
                                        "review_error": None})


def _incident(**overrides):
    incident = {"description": "Worker fell from scaffolding about 10 metres, no harness worn, fracture",
                "location": "Site B - Warehouse", "reporter_role": "safety_officer", "injury": True,
                "timestamp": "2026-10-05T21:00:00"}
    incident.update(overrides)
    return incident


def test_serious_night_fall_is_scored_dark_and_stops_work(monkeypatch):
    _canned_ai(monkeypatch, _flags())
    records = []
    final = main.process_incident(_incident(), records, interactive=False)
    assert final["time_of_day"] == "night" and final["lighting_condition"] == "dark"
    assert final["hazard_type"] == "fall_from_height" and final["severity_estimate"] == 5
    assert final["outcome"] == "stop_work_review"
    assert main.data_manager.load_records() == [final] and records == [final]


def test_minor_daytime_incident_is_only_logged(monkeypatch):
    flags = _flags(hazard_category="vehicular", injury_treatment="none", elevated_places=[],
                   height_estimate_m=None, ppe_status="worn")
    _canned_ai(monkeypatch, flags)
    incident = _incident(description="Forklift reversed into a stack of pallets, nobody hurt, PPE worn",
                         injury=False, timestamp="2026-10-06T14:05:00")
    final = main.process_incident(incident, [], interactive=False)
    assert final["lighting_condition"] == "daylight" and final["severity_estimate"] == 1
    assert final["outcome"] == "log_only"


def test_rain_is_carried_from_the_weather_step_into_lighting_and_severity(monkeypatch):
    weather = {"temperature_c": 28, "humidity_pct": 90, "precipitation_mm": 2.0}
    _canned_ai(monkeypatch, _flags(injury_treatment="none", ppe_status="worn"), weather)
    incident = _incident(description="Worker slipped on scaffolding in heavy rain, no injury, harness worn",
                         injury=False, timestamp="2026-10-06T09:00:00")
    final = main.process_incident(incident, [], interactive=False)
    assert final["weather_available"] is True and final["condition"] == "rain"
    assert final["lighting_condition"] == "low_light"
    assert "Raining during work at height or with machinery (+1)" in final["severity_reasons"]


def test_three_earlier_incidents_at_one_site_escalate_a_minor_one(monkeypatch):
    flags = _flags(hazard_category="fall", injury_treatment="none", elevated_places=[],
                   height_estimate_m=None, ppe_status="unspecified")
    _canned_ai(monkeypatch, flags)
    records = []
    for day in ("01", "02", "03"):
        main.process_incident(_incident(injury=False, timestamp=f"2026-10-{day}T10:00:00"), records, interactive=False)
    fourth = main.process_incident(_incident(injury=False, timestamp="2026-10-04T10:00:00"), records, interactive=False)
    assert fourth["outcome"] == "systemic_escalation"
