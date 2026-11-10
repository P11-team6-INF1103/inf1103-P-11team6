# Darrel
import io
import os

import pytest

from ai_clients.response_cache import ResponseCache
from ai_manager import AIManager
from ai_steps.hazard_flag_step import HazardFlagStep
from data_manager import DataManager
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from tests.doubles.fake_gemini import FakeGemini
from tests.doubles.fake_search import FakeSearch
from tests.doubles.fake_weather import FakeWeather
from tests.fakes import HAZARD_REPLY
from web_api import WebApi
from web_support.rate_limiter import RateLimiter

SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")
FORM = {"description": "Scaffold plank fell from level 4 near a worker", "location": "Site B",
        "reporter_role": "safety_officer", "injury": "true"}
