def rate(client, user_id="user-1", title="Track", artist="Artist", album="Album", rating="up"):
    return client.post(
        "/rate",
        json={
            "user_id": user_id,
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


def test_rate_missing_user_id(client):
    resp = client.post("/rate", json={"title": "Track", "rating": "up"})
    assert resp.status_code == 400


def test_rate_missing_title(client):
    resp = client.post("/rate", json={"user_id": "user-1", "rating": "up"})
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
    resp = client.get("/rate-status", query_string={"user_id": "user-1", "title": "Track"})
    assert resp.status_code == 200
    assert resp.get_json() == {"up_count": 0, "down_count": 0, "user_rating": None}


def test_rate_status_reflects_existing_rating(client):
    rate(client, user_id="user-1", rating="up")

    resp = client.get(
        "/rate-status",
        query_string={"user_id": "user-1", "title": "Track", "artist": "Artist", "album": "Album"},
    )
    assert resp.get_json() == {"up_count": 1, "down_count": 0, "user_rating": "up"}


def test_rate_status_missing_user_id(client):
    resp = client.get("/rate-status", query_string={"title": "Track"})
    assert resp.status_code == 400


def test_rate_status_missing_title(client):
    resp = client.get("/rate-status", query_string={"user_id": "user-1"})
    assert resp.status_code == 400
