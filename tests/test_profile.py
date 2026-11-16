# Darrel
import io

from tests.api_helpers import make_client
from tests.test_web_api import sample_bytes
from web_support.profile_store import ProfileStore


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


def test_bad_pictures_are_refused_with_reasons(tmp_path):
    client = make_client(tmp_path)
    assert "Choose a picture" in client.put("/api/profile/photo").get_json()["errors"][0]
    assert "not a real image" in upload(client, b"just text").get_json()["errors"][0]
    assert ".png, .jpg" in upload(client, sample_bytes(), "me.gif").get_json()["errors"][0]
    too_big = upload(client, b"x" * (ProfileStore.MAX_BYTES + 1))
    assert too_big.status_code == 422 and "larger than 1 MB" in too_big.get_json()["errors"][0]
    assert client.get("/api/profile").get_json()["has_photo"] is False


def test_each_account_has_its_own_picture_and_it_needs_a_login(tmp_path):
    client = make_client(tmp_path)
    upload(client, sample_bytes())
    token = client.post("/api/login", json={"username": "darrel", "password": "123"}).get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    assert client.get("/api/profile").get_json() == {"username": "darrel", "has_photo": False}
    assert client.get(f"/api/profile/photo?token={token}").status_code == 404
    client.environ_base.pop("HTTP_AUTHORIZATION")
    assert client.get("/api/profile").status_code == 401 and upload(client, sample_bytes()).status_code == 401
