# Darrel
import io

from tests.api_helpers import make_client


def upload(client, content, name="me.png"):
    return client.put("/api/profile/photo", data={"photo": (io.BytesIO(content), name)},
                      content_type="multipart/form-data")


def test_profile_shows_the_logged_in_account(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/api/profile").get_json() == {"username": "supervisor", "has_photo": False}
    assert client.get("/api/profile/photo").status_code == 404
