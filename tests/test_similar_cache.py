# Lennart
import pytest

from ai_clients.similarity_matcher import SimilarityMatcher

FALL = "Worker slipped on the wet floor near the loading bay."


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
