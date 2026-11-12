import json
import logging
import os

from ai_clients.constants import AI_SEED
from ai_clients.json_reply import JsonReply
from ai_clients.response_cache import ResponseCache
from models.incident_photo import IncidentPhoto

logger = logging.getLogger(__name__)


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
    # 'subject' is the incident text inside the prompt: a saved reply for a similarly worded subject is reused.
    def ask_json(self, prompt: str, schema: dict, photo: IncidentPhoto | None = None, subject: str | None = None) -> object:
        photo_id = photo.fingerprint() if photo else ""
        schema_text = json.dumps(schema, sort_keys=True)
        key = ResponseCache.make_key("gemini", prompt, schema_text, photo_id)
        scope = ResponseCache.make_scope("gemini", prompt, subject, schema_text, photo_id) if subject else None
        cached = self._cache.lookup(key, scope, subject)
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
            self._cache.remember(key, text, scope, subject)
            return parsed
        raise ValueError(f"Gemini reply was malformed twice: {last_error}")