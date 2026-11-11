# Daniel
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from database import Database
from models.incident import Incident
from models.incident_photo import IncidentPhoto
from models.photo_error import PhotoError


class DocumentStore(ABC):
    # Interface for one stored JSON document. DataManager only calls these three methods, so a file and a database
    # row are interchangeable (Liskov) and a new kind of storage is a new subclass, not a change to DataManager (open/closed).

    # The stored value (an empty list or dict if there is none) and a message if something was wrong; never raises.
    @abstractmethod
    def read(self) -> tuple[dict | list, str | None]:
        ...

    # Replaces the stored value; returns False instead of raising.
    @abstractmethod
    def write(self, data: dict | list) -> bool:
        ...

    # Removes the stored value; returns False only if it exists and cannot be removed.
    @abstractmethod
    def delete(self) -> bool:
        ...


class JsonFile(DocumentStore):
    # One JSON file on disk that must hold a list or a dict.
    def __init__(self, path: str, expected_type: type) -> None:
        self._path = path
        self._expected_type = expected_type

    @property
    def path(self) -> str:
        return self._path

    # Renames a bad file to <name>.corrupt-<time> so it is kept; returns the new name, or None if it cannot be moved.
    def _set_aside_corrupt(self) -> str | None:
        backup = f"{self._path}.corrupt-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
        try:
            os.replace(self._path, backup)
            return os.path.basename(backup)
        except OSError:
            return None

    # Reads the file; a missing, corrupt or wrong-shape file gives an empty value and a message, never an error.
    def read(self) -> tuple[dict | list, str | None]:
        name = os.path.basename(self._path)
        if not os.path.exists(self._path):
            return self._expected_type(), None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            backup = self._set_aside_corrupt()
            return self._expected_type(), f"{name} was corrupt (kept as {backup or 'unmovable file'})"
        except OSError as error:
            return self._expected_type(), f"could not read {name}: {error}"
        if not isinstance(data, self._expected_type):
            backup = self._set_aside_corrupt()
            return self._expected_type(), f"{name} had the wrong format (kept as {backup or 'unmovable file'})"
        return data, None

    # Writes through a temp file so a crash cannot leave half a file; returns False instead of raising.
    def write(self, data: dict | list) -> bool:
        temp_path = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str, sort_keys=True)
            os.replace(temp_path, self._path)
            return True
        except (OSError, TypeError, ValueError):
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return False

    # Removes the file; returns False only if it exists and cannot be removed.
    def delete(self) -> bool:
        try:
            os.remove(self._path)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return True


class DbJson(DocumentStore):
    # The same job as JsonFile, but the dict lives in the database's documents table, so it survives a server restart.
    def __init__(self, database: Database, name: str, expected_type: type) -> None:
        self._database = database
        self._name = name
        self._expected_type = expected_type

    def read(self) -> tuple[dict | list, str | None]:
        try:
            with self._database.connect() as connection:
                row = connection.execute("SELECT data FROM documents WHERE name = ?", (self._name,)).fetchone()
            data = json.loads(row["data"]) if row else self._expected_type()
        except (json.JSONDecodeError, TypeError):
            return self._expected_type(), f"{self._name} was corrupt in the database"
        except Exception as error:
            return self._expected_type(), f"could not read {self._name}: {error}"
        if not isinstance(data, self._expected_type):
            return self._expected_type(), f"{self._name} had the wrong format"
        return data, None

    def write(self, data: dict | list) -> bool:
        try:
            with self._database.connect() as connection:
                connection.execute(
                    "INSERT INTO documents (name, data) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET data = excluded.data",
                    (self._name, json.dumps(data, default=str, sort_keys=True)))
            return True
        except Exception:
            return False

    def delete(self) -> bool:
        try:
            with self._database.connect() as connection:
                connection.execute("DELETE FROM documents WHERE name = ?", (self._name,))
            return True
        except Exception:
            return False


