# Daniel
import json
import os
from datetime import datetime

from data_stores.document_store import DocumentStore


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
