#Ren Xiang

import json

from ai_clients.gemini_client import GeminiClient
from ai_steps.enrichment_step import EnrichmentStep
from models.incident import Incident


class ReviewStep(EnrichmentStep):
    name = "After-action review"
    SCHEMA = {
        "type": "object",
        "properties": {
            "likely_causes": {"type": "array", "items": {"type": "string"}},
            "prevention_actions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["likely_causes", "prevention_actions"],
    }
    _CONTEXT_KEYS = (
        "injury", "hazard_category", "injury_treatment", "working_at_height",
        "heavy_machinery_present", "ppe_status", "time_of_day", "lighting_condition",
        "monsoon_season", "condition", "photo_summary", "photo_hazards_seen", "web_industry_context",
    )

    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    # Builds the prompt from everything gathered so far, including what the photo showed.
    def build_prompt(self, incident: Incident) -> str:
        context = {key: incident.get(key) for key in self._CONTEXT_KEYS}
        context["description"] = incident.description
        context["similar_past_incidents_on_site"] = [
            {"description": s.get("description"), "outcome": s.get("outcome")}
            for s in incident.get("similar_incidents") or []
        ]
        return (
            "You are helping a Singapore construction company write an after-action "
            f"review for a workplace safety incident. Everything recorded (JSON):\n{json.dumps(context)}\n\n"
            "Return:\nlikely_causes: 2-3 short sentences on why it most likely "
            "happened, based only on the facts above. Say 'possibly' where you infer.\n"
            "prevention_actions: 3-4 short, practical actions a site team could take "
            "to stop it happening again.\n"
            "Write for site managers with no technical background: plain English, no jargon.\n"
            "Do NOT rate the severity or say whether work should stop."
        )

    # Asks Gemini for advisory causes and prevention actions (never scored).
    def run(self, incident: Incident, history: list[Incident]) -> dict:
        parsed = self._gemini.ask_json(self.build_prompt(incident), self.SCHEMA)
        causes = [c.strip() for c in parsed["likely_causes"] if c.strip()]
        actions = [a.strip() for a in parsed["prevention_actions"] if a.strip()]
        if not causes or not actions:
            raise ValueError("AI response was missing causes or prevention actions")
        return {"review_likely_causes": causes[:3], "review_prevention_actions": actions[:4], "review_error": None}

    def error_fields(self, message: str) -> dict:
        return {"review_likely_causes": None, "review_prevention_actions": None,
                "review_error": f"AI review failed: {message}"}