import os
import json
from datetime import datetime

import requests
from dotenv import load_dotenv
from google import genai
import INF1103_Project_Folders.inf1103secret.data_manager as data_manager

load_dotenv()

AI_SEED = 42

GEMINI_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_SEARCH_MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

_SG_LATITUDE = 1.3521
_SG_LONGITUDE = 103.8198

HAZARD_CATEGORIES = (
    "fall", "fall_from_height", "electrical", "chemical", "vehicular",
    "struck_by_machinery", "low_visibility", "other",
)
INJURY_SEVERITIES = ("none", "minor", "serious", "fatal", "unspecified")

_WEATHER_KEYWORDS = (
    "rain", "wet", "storm", "wind", "windy", "flood", "lightning",
    "thunder", "haze", "hot", "heat", "humid",
)

def is_weather_relevant(record):
    """Checks hazard keywords in the description to decide if weather
    context matters. Simple keyword match — skips the API call otherwise."""
    description = record.get("description", "").lower()
    return any(keyword in description for keyword in _WEATHER_KEYWORDS)


def call_weather_api(location):
    """Calls Open-Meteo (free, no key needed) for current Singapore weather.
    Returns a dict or None on failure — never raises uncaught."""
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
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

def search_web_for_similar_incidents(record):
    """Runs for every incident. Asks Groq (GPT-OSS + browser_search) to
    search the internet for (a) whether this kind of hazard is a known
    problem in the construction industry and how it is usually fixed, and
    (b) up to 3 real reported incidents with the same hazard and what was
    done afterwards, preferring Singapore. The reply is validated against
    WEB_SEARCH_SCHEMA before use. Returns {"industry_context": str,
    "incidents": list[dict]}. Raises on an actual failure (no
    GROQ_API_KEY, API error, reply that fails the schema) so
    enrich_record() can record web_search_error."""
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
            _validate_schema(parsed, WEB_SEARCH_SCHEMA)

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

