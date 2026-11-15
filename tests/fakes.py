#Ren Xiang
from ai_clients.response_cache import ResponseCache

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

def empty_cache() -> ResponseCache:
    return ResponseCache()