# Ren Xiang
import hashlib
import logging

logger = logging.getLogger(__name__)

# The key under which the saved descriptions are kept inside the exported dict (old saved caches do not have it).
_SIMILAR_KEY = "__similar__"

class ResponseCache:
    # Validated AI and weather replies already received, keyed by a hash of the request.
    # The same incident then gets the same answer on every run, and a re-run costs no API quota.
    # The lock keeps it safe when the evidence steps run in parallel threads.

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
