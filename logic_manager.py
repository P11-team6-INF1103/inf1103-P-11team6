import re
from datetime import datetime

# Whole-word match only: "window" must not count as "wind", "constraint" as
# "rain", or "shot" as "hot".
_WEATHER_WORDS = re.compile(
    r"\b(rain|rains|raining|rainy|rained|wet|storm|storms|stormy|wind|winds|windy|"
    r"flood|floods|flooded|flooding|lightning|thunder|thunderstorm|thunderstorms|"
    r"haze|hazy|hot|heat|humid|humidity)\b",
    re.IGNORECASE,
)

# MOM "Type A" hazard types: the ones with a higher fatality risk.
_TYPE_A_HAZARDS = ("fall_from_height", "vehicular", "struck_by_machinery")

_INJURY_POINTS = {"none": 0, "unspecified": 0, "first_aid": 1, "hospital": 2}
_INJURY_LABELS = {"first_aid": "Minor injury, first aid only", "hospital": "Serious injury, hospital treatment"}

_ESCALATED_OUTCOMES = ("stop_work_review", "systemic_escalation")

_POOR_LIGHT_LEVELS = ("dark", "low_light")

MAX_SEVERITY = 5
HIGH_SEVERITY = 4  # Rule 1: this severity or above means stop-work review
SYSTEMIC_INCIDENT_COUNT = 3  # Rule 2: this many earlier incidents at one location

_HEAVY_MACHINERY_WORDS = (
    "crane", "excavator", "forklift", "generator", "conveyor", "bulldozer",
    "backhoe", "digger", "loader", "grader", "compactor", "road roller",
    "crusher", "tractor", "truck", "lorry", "dumper", "tipper", "bobcat",
    "skid steer", "telehandler", "paver", "trencher", "concrete pump",
    "cement mixer", "piling", "pile driver", "drill rig", "hoist",
    "scissor lift", "boom lift", "mewp", "elevating work platform",
)

