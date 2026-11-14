#Ren Xiang
from ai_clients.response_cache import ResponseCache
from ai_manager import (
    HazardFlagStep,
    PhotoAnalysisStep,
    ReviewStep,
    SimilarIncidentStep,
)

# Hard-coded sample AI replies, so the tests never call a live API.
HAZARD_REPLY = {
    "hazard_category": "fall_from_height", "injury_treatment": "hospital",
    "equipment_mentioned": ["scaffold"], "elevated_places": ["level 4 scaffold"],
    "height_estimate_m": 12, "ppe_status": "unspecified",
    "is_valid_incident": True, "invalid_reason": "",
}
PHOTO_REPLY = {
    "photo_matches_description": True, "photo_summary": "A scaffold with a worker without a helmet.",
    "photo_hazards_seen": ["no helmet", "unguarded edge"], "photo_ppe_status": "not_worn",
    "photo_shows_height": True, "photo_shows_machinery": False,
}
REVIEW_REPLY = {"likely_causes": ["Plank was not tied down."], "prevention_actions": ["Inspect scaffolds daily."]}
WEB_REPLY = {
    "industry_context": "Falls from height are the top cause of deaths in construction.",
    "incidents": [{"summary": "Worker fell from scaffold", "location": "Singapore", "date": "2025",
                   "action_taken": "Stop-work order", "source_url": "https://example.com/news"}],
}


class FakeGemini:
    # Stands in for GeminiClient: same ask_json() method, answers picked by which schema is asked for.
    def __init__(self, replies: dict | None = None, error: Exception | None = None) -> None:
        self.replies = {
            id(HazardFlagStep.SCHEMA): HAZARD_REPLY,
            id(PhotoAnalysisStep.SCHEMA): PHOTO_REPLY,
            id(ReviewStep.SCHEMA): REVIEW_REPLY,
            id(SimilarIncidentStep.SCHEMA): [],
        }
        self.replies.update(replies or {})
        self.error = error
        self.calls = []

    def ask_json(self, prompt: str, schema: dict, photo: object = None) -> object:
        self.calls.append({"prompt": prompt, "schema": schema, "photo": photo})
        if self.error:
            raise self.error
        return self.replies[id(schema)]


class FakeSearch:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def search_json(self, prompt: str, schema: dict, subject: str | None = None) -> dict:
        if self.error:
            raise self.error
        return WEB_REPLY


class FakeWeather:
    def __init__(self, weather: dict | None = None) -> None:
        self.weather = weather

    def get_weather(self, timestamp: str | None) -> dict | None:
        return self.weather


def empty_cache() -> ResponseCache:
    return ResponseCache()