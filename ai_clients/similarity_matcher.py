# Lennart
import re
from difflib import SequenceMatcher

from ai_clients.constants import FILLER_WORDS, TYPO_MIN_LENGTH, TYPO_MIN_RATIO


class SimilarityMatcher:
    # Decides whether two incident descriptions say the same thing, so one saved AI reply can serve both.
    # It is deliberately strict because the reply feeds a safety score: the descriptions must hold the same
    # words in the same order. Capital letters, punctuation, filler words (a, the, was) and a small spelling
    # slip in the middle of a long word are ignored. A different word, a different number or a missing "not" is a mismatch.

    # The meaningful words of a text in order: lower case, no punctuation, no filler, plural "s" removed.
    @staticmethod
    def key_words(text: str) -> list[str]:
        words = re.findall(r"[a-z0-9]+", str(text).lower().replace("'", ""))
        return [word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
                for word in words if word not in FILLER_WORDS]

    # True when two words are the same word, allowing one small spelling slip in a long word without digits.
    @staticmethod
    def _same_word(first: str, second: str) -> bool:
        if first == second:
            return True
        if min(len(first), len(second)) < TYPO_MIN_LENGTH or any(c.isdigit() for c in first + second):
            return False
        return (first[0] == second[0] and first[-1] == second[-1]
                and SequenceMatcher(None, first, second).ratio() >= TYPO_MIN_RATIO)

    # True when the two texts are worded the same way once filler and small slips are ignored.
    def is_match(self, first: str, second: str) -> bool:
        a, b = self.key_words(first), self.key_words(second)
        return bool(a) and len(a) == len(b) and all(self._same_word(x, y) for x, y in zip(a, b))
