import hashlib
import json
import logging
import os
import threading

import requests

from models import IncidentPhoto

# Ren Xiang
logger = logging.getLogger(__name__)

# Fixed seed so the same input gives the same answer as far as the model allows.
AI_SEED = 42 

# Ren Xiang
class ResponseCache:
    # Validated AI and weather replies already received, keyed by a hash of the request.
    # The same incident then gets the same answer on every run, and a re-run costs no API quota.
    # The lock keeps it safe when the evidence steps run in parallel threads.
    def __init__(self, saved: dict | None = None) -> None:
        self.__entries = dict(saved) if isinstance(saved, dict) else {}
        self.__lock = threading.Lock()

    # Builds the cache key for a request: its kind plus a hash of its parts.
    @staticmethod
    def make_key(kind: str, *parts: str) -> str:
        return kind + ":" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get(self, key: str) -> object:
        with self.__lock:
            return self.__entries.get(key)

    def put(self, key: str, value: object) -> None:
        with self.__lock:
            self.__entries[key] = value

    # A copy of every entry so the data manager can save it.
    def export(self) -> dict:
        with self.__lock:
            return dict(self.__entries)


# Ren Xiang
class JsonReply:
    # Turns AI reply text into checked JSON. Every reply goes through here before any field is used.

    _TYPE_CHECKS = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }

    # Parses a JSON reply after stripping any ```json fence; raises ValueError if it is not JSON.
    @staticmethod
    def parse(text: str) -> object:
        cleaned = str(text).strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned)

    # Pulls the first {...} object out of a reply that has other text around it, or returns None.
    @staticmethod
    def extract_object(text: str) -> dict | None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None

    # Checks parsed JSON against a schema (types, enums, required keys); raises ValueError on a mismatch.
    @classmethod
    def validate(cls, data: object, schema: dict, path: str = "response") -> None:
        allowed = schema.get("type")
        if allowed is not None:
            allowed = allowed if isinstance(allowed, list) else [allowed]
            if not any(cls._TYPE_CHECKS[t](data) for t in allowed):
                raise ValueError(f"{path}: expected {' or '.join(allowed)}, got {type(data).__name__}")
        if "enum" in schema and data not in schema["enum"]:
            raise ValueError(f"{path}: {data!r} is not one of {schema['enum']}")
        if isinstance(data, dict):
            for key in schema.get("required", []):
                if key not in data:
                    raise ValueError(f"{path}: missing required field '{key}'")
            for key, sub_schema in schema.get("properties", {}).items():
                if key in data:
                    cls.validate(data[key], sub_schema, f"{path}.{key}")
        if isinstance(data, list) and "items" in schema:
            for index, item in enumerate(data):
                cls.validate(item, schema["items"], f"{path}[{index}]")


# Ren Xiang
class GeminiClient:
    # Tried in order. Each model has its own free-tier quota, so if one fails the next is tried.
    MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest")

    # Shares the cache it is given with the other clients (association).
    def __init__(self, cache: ResponseCache, sdk_client: object | None = None) -> None:
        self._cache = cache
        self._sdk_client = sdk_client

    # Creates the Google SDK client the first time it is needed; raises RuntimeError if there is no API key.
    def _client(self) -> object:
        if self._sdk_client is None:
            if not os.getenv("GEMINI_API_KEY"):
                raise RuntimeError("Gemini client unavailable (check GEMINI_API_KEY)")
            from google import genai
            self._sdk_client = genai.Client(http_options={"retry_options": {"attempts": 1}, "timeout": 25000})
        return self._sdk_client

    # The request body: just the prompt, or the prompt plus the photo as an image part.
    @staticmethod
    def _build_input(prompt: str, photo: IncidentPhoto | None) -> object:
        if photo is None:
            return prompt
        return [
            {"type": "text", "text": prompt},
            {"type": "image", "data": photo.as_base64(), "mime_type": photo.mime_type},
        ]

    # Sends the request to each model in turn and returns the first reply text; raises if all fail.
    def _call(self, prompt: str, schema: dict, photo: IncidentPhoto | None) -> str:
        client = self._client()
        last_error = None
        for model in self.MODELS:
            try:
                interaction = client.interactions.create(
                    model=model,
                    input=self._build_input(prompt, photo),
                    response_format={"type": "text", "mime_type": "application/json", "schema": schema},
                    generation_config={"seed": AI_SEED},
                )
                return interaction.output_text
            except Exception as error:
                logger.warning("Gemini model %s failed: %s", model, error)
                last_error = error
        raise RuntimeError(f"All Gemini models failed; last error: {last_error}")

    # Returns a schema-valid JSON reply, from the cache if possible, asking again once if it is malformed.
    def ask_json(self, prompt: str, schema: dict, photo: IncidentPhoto | None = None) -> object:
        photo_id = photo.fingerprint() if photo else ""
        key = ResponseCache.make_key("gemini", prompt, json.dumps(schema, sort_keys=True), photo_id)
        cached = self._cache.get(key)
        if cached is not None:
            try:
                parsed = JsonReply.parse(cached)
                JsonReply.validate(parsed, schema)
                return parsed
            except ValueError:
                pass
        last_error = None
        for _attempt in range(2):
            text = self._call(prompt, schema, photo)
            try:
                parsed = JsonReply.parse(text)
                JsonReply.validate(parsed, schema)
            except ValueError as error:
                logger.warning("Malformed Gemini reply: %s", error)
                last_error = error
                continue
            self._cache.put(key, text)
            return parsed
        raise ValueError(f"Gemini reply was malformed twice: {last_error}")
