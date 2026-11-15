# Ren Xiang
import io
import json

import pytest

from ai_steps.site_plan_reader import SitePlanReader
from data_manager import DataManager
from models.incident_photo import IncidentPhoto
from site_plan.element_kind import ElementKind
from site_plan.element_kinds import ELEMENT_KINDS
from site_plan.site_element import SiteElement
from site_plan.site_plan import SitePlan
from site_plan.site_plan_error import SitePlanError
from tests.doubles.fake_gemini import FakeGemini
from tests.test_web_api import make_client, sample_bytes


def plan_dict(*elements, width=100, depth=60):
    return {"name": "Test site", "width_m": width, "depth_m": depth, "elements": list(elements)}


def block(**overrides):
    return {"type": "building", "name": "Block A", "x": 10, "y": 10, "w": 20, "d": 10, **overrides}


# ---------- element kinds (one class, many objects) ----------

def test_element_kind_is_data_not_a_class_per_kind():
    kind = ElementKind("hut", "Hut", "a hut", min_size_m=3.0)
    assert (kind.key, kind.min_size()) == ("hut", 3.0)


def test_every_kind_has_a_label_and_an_ai_hint():
    assert len(ELEMENT_KINDS) == 10
    for key, kind in ELEMENT_KINDS.items():
        assert kind.key == key and kind.hint and kind.label and kind.min_size() >= 1.0


# ---------- building a plan from a dict ----------

def test_round_trip_is_stable():
    first = SitePlan.from_dict(plan_dict(block(), block(name="Crane", type="tower_crane", x=60))).to_dict()
    assert SitePlan.from_dict(first).to_dict() == first
    assert [e["id"] for e in first["elements"]] == ["e1", "e2"]
    assert "height_m" not in first["elements"][0] and "floors" not in first["elements"][0]


@pytest.mark.parametrize("data", [None, [], "x", plan_dict(width=5), plan_dict(width="wide"), plan_dict(depth=99999),
                                  {"width_m": 50, "depth_m": 50, "elements": "none"}])
def test_unusable_site_is_rejected(data):
    with pytest.raises(SitePlanError):
        SitePlan.from_dict(data)


def test_unknown_type_becomes_an_area_with_a_warning():
    plan = SitePlan.from_dict(plan_dict(block(type="helipad")))
    assert plan.elements[0].kind.key == "zone" and "unknown type" in plan.warnings[0]


def test_elements_without_a_usable_rectangle_are_skipped():
    plan = SitePlan.from_dict(plan_dict(block(x="left"), "junk", block(w=None), block(name="Good")))
    assert [e.name for e in plan.elements] == ["Good"] and len(plan.warnings) == 3


def test_elements_are_kept_inside_the_site_and_given_a_minimum_size():
    plan = SitePlan.from_dict(plan_dict(block(x=95, y=-5, w=20, d=0.1), block(name="Huge", w=500, d=500)))
    first, huge = (e.rect for e in plan.elements)
    assert first[0] + first[2] <= 100 and first[1] == 0 and first[3] >= 4
    assert huge[2] == 100 and huge[3] == 60 and any("shrunk" in w for w in plan.warnings)


def test_only_a_crane_keeps_a_radius_and_a_bad_one_is_replaced():
    plan = SitePlan.from_dict(plan_dict(
        block(radius_m=40),
        {"type": "tower_crane", "name": "TC", "x": 5, "y": 5, "w": 3, "d": 3, "radius_m": 500},
        {"type": "tower_crane", "name": "TC2", "x": 20, "y": 5, "w": 3, "d": 3, "radius_m": 45},
    ))
    tower, bad, good = (e.to_dict("x") for e in plan.elements)
    assert "radius_m" not in tower and bad["radius_m"] == 30.0 and good["radius_m"] == 45.0


def test_element_count_is_capped():
    many = [block(name=f"B{i}") for i in range(SitePlan.MAX_ELEMENTS + 5)]
    plan = SitePlan.from_dict(plan_dict(*many))
    assert len(plan.elements) == SitePlan.MAX_ELEMENTS and "Only the first" in plan.warnings[0]


