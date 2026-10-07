import os
import json
import hashlib
import logging
from datetime import datetime

import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Tried in order. Each model has its own free-tier quota, so if one is out
# of quota, overloaded or times out, the next one is tried.
AI_SEED = 42

GEMINI_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_SEARCH_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

# Lennart
def _get_gemini_client():
    try:
        return genai.Client(http_options={"retry_options": {"attempts": 1}, "timeout": 25000})
    except Exception:
        return None

# Lennart
def _parse_json_safe(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned)

def _call_gemini(client, prompt):
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )
    return response.text

def _validate_schema(data, required_fields):
    if not isinstance(data, dict):
        return False
    for field in required_fields:
        if field not in data:
            return False
    return True

# Every incident in this system is on a Singapore construction site, so the
# weather API is called for Singapore regardless of which site logged the
# incident. Keeps the weather call simple instead of geocoding free-text
# site names.
_SG_LATITUDE = 1.3521
_SG_LONGITUDE = 103.8198

HAZARD_CATEGORIES = (
    "fall", "fall_from_height", "electrical", "chemical", "vehicular",
    "struck_by_machinery", "low_visibility", "other",
)
INJURY_SEVERITIES = ("none", "minor", "serious", "fatal", "unspecified")

# Lennart
def extract_hazard_context_flags(description):
    defaults = {
        "hazard_category": None,
        "injury_severity": "unspecified",
        "working_at_height": False,
        "height_estimate_m": None,
        "heavy_machinery_present": False,
        "ppe_status": "unspecified",
        "context_flags_error": None,
    }

    client = _get_gemini_client()
    if client is None:
        result = dict(defaults)
        result["context_flags_error"] = "Gemini client unavailable"
        return result

    required_fields = [
        "hazard_category",
        "injury_severity",
        "working_at_height",
        "heavy_machinery_present",
        "ppe_status",
    ]

    prompt = (
        "Read this workplace safety incident description and reply with "
        "only a JSON object, no other text.\n\n"
        f"Description: \"{description}\"\n\n"
        f"hazard_category: one of {list(HAZARD_CATEGORIES)}.\n"
        f"injury_severity: one of {list(INJURY_SEVERITIES)}.\n"
        "working_at_height: true only if someone was working on or fell "
        "from an elevated position.\n"
        "height_estimate_m: a number if a height is stated, otherwise null.\n"
        "heavy_machinery_present: true if a crane, excavator, forklift, "
        "generator or conveyor is mentioned.\n"
        "ppe_status: one of 'worn', 'not_worn', 'unspecified'."
    )

    try:
        parsed = _parse_json_safe(_call_gemini(client, prompt))
        if not _validate_schema(parsed, required_fields):
            raise ValueError("Gemini reply was missing required fields")
        if parsed["hazard_category"] not in HAZARD_CATEGORIES:
            raise ValueError("invalid hazard_category")

        result = dict(defaults)
        result["hazard_category"] = parsed["hazard_category"]
        if parsed.get("injury_severity") in INJURY_SEVERITIES:
            result["injury_severity"] = parsed["injury_severity"]
        if isinstance(parsed.get("working_at_height"), bool):
            result["working_at_height"] = parsed["working_at_height"]
        if isinstance(parsed.get("height_estimate_m"), (int, float)):
            result["height_estimate_m"] = parsed["height_estimate_m"]
        if isinstance(parsed.get("heavy_machinery_present"), bool):
            result["heavy_machinery_present"] = parsed["heavy_machinery_present"]
        if parsed.get("ppe_status") in ("worn", "not_worn", "unspecified"):
            result["ppe_status"] = parsed["ppe_status"]
        return result

    except Exception as error:
        result = dict(defaults)
        result["context_flags_error"] = f"AI extraction failed: {error}"
        return result

_WEATHER_KEYWORDS = (
    "rain", "wet", "storm", "wind", "windy", "flood", "lightning",
    "thunder", "haze", "hot", "heat", "humid",
)

def is_weather_relevant(record):
    """Checks hazard keywords in the description to decide if weather
    context matters. Simple keyword match — skips the API call otherwise."""
    description = record.get("description", "").lower()
    return any(keyword in description for keyword in _WEATHER_KEYWORDS)

#daniel
def get_time_of_day(timestamp):
    try:
        hour = datetime.fromisoformat(timestamp).hour
    except (TypeError, ValueError):
        return "day"
    if 7 <= hour < 18:
        return "day"
    if 18 <= hour < 20 or 5 <= hour < 7:
        return "dusk_dawn"
    return "night"

