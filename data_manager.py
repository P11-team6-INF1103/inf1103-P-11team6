import json
import os
from datetime import datetime, timedelta

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# The data folder: INCIDENT_DATA_DIR if set, otherwise ./data.
def _data_dir() -> str:
    return os.environ.get("INCIDENT_DATA_DIR") or _DATA_DIR


# Path of incidents.json.
def _incidents_path() -> str:
    return os.path.join(_data_dir(), "incidents.json")


# Path of ai_cache.json.
def _cache_path() -> str:
    return os.path.join(_data_dir(), "ai_cache.json")


# Renames a bad file to <name>.corrupt-<time> so it is kept; returns the new path, or None if it cannot be moved.
def _set_aside_corrupt(path: str) -> str | None:
    backup = f"{path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    try:
        os.replace(path, backup)
        return backup
    except OSError:
        return None


# Reads a JSON file of the expected type; a missing, corrupt or wrong-shape file gives an empty value and a message, never an error.
def _read_json(path: str, expected_type: type) -> tuple[dict | list, str | None]:
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


# Writes JSON through a temp file so a crash cannot leave half a file; returns False instead of raising.
def _write_json(path: str, data: dict | list) -> bool:
    temp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, sort_keys=True)
        os.replace(temp_path, path)
        return True
    except (OSError, TypeError, ValueError):
        try:
            os.remove(temp_path)
        except OSError:
            pass
        return False


# Path of data/app.log, or None if the data folder cannot be created.
def get_log_path() -> str | None:
    try:
        os.makedirs(_data_dir(), exist_ok=True)
    except OSError:
        return None
    return os.path.join(_data_dir(), "app.log")


# Lennart
# Loads every saved incident on start-up; a missing or corrupt file gives an empty list.
def load_records() -> list:
    data, _problem = _read_json(_incidents_path(), list)
    return [item for item in data if isinstance(item, dict)]


# Says what is wrong with the incidents file (corrupt, wrong format, unreadable), or None if it is fine or missing.
def check_records_file() -> str | None:
    _data, problem = _read_json(_incidents_path(), list)
    return problem


# Loads the saved AI reply cache, or an empty dict if it is missing or corrupt.
def load_ai_cache() -> dict:
    data, _problem = _read_json(_cache_path(), dict)
    return data


# Saves the AI reply cache; returns False if it cannot be written.
def save_ai_cache(cache: dict) -> bool:
    return _write_json(_cache_path(), cache)


# Daniel
# Appends one incident to incidents.json; returns False and leaves the file alone if it is corrupt or cannot be written.
def save_record(record: dict) -> bool:
    path = _incidents_path()
    records, problem = _read_json(path, list)
    if problem and os.path.exists(path):
        return False
    records = [item for item in records if isinstance(item, dict)]
    records.append(record)
    return _write_json(path, records)


# Removes the incident at a 0-based position in incidents.json; returns False and leaves the file alone if it is corrupt, out of range or cannot be written.
def delete_record(index: int) -> bool:
    path = _incidents_path()
    records, problem = _read_json(path, list)
    if problem and os.path.exists(path):
        return False
    records = [item for item in records if isinstance(item, dict)]
    if not 0 <= index < len(records):
        return False
    del records[index]
    return _write_json(path, records)


# Ren Xiang
# Incidents at one location in the last N days, newest first; records with a bad timestamp are skipped.
def query_by_location(location: str, days: int, as_of: str | None = None, records: list | None = None) -> list:
    try:
        reference = datetime.fromisoformat(as_of) if as_of else datetime.now()
    except (TypeError, ValueError):
        reference = datetime.now()
    cutoff = reference - timedelta(days=days)
    matches = []
    for record in (load_records() if records is None else records):
        if not isinstance(record, dict) or record.get("location") != location:
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


# Saved locations with their incident counts, sorted by name.
def list_locations(records: list | None = None) -> list:
    counts = {}
    for record in (load_records() if records is None else records):
        if not isinstance(record, dict):
            continue
        location = record.get("location")
        if isinstance(location, str) and location.strip():
            counts[location] = counts.get(location, 0) + 1
    return sorted(counts.items(), key=lambda item: (item[0].lower(), item[0]))
