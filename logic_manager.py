# classifications
_TYPE_A_HAZARDS = ("fall_from_height", "vehicular", "struck_by_machinery")

_INJURY_POINTS = {"none": 0, "unspecified": 0, "minor": 1, "serious": 2}

_ESCALATED_OUTCOMES = ("stop_work_review", "systemic_escalation")

SEVERITY_LEVELS = {
    1: ("Minimal", "Near miss or no injury, low-risk hazard, controls in place "
                   "(e.g. PPE worn). Record it and carry on."),
    2: ("Minor", "One aggravating factor, e.g. a minor injury or a ground-level "
                 "slip/trip. Record it; supervisor fixes the cause on the spot."),
    3: ("Moderate", "Several aggravating factors, e.g. injury in poor lighting, or "
                    "a high-risk hazard type with no injury. Logged, but the site "
                    "team should review the cause this week."),
    4: ("High", "Serious injury, or a MOM Type A hazard (fall from height, vehicle, "
                "machinery) combined with injury, height or missing PPE. Work "
                "stops for a safety review."),
    5: ("Critical", "Fatal, or several serious factors at once (e.g. fall from "
                    "height, no harness, injured, at night). Work stops "
                    "immediately; report to management and MOM as required."),
}

OUTCOME_ACTIONS = {
    "stop_work_review": "Stop the affected work and hold a safety review before it restarts.",
    "systemic_escalation": "Escalate to management: this location keeps having incidents.",
    "log_only": "Record the incident; no escalation needed.",
    "pending_review": "The AI could not assess it; a person must review it manually.",
}
