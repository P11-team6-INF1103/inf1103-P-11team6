import json
import os
<<<<<<< HEAD
<<<<<<< HEAD
=======
from datetime import datetime, timedelta
>>>>>>> origin/main
=======
from datetime import datetime, timedelta
>>>>>>> 4708af42e0662aff3b3c2e5da5d299f7cb60e6f9

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_DATA_PATH = os.path.join(_DATA_DIR, "incidents.json")


<<<<<<< HEAD
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
<<<<<<< HEAD
=======
def _set_aside_corrupt(path):
    """Renames an unreadable data file so the next save cannot destroy it.
    Returns the new name, or None if the rename failed."""
    backup = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    try:
        os.replace(path, backup)
        return backup
    except OSError:
        return None


def _read_json(path, expected_type):
    """Reads one JSON file. Returns (value, problem): value is an empty
    `expected_type()` when the file is missing, unreadable or the wrong
    shape, and `problem` says what was wrong (None when fine/missing)."""
    if not os.path.exists(path):
        return expected_type(), None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        backup = _set_aside_corrupt(path)
        return expected_type(), f"{os.path.basename(path)} was corrupt (kept as {os.path.basename(backup) if backup else 'unmovable file'})"
    except OSError as error:
        return expected_type(), f"could not read {os.path.basename(path)}: {error}"
    if not isinstance(data, expected_type):
        backup = _set_aside_corrupt(path)
        return expected_type(), f"{os.path.basename(path)} had the wrong format (kept as {os.path.basename(backup) if backup else 'unmovable file'})"
    return data, None


# Lennart
def load_records():
    """Loads incidents.json (main.py calls this once on startup). Returns
    an empty list if the file is missing, corrupt or the wrong shape —
    never raises. Entries that are not objects are dropped."""
    data, _problem = _read_json(_DATA_PATH, list)
    return [item for item in data if isinstance(item, dict)]


#Daniel
def save_record(record):

    os.makedirs(_DATA_DIR, exist_ok=True)
    records = load_records()
    records.append(record)
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

#Ren Xiang
def query_by_location(location, days):
  
=======

#Ren Xiang
def query_by_location(location, days):
    """Filters records by location within the last N days. Used by
    is_systemic_risk() and by assess_severity()'s recurrence judgment.
    Most recent first. Returns contracts.md section 4 shape only:
    location, timestamp, outcome."""
>>>>>>> 4708af42e0662aff3b3c2e5da5d299f7cb60e6f9
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
<<<<<<< HEAD
    return matches
>>>>>>> origin/main
=======
    return matches
>>>>>>> 4708af42e0662aff3b3c2e5da5d299f7cb60e6f9
