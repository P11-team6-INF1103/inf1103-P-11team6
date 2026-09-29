import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_DATA_PATH = os.path.join(_DATA_DIR, "incidents.json")


# Lennart
def load_records():
    if not os.path.exists(_DATA_PATH):
        return []
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, OSError):
        return []
