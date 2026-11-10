# Lennart
# Copy this whole file into project 2. Full task list: "project 2 docs/Task_Allocation_Part2.pdf".
import base64
import hashlib
import os
from typing import ClassVar

from models.photo_error import PhotoError


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
