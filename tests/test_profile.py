# Darrel
import io

from tests.api_helpers import make_client
from tests.test_web_api import sample_bytes


def upload(client, content, name="me.png"):
    return client.put("/api/profile/photo", data={"photo": (io.BytesIO(content), name)},
                      content_type="multipart/form-data")


def test_profile_shows_the_logged_in_account(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/profile").get_json() == {"username": "supervisor", "has_photo": False}
    assert client.get("/api/profile/photo").status_code == 404


def test_upload_replace_and_remove_a_profile_picture(tmp_path):
    client = make_client(tmp_path)
    assert upload(client, sample_bytes()).get_json()["has_photo"] is True
    picture = client.get("/api/profile/photo")
    assert picture.status_code == 200 and picture.mimetype == "image/png" and picture.data == sample_bytes()
    assert upload(client, sample_bytes(), "again.png").status_code == 200
    assert client.delete("/api/profile/photo").get_json()["has_photo"] is False
    assert client.get("/api/profile/photo").status_code == 404
