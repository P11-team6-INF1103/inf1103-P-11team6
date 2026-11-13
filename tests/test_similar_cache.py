# Lennart
import pytest

from ai_clients.gemini_client import GeminiClient
from ai_clients.response_cache import ResponseCache
from ai_clients.similarity_matcher import SimilarityMatcher

SCHEMA = {"type": "array", "items": {"type": "string"}}
FALL = "Worker slipped on the wet floor near the loading bay."


class FakeSdk:
    def __init__(self, texts):
        self.texts = list(texts)
        self.inputs = []
        self.interactions = self

    def create(self, model, input, response_format, generation_config):
        self.inputs.append(input)
        return type("Reply", (), {"output_text": self.texts.pop(0)})()


def prompt_for(text):
    return f"Read this incident:\n\"{text}\"\nReturn the hazards."


# --- SimilarityMatcher: what counts as the same wording ---

@pytest.mark.parametrize("other", [
    "worker slipped on wet floor near loading bay",         # capitals, punctuation and filler words
    "WORKER  SLIPPED ON THE WET FLOOR NEAR THE LOADING BAY!!",
    "A worker slipped on the wet floors near the loading bays",  # plural s
    "Worker slipped on the wet floor near the loadng bay.",  # one letter missing in a long word
])
def test_same_wording_matches(other):
    assert SimilarityMatcher().is_match(FALL, other)


@pytest.mark.parametrize("other", [
    "Worker slipped on the dry floor near the loading bay.",      # a different word
    "Worker tripped on the wet floor near the loading bay.",
    "Worker slipped on the wet floor near the loading bay twice.",  # an extra word
    "Worker slipped on the wet floor.",                           # a missing part
    "",
])
def test_different_wording_does_not_match(other):
    assert not SimilarityMatcher().is_match(FALL, other)


def test_numbers_negations_and_word_order_are_never_ignored():
    matcher = SimilarityMatcher()
    assert not matcher.is_match("Fell from the 3rd floor scaffold", "Fell from the 2nd floor scaffold")
    assert not matcher.is_match("Fell 3 metres from the scaffold", "Fell 30 metres from the scaffold")
    assert not matcher.is_match("Worker wore a harness when he fell", "Worker did not wear a harness when he fell")
    assert not matcher.is_match("Harness was worn", "Harness was not worn")
    assert not matcher.is_match("Forklift hit the worker", "Worker hit the forklift")


def test_a_spelling_slip_in_a_look_alike_word_is_not_forgiven():
    # "overhead" and "overheat" are close in spelling but are different hazards.
    assert not SimilarityMatcher().is_match("Cable hanging overhead", "Cable hanging overheat")


# --- ResponseCache ---

def test_lookup_finds_exact_then_similar_and_counts_them():
    cache = ResponseCache()
    scope = ResponseCache.make_scope("gemini", prompt_for(FALL), FALL)
    cache.remember("k1", "reply", scope, FALL)
    assert cache.lookup("k1") == "reply"
    other = "worker slipped on wet floor near loading bay"
    other_scope = ResponseCache.make_scope("gemini", prompt_for(other), other)
    assert other_scope == scope  # only the subject differs, so the scope is shared
    assert cache.lookup("k2", other_scope, other) == "reply"
    assert cache.lookup("k3", scope, "Someone cut a hand on a saw") is None
    assert cache.stats() == {"exact": 1, "similar": 1, "miss": 1}


def test_a_different_prompt_around_the_subject_never_shares_a_reply():
    cache = ResponseCache()
    cache.remember("k1", "fall reply", ResponseCache.make_scope("web", f"Hazard: fall\n{FALL}", FALL), FALL)
    scope = ResponseCache.make_scope("web", f"Hazard: electrical\n{FALL}", FALL)
    assert cache.lookup("k2", scope, FALL) is None


def test_a_subject_that_is_not_in_the_prompt_only_matches_exactly():
    scope = ResponseCache.make_scope("gemini", "a prompt without the subject", FALL)
    assert scope == ResponseCache.make_scope("gemini", "a prompt without the subject", FALL)
    assert scope != ResponseCache.make_scope("gemini", "a prompt without the subject!", FALL)


def test_refresh_makes_every_lookup_miss_but_still_saves_new_replies():
    cache = ResponseCache()
    cache.remember("k1", "old", "scope", FALL)
    cache.put("k2", "weather")
    with cache.refresh():
        assert cache.lookup("k1", "scope", FALL) is None
        assert cache.get("k2") is None
        cache.remember("k1", "new", "scope", FALL)
    assert cache.lookup("k1") == "new"
    assert cache.get("k2") == "weather"


# --- The clients and the hazard step ---

def test_gemini_reuses_a_reply_for_a_similarly_worded_subject_without_calling_the_api():
    sdk = FakeSdk(['["fall"]', '["cut"]'])
    client = GeminiClient(ResponseCache(), sdk)
    other = "worker slipped on wet floor near loading bay"
    assert client.ask_json(prompt_for(FALL), SCHEMA, subject=FALL) == ["fall"]
    assert client.ask_json(prompt_for(other), SCHEMA, subject=other) == ["fall"]
    assert len(sdk.inputs) == 1
    assert client.ask_json(prompt_for("Someone cut a hand"), SCHEMA, subject="Someone cut a hand") == ["cut"]
    assert len(sdk.inputs) == 2


def test_gemini_without_a_subject_still_needs_an_exact_match():
    sdk = FakeSdk(['["a"]', '["b"]'])
    client = GeminiClient(ResponseCache(), sdk)
    assert client.ask_json(prompt_for(FALL), SCHEMA) == ["a"]
    assert client.ask_json(prompt_for(FALL.lower()), SCHEMA) == ["b"]
    assert len(sdk.inputs) == 2


def test_gemini_ignores_a_saved_similar_reply_that_no_longer_fits_the_schema():
    cache = ResponseCache()
    scope = ResponseCache.make_scope("gemini", prompt_for(FALL), FALL, '{"items": {"type": "string"}, "type": "array"}', "")
    cache.remember("old", '{"not": "an array"}', scope, FALL)
    sdk = FakeSdk(['["fresh"]'])
    assert GeminiClient(cache, sdk).ask_json(prompt_for(FALL.lower()), SCHEMA, subject=FALL.lower()) == ["fresh"]
    assert len(sdk.inputs) == 1
