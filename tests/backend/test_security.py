from http.cookies import SimpleCookie

from app import VOTER_COOKIE, app, voter_serializer


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
