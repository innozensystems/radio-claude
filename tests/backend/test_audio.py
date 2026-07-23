import io


def test_serve_audio_known_file(client):
    client.post(
        "/tracks",
        data={"title": "Song", "audio": (io.BytesIO(b"audio-bytes"), "known.mp3")},
        content_type="multipart/form-data",
    )

    resp = client.get("/audio/known.mp3")
    assert resp.status_code == 200
    assert resp.data == b"audio-bytes"


def test_serve_audio_unknown_file(client):
    resp = client.get("/audio/does-not-exist.mp3")
    assert resp.status_code == 404


def test_serve_audio_path_traversal_blocked(client):
    resp = client.get("/audio/..%2Fapp.py")
    assert resp.status_code in (404, 400)
