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
