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


def test_create_with_photo_then_list_get_photo_and_delete(client):
    response = upload(client, photo_bytes=sample_bytes())
    assert response.status_code == 201
    created = response.get_json()
    assert created["id"] == 1 and created["has_photo"] and created["outcome"] == "stop_work_review"
    assert "photo_saved_path" not in created  # server paths never reach the browser
    assert len(client.get("/api/incidents").get_json()) == 1
    assert client.get("/api/incidents/1/photo").data == sample_bytes()
    assert client.delete("/api/incidents/1").status_code == 200
    assert client.get("/api/incidents").get_json() == []
    assert client.get("/api/incidents/1").status_code == 404


def test_bad_form_and_fake_photo_are_rejected_with_reasons(client):
    response = upload(client, form={**FORM, "description": "???", "injury": "maybe"},
                      photo_bytes=b"not an image", name="fake.jpg")
    errors = response.get_json()["errors"]
    assert response.status_code == 422 and len(errors) == 3
    assert any("not a real image" in e for e in errors)


def test_ai_rejection_is_returned_to_the_browser(tmp_path):
    gemini = FakeGemini(replies={id(HazardFlagStep.SCHEMA): {**HAZARD_REPLY, "is_valid_incident": False,
                                                             "invalid_reason": "This is test text."}})
    response = upload(make_client(tmp_path, gemini))
    assert response.status_code == 422 and response.get_json()["rejected"] == "This is test text."


def test_json_body_without_photo_works(client):
    response = client.post("/api/incidents", json={**FORM, "injury": False})
    assert response.status_code == 201 and response.get_json()["has_photo"] is False


def test_location_list_and_query(client):
    upload(client)
    assert client.get("/api/locations").get_json() == [{"location": "Site B", "count": 1}]
    found = client.get("/api/locations/query?location=Site B&days=30").get_json()
    assert len(found) == 1 and found[0]["id"] == 1
    assert client.get("/api/locations/query?location=&days=x").status_code == 422


def test_rate_limit(tmp_path):
    client = make_client(tmp_path, post_limit=1)
    assert upload(client).status_code == 201
    assert upload(client).status_code == 429
    limiter = RateLimiter(limit=2)
    assert [limiter.too_many("a"), limiter.too_many("a"), limiter.too_many("a"), limiter.too_many("b")] == \
        [False, False, True, False]


def test_upload_from_bytes_is_checked_like_a_file():
    from models.incident_photo import IncidentPhoto
    from models.photo_error import PhotoError
    assert IncidentPhoto.from_bytes("a.png", sample_bytes()).mime_type == "image/png"
    with pytest.raises(PhotoError, match="5 MB"):
        IncidentPhoto.from_bytes("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * IncidentPhoto.MAX_BYTES)
