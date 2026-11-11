# Lennart
from web_support.rate_limiter import RateLimiter


def test_each_client_has_its_own_budget():
    limiter = RateLimiter(limit=2)
    assert [limiter.too_many("a"), limiter.too_many("a"), limiter.too_many("a"), limiter.too_many("b")] == \
        [False, False, True, False]


def test_budget_comes_back_after_the_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("web_support.rate_limiter.time.time", lambda: now[0])
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.too_many("a") is False
    assert limiter.too_many("a") is True
    now[0] += 61
    assert limiter.too_many("a") is False
