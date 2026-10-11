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

# classifications
_TYPE_A_HAZARDS = ("fall_from_height", "vehicular", "struck_by_machinery")

_INJURY_POINTS = {"none": 0, "unspecified": 0, "first_aid": 1, "hospital": 2}
_INJURY_LABELS = {"first_aid": "Minor injury, first aid only", "hospital": "Serious injury, hospital treatment"}

_ESCALATED_OUTCOMES = ("stop_work_review", "systemic_escalation")

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

#daniel
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

# darrel
def get_monsoon_season(timestamp: str | None) -> str:
    """Pure function. Returns Singapore's monsoon season for the incident
    date, using the Meteorological Service Singapore calendar:
    'northeast_monsoon' (Dec to early Mar), 'inter_monsoon' (late Mar to
    May, Oct to Nov), 'southwest_monsoon' (Jun to Sep). Context only,
    never used to score. An unreadable timestamp falls back to the
    inter-monsoon label so the result never depends on today's date."""
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

# darrel
def is_weather_relevant(record: dict) -> bool:
    """Whole-word keyword match on the description: does weather context
    matter for this incident? Decides whether the weather API is called
    (and, because the two are mutually exclusive, whether similar past
    incidents are searched instead)."""
    return bool(_WEATHER_WORDS.search(str(record.get("description", ""))))

#darrel
def plan_enrichment(record):
    """Which optional lookups ai_manager.enrich_record() should make for this
    incident. Returns {"run_weather": bool, "run_similar": bool}. When
    weather matters the weather API is called and similar past incidents are
    skipped; otherwise the other way round. The web search always runs, so
    it needs no flag."""
    relevant = is_weather_relevant(record)
    return {"run_weather": relevant, "run_similar": not relevant}


# darrel
def classify_lighting_condition(time_of_day: str, condition: str | None) -> str:
    """One step darker than time_of_day if weather cuts visibility. Never
    returns None."""
    levels = ["daylight", "low_light", "dark"]
    base = {"day": 0, "dusk_dawn": 1, "night": 2}.get(time_of_day, 0)
    if condition == "rain":
        base += 1
    base = min(base, len(levels) - 1)
    return levels[base]

def apply_weather(enriched: dict) -> dict:
    result = dict(enriched)
    precipitation_mm = enriched.get("precipitation_mm")
    if isinstance(precipitation_mm, (int, float)):
        result["condition"] = "rain" if precipitation_mm > 0 else "clear"
    return result

def derive_context(incident):
    """Rules that need no API: weather relevance, which lookups to make
    (run_weather, run_similar), time of day and monsoon season. Run before
    ai_manager.enrich_record(). Returns a new dict."""
    result = dict(incident)
    result["weather_relevant"] = is_weather_relevant(incident)
    result.update(plan_enrichment(incident))
    result["time_of_day"] = get_time_of_day(incident.get("timestamp"))
    result["monsoon_season"] = get_monsoon_season(incident.get("timestamp"))
    return result


def apply_lighting(enriched: dict) -> dict:
    lit = dict(enriched)
    lit["lighting_condition"] = classify_lighting_condition(
        enriched.get("time_of_day", "day"), enriched.get("condition")
    )
    return lit

def _text_list(value):
    """The non-empty strings in a list, lower-cased; anything else is ignored."""
    if not isinstance(value, list):
        return []
    return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]

def apply_hazard_rules(enriched):
    """Adds working_at_height and heavy_machinery_present from the AI's raw
    lists. Working at height: the AI named at least one elevated place the
    person was on or fell from. Heavy machinery: any named equipment contains
    a word from _HEAVY_MACHINERY_WORDS. If the AI failed the lists are empty
    and both are False, the same as before. Run after
    ai_manager.enrich_record() and before assess_severity() and the review.
    Returns a new dict."""
    result = dict(enriched)
    equipment = _text_list(enriched.get("equipment_mentioned"))
    places = _text_list(enriched.get("elevated_places"))
    result["working_at_height"] = bool(places)
    result["heavy_machinery_present"] = any(
        word in name for name in equipment for word in _HEAVY_MACHINERY_WORDS
    )
    return result

def assess_severity(record, weather_data=None, history=None):
    if weather_data is None:
        weather_data = {}
    if history is None:
        history = []

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

    hazard_type = record["hazard_category"]
    injury_treatment = record.get("injury_treatment", "unspecified")
    at_height = record.get("working_at_height")
    machinery = record.get("heavy_machinery_present")
    ppe_not_worn = record.get("ppe_status") == "not_worn"
    poor_light = record.get("lighting_condition") in ("dark", "low_light")
    similar = record.get("similar_incidents") or []
    similar_escalated = any(item.get("outcome") in _ESCALATED_OUTCOMES for item in similar)

    #severity_estimate simple additive score capped 1-5 
    severity = 1
    reasons = []
    if injury_treatment == "died":
        severity = 5
        reasons.append("Someone died (set to 5)")
    else:
        injury_points = _INJURY_POINTS.get(injury_treatment, 0)
        if injury_points:
            severity += injury_points
            reasons.append(f"{_INJURY_LABELS[injury_treatment]} (+{injury_points})")
        if record.get("injury") and injury_treatment in ("none", "unspecified"):
            severity += 1
            reasons.append("Someone was hurt, but how badly wasn't described (+1)")
    if hazard_type in _TYPE_A_HAZARDS:
        severity += 1
        reasons.append("One of MOM's highest-risk hazard types (+1)")
    if at_height:
        severity += 1
        reasons.append("Working at height (+1)")
    if machinery and ppe_not_worn:
        severity += 1
        reasons.append("Heavy machinery around, without safety gear (+1)")
    if ppe_not_worn:
        severity += 1
        reasons.append("Safety gear (PPE) not worn (+1)")
    elif record.get("ppe_status") == "worn":
        severity -= 1
        reasons.append("Safety gear (PPE) was worn (-1)")
    if poor_light:
        severity += 1
        reasons.append("Poor lighting or dark (+1)")
    if weather_data.get("condition") == "rain" and (at_height or machinery):
        severity += 1
        reasons.append("Raining during work at height or with machinery (+1)")
    if similar_escalated:
        severity += 1
        reasons.append("A similar past incident on our sites was escalated (+1)")
    severity = max(1, min(severity, 5))

    #likelihood_recurrence: simple tiered logic
    recurrence = "low"
    if poor_light or len(history) >= 1:
        recurrence = "medium"
    if severity >= 4 or len(history) >= 3 or similar_escalated:
        recurrence = "high"

    result["hazard_type"] = hazard_type
    result["severity_estimate"] = severity
    result["likelihood_recurrence"] = recurrence
    result["severity_reasons"] = reasons
    result["assessment_error"] = None
    return result

def is_high_severity(record: dict) -> bool:
    severity = record.get("severity_estimate", 0)
    injury = record.get("injury", False)
    recurrence = record.get("likelihood_recurrence", "unknown")
    return severity >= 4 or (injury and recurrence == "high")

def is_systemic_risk(record: dict, history: list) -> bool:
    return len(history) >= 3

def decide_outcome(record: dict, history: list) -> str:
    if record.get("assessment_error"):
        return "pending_review"
    if is_high_severity(record):
        return "stop_work_review"
    if is_systemic_risk(record, history):
        return "systemic_escalation"
    return "log_only"

def screen_incident(record):
    if not isinstance(record, dict) or record.get("is_valid_incident") is not False:
        return {"accepted": True, "reject_reason": None}
    reason = str(record.get("invalid_reason") or "").strip()
    return {
        "accepted": False,
        "reject_reason": reason or "it does not describe a workplace safety incident",
    }