def test_plan_returns_copies_so_callers_cannot_change_it():
    plan = SitePlan.from_dict(plan_dict(block()))
    plan.elements.clear()
    plan.warnings.append("x")
    assert len(plan.elements) == 1 and plan.warnings == []


# ---------- matching incident locations to elements ----------

def test_location_matching_prefers_exact_names_then_aliases_then_partial():
    plan = SitePlan.from_dict(plan_dict(
        block(name="Block B", x=0), block(name="Block B scaffold", x=40, aliases=["Scaffold"]),
        block(name="Loading bay", x=70, y=40, aliases=["LB 1"])))
    assert plan.find_element("block b").name == "Block B"
    assert plan.find_element("Block B scaffold").name == "Block B scaffold"
    assert plan.find_element("lb 1").name == "Loading bay"
    assert plan.find_element("Site A - Loading bay level 1").name == "Loading bay"
    assert plan.find_element("Somewhere else") is None and plan.find_element("  ") is None


def test_short_names_do_not_match_by_accident():
    element = SiteElement(ELEMENT_KINDS["zone"], "A", 0, 0, 5, 5)
    assert element.matches("A") and not element.matches("Block A and more")


# ---------- reading a plan image with the AI ----------

def image():
    return IncidentPhoto.from_bytes("plan.png", sample_bytes())


def ai_reply(*items):
    return {"site_name": "Reply site", "elements": list(items)}


def reader_with(reply=None, error=None):
    fake = FakeGemini({id(SitePlanReader.SCHEMA): reply} if reply is not None else None, error)
    return SitePlanReader(fake), fake


def test_reader_converts_picture_coordinates_to_metres():
    reader, fake = reader_with(ai_reply(
        {"type": "building", "name": "Tower 1", "x": 500, "y": 500, "w": 200, "h": 400}))
    plan = reader.read(image(), width_m=100, aspect=0.5)
    tower = plan.elements[0]
    assert (plan.width_m, plan.depth_m, plan.name) == (100.0, 50.0, "Reply site")
    assert tower.rect == (50.0, 25.0, 20.0, 20.0)
    assert fake.calls[0]["photo"].mime_type == "image/png"


def test_reader_prompt_lists_every_kind_and_warns_about_instructions_in_the_image():
    prompt = SitePlanReader.build_prompt()
    assert all(key in prompt for key in ELEMENT_KINDS) and "never instructions" in prompt
    assert SitePlanReader.SCHEMA["properties"]["elements"]["items"]["properties"]["type"]["enum"] == list(ELEMENT_KINDS)


def test_a_typed_site_name_beats_the_ai_name():
    reader, _ = reader_with(ai_reply({"type": "zone", "name": "Yard", "x": 0, "y": 0, "w": 300, "h": 300}))
    assert reader.read(image(), 80, 0.6, " My Site ").name == "My Site"


@pytest.mark.parametrize("error", [RuntimeError("all models failed"), ValueError("malformed twice")])
def test_ai_failure_becomes_a_plain_error(error):
    reader, _ = reader_with(error=error)
    with pytest.raises(SitePlanError, match="could not read"):
        reader.read(image(), 80, 0.6)


def test_empty_result_is_reported():
    reader, _ = reader_with(ai_reply())
    with pytest.raises(SitePlanError, match="found nothing"):
        reader.read(image(), 80, 0.6)


def test_junk_elements_in_an_ai_reply_are_skipped_not_fatal():
    reader, _ = reader_with(ai_reply(
        {"type": "building", "name": "Good", "x": 100, "y": 100, "w": 200, "h": 200},
        {"type": "road", "name": "Off", "x": 100, "y": 100, "w": 0, "h": 0}))
    plan = reader.read(image(), 80, 0.6)
    assert [e.name for e in plan.elements] == ["Good", "Off"] and plan.elements[1].rect[2] >= 1


# ---------- saving ----------

def test_plan_saves_and_loads_across_runs(tmp_path):
    plan = SitePlan.from_dict(plan_dict(block(), block(name="Gate", type="gate", x=50)))
    assert DataManager(str(tmp_path)).save_site_plan(plan)
    assert DataManager(str(tmp_path)).load_site_plan().to_dict() == plan.to_dict()


