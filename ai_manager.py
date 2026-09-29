import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

AI_SEED = 42


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


HAZARD_CATEGORIES = (
    "fall",
    "fall_from_height",
    "electrical",
    "chemical",
    "vehicular",
    "struck_by_machinery",
    "low_visibility",
    "other",
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


def get_time_of_day(timestamp):
    return "day"


def classify_lighting_condition(time_of_day, condition):
    return "daylight"


def is_weather_relevant(record):
    return False


def call_weather_api(location):
    return None


def validate_weather_response(response):
    return False


def find_similar_incidents(record):
    return []


def search_web_for_similar_incidents(record):
    return {"industry_context": None, "incidents": []}


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
            enriched["enrichment_error"] = None
        else:
            enriched["weather_available"] = False
            enriched["condition"] = None
            enriched["temperature_c"] = None
            enriched["humidity_pct"] = None
            enriched["enrichment_error"] = "Weather data unavailable or invalid"
    else:
        enriched["weather_available"] = False
        enriched["condition"] = None
        enriched["temperature_c"] = None
        enriched["humidity_pct"] = None
        enriched["enrichment_error"] = None

    time_of_day = get_time_of_day(record.get("timestamp"))
    enriched["time_of_day"] = time_of_day
    enriched["lighting_condition"] = classify_lighting_condition(time_of_day, enriched["condition"])

    flags = extract_hazard_context_flags(record.get("description", ""))
    enriched["hazard_category"] = flags["hazard_category"]
    enriched["injury_severity"] = flags["injury_severity"]
    enriched["working_at_height"] = flags["working_at_height"]
    enriched["height_estimate_m"] = flags["height_estimate_m"]
    enriched["heavy_machinery_present"] = flags["heavy_machinery_present"]
    enriched["ppe_status"] = flags["ppe_status"]
    enriched["context_flags_error"] = flags["context_flags_error"]

    if not weather_relevant:
        enriched["similar_incidents_checked"] = True
        try:
            enriched["similar_incidents"] = find_similar_incidents(enriched)
            enriched["similar_incidents_error"] = None
        except Exception as error:
            enriched["similar_incidents"] = None
            enriched["similar_incidents_error"] = str(error)
    else:
        enriched["similar_incidents_checked"] = False
        enriched["similar_incidents"] = None
        enriched["similar_incidents_error"] = None

    try:
        web = search_web_for_similar_incidents(enriched)
        enriched["web_industry_context"] = web["industry_context"]
        enriched["web_incidents"] = web["incidents"]
        enriched["web_search_error"] = None
    except Exception as error:
        enriched["web_industry_context"] = None
        enriched["web_incidents"] = None
        enriched["web_search_error"] = str(error)

    enriched.update(review_step(enriched))

    return enriched
