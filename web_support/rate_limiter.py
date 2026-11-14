# Lennart
import threading
import time


class RateLimiter:
    # Every new incident costs Gemini / Groq quota, so each client gets a small budget per time window.
    def __init__(self, limit: int, window_seconds: int = 600) -> None:
        self._limit = limit
        self._window = window_seconds
        self._recent: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    # True if this client has used up its budget; otherwise records the request and returns False.
    def too_many(self, client: str) -> bool:
        now = time.time()
        with self._lock:
            recent = [t for t in self._recent.get(client, []) if now - t < self._window]
            if len(recent) >= self._limit:
                self._recent[client] = recent
                return True
            self._recent[client] = recent + [now]
            return False
