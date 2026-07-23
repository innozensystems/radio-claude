import io
import os


def upload(client, title="My Song", artist="An Artist", filename="song.mp3", content=b"fake audio bytes"):
    return client.post(
        "/tracks",
        data={
            "title": title,
            "artist": artist,
            "audio": (io.BytesIO(content), filename),
        },
        content_type="multipart/form-data",
    )


def test_list_tracks_empty(client):
    resp = client.get("/tracks")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_track(client):
    resp = upload(client)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "My Song"
    assert body["artist"] == "An Artist"
    assert body["url"] == "/audio/song.mp3"

    saved_path = os.path.join(client.application.config["UPLOAD_FOLDER"], "song.mp3")
    assert os.path.exists(saved_path)

    listed = client.get("/tracks").get_json()
    assert len(listed) == 1
    assert listed[0]["title"] == "My Song"


def test_create_track_missing_file(client):
    resp = client.post(
        "/tracks",
        data={"title": "No File"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_track_default_title(client):
    resp = client.post(
        "/tracks",
        data={"audio": (io.BytesIO(b"data"), "untitled.mp3")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "Untitled"


def test_create_track_deduplicates_filename(client):
    first = upload(client, title="First", filename="dupe.mp3")
    second = upload(client, title="Second", filename="dupe.mp3")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.get_json()["url"] == "/audio/dupe.mp3"
    assert second.get_json()["url"] == "/audio/dupe_1.mp3"

    upload_dir = client.application.config["UPLOAD_FOLDER"]
    assert os.path.exists(os.path.join(upload_dir, "dupe.mp3"))
    assert os.path.exists(os.path.join(upload_dir, "dupe_1.mp3"))

    listed = client.get("/tracks").get_json()
    assert len(listed) == 2


def test_delete_track(client):
    created = upload(client, filename="delete_me.mp3").get_json()
    upload_dir = client.application.config["UPLOAD_FOLDER"]
    saved_path = os.path.join(upload_dir, "delete_me.mp3")
    assert os.path.exists(saved_path)

    resp = client.delete(f"/tracks/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == {"deleted": created["id"]}
    assert not os.path.exists(saved_path)
    assert client.get("/tracks").get_json() == []


def test_delete_track_not_found(client):
    resp = client.delete("/tracks/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_create_track_over_max_content_length(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 10
    resp = upload(client, content=b"this payload is definitely bigger than ten bytes")
    assert resp.status_code == 413
