# import os
# import time

# import pytest

# from ai_clients import (
#     GeminiClient,
#     JsonReply,
#     ResponseCache,
# )
# from ai_manager import (
#     AIManager,
#     EnrichmentStep,
#     HazardFlagStep,
#     PhotoAnalysisStep,
#     ReviewStep,
#     SimilarIncidentStep,
#     WeatherStep,
#     WebSearchStep,
# )
# from logic_manager import OUTCOME_ACTIONS
# from models.incident import Incident
# from models.incident_photo import IncidentPhoto
# from tests.fakes import HAZARD_REPLY, FakeGemini, FakeSearch, FakeWeather

# # Ren Xiang
# SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")


# def make(photo=False, **fields):
#     incident = Incident("Scaffold plank fell from level 4", "Site B", "safety_officer", False,
#                         "2026-10-21T21:40:00", IncidentPhoto.from_file(SAMPLE_PHOTO) if photo else None)
#     incident.update(fields)
#     return incident


# # Ren Xiang
# # --- Reply parsing and schema validation ---

# def test_parse_strips_code_fences_and_rejects_non_json():
#     assert JsonReply.parse('```json\n{"a": 1}\n```') == {"a": 1}
#     with pytest.raises(ValueError):
#         JsonReply.parse("Sorry, I cannot help with that")


# def test_schema_validation_catches_wrong_types_enums_and_missing_keys():
#     JsonReply.validate(HAZARD_REPLY, HazardFlagStep.SCHEMA)
#     for broken in ({**HAZARD_REPLY, "hazard_category": "earthquake"},
#                    {**HAZARD_REPLY, "elevated_places": "roof"},
#                    {k: v for k, v in HAZARD_REPLY.items() if k != "ppe_status"}):
#         with pytest.raises(ValueError):
#             JsonReply.validate(broken, HazardFlagStep.SCHEMA)


# def test_extract_object_finds_json_inside_text():
#     assert JsonReply.extract_object('Here you go: {"a": 1} thanks') == {"a": 1}
#     assert JsonReply.extract_object("no json here") is None


# # Ren Xiang
# # --- Gemini client with a fake SDK (no live API) ---

# class FakeSdk:
#     def __init__(self, texts):
#         self.texts = list(texts)
#         self.inputs = []
#         self.interactions = self

#     def create(self, model, input, response_format, generation_config):
#         self.inputs.append(input)
#         text = self.texts.pop(0)
#         if isinstance(text, Exception):
#             raise text
#         return type("Reply", (), {"output_text": text})()


# def test_gemini_retries_once_on_malformed_reply_then_caches():
#     sdk = FakeSdk(["not json", '["x"]'])
#     client = GeminiClient(ResponseCache(), sdk)
#     schema = {"type": "array", "items": {"type": "string"}}
#     assert client.ask_json("prompt", schema) == ["x"]
#     assert client.ask_json("prompt", schema) == ["x"]  # second call comes from the cache
#     assert len(sdk.inputs) == 2


# def test_gemini_gives_up_after_two_malformed_replies():
#     client = GeminiClient(ResponseCache(), FakeSdk(["{bad", '{"wrong": "shape"}']))
#     with pytest.raises(ValueError, match="malformed"):
#         client.ask_json("prompt", {"type": "array"})


# def test_gemini_falls_back_to_the_next_model_on_connection_failure():
#     sdk = FakeSdk([ConnectionError("timeout"), "[]"])
#     assert GeminiClient(ResponseCache(), sdk).ask_json("p", {"type": "array"}) == []
#     all_fail = FakeSdk([ConnectionError("down")] * 3)
#     with pytest.raises(RuntimeError, match="All Gemini models failed"):
#         GeminiClient(ResponseCache(), all_fail).ask_json("p", {"type": "array"})


# def test_gemini_without_api_key_raises_a_clear_error():
#     with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
#         GeminiClient(ResponseCache()).ask_json("p", {"type": "array"})


# def test_photo_is_sent_to_gemini_as_an_image_part():
#     sdk = FakeSdk(["[]"])
#     photo = IncidentPhoto.from_file(SAMPLE_PHOTO)
#     GeminiClient(ResponseCache(), sdk).ask_json("describe", {"type": "array"}, photo)
#     text_part, image_part = sdk.inputs[0]
#     assert text_part == {"type": "text", "text": "describe"}
#     assert image_part["type"] == "image" and image_part["mime_type"] == "image/png"
#     assert image_part["data"] == photo.as_base64()

# # Ren Xiang
# # --- Steps (polymorphism, LSP) ---

# def all_steps(gemini, search, weather):
#     return [HazardFlagStep(gemini), PhotoAnalysisStep(gemini), WeatherStep(weather),
#             SimilarIncidentStep(gemini, OUTCOME_ACTIONS), WebSearchStep(search), ReviewStep(gemini)]


# def test_every_step_returns_a_dict_and_never_raises_even_when_the_api_fails():
#     broken = all_steps(FakeGemini(error=ConnectionError("down")), FakeSearch(error=TimeoutError("slow")),
#                        FakeWeather(None))
#     incident = make(photo=True, run_weather=True, run_similar=True)
#     history = [make()]
#     for step in broken:
#         assert isinstance(step, EnrichmentStep)
#         fields = step.safe_run(incident, history)
#         assert isinstance(fields, dict)
#         assert any(key.endswith("_error") and value for key, value in fields.items()), step.name


# def test_hazard_step_cleans_a_good_reply():
#     fields = HazardFlagStep(FakeGemini()).safe_run(make(), [])
#     assert fields["hazard_category"] == "fall_from_height" and fields["height_estimate_m"] == 12
#     assert fields["context_flags_error"] is None

# # Ren Xiang
# # --- AIManager and threading (advanced feature) ---

# def test_ai_manager_fills_in_every_step():
#     ai = AIManager(FakeGemini(), FakeSearch(),
#                    FakeWeather({"temperature_c": 30, "humidity_pct": 80, "precipitation_mm": 1.0}), OUTCOME_ACTIONS)
#     incident = make(photo=True, run_weather=True, run_similar=False)
#     ai.extract_hazards(incident)
#     ai.gather_evidence(incident, [])
#     ai.write_review(incident)
#     assert incident.get("hazard_category") == "fall_from_height"
#     assert incident.get("photo_analysed") and incident.get("weather_available")
#     assert incident.get("web_incidents") and incident.get("review_likely_causes")


# def test_evidence_steps_run_in_parallel_threads():
#     class SlowSearch(FakeSearch):
#         def search_json(self, prompt, schema):
#             time.sleep(0.4)
#             return super().search_json(prompt, schema)

#     class SlowWeather(FakeWeather):
#         def get_weather(self, timestamp):
#             time.sleep(0.4)

#     class SlowGemini(FakeGemini):
#         def ask_json(self, prompt, schema, photo=None):
#             time.sleep(0.4)
#             return super().ask_json(prompt, schema, photo)

#     ai = AIManager(SlowGemini(), SlowSearch(), SlowWeather(), OUTCOME_ACTIONS)
#     incident = make(photo=True, run_weather=True, run_similar=True)
#     start = time.perf_counter()
#     ai.gather_evidence(incident, [make()])
#     elapsed = time.perf_counter() - start
#     assert elapsed < 1.0  # four 0.4 s steps one after another would take 1.6 s
#     assert incident.get("photo_analysed") and incident.get("similar_incidents_checked")