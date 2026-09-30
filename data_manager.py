import json
import os
from datetime import datetime, timedelta

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

#Ren Xiang
def query_by_location(location, days):
    """Filters records by location within the last N days. Used by
    is_systemic_risk() and by assess_severity()'s recurrence judgment.
    Most recent first. Returns contracts.md section 4 shape only:
    location, timestamp, outcome."""
    cutoff = datetime.now() - timedelta(days=days)
    matches = []
    for record in load_records():
        if record.get("location") != location:
            continue
        try:
            record_time = datetime.fromisoformat(record.get("timestamp", ""))
        except (TypeError, ValueError):
            continue
        if record_time >= cutoff:
            matches.append({
                "location": record.get("location"),
                "timestamp": record.get("timestamp"),
                "outcome": record.get("outcome"),
            })
    matches.sort(key=lambda r: r["timestamp"], reverse=True)
    return matches