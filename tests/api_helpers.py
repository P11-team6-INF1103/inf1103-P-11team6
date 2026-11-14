# Darrel
# Shared by the API-level tests (workflow, search): a test client.
from ai_clients.response_cache import ResponseCache
from ai_manager import AIManager
from data_manager import DataManager
from io_manager import IOManager
from logic_manager import LogicManager
from logic_rules.constants import OUTCOME_ACTIONS, SEVERITY_LEVELS
from main import IncidentTriageApp
from tests.doubles.fake_gemini import FakeGemini
from tests.doubles.fake_search import FakeSearch
from tests.doubles.fake_weather import FakeWeather
from web_api import WebApi

FORM = {"description": "Scaffold plank fell from level 4 near a worker", "location": "Site B",
        "reporter_role": "safety_officer", "injury": "true"}


def make_client(tmp_path):
    ai = AIManager(FakeGemini(), FakeSearch(), FakeWeather(None), OUTCOME_ACTIONS)
    app = IncidentTriageApp(IOManager(SEVERITY_LEVELS, OUTCOME_ACTIONS), ai,
                            LogicManager(LogicManager.default_rules()), DataManager(str(tmp_path)), ResponseCache())
    return WebApi(app, ["http://localhost:5173"], 50).flask.test_client()
