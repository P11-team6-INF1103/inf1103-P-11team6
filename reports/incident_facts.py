# Daniel
from datetime import date, datetime


class IncidentFacts:
    # Reads the few values the report needs out of an incident dict, tolerating missing or odd data.

    # What an incident's severity is for averaging: None when the AI could not assess it.
    @staticmethod
    def severity(incident: dict) -> int | None:
        if incident.get("assessment_error"):
            return None
        value = incident.get("severity_estimate")
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    # The severities of the incidents that have one.
    @staticmethod
    def scores(incidents: list[dict]) -> list[int]:
        return [s for s in map(IncidentFacts.severity, incidents) if s is not None]

    @staticmethod
    def average(values: list[int]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    # The calendar day of an incident, or None when its timestamp cannot be read.
    @staticmethod
    def day(incident: dict) -> date | None:
        try:
            return datetime.fromisoformat(str(incident.get("timestamp"))).date()
        except ValueError:
            return None
