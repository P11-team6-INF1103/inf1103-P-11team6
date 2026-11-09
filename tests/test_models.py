# Lennart
import os

import pytest

from models import Incident, IncidentPhoto, PhotoError

SAMPLE_PHOTO = os.path.join(os.path.dirname(__file__), "sample_photo.png")


def test_valid_png_is_accepted_and_encoded():
    photo = IncidentPhoto.from_file(SAMPLE_PHOTO)
    assert photo.mime_type == "image/png" and photo.file_name == "sample_photo.png"
    assert photo.as_base64().startswith("iVBORw0KGgo")  # base64 of the PNG signature
    assert len(photo.fingerprint()) == 16


@pytest.mark.parametrize("name, content, message", [
    ("notes.txt", b"hello", "must be a .png"),
    ("missing.png", None, "No file found"),
    ("empty.png", b"", "empty"),
    ("fake.jpg", b"this is not a jpeg", "not a real image"),
])
def test_bad_photos_are_rejected_with_a_reason(tmp_path, name, content, message):
    path = tmp_path / name
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(PhotoError, match=message):
        IncidentPhoto.from_file(str(path))


def test_photo_over_5_mb_is_rejected(tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * IncidentPhoto.MAX_BYTES)
    with pytest.raises(PhotoError, match="5 MB"):
        IncidentPhoto.from_file(str(path))


def test_incident_protects_typed_fields_and_round_trips():
    incident = Incident("Worker slipped on wet floor", "Site A", "supervisor", True, "2026-10-20T09:00:00",
                        IncidentPhoto.from_file(SAMPLE_PHOTO))
    incident.update({"description": "changed", "severity_estimate": 3})
    assert incident.description == "Worker slipped on wet floor"
    assert incident.get("severity_estimate") == 3 and incident.get("photo_file") == "sample_photo.png"
    again = Incident.from_dict(incident.to_dict())
    assert again.to_dict() == incident.to_dict()
    assert not again.has_photo()  # photo bytes are not reloaded, only the file name is kept


def test_from_dict_rejects_broken_records():
    with pytest.raises(ValueError):
        Incident.from_dict({"description": "no location"})
