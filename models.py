# Lennart
import base64
import hashlib
import os
from datetime import datetime
from typing import ClassVar

# Used as the photo of an edit to mean "keep the photo the incident already has".
KEEP_PHOTO = "keep"


class PhotoError(ValueError):
    pass


class IncidentPhoto:
    # Accepted photo types: file extension -> MIME type sent to the AI.
    ALLOWED_TYPES: ClassVar[dict[str, str]] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    MAX_BYTES = 5 * 1024 * 1024

    # The first bytes every real file of each type starts with.
    _SIGNATURES: ClassVar[dict[str, tuple[bytes, ...]]] = {
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/webp": (b"RIFF",),
    }

    # Keeps the photo bytes private; use from_file() to build one from a path.
    def __init__(self, file_name: str, mime_type: str, content: bytes) -> None:
        self.__file_name = file_name
        self.__mime_type = mime_type
        self.__content = content

    # The MIME type for a file name, or a PhotoError if the type is not allowed.
    @classmethod
    def _mime_type_for(cls, file_name: str) -> str:
        extension = os.path.splitext(file_name)[1].lower()
        if extension not in cls.ALLOWED_TYPES:
            raise PhotoError("Photo must be a .png, .jpg, .jpeg or .webp file.")
        return cls.ALLOWED_TYPES[extension]

    # Checks photo bytes already in memory (e.g. uploaded from the web dashboard); raises PhotoError if unusable.
    @classmethod
    def from_bytes(cls, file_name: str, content: bytes) -> "IncidentPhoto":
        mime_type = cls._mime_type_for(file_name)
        if not content:
            raise PhotoError("The photo file is empty.")
        if len(content) > cls.MAX_BYTES:
            raise PhotoError("The photo is larger than 5 MB. Please use a smaller photo.")
        if not content.startswith(cls._SIGNATURES[mime_type]):
            raise PhotoError("The file is not a real image (it may be corrupt or renamed).")
        return cls(os.path.basename(file_name), mime_type, content)

    # Reads and checks a photo file; raises PhotoError with a plain-English reason if it cannot be used.
    @classmethod
    def from_file(cls, path: str) -> "IncidentPhoto":
        cls._mime_type_for(path)
        if not os.path.isfile(path):
            raise PhotoError(f"No file found at {path}.")
        if os.path.getsize(path) > cls.MAX_BYTES:
            raise PhotoError("The photo is larger than 5 MB. Please use a smaller photo.")
        try:
            with open(path, "rb") as f:
                content = f.read()
        except OSError as error:
            raise PhotoError(f"Could not read the photo: {error}") from error
        return cls.from_bytes(path, content)

    @property
    def file_name(self) -> str:
        return self.__file_name

    @property
    def mime_type(self) -> str:
        return self.__mime_type

    @property
    def content(self) -> bytes:
        return self.__content

    # The photo as base64 text, the form the Gemini API expects.
    def as_base64(self) -> str:
        return base64.b64encode(self.__content).decode("ascii")

    # A short fingerprint of the photo, used in cache keys and saved file names.
    def fingerprint(self) -> str:
        return hashlib.sha256(self.__content).hexdigest()[:16]


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
