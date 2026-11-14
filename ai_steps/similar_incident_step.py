# Sufi

import json

from ai_clients.gemini_client import GeminiClient
from ai_steps.enrichment_step import EnrichmentStep
from models.incident import Incident


class SimilarIncidentStep(EnrichmentStep):
    name = "Similar-incidents lookup"
    SCHEMA = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "resolution_notes": {"type": "string"}},
            "required": ["id", "resolution_notes"],
        },
    }

    def __init__(self, gemini: GeminiClient, outcome_meanings: dict) -> None:
        self._gemini = gemini
        self._outcome_meanings = outcome_meanings

    # Only when weather is not relevant (the same rule as Part 1).
    def should_run(self, incident: Incident) -> bool:
        return bool(incident.get("run_similar"))

    def skipped_fields(self) -> dict:
        return {"similar_incidents_checked": False, "similar_incidents": None, "similar_incidents_error": None}

    # Builds the prompt asking which past incidents share the new incident's hazard.
    def build_prompt(self, incident: Incident, recent: list[Incident]) -> str:
        candidates = [
            {"id": i, "description": r.description, "hazard_type": r.get("hazard_type", "unknown"),
             "outcome": r.get("outcome", "unknown")}
            for i, r in enumerate(recent)
        ]
        return (
            f"Here is a new workplace safety incident:\n\"{incident.description}\"\n\n"
            f"Here are past incidents (JSON):\n{json.dumps(candidates)}\n\n"
            "Return a JSON array with the id of each past incident that shares a "
            "similar hazard signature with the new one (same kind of hazard). If "
            "none are similar, return an empty array. For each match, add a "
            "one-sentence resolution_notes saying what its recorded outcome means "
            "was done on site. What each recorded outcome means (JSON): "
            f"{json.dumps(self._outcome_meanings, sort_keys=True)}"
        )

    # Asks Gemini which of the last 10 saved incidents are similar; the facts come from the saved records, not the AI.
    def run(self, incident: Incident, history: list[Incident]) -> dict:
        result = {"similar_incidents_checked": True, "similar_incidents": [], "similar_incidents_error": None}
        recent = history[-10:]
        if not recent:
            return result
        parsed = self._gemini.ask_json(self.build_prompt(incident, recent), self.SCHEMA)
        seen = set()
        for item in parsed:
            index = item["id"]
            if not 0 <= index < len(recent) or index in seen:
                continue
            seen.add(index)
            saved = recent[index]
            result["similar_incidents"].append({
                "description": saved.description, "location": saved.location,
                "timestamp": saved.timestamp, "hazard_type": saved.get("hazard_type", "unknown"),
                "outcome": saved.get("outcome", "unknown"), "resolution_notes": item["resolution_notes"],
            })
        return result

    def error_fields(self, message: str) -> dict:
        return {"similar_incidents_checked": True, "similar_incidents": None,
                "similar_incidents_error": f"Similar-incidents lookup failed: {message}"}
