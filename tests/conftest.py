# Lennart
import pytest
import requests


# Every test runs offline with no API keys and a temporary data folder, so real data is never touched.
@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch):
    # Blank, not deleted: load_dotenv() refills a missing variable from the real .env but never overrides an existing one.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "")  # tests must never touch a real database
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(tmp_path / "data"))

    def no_network(*args, **kwargs):
        raise requests.ConnectionError("network blocked in tests")

    monkeypatch.setattr(requests, "get", no_network)
    monkeypatch.setattr(requests, "post", no_network)
