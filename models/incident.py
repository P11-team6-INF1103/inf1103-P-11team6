# Lennart
from datetime import datetime

from models.incident_photo import IncidentPhoto


class Incident:
    # The four fields the supervisor types; everything else is added later by the AI and the rules.
    _REQUIRED = ("description", "location", "reporter_role", "injury")

    # Builds a new incident; the timestamp defaults to now.
    def __init__(self, description: str, location: str, reporter_role: str, injury: bool,
                 timestamp: str | None = None, photo: IncidentPhoto | None = None) -> None:
        self._fields = {
            "description": description,
            "location": location,
            "reporter_role": reporter_role,
            "injury": bool(injury),
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        self._photo = None
        if photo is not None:
            self.attach_photo(photo)

    @property
    def description(self) -> str:
        return self._fields["description"]

    @property
    def location(self) -> str:
        return self._fields["location"]

    @property
    def injury(self) -> bool:
        return self._fields["injury"]

    @property
    def timestamp(self) -> str:
        return self._fields["timestamp"]

    @property
    def photo(self) -> IncidentPhoto | None:
        return self._photo

    # True if a photo was attached in this run (photos are not reloaded from disk).
    def has_photo(self) -> bool:
        return self._photo is not None

    # Attaches a photo to the incident and records its file name.
    def attach_photo(self, photo: IncidentPhoto) -> None:
        self._photo = photo
        self._fields["photo_file"] = photo.file_name

    # Reads one field, like dict.get().
    def get(self, key: str, default: object = None) -> object:
        return self._fields.get(key, default)

    # Adds or replaces the fields produced by the AI and the rules; the four typed fields cannot be changed.
    def update(self, fields: dict) -> None:
        for key, value in fields.items():
            if key in self._REQUIRED:
                continue
            self._fields[key] = value

    # Older versions of this incident, oldest first, each a full snapshot with its 'version' number.
    @property
    def history(self) -> list[dict]:
        return list(self._fields.get("history") or [])

    # The version number of this incident: 1 until it has been edited or reverted.
    @property
    def version(self) -> int:
        return len(self.history) + 1

    # A copy of every field except the history, with this version's number, for the history list.
    def snapshot(self) -> dict:
        data = {key: value for key, value in self._fields.items() if key != "history"}
        data["version"] = self.version
        return data

    # Makes this incident the newest version of 'previous': the older versions plus 'previous' itself are kept.
    def follow(self, previous: "Incident") -> None:
        self._fields["history"] = previous.history + [previous.snapshot()]

    # A copy of every field, ready to save as JSON.
    def to_dict(self) -> dict:
        return dict(self._fields)

    # Rebuilds an incident from a saved dict; raises ValueError if a typed field is missing.
    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        if not isinstance(data, dict) or any(key not in data for key in cls._REQUIRED):
            raise ValueError("saved incident is missing a required field")
        incident = cls(data["description"], data["location"], data["reporter_role"],
                       data["injury"], data.get("timestamp"))
        incident.update(data)
        return incident
