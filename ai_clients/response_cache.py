# Ren Xiang
import hashlib
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from ai_clients.constants import MAX_SIMILAR_PER_SCOPE
from ai_clients.similarity_matcher import SimilarityMatcher

logger = logging.getLogger(__name__)

# The key under which the saved descriptions are kept inside the exported dict (old saved caches do not have it).
_SIMILAR_KEY = "__similar__"

class ResponseCache:
    # Validated AI and weather replies already received, keyed by a hash of the request.
    # The same incident then gets the same answer on every run, and a re-run costs no API quota.
    # The lock keeps it safe when the evidence steps run in parallel threads.

# Lennart
    # A reply is also found by wording: a request that differs from a saved one only by capital letters,
    # punctuation, filler words or a spelling slip reuses the saved reply (see SimilarityMatcher).
    def __init__(self, saved: dict | None = None, matcher: SimilarityMatcher | None = None) -> None:
        saved = dict(saved) if isinstance(saved, dict) else {}
        index = saved.pop(_SIMILAR_KEY, None)
        self.__entries = saved
        self.__similar: dict[str, list[dict]] = {
            scope: [dict(item) for item in items if isinstance(item, dict) and "subject" in item and "key" in item]
            for scope, items in (index.items() if isinstance(index, dict) else []) if isinstance(items, list)
        }
        self.__matcher = matcher or SimilarityMatcher()
        self.__lock = threading.Lock()
        self.__refresh_depth = 0
        self.__counts = {"exact": 0, "similar": 0, "miss": 0}

# Ren Xiang

    # Builds the cache key for a request: its kind plus a hash of its parts.
    @staticmethod
    def make_key(kind: str, *parts: str) -> str:
        return kind + ":" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get(self, key: str) -> object:
        with self.__lock:
            return None if self.__refresh_depth else self.__entries.get(key)

    def put(self, key: str, value: object) -> None:
        with self.__lock:
            self.__entries[key] = value

# Lennart
    # Builds the scope that groups requests which are the same apart from the incident text: the prompt with
    # the subject cut out. A different hazard type or schema gives a different scope, so they never mix.
    @staticmethod
    def make_scope(kind: str, prompt: str, subject: str, *parts: str) -> str:
        return ResponseCache.make_key(kind + "-scope", prompt.replace(subject, "\x00subject\x00"), *parts)

    # Looks a request up: first by its exact key, then (when a subject is given) by a similar saved subject.
    # While refresh() is active nothing is read, so the AI really runs again.
    def lookup(self, key: str, scope: str | None = None, subject: str | None = None) -> object:
        with self.__lock:
            if self.__refresh_depth:
                return None
            found = self.__entries.get(key)
            if found is not None:
                self.__counts["exact"] += 1
                return found
            for item in reversed(self.__similar.get(scope, [])) if scope and subject else []:
                found = self.__entries.get(item["key"])
                if found is not None and self.__matcher.is_match(item["subject"], subject):
                    self.__counts["similar"] += 1
                    logger.info("Reused a saved AI reply for a similarly worded request (no API call).")
                    return found
            self.__counts["miss"] += 1
            return None

    # Saves a reply; with a scope and subject it is also remembered by wording for later lookups.
    def remember(self, key: str, value: object, scope: str | None = None, subject: str | None = None) -> None:
        with self.__lock:
            self.__entries[key] = value
            if scope and subject:
                items = self.__similar.setdefault(scope, [])
                if all(item["key"] != key for item in items):
                    items.append({"subject": subject, "key": key})
                    del items[:-MAX_SIMILAR_PER_SCOPE]

    # While the 'with' block runs, lookups find nothing, so every step asks the AI again (the new replies are still saved).
    @contextmanager
    def refresh(self) -> Iterator[None]:
        with self.__lock:
            self.__refresh_depth += 1
        try:
            yield
        finally:
            with self.__lock:
                self.__refresh_depth -= 1

    # How many lookups were answered by an exact match, by a similar one, or not at all.
    def stats(self) -> dict:
        with self.__lock:
            return dict(self.__counts)

# Lennart
    # A copy of every entry, and the saved wordings, so the data manager can save them.
    def export(self) -> dict:
        with self.__lock:
            saved = dict(self.__entries)
            if self.__similar:
                saved[_SIMILAR_KEY] = {scope: [dict(item) for item in items] for scope, items in self.__similar.items()}
            return saved
