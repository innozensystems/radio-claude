import os

import pytest

os.environ.setdefault("STREAM_URL", "https://stream.example.com/live.m3u8")
os.environ.setdefault(
    "HLS_FALLBACK_URL", "https://stream.example.com/compatible.m3u8"
)
os.environ.setdefault("METADATA_URL", "https://stream.example.com/metadata.json")
os.environ.setdefault("COVER_URL", "https://stream.example.com/cover.jpg")

from app import app as flask_app
from app import init_db


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    flask_app.config["TESTING"] = True
    flask_app.config["DATABASE"] = str(db_path)
    flask_app.config["UPLOAD_FOLDER"] = str(upload_dir)

    init_db(str(db_path))

    with flask_app.test_client() as test_client:
        yield test_client