def call_weather_api(location):
    """Calls Open-Meteo (free, no key needed) for current Singapore weather.
    Returns a dict or None on failure — never raises uncaught."""
    try:
        response = requests.get(
            "[https://api.open-meteo.com/v1/forecast](https://api.open-meteo.com/v1/forecast)",
            params={
                "latitude": _SG_LATITUDE,
                "longitude": _SG_LONGITUDE,
                "current": "temperature_2m,relative_humidity_2m,precipitation",
                "timezone": "Asia/Singapore",
            },
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        current = data.get("current", {})
        precipitation = current.get("precipitation", 0) or 0
        return {
            "condition": "rain" if precipitation > 0 else "clear",
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
        }
    except Exception:
        return None

def validate_weather_response(response):
    """Checks condition, temperature_c, humidity_pct are present and
    sensible."""
    if not isinstance(response, dict):
        return False
    condition = response.get("condition")
    temperature_c = response.get("temperature_c")
    humidity_pct = response.get("humidity_pct")
    if condition not in ("rain", "clear"):
        return False
    if not isinstance(temperature_c, (int, float)) or not (-10 <= temperature_c <= 50):
        return False
    if not isinstance(humidity_pct, (int, float)) or not (0 <= humidity_pct <= 100):
        return False
    return True

def classify_lighting_condition(time_of_day, condition):
    """One step darker than time_of_day if weather cuts visibility. Reads
    condition from Darrel's own weather response. Never returns None."""
    levels = ["daylight", "low_light", "dark"]
    base = {"day": 0, "dusk_dawn": 1, "night": 2}.get(time_of_day, 0)
    if condition == "rain":
        base += 1
    base = min(base, len(levels) - 1)
    return levels[base]

def find_similar_incidents(record, history_records=None):
    return []

def _extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None

WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "industry_context": {"type": "string"},
        "incidents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "location": {"type": "string"},
                    "date": {"type": "string"},
                    "action_taken": {"type": "string"},
                    "source_url": {"type": "string"},
                },
                "required": ["summary", "location", "date", "action_taken", "source_url"],
            },
        },
    },
    "required": ["industry_context", "incidents"],
}

def search_web_for_similar_incidents(record):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in .env")

    prompt = (
        "A workplace safety incident was just reported on a construction site "
        "in Singapore:\n"
        f"\"{record.get('description', '')}\"\n"
        f"Hazard type: {record.get('hazard_category') or 'unknown'}\n\n"
        "Search the web, then write for site managers with no technical "
        "background: plain English, short sentences, no jargon.\n"
        "1. industry_context: 2-3 sentences. Is this a known, common problem in "
        "the construction industry (use Singapore figures from MOM or the WSH "
        "Council if you find them), and what is the usual way companies fix it?\n"
        "2. incidents: up to 3 REAL, publicly reported incidents with the same "
        "kind of hazard. Prefer Singapore (MOM, WSH Council, Straits Times, "
        "CNA); use other countries only if you find no Singapore ones. Only "
        "include incidents you found a source for - never invent one. For "
        "each, say what was done afterwards to fix or punish it.\n\n"
        "Reply with ONLY this JSON object, no other text:\n"
        '{"industry_context": "...", "incidents": [{"summary": "one sentence on '
        'what happened", "location": "place, country", "date": "YYYY or YYYY-MM '
        'or unknown", "action_taken": "what was done afterwards, or unknown", '
        '"source_url": "https://..."}]}\n'
        "If you find no incidents, use an empty list for incidents."
    )

    # Assuming _cache_key and _RESPONSE_CACHE are defined elsewhere or imported
    # cache_key = _cache_key("groq", prompt)
    # if cache_key in _RESPONSE_CACHE:
    #     return _RESPONSE_CACHE[cache_key]

    last_error = None
    for model in GROQ_SEARCH_MODELS:
        try:
            response = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": [{"type": "browser_search"}],
                    "tool_choice": "required",
                    "reasoning_effort": "low",
                    "max_completion_tokens": 4096,
                    "temperature": 0.2,
                    "seed": AI_SEED,
                },
                timeout=60,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"].get("content") or ""
            parsed = _extract_json_object(content)
            if parsed is None:
                raise ValueError("Groq reply had no JSON object")
            
            # _validate_json_schema is called here, make sure it is defined elsewhere
            # _validate_json_schema(parsed, WEB_SEARCH_SCHEMA)

            # Drop incidents without a real web link — they can't be checked.
            incidents = [
                {key: item[key].strip() for key in WEB_SEARCH_SCHEMA["properties"]["incidents"]["items"]["required"]}
                for item in parsed["incidents"][:3]
                if item["source_url"].startswith(("http://", "https://")) and item["summary"].strip()
            ]

            return {
                "industry_context": parsed["industry_context"].strip() or None,
                "incidents": incidents,
            }
        except Exception as error:
            last_error = error
    raise RuntimeError(f"Groq web search failed; last error: {last_error}")

def review_step(record):
    return {
        "monsoon_season": "inter_monsoon",
        "review_likely_causes": None,
        "review_prevention_actions": None,
        "review_error": None,
    }

# Lennart
def enrich_record(record):
    enriched = dict(record)
    weather_relevant = is_weather_relevant(record)

    if weather_relevant:
        raw_weather = call_weather_api(record.get("location", ""))
        if raw_weather is not None and validate_weather_response(raw_weather):
            enriched["weather_available"] = True
            enriched["condition"] = raw_weather["condition"]
            enriched["temperature_c"] = raw_weather["temperature_c"]
            enriched["humidity_pct"] = raw_weather["humidity_pct"]