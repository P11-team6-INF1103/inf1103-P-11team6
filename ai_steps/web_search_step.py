# Darrel
from ai_clients.groq_search_client import GroqSearchClient
from ai_steps.enrichment_step import EnrichmentStep
from models.incident import Incident


class WebSearchStep(EnrichmentStep):
    name = "Web search"
    SCHEMA = {
        "type": "object",
        "properties": {
            "industry_context": {"type": "string"},
            "incidents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {key: {"type": "string"} for key in
                                   ("summary", "location", "date", "action_taken", "source_url")},
                    "required": ["summary", "location", "date", "action_taken", "source_url"],
                },
            },
        },
        "required": ["industry_context", "incidents"],
    }

    def __init__(self, search: GroqSearchClient) -> None:
        self._search = search

    # Builds the prompt asking for industry context and real similar incidents.
    @staticmethod
    def build_prompt(incident: Incident) -> str:
        return (
            "A workplace safety incident was just reported on a construction site "
            f"in Singapore:\n\"{incident.description}\"\n"
            f"Hazard type: {incident.get('hazard_category') or 'unknown'}\n\n"
            "Search the web, then write for site managers with no technical "
            "background: plain English, short sentences, no jargon.\n"
            "1. industry_context: 2-3 sentences. Is this a known, common problem in "
            "the construction industry (use Singapore figures from MOM or the WSH "
            "Council if you find them), and what is the usual way companies fix it?\n"
            "2. incidents: up to 3 REAL, publicly reported incidents with the same "
            "kind of hazard. Prefer Singapore; use other countries only if you find "
            "none. Only include incidents you found a source for - never invent one.\n\n"
            "Reply with ONLY this JSON object, no other text:\n"
            '{"industry_context": "...", "incidents": [{"summary": "...", "location": '
            '"place, country", "date": "YYYY or YYYY-MM or unknown", "action_taken": '
            '"what was done afterwards, or unknown", "source_url": "https://..."}]}'
        )

    # Runs the Groq web search and keeps at most 3 incidents that have a summary and a web link.
    def run(self, incident: Incident, history: list[Incident]) -> dict:
        parsed = self._search.search_json(self.build_prompt(incident), self.SCHEMA, subject=incident.description)
        keys = self.SCHEMA["properties"]["incidents"]["items"]["required"]
        incidents = [
            {key: item[key].strip() for key in keys}
            for item in parsed["incidents"][:3]
            if item["source_url"].startswith(("http://", "https://")) and item["summary"].strip()
        ]
        return {"web_industry_context": parsed["industry_context"].strip() or None,
                "web_incidents": incidents, "web_search_error": None}

    def error_fields(self, message: str) -> dict:
        return {"web_industry_context": None, "web_incidents": None, "web_search_error": message}
