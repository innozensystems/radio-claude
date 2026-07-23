from app import VOTER_COOKIE, voter_serializer


def rate(client, user_id="user-1", title="Track", artist="Artist", album="Album", rating="up"):
    client.set_cookie(VOTER_COOKIE, voter_serializer().dumps(user_id))
    return client.post(
        "/rate",
        json={
            "title": title,
            "artist": artist,
            "album": album,
            "rating": rating,
        },
    )


def test_rate_new_up(client):
    resp = rate(client, rating="up")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"up_count": 1, "down_count": 0, "user_rating": "up"}


def test_rate_change_rating_updates_not_duplicates(client):
    rate(client, user_id="user-1", rating="up")
    resp = rate(client, user_id="user-1", rating="down")

    assert resp.status_code == 200
    assert resp.get_json() == {"up_count": 0, "down_count": 1, "user_rating": "down"}


def test_rate_same_rating_twice_is_idempotent(client):
    rate(client, user_id="user-1", rating="up")
    resp = rate(client, user_id="user-1", rating="up")

    assert resp.get_json() == {"up_count": 1, "down_count": 0, "user_rating": "up"}


def test_rate_ignores_client_supplied_user_id(client):
    first = client.post(
        "/rate",
        json={"user_id": "attacker-chosen-1", "title": "Track", "rating": "up"},
    )
    second = client.post(
        "/rate",
        json={"user_id": "attacker-chosen-2", "title": "Track", "rating": "up"},
    )

    assert first.status_code == 200
    assert second.get_json()["up_count"] == 1


def test_rate_missing_title(client):
    resp = client.post("/rate", json={"rating": "up"})
    assert resp.status_code == 400


def test_rate_invalid_rating_value(client):
    resp = rate(client, rating="sideways")
    assert resp.status_code == 400


def test_rate_multiple_users_aggregate(client):
    rate(client, user_id="user-1", rating="up")
    rate(client, user_id="user-2", rating="up")
    resp = rate(client, user_id="user-3", rating="down")

    body = resp.get_json()
    assert body["up_count"] == 2
    assert body["down_count"] == 1
    assert body["user_rating"] == "down"


def test_rate_status_no_prior_rating(client):
    resp = client.get("/rate-status", query_string={"title": "Track"})
    assert resp.status_code == 200
    assert resp.get_json() == {"up_count": 0, "down_count": 0, "user_rating": None}


def test_rate_status_reflects_existing_rating(client):
    rate(client, user_id="user-1", rating="up")

    resp = client.get(
        "/rate-status",
        query_string={"title": "Track", "artist": "Artist", "album": "Album"},
    )
    assert resp.get_json() == {"up_count": 1, "down_count": 0, "user_rating": "up"}


def test_rate_status_missing_title(client):
    resp = client.get("/rate-status")
    assert resp.status_code == 400


def test_server_sets_signed_http_only_voter_cookie(client):
    resp = client.post("/rate", json={"title": "Track", "rating": "up"})
    cookie = resp.headers.get("Set-Cookie", "")

    assert f"{VOTER_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
