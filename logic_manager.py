import re
from datetime import datetime

# Daniel
# OUTCOME_ACTIONS and SEVERITY_LEVELS are only here because main.py still reads them from logic_manager;
# drop them (and the noqa) once main.py imports them from logic_rules.constants.
from logic_rules.constants import (  # noqa: F401
    HIGH_SEVERITY,
    INJURY_MIN_SEVERITY,
    MAX_SEVERITY,
    OUTCOME_ACTIONS,
    SEVERITY_LEVELS,
    SYSTEMIC_INCIDENT_COUNT,
)
from logic_rules.log_only_rule import LogOnlyRule
from logic_rules.outcome_rule import OutcomeRule
from logic_rules.pending_review_rule import PendingReviewRule
from logic_rules.photo_mismatch_rule import PhotoMismatchRule
from logic_rules.stop_work_rule import StopWorkRule
from logic_rules.systemic_risk_rule import SystemicRiskRule
from models.incident import Incident


# Sufi
class LogicManager:
    # Whole-word match only: "window" must not count as "wind", "constraint" as
    # "rain", or "shot" as "hot".
    _WEATHER_WORDS = re.compile(
        r"\b(rain|rains|raining|rainy|rained|wet|storm|storms|stormy|wind|winds|windy|"
        r"flood|floods|flooded|flooding|lightning|thunder|thunderstorm|thunderstorms|"
        r"haze|hazy|hot|heat|humid|humidity)\b",
        re.IGNORECASE,
    )

    # Daniel
    # MOM "Type A" hazard types: the ones with a higher fatality risk.
    _TYPE_A_HAZARDS = ("fall_from_height", "vehicular", "struck_by_machinery")
    _INJURY_POINTS = {"none": 0, "unspecified": 0, "first_aid": 1, "hospital": 2}
    _INJURY_LABELS = {"first_aid": "Minor injury, first aid only", "hospital": "Serious injury, hospital treatment"}
    _ESCALATED_OUTCOMES = ("stop_work_review", "systemic_escalation")
    _POOR_LIGHT_LEVELS = ("dark", "low_light")


    _HEAVY_MACHINERY_WORDS = (
        "crane", "excavator", "forklift", "generator", "conveyor", "bulldozer",
        "backhoe", "digger", "loader", "grader", "compactor", "road roller",
        "crusher", "tractor", "truck", "lorry", "dumper", "tipper", "bobcat",
        "skid steer", "telehandler", "paver", "trencher", "concrete pump",
        "cement mixer", "piling", "pile driver", "drill rig", "hoist",
        "scissor lift", "boom lift", "mewp", "elevating work platform",
    )


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


    # Daniel
    # Singapore's monsoon season for the incident date; an unreadable timestamp gives 'inter_monsoon'.
    def get_monsoon_season(timestamp: str | None) -> str:
        try:
            when = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            return "inter_monsoon"
        if when.month in (12, 1, 2) or (when.month == 3 and when.day <= 15):
            return "northeast_monsoon"
        if 6 <= when.month <= 9:
            return "southwest_monsoon"
        return "inter_monsoon"


    # Darrel
    # True if the description mentions weather, so the weather API should be called.
    def is_weather_relevant(self, record: dict) -> bool:
        return bool(self._WEATHER_WORDS.search(str(record.get("description", ""))))


    # Decides which optional lookups to run: weather when it matters, otherwise similar past incidents.
    def plan_enrichment(self, record: dict) -> dict:
        relevant = self.is_weather_relevant(record)
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
    def derive_context(self, incident: dict) -> dict:
        result = dict(incident)
        result["weather_relevant"] = self.is_weather_relevant(incident)
        result.update(self.plan_enrichment(incident))
        result["time_of_day"] = self.get_time_of_day(incident.get("timestamp"))
        result["monsoon_season"] = self.get_monsoon_season(incident.get("timestamp"))
        return result


    # Adds lighting_condition from the time of day and the weather; returns a new dict.
    def apply_lighting(self, enriched: dict) -> dict:
        lit = dict(enriched)
        lit["lighting_condition"] = self.classify_lighting_condition(
            enriched.get("time_of_day", "day"), enriched.get("condition")
        )
        return lit


    # The non-empty strings in a list, stripped and lower-cased; anything else is ignored.
    def _text_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]


    # Adds working_at_height and heavy_machinery_present from the AI's elevated-place and equipment lists; returns a new dict.
    def apply_hazard_rules(self, enriched: dict) -> dict:
        result = dict(enriched)
        equipment = self._text_list(enriched.get("equipment_mentioned"))
        places = self._text_list(enriched.get("elevated_places"))
        result["working_at_height"] = bool(places)
        result["heavy_machinery_present"] = any(
            word in name for name in equipment for word in self._HEAVY_MACHINERY_WORDS
        )
        return result


    # Daniel
    # Starting severity and its reasons from what happened to the person (5 if someone died).
    def _score_injury(self, record: dict) -> tuple[int, list[str]]:
        treatment = record.get("injury_treatment", "unspecified")
        if treatment == "died":
            return MAX_SEVERITY, ["Someone died (set to 5)"]
        severity, reasons = 1, []
        points = self._INJURY_POINTS.get(treatment, 0)
        if points:
            severity += points
            reasons.append(f"{self._INJURY_LABELS[treatment]} (+{points})")
        if record.get("injury") and treatment in ("none", "unspecified"):
            severity += 1
            reasons.append("Someone was hurt, but how badly wasn't described (+1)")
        return severity, reasons


    # Daniel
    # Points added or removed by the hazard type and the site conditions, with a reason for each.
    def _score_conditions(self, record: dict, similar_escalated: bool) -> tuple[int, list[str]]:
        at_height = record.get("working_at_height")
        machinery = record.get("heavy_machinery_present")
        ppe_not_worn = record.get("ppe_status") == "not_worn"
        checks = [
            (record.get("hazard_category") in self._TYPE_A_HAZARDS, 1, "One of MOM's highest-risk hazard types"),
            (at_height, 1, "Working at height"),
            (machinery and ppe_not_worn, 1, "Heavy machinery around, without safety gear"),
            (ppe_not_worn, 1, "Safety gear (PPE) not worn"),
            (record.get("ppe_status") == "worn", -1, "Safety gear (PPE) was worn"),
            (record.get("lighting_condition") in self._POOR_LIGHT_LEVELS, 1, "Poor lighting or dark"),
            (record.get("condition") == "rain" and (at_height or machinery), 1,
            "Raining during work at height or with machinery"),
            (similar_escalated, 1, "A similar past incident on our sites was escalated"),
        ]
        change, reasons = 0, []
        for applies, points, text in checks:
            if applies:
                change += points
                reasons.append(f"{text} ({points:+d})")
        return change, reasons


    # Daniel
    # 'low', 'medium' or 'high' chance of this kind of incident happening again.
    def _recurrence_level(self, severity: int, record: dict, history: list, similar_escalated: bool) -> str:
        if severity >= HIGH_SEVERITY or len(history) >= SYSTEMIC_INCIDENT_COUNT or similar_escalated:
            return "high"
        if record.get("lighting_condition") in self._POOR_LIGHT_LEVELS or history:
            return "medium"
        return "low"


    # Daniel
    # Scores the incident (hazard type, severity 1-5, recurrence, reasons); sets assessment_error instead of guessing if the AI failed.
    # weather_data is no longer read (rain comes from the record's own condition); it stays only so the current
    # main.py call keeps working, and goes when this moves into LogicManager. Returns a new dict.
    def assess_severity(self, record: dict, weather_data: dict | None = None, history: list | None = None) -> dict:
        history = history or []
        result = dict(record)
        if record.get("context_flags_error") or record.get("hazard_category") is None:
            result.update({
                "hazard_type": "unassessed", "severity_estimate": 0,
                "likelihood_recurrence": "unknown", "severity_reasons": [],
                "assessment_error": ("Cannot judge severity without AI hazard extraction: "
                                    f"{record.get('context_flags_error') or 'hazard_category missing'}"),
            })
            return result
        similar = record.get("similar_incidents") or []
        similar_escalated = any(item.get("outcome") in self._ESCALATED_OUTCOMES for item in similar)
        severity, reasons = self._score_injury(record)
        change, more_reasons = self._score_conditions(record, similar_escalated)
        severity = max(1, min(severity + change, self.MAX_SEVERITY))
        injured = record.get("injury") or record.get("injury_treatment") in ("first_aid", "hospital", "died")
        if injured and severity < self.INJURY_MIN_SEVERITY:
            severity = self.INJURY_MIN_SEVERITY
            reasons.append(f"Someone was injured, so severity is at least {self.INJURY_MIN_SEVERITY}")
        result.update({
            "hazard_type": record.get("hazard_category"),
            "severity_estimate": severity,
            "likelihood_recurrence": self._recurrence_level(severity, record, history, similar_escalated),
            "severity_reasons": reasons + more_reasons,
            "assessment_error": None,
        })
        return result


    # Darrel
    # Rule 1: severity 4 or more, or an injury with high recurrence likelihood.
    def is_high_severity(record: dict) -> bool:
        severity = record.get("severity_estimate", 0)
        injury = record.get("injury", False)
        recurrence = record.get("likelihood_recurrence", "unknown")
        return severity >= HIGH_SEVERITY or (injury and recurrence == "high")


    # Sufi
    # Picks the outcome in order: pending_review, stop_work_review, systemic_escalation, log_only.
    def decide_outcome(self, incident: Incident, history: list) -> str:
        for rule in self._rules:
            if rule.applies(incident, history):
                incident.update({"outcome": rule.outcome})
                return rule.outcome
        incident.update({"outcome": "pending_review"})
        return "pending_review"


    # Sufi
    # Rejects an incident only when the AI said it is not a real safety incident; accepts it if the AI is down.
    @staticmethod
    def screen_incident(incident: Incident) -> tuple[bool, str | None]:
        if incident.get("is_valid_incident") is not False:
            return True, None
        reason = str(incident.get("invalid_reason") or "").strip()
        return False, reason or "it does not describe a workplace safety incident"


    # Sufi
    # The Part 1 rules plus the Part 2 photo rule, in the order they are checked.
    @staticmethod
    def default_rules() -> list[OutcomeRule]:
        return [PendingReviewRule(), StopWorkRule(), PhotoMismatchRule(), SystemicRiskRule(), LogOnlyRule()]


    # Sufi
    # Keeps the rule objects it is given (aggregation: the rules exist on their own and can be reused).
    def __init__(self, rules: list[OutcomeRule]) -> None:
        self._rules = list(rules)


    # Sufi
    # New in Part 2: fills gaps in the description with what the AI saw in the photo, and lists each change.
    def apply_photo_evidence(self, incident: Incident) -> None:
        if not incident.get("photo_analysed"):
            return
        notes = []
        photo_ppe = incident.get("photo_ppe_status")
        if incident.get("ppe_status") == "unspecified" and photo_ppe in ("worn", "not_worn"):
            incident.update({"ppe_status": photo_ppe})
            notes.append(f"Safety gear status taken from the photo ({photo_ppe.replace('_', ' ')})")
        if incident.get("photo_shows_height") and not incident.get("working_at_height"):
            incident.update({"working_at_height": True})
            notes.append("The photo shows work at height")
        if incident.get("photo_shows_machinery") and not incident.get("heavy_machinery_present"):
            incident.update({"heavy_machinery_present": True})
            notes.append("The photo shows heavy machinery")
        incident.update({"photo_evidence_used": notes})