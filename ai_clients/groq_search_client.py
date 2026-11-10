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
