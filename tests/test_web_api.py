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


def make_client(tmp_path, gemini=None, post_limit=10):
    ai = AIManager(gemini or FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                            LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path)), ResponseCache())
    return WebApi(app, ["http://localhost:5173"], post_limit).flask.test_client()


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def upload(client, form=FORM, photo_bytes=None, name="scene.png"):
    data = dict(form)
    if photo_bytes is not None:
        data["photo"] = (io.BytesIO(photo_bytes), name)
    return client.post("/api/incidents", data=data, content_type="multipart/form-data")


def sample_bytes():
    with open(SAMPLE_PHOTO, "rb") as f:
        return f.read()


def test_health_and_meta(client):
    assert client.get("/api/health").get_json()["status"] == "ok"
    meta = client.get("/api/meta").get_json()
    assert meta["severity_levels"]["5"]["name"] == "Critical" and "photo_review" in meta["outcome_names"]