class DataManager:
    # A saved photo's reference starts with this when the photo is in the database instead of a file.
    DB_PHOTO_PREFIX = "db:"

    # The data folder: INCIDENT_DATA_DIR if set, otherwise ./data next to this file.
    @staticmethod
    def default_folder() -> str:
        return os.environ.get("INCIDENT_DATA_DIR") or os.path.join(os.path.dirname(__file__), "data")

    # Creates and owns the JSON files it manages (composition). Given a shared database (Postgres), the incidents,
    # AI cache and site plan live in it instead of in files, so they survive a server restart.
    def __init__(self, folder: str | None = None, shared_database: Database | None = None) -> None:
        self._folder = folder or self.default_folder()
        self._shared = shared_database
        self._database = shared_database
        self._incidents_file = JsonFile(os.path.join(self._folder, "incidents.json"), list)
        self._cache_file: DocumentStore = JsonFile(os.path.join(self._folder, "ai_cache.json"), dict)
        self._plan_file: DocumentStore = JsonFile(os.path.join(self._folder, "site_plan.json"), dict)
        if shared_database is not None:
            self._cache_file = DbJson(shared_database, "ai_cache", dict)
            self._plan_file = DbJson(shared_database, "site_plan", dict)

    # The database for the priority workflow: the shared one, or a SQLite file in the data folder.
    @property
    def database(self) -> Database:
        if self._database is None:
            self._database = Database(self.database_path)
        return self._database

    # The SQLite file with each incident's priority and resolved status.
    @property
    def database_path(self) -> str:
        return os.path.join(self._folder, "app.db")

    # True when everything is kept in the shared database rather than in local files.
    @property
    def uses_database(self) -> bool:
        return self._shared is not None

    # Path of app.log, or None if the data folder cannot be created (or there is no local data at all).
    def get_log_path(self) -> str | None:
        if self._shared:
            return None
        try:
            os.makedirs(self._folder, exist_ok=True)
        except OSError:
            return None
        return os.path.join(self._folder, "app.log")

    # Says what is wrong with the incidents file, or None if it is fine or missing.
    def check_records_file(self) -> str | None:
        if self._shared:
            return None
        _data, problem = self._incidents_file.read()
        return problem

    # The saved incidents as plain dicts, or None if the file exists but is unreadable.
    def _read_record_dicts(self) -> list | None:
        data, problem = self._incidents_file.read()
        if problem and os.path.exists(self._incidents_file.path):
            return None
        return [item for item in data if isinstance(item, dict)]

    # Loads every saved incident; a missing or corrupt file gives an empty list, and broken entries are skipped.
    def load_records(self) -> list[Incident]:
        if self._shared:
            return self._load_shared()
        data, _problem = self._incidents_file.read()
        incidents = []
        for item in data:
            try:
                incidents.append(Incident.from_dict(item))
            except ValueError:
                continue
        return incidents

    # Appends one incident; returns False and leaves the file alone if it is corrupt or cannot be written.
    def save_record(self, incident: Incident) -> bool:
        if self._shared:
            return self._shared_write(
                "INSERT INTO incidents (timestamp, location, data) VALUES (?, ?, ?)",
                (incident.timestamp, incident.location, self._dump(incident)))
        records = self._read_record_dicts()
        if records is None:
            return False
        records.append(incident.to_dict())
        return self._incidents_file.write(records)

    # Replaces the incident at a 0-based position (an edit or revert); returns False if it could not be written.
    def replace_record(self, index: int, incident: Incident) -> bool:
        if self._shared:
            return self._shared_write(
                "UPDATE incidents SET timestamp = ?, location = ?, data = ? WHERE id = ?",
                (incident.timestamp, incident.location, self._dump(incident)), index=index)
        records = self._read_record_dicts()
        if records is None or not 0 <= index < len(records):
            return False
        records[index] = incident.to_dict()
        return self._incidents_file.write(records)

    # Removes the incident at a 0-based position; returns False if the file is corrupt, the index is wrong or it cannot be written.
    def delete_record(self, index: int) -> bool:
        if self._shared:
            return self._shared_write("DELETE FROM incidents WHERE id = ?", (), index=index)
        records = self._read_record_dicts()
        if records is None or not 0 <= index < len(records):
            return False
        del records[index]
        return self._incidents_file.write(records)

    @staticmethod
    def _dump(incident: Incident) -> str:
        return json.dumps(incident.to_dict(), default=str, sort_keys=True)

    # Every saved incident in the order it was saved; a broken row is skipped.
    def _load_shared(self) -> list[Incident]:
        try:
            with self._shared.connect() as connection:
                rows = connection.execute("SELECT data FROM incidents ORDER BY id").fetchall()
        except Exception:
            return []
        incidents = []
        for row in rows:
            try:
                incidents.append(Incident.from_dict(json.loads(row["data"])))
            except (ValueError, TypeError):
                continue
        return incidents

    # Runs one write. With index (0-based, in save order) it targets that incident's row, passed last as the id.
    def _shared_write(self, sql: str, params: tuple, index: int | None = None) -> bool:
        try:
            with self._shared.connect() as connection:
                if index is not None:
                    ids = [row["id"] for row in connection.execute("SELECT id FROM incidents ORDER BY id").fetchall()]
                    if not 0 <= index < len(ids):
                        return False
                    params = (*params, ids[index])
                connection.execute(sql, params)
            return True
        except Exception:
            return False

    # Copies an uploaded photo into data/photos so the evidence is kept; returns the saved path, or None on failure.
    def store_photo(self, photo: IncidentPhoto) -> str | None:
        if self._shared:
            try:
                with self._shared.connect() as connection:
                    connection.execute(
                        "INSERT INTO photos (fingerprint, mime_type, content) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                        (photo.fingerprint(), photo.mime_type, photo.content))
            except Exception:
                return None
            return self.DB_PHOTO_PREFIX + photo.fingerprint()
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[photo.mime_type]
        path = os.path.join(self._folder, "photos", photo.fingerprint() + extension)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(photo.content)
        except OSError:
            return None
        return path

    # (bytes, MIME type) of a photo stored in the database from its "db:<fingerprint>" reference, or None.
    def read_photo(self, reference: str) -> tuple[bytes, str] | None:
        if not self._shared or not str(reference).startswith(self.DB_PHOTO_PREFIX):
            return None
        try:
            with self._shared.connect() as connection:
                row = connection.execute("SELECT mime_type, content FROM photos WHERE fingerprint = ?",
                                         (reference[len(self.DB_PHOTO_PREFIX):],)).fetchone()
        except Exception:
            return None
        return (bytes(row["content"]), row["mime_type"]) if row else None

    # Loads the photo saved for an incident again, or None if it has no photo or the file is gone or unusable.
    def load_photo(self, incident: Incident) -> IncidentPhoto | None:
        path = incident.get("photo_saved_path")
        if not path:
            return None
        if path.startswith(self.DB_PHOTO_PREFIX):
            stored = self.read_photo(path)
            if not stored:
                return None
            extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(stored[1], ".png")
            try:
                return IncidentPhoto.from_bytes(str(incident.get("photo_file") or "photo" + extension), stored[0])
            except PhotoError:
                return None
        try:
            return IncidentPhoto.from_file(path)
        except PhotoError:
            return None

    # Loads the saved AI reply cache, or an empty dict if it is missing or corrupt.
    def load_ai_cache(self) -> dict:
        data, _problem = self._cache_file.read()
        return data

    # Saves the AI reply cache; returns False if it cannot be written.
    def save_ai_cache(self, cache: dict) -> bool:
        return self._cache_file.write(cache)

    # Incidents at one location in the last N days, newest first; records with a bad timestamp are skipped.
    def query_by_location(self, location: str, days: int, as_of: str | None = None,
                          records: list[Incident] | None = None) -> list[Incident]:
        try:
            reference = datetime.fromisoformat(as_of) if as_of else datetime.now()
        except (TypeError, ValueError):
            reference = datetime.now()
        cutoff = reference - timedelta(days=days)
        matches = []
        for incident in self.load_records() if records is None else records:
            if incident.location != location:
                continue
            try:
                when = datetime.fromisoformat(incident.timestamp)
            except (TypeError, ValueError):
                continue
            if when >= cutoff:
                matches.append(incident)
        matches.sort(key=lambda item: item.timestamp, reverse=True)
        return matches

    # Saved locations with their incident counts, sorted by name.
    def list_locations(self, records: list[Incident] | None = None) -> list[tuple[str, int]]:
        counts = {}
        for incident in self.load_records() if records is None else records:
            location = incident.location
            if isinstance(location, str) and location.strip():
                counts[location] = counts.get(location, 0) + 1
        return sorted(counts.items(), key=lambda item: (item[0].lower(), item[0]))


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