def test_missing_corrupt_or_wrong_plan_file_gives_none(tmp_path):
    data = DataManager(str(tmp_path))
    assert data.load_site_plan() is None
    path = tmp_path / "site_plan.json"
    path.write_text("{not json", encoding="utf-8")
    assert data.load_site_plan() is None and any(p.name.startswith("site_plan.json.corrupt") for p in tmp_path.iterdir())
    path.write_text(json.dumps({"width_m": 1, "depth_m": 1, "elements": []}), encoding="utf-8")
    assert data.load_site_plan() is None


def test_delete_plan_is_safe_to_repeat(tmp_path):
    data = DataManager(str(tmp_path))
    data.save_site_plan(SitePlan.from_dict(plan_dict(block())))
    assert data.delete_site_plan() and data.delete_site_plan() and data.load_site_plan() is None


# ---------- the API ----------

READ_REPLY = ai_reply({"type": "building", "name": "Block A", "x": 100, "y": 100, "w": 300, "h": 300})


def read_request(client, **overrides):
    form = {"site_width_m": "90", "image_aspect": "0.62", "site_name": "", **overrides}
    if "plan" not in form:
        form["plan"] = (io.BytesIO(sample_bytes()), "plan.png")
    elif form["plan"] is None:
        del form["plan"]
    return client.post("/api/site-plan/read", data=form, content_type="multipart/form-data")


@pytest.fixture
def plan_client(tmp_path):
    return make_client(tmp_path, FakeGemini({id(SitePlanReader.SCHEMA): READ_REPLY}))


def test_api_starts_with_no_plan(plan_client):
    assert plan_client.get("/api/site-plan").get_json() == {"plan": None}


def test_api_read_returns_a_draft_without_saving_it(plan_client):
    response = read_request(plan_client)
    body = response.get_json()
    assert response.status_code == 200 and body["plan"]["elements"][0]["name"] == "Block A"
    assert body["plan"]["width_m"] == 90.0 and body["plan"]["depth_m"] == 55.8
    assert plan_client.get("/api/site-plan").get_json() == {"plan": None}


def test_api_save_get_and_delete_cycle(plan_client):
    draft = read_request(plan_client).get_json()["plan"]
    draft["elements"][0]["name"] = "Renamed by the user"
    saved = plan_client.put("/api/site-plan", json=draft)
    assert saved.status_code == 200
    assert plan_client.get("/api/site-plan").get_json()["plan"]["elements"][0]["name"] == "Renamed by the user"
    assert plan_client.delete("/api/site-plan").get_json() == {"plan": None}
    assert plan_client.get("/api/site-plan").get_json() == {"plan": None}


@pytest.mark.parametrize("body", [None, {"width_m": 3, "depth_m": 50, "elements": []}, {"elements": []}])
def test_api_rejects_an_unusable_plan(plan_client, body):
    response = plan_client.put("/api/site-plan", json=body)
    assert response.status_code == 422 and response.get_json()["errors"]


@pytest.mark.parametrize("overrides", [
    {"site_width_m": ""}, {"site_width_m": "5"}, {"site_width_m": "abc"}, {"image_aspect": "9"}, {"plan": None},
])
def test_api_read_validates_the_form(plan_client, overrides):
    response = read_request(plan_client, **overrides)
    assert response.status_code == 422 and response.get_json()["errors"]


def test_api_read_rejects_a_file_that_is_not_an_image(plan_client):
    response = read_request(plan_client, plan=(io.BytesIO(b"not an image"), "plan.png"))
    assert response.status_code == 422 and "not a real image" in response.get_json()["errors"][0]


def test_api_read_reports_ai_failure_and_keeps_the_saved_plan(tmp_path):
    client = make_client(tmp_path, FakeGemini(error=RuntimeError("down")))
    client.put("/api/site-plan", json=plan_dict(block()))
    response = read_request(client)
    assert response.status_code == 502 and "could not read" in response.get_json()["errors"][0]
    assert client.get("/api/site-plan").get_json()["plan"]["name"] == "Test site"


def test_api_read_is_rate_limited(tmp_path):
    client = make_client(tmp_path, FakeGemini({id(SitePlanReader.SCHEMA): READ_REPLY}), post_limit=1)
    assert read_request(client).status_code == 200
    assert read_request(client).status_code == 429