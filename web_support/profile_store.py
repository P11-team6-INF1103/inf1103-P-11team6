# Darrel
import base64
import binascii

from data_stores.db_json import DbJson
from database import Database
from models.incident_photo import IncidentPhoto


class ProfileStore:
    # Each account's profile picture. One document per account in the database, so it survives a server restart.
    MAX_BYTES = 1024 * 1024

    def __init__(self, database: Database) -> None:
        self._database = database

    def _document(self, username: str) -> DbJson:
        return DbJson(self._database, f"profile_photo:{username}", dict)

    # Saves the picture (already checked by IncidentPhoto.from_bytes). False if the database could not be written.
    def save_photo(self, username: str, photo: IncidentPhoto) -> bool:
        return self._document(username).write({"mime_type": photo.mime_type, "content": photo.as_base64()})

    # (bytes, MIME type) of the account's picture, or None if it has none.
    def photo(self, username: str) -> tuple[bytes, str] | None:
        data, error = self._document(username).read()
        if error or not data.get("content"):
            return None
        try:
            return base64.b64decode(data["content"], validate=True), data.get("mime_type", "image/png")
        except (binascii.Error, TypeError):
            return None

    def delete_photo(self, username: str) -> bool:
        return self._document(username).delete()
