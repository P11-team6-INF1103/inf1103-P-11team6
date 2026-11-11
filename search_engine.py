# Daniel
import re


class IncidentSearch:
    # Ranked free-text search over incidents as the browser sees them (the dicts from WebApi._to_json).
    # Every search word must match somewhere (AND); a word matches the start of any word in a field.
    # "double quotes" search for an exact phrase, and #12 or 12 finds incident number 12.

    # How much a match in each field is worth.
    FIELD_WEIGHTS = {
        "description": 4.0, "location": 3.0, "hazard": 3.0, "causes": 1.5, "actions": 1.0,
        "reporter": 1.0, "resolution": 1.0, "photo": 0.5, "sources": 0.5,
    }
    _QUERY_PARTS = re.compile(r'"([^"]+)"|(\S+)')
    _WORD = re.compile(r"[a-z0-9]+")

    def __init__(self, hazard_names: dict[str, str] | None = None) -> None:
        self._hazard_names = hazard_names or {}

    def _fields(self, incident: dict) -> dict[str, str]:
        hazard = incident.get("hazard_type") or ""
        sources = " ".join(str(w.get("summary", "")) for w in incident.get("web_incidents") or [] if isinstance(w, dict))
        return {
            "description": str(incident.get("description") or ""),
            "location": str(incident.get("location") or ""),
            "hazard": f"{hazard} {self._hazard_names.get(hazard, '')} {incident.get('hazard_category') or ''}",
            "causes": " ".join(map(str, incident.get("review_likely_causes") or [])),
            "actions": " ".join(map(str, incident.get("review_prevention_actions") or [])),
            "reporter": f"{incident.get('reporter_role') or ''} {incident.get('reported_by') or ''}",
            "resolution": str(incident.get("resolution_note") or ""),
            "photo": " ".join(str(v) for v in (incident.get("photo_description"), incident.get("photo_findings")) if v),
            "sources": sources,
        }
