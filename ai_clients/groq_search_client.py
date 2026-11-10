# Darrel
import logging
import os

import requests

from ai_clients.constants import AI_SEED
from ai_clients.json_reply import JsonReply
from ai_clients.response_cache import ResponseCache

logger = logging.getLogger(__name__)


class GroqSearchClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"
    # Groq models with the built-in browser_search tool, tried in order.
    MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")

    def __init__(self, cache: ResponseCache) -> None:
        self._cache = cache

    # Makes one browser-search call with one model and returns its schema-valid JSON reply.
    def _call(self, model: str, prompt: str, schema: dict, api_key: str) -> dict:
        response = requests.post(
            self.URL,
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
        parsed = JsonReply.extract_object(content)
        if parsed is None:
            raise ValueError("Groq reply had no JSON object")
        JsonReply.validate(parsed, schema)
        return parsed