SEVERITY_LEVELS = {
    1: ("Minimal", (
        "Near miss or no injury, low-risk hazard, controls in place "
        "(e.g. PPE worn). Record it and carry on.")),
    2: ("Minor", (
        "One aggravating factor, e.g. a minor injury or a ground-level "
        "slip/trip. Record it; supervisor fixes the cause on the spot.")),
    3: ("Moderate", (
        "Several aggravating factors, e.g. injury in poor lighting, or "
        "a high-risk hazard type with no injury. Logged, but the site "
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
    "systemic_escalation": "Escalate to management: this location keeps having incidents.",
    "log_only": "Record the incident; no escalation needed.",
    "pending_review": "The AI could not assess it; a person must review it manually.",
}


# Daniel
# 'day', 'dusk_dawn' or 'night' from the timestamp hour; an unreadable timestamp counts as 'day'.
def get_time_of_day(timestamp: str | None) -> str:
    try:
        hour = datetime.fromisoformat(timestamp).hour
    except (TypeError, ValueError):
        return "day"
    if 7 <= hour < 18:
        return "day"
    if 18 <= hour < 20 or 5 <= hour < 7:
        return "dusk_dawn"
    return "night"


# Ren Xiang
# Singapore's monsoon season for the incident date (context only); an unreadable timestamp gives 'inter_monsoon'.
def get_monsoon_season(timestamp: str | None) -> str:
    try:
        when = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return "inter_monsoon"
    month = when.month
    if month in (12, 1, 2) or (month == 3 and when.day <= 15):
        return "northeast_monsoon"
    if 6 <= month <= 9:
        return "southwest_monsoon"
    return "inter_monsoon"


# Darrel
# True if the description mentions weather, so the weather API should be called.
def is_weather_relevant(record: dict) -> bool:
    return bool(_WEATHER_WORDS.search(str(record.get("description", ""))))


# Decides which optional lookups to run: weather when it matters, otherwise similar past incidents.
def plan_enrichment(record: dict) -> dict:
    relevant = is_weather_relevant(record)
    return {"run_weather": relevant, "run_similar": not relevant}


# Darrel
# 'daylight', 'low_light' or 'dark': one step darker than the time of day when it is raining.
def classify_lighting_condition(time_of_day: str, condition: str | None) -> str:
    levels = ["daylight", "low_light", "dark"]
    base = {"day": 0, "dusk_dawn": 1, "night": 2}.get(time_of_day, 0)
    if condition == "rain":
        base += 1
    base = min(base, len(levels) - 1)
    return levels[base]


# Turns precipitation_mm into condition ('rain' or 'clear'); returns a new dict.
def apply_weather(enriched: dict) -> dict:
    result = dict(enriched)
    precipitation_mm = enriched.get("precipitation_mm")
    if isinstance(precipitation_mm, (int, float)):
        result["condition"] = "rain" if precipitation_mm > 0 else "clear"
    return result


# Adds what needs no API (weather relevance, lookup plan, time of day, monsoon season); returns a new dict.
def derive_context(incident: dict) -> dict:
    result = dict(incident)
    result["weather_relevant"] = is_weather_relevant(incident)
    result.update(plan_enrichment(incident))
    result["time_of_day"] = get_time_of_day(incident.get("timestamp"))
    result["monsoon_season"] = get_monsoon_season(incident.get("timestamp"))
    return result


# Adds lighting_condition from the time of day and the weather; returns a new dict.
def apply_lighting(enriched: dict) -> dict:
    lit = dict(enriched)
    lit["lighting_condition"] = classify_lighting_condition(
        enriched.get("time_of_day", "day"), enriched.get("condition")
    )
    return lit


# The non-empty strings in a list, stripped and lower-cased; anything else is ignored.
def _text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]


# Adds working_at_height and heavy_machinery_present from the AI's elevated-place and equipment lists; returns a new dict.
def apply_hazard_rules(enriched: dict) -> dict:
    result = dict(enriched)
    equipment = _text_list(enriched.get("equipment_mentioned"))
    places = _text_list(enriched.get("elevated_places"))
    result["working_at_height"] = bool(places)
    result["heavy_machinery_present"] = any(
        word in name for name in equipment for word in _HEAVY_MACHINERY_WORDS
    )
    return result


# Starting severity and its reasons from what happened to the person (5 if someone died).
def _score_injury(record: dict) -> tuple[int, list[str]]:
    injury_treatment = record.get("injury_treatment", "unspecified")
    if injury_treatment == "died":
        return MAX_SEVERITY, ["Someone died (set to 5)"]
    severity = 1
    reasons = []
    injury_points = _INJURY_POINTS.get(injury_treatment, 0)
    if injury_points:
        severity += injury_points
        reasons.append(f"{_INJURY_LABELS[injury_treatment]} (+{injury_points})")
    if record.get("injury") and injury_treatment in ("none", "unspecified"):
        severity += 1
        reasons.append("Someone was hurt, but how badly wasn't described (+1)")
    return severity, reasons


# Points added or removed by the hazard type and the site conditions, with a reason for each.
def _score_conditions(record: dict, weather_data: dict, hazard_type: str, similar_escalated: bool) -> tuple[int, list[str]]:
    at_height = record.get("working_at_height")
    machinery = record.get("heavy_machinery_present")
    ppe_not_worn = record.get("ppe_status") == "not_worn"
    poor_light = record.get("lighting_condition") in _POOR_LIGHT_LEVELS

    change = 0
    reasons = []
    if hazard_type in _TYPE_A_HAZARDS:
        change += 1
        reasons.append("One of MOM's highest-risk hazard types (+1)")
    if at_height:
        change += 1
        reasons.append("Working at height (+1)")
    if machinery and ppe_not_worn:
        change += 1
        reasons.append("Heavy machinery around, without safety gear (+1)")
    if ppe_not_worn:
        change += 1
        reasons.append("Safety gear (PPE) not worn (+1)")
    elif record.get("ppe_status") == "worn":
        change -= 1
        reasons.append("Safety gear (PPE) was worn (-1)")
    if poor_light:
        change += 1
        reasons.append("Poor lighting or dark (+1)")
    if weather_data.get("condition") == "rain" and (at_height or machinery):
        change += 1
        reasons.append("Raining during work at height or with machinery (+1)")
    if similar_escalated:
        change += 1
        reasons.append("A similar past incident on our sites was escalated (+1)")
    return change, reasons


# Total severity capped to 1-5, with the plain-English reason for every point.
def _score_severity(record: dict, weather_data: dict, hazard_type: str, similar_escalated: bool) -> tuple[int, list[str]]:
    severity, reasons = _score_injury(record)
    change, condition_reasons = _score_conditions(record, weather_data, hazard_type, similar_escalated)
    return max(1, min(severity + change, MAX_SEVERITY)), reasons + condition_reasons


# 'low', 'medium' or 'high' chance of this kind of incident happening again.
def _recurrence_level(severity: int, poor_light: bool, history: list, similar_escalated: bool) -> str:
    if severity >= HIGH_SEVERITY or len(history) >= SYSTEMIC_INCIDENT_COUNT or similar_escalated:
        return "high"
    if poor_light or len(history) >= 1:
        return "medium"
    return "low"


# Daniel
# Scores one enriched incident (hazard type, severity 1-5, recurrence, reasons); sets assessment_error instead of guessing if the AI failed.
def assess_severity(record: dict, weather_data: dict | None = None, history: list | None = None) -> dict:
    weather_data = weather_data or {}
    history = history or []

    result = dict(record)

    if record.get("context_flags_error") or record.get("hazard_category") is None:
        result["hazard_type"] = "unassessed"
        result["severity_estimate"] = 0
        result["likelihood_recurrence"] = "unknown"
        result["severity_reasons"] = []
        result["assessment_error"] = (
            "Cannot judge severity without AI hazard extraction: "
            f"{record.get('context_flags_error') or 'hazard_category missing'}"
        )
        return result

    similar = record.get("similar_incidents") or []
    similar_escalated = any(item.get("outcome") in _ESCALATED_OUTCOMES for item in similar)
    severity, reasons = _score_severity(record, weather_data, record["hazard_category"], similar_escalated)
    poor_light = record.get("lighting_condition") in _POOR_LIGHT_LEVELS

    result["hazard_type"] = record["hazard_category"]
    result["severity_estimate"] = severity
    result["likelihood_recurrence"] = _recurrence_level(severity, poor_light, history, similar_escalated)
    result["severity_reasons"] = reasons
    result["assessment_error"] = None
    return result


# Darrel
# Rule 1: severity 4 or more, or an injury with high recurrence likelihood.
def is_high_severity(record: dict) -> bool:
    severity = record.get("severity_estimate", 0)
    injury = record.get("injury", False)
    recurrence = record.get("likelihood_recurrence", "unknown")
    return severity >= HIGH_SEVERITY or (injury and recurrence == "high")


# Sufi
# Rule 2: this location already has 3 or more incidents in the history window.
def is_systemic_risk(record: dict, history: list) -> bool:
    return len(history) >= SYSTEMIC_INCIDENT_COUNT


# Sufi
# Picks the outcome in order: pending_review, stop_work_review, systemic_escalation, log_only.
def decide_outcome(record: dict, history: list) -> str:
    if record.get("assessment_error"):
        return "pending_review"
    if is_high_severity(record):
        return "stop_work_review"
    if is_systemic_risk(record, history):
        return "systemic_escalation"
    return "log_only"


# Rejects an incident only when the AI said it is not a real safety incident; accepts it if the AI is down.
def screen_incident(record: dict) -> dict:
    if not isinstance(record, dict) or record.get("is_valid_incident") is not False:
        return {"accepted": True, "reject_reason": None}
    reason = str(record.get("invalid_reason") or "").strip()
    return {
        "accepted": False,
        "reject_reason": reason or "it does not describe a workplace safety incident",
    }
