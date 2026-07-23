from http.cookies import SimpleCookie

import pytest

from app import VOTER_COOKIE, app, configured_url, voter_serializer


def extract_cookie(response, name):
    cookies = SimpleCookie()
    cookies.load(response.headers["Set-Cookie"])
    return cookies[name]


def test_tampered_voter_cookie_is_replaced(client):
    client.set_cookie(VOTER_COOKIE, "tampered-cookie")

    response = client.get("/rate-status", query_string={"title": "Track"})

    assert response.status_code == 200
    replacement = extract_cookie(response, VOTER_COOKIE)
    assert replacement.value != "tampered-cookie"
    assert voter_serializer().loads(replacement.value)


def test_signed_voter_identities_are_isolated(client):
    client.set_cookie(VOTER_COOKIE, voter_serializer().dumps("voter-one"))
    first_response = client.post(
        "/rate",
        json={"title": "Track", "artist": "Artist", "album": "Album", "rating": "up"},
    )

    client.set_cookie(VOTER_COOKIE, voter_serializer().dumps("voter-two"))
    second_response = client.post(
        "/rate",
        json={"title": "Track", "artist": "Artist", "album": "Album", "rating": "down"},
    )

    assert first_response.status_code == 200
    assert second_response.get_json() == {
        "up_count": 1,
        "down_count": 1,
        "user_rating": "down",
    }


def test_security_headers_are_present(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )

    csp = response.headers["Content-Security-Policy"]
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert "'unsafe-inline'" not in csp


def test_media_configuration_is_rendered_and_allowed_by_csp(client):
    response = client.get("/")
    body = response.get_data(as_text=True)
    csp = response.headers["Content-Security-Policy"]

    assert 'data-stream-url="https://stream.example.com/live.m3u8"' in body
    assert (
        'data-hls-fallback-url="https://stream.example.com/compatible.m3u8"'
        in body
    )
    assert 'data-metadata-url="https://stream.example.com/metadata.json"' in body
    assert 'data-cover-url="https://stream.example.com/cover.jpg"' in body
    assert "https://stream.example.com" in csp


def test_configured_url_rejects_missing_and_non_http_values(monkeypatch):
    monkeypatch.delenv("TEST_MEDIA_URL", raising=False)
    with pytest.raises(RuntimeError, match="must be configured"):
        configured_url("TEST_MEDIA_URL")

    monkeypatch.setenv("TEST_MEDIA_URL", "file:///tmp/media.m3u8")
    with pytest.raises(RuntimeError, match=r"absolute HTTP\(S\) URL"):
        configured_url("TEST_MEDIA_URL")


def test_oversized_request_is_rejected(client):
    original_limit = app.config["MAX_CONTENT_LENGTH"]
    app.config["MAX_CONTENT_LENGTH"] = 128
    try:
        response = client.post(
            "/rate",
            data=b"x" * 129,
            content_type="application/json",
        )
    finally:
        app.config["MAX_CONTENT_LENGTH"] = original_limit

    assert response.status_code == 413
