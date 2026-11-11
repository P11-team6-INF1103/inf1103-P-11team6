# Daniel

MAX_SEVERITY = 5

INJURY_MIN_SEVERITY = 3  # anyone injured scores at least this, whatever else the conditions take away

HIGH_SEVERITY = 4  # Rule 1: this severity or above means stop-work review

SYSTEMIC_INCIDENT_COUNT = 3  # Rule 2: this many earlier incidents at one location

SEVERITY_LEVELS = {
    1: ("Minimal", (
        "Near miss or no injury, low-risk hazard, controls in place "
        "(e.g. PPE worn). Record it and carry on.")),
    2: ("Minor", (
        "No injury, with one aggravating factor, e.g. a ground-level "
        "slip/trip. Record it; supervisor fixes the cause on the spot.")),
    3: ("Moderate", (
        "Anyone injured (the minimum for an injury), or several aggravating "
        "factors with no injury. Logged, but the site "
        "team should review the cause this week.")),
    4: ("High", (
        "Serious injury, or a MOM Type A hazard (fall from height, vehicle, "
        "machinery) combined with injury, height or missing PPE. Work "
        "stops for a safety review.")),
    5: ("Critical", (
        "Fatal, or several serious factors at once (e.g. fall from "
        "height, no harness, injured, at night). Work stops "
        "immediately; report to management and MOM as required.")),
}

OUTCOME_ACTIONS = {
    "stop_work_review": "Stop the affected work and hold a safety review before it restarts.",
    "photo_review": "The photo does not seem to match the description; a person should check it.",
    "systemic_escalation": "Escalate to management: this location keeps having incidents.",
    "log_only": "Record the incident; no escalation needed.",
    "pending_review": "The AI could not assess it; a person must review it manually.",
}
