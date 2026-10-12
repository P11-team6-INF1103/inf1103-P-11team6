import pytest

from tests._suite import offline


# Blocks the network and empties the API keys for every test.
@pytest.fixture(autouse=True)
def _no_network():
    with offline():
        yield


# Points every test at a temporary data folder so the real incidents.json is never touched.
@pytest.fixture(autouse=True)
def _never_touch_real_data(tmp_path, monkeypatch):
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(tmp_path / "data"))
