import pytest

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
