import io

from fastapi.testclient import TestClient
from PIL import Image

from api.auth import current_user
from api.main import app


def test_private_image_upload_and_saved_notes(tmp_path, monkeypatch):
    monkeypatch.setattr("api.images.DATA_DIR", tmp_path)
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), "navy").save(buffer, format="PNG")
    with TestClient(app) as client:
        invalid = client.post("/v1/images", files={"file": ("fake.png", b"not an image", "image/png")})
        assert invalid.status_code == 422
        created = client.post("/v1/images", files={"file": ("sky.png", buffer.getvalue(), "image/png")})
        assert created.status_code == 201, created.text
        image = created.json()
        assert (image["width"], image["height"]) == (8, 6)
        saved = client.put(f"/v1/images/{image['id']}", json={"note": "Bright point", "marks": [{"x": 25, "y": 50}]})
        assert saved.status_code == 200
        assert saved.json()["marks"] == [{"x": 25.0, "y": 50.0}]
        assert client.get(image["image_url"]).content == buffer.getvalue()
        app.dependency_overrides[current_user] = lambda: "0x" + "2" * 40
        assert client.get(image["image_url"]).status_code == 404
        assert client.get("/v1/images").json()["images"] == []


def test_failed_metadata_commit_removes_uploaded_file(tmp_path, monkeypatch):
    monkeypatch.setattr("api.images.DATA_DIR", tmp_path)
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "navy").save(buffer, format="PNG")

    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def add(self, _row):
            pass

        def commit(self):
            raise RuntimeError("database write failed")

    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr("api.images.SessionLocal", BrokenSession)
        response = client.post("/v1/images", files={"file": ("sky.png", buffer.getvalue(), "image/png")})
        assert response.status_code == 500
    assert list((tmp_path / "images").iterdir()) == []
