"""Flask single-page app with audio tracks and ratings."""

import os
import secrets
import sqlite3
import uuid
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, render_template, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

DATABASE = os.path.join(os.path.dirname(__file__), "data", "app.db")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")

os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB
app.config["DATABASE"] = os.environ.get("DATABASE_URL", DATABASE)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


def configured_url(name, default=None):
    value = os.environ.get(name) or default
    if not value:
        raise RuntimeError(f"{name} must be configured")

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{name} must be an absolute HTTP(S) URL")
    return value


def url_origin(url):
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


app.config["STREAM_URL"] = configured_url("STREAM_URL")
app.config["HLS_FALLBACK_URL"] = configured_url(
    "HLS_FALLBACK_URL", app.config["STREAM_URL"]
)
app.config["METADATA_URL"] = configured_url("METADATA_URL")
app.config["COVER_URL"] = configured_url("COVER_URL")

VOTER_COOKIE = "radio_voter"
VOTER_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


@app.after_request
def set_csp_header(response):
    stream_origins = sorted(
        {
            url_origin(app.config["STREAM_URL"]),
            url_origin(app.config["HLS_FALLBACK_URL"]),
        }
    )
    metadata_origin = url_origin(app.config["METADATA_URL"])
    cover_origin = url_origin(app.config["COVER_URL"])
    connect_sources = " ".join(
        sorted({"'self'", metadata_origin, *stream_origins})
    )
    media_sources = " ".join([*stream_origins, "blob:"])

    response.headers["Content-Security-Policy"] = (
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' https://fonts.googleapis.com; "
        f"connect-src {connect_sources}; "
        f"media-src {media_sources}; "
        "worker-src blob:; "
        f"img-src 'self' {cover_origin} https://fonts.gstatic.com; "
        "font-src https://fonts.gstatic.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "default-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    if request.path == "/":
        response.headers["Cache-Control"] = "no-cache"

    voter_cookie = getattr(g, "_voter_cookie", None)
    if voter_cookie:
        response.set_cookie(
            VOTER_COOKIE,
            voter_cookie,
            max_age=VOTER_COOKIE_MAX_AGE,
            httponly=True,
            secure=request.is_secure,
            samesite="Strict",
        )
    return response


def is_postgres(database=None):
    database = database or app.config["DATABASE"]
    return database.startswith(("postgresql://", "postgres://"))


def connect_db(database=None):
    database = database or app.config["DATABASE"]
    if is_postgres(database):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(database, row_factory=dict_row)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    return connection


def execute(db, query, params=()):
    if is_postgres():
        query = query.replace("?", "%s")
    return db.execute(query, params)


def voter_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="radio-voter")


def current_voter_id():
    token = request.cookies.get(VOTER_COOKIE)
    if token:
        try:
            return voter_serializer().loads(token, max_age=VOTER_COOKIE_MAX_AGE)
        except (BadSignature, SignatureExpired):
            pass

    voter_id = str(uuid.uuid4())
    g._voter_cookie = voter_serializer().dumps(voter_id)
    return voter_id


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = connect_db()
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db(db_path=None):
    database = db_path or app.config["DATABASE"]
    primary_key = (
        "BIGSERIAL PRIMARY KEY"
        if is_postgres(database)
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    with connect_db(database) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS tracks (
                id {primary_key},
                title TEXT NOT NULL,
                artist TEXT,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS ratings (
                id {primary_key},
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT,
                album TEXT,
                rating TEXT NOT NULL CHECK(rating IN ('up', 'down')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, title, artist, album)
            )
            """
        )
        conn.commit()


@app.route("/")
def index():
    return render_template(
        "index.html",
        stream_url=app.config["STREAM_URL"],
        hls_fallback_url=app.config["HLS_FALLBACK_URL"],
        metadata_url=app.config["METADATA_URL"],
        cover_url=app.config["COVER_URL"],
    )


@app.route("/tracks", methods=["GET"])
def list_tracks():
    db = get_db()
    rows = execute(
        db,
        "SELECT id, title, artist, filename FROM tracks ORDER BY created_at DESC"
    ).fetchall()
    tracks = [
        {
            "id": row["id"],
            "title": row["title"],
            "artist": row["artist"],
            "url": f"/audio/{row['filename']}",
        }
        for row in rows
    ]
    return jsonify(tracks)


@app.route("/tracks", methods=["POST"])
def create_track():
    title = request.form.get("title", "Untitled").strip()
    artist = request.form.get("artist", "").strip()
    file = request.files.get("audio")

    if not file or file.filename == "":
        return jsonify({"error": "No audio file provided"}), 400

    filename = os.path.basename(file.filename)
    saved_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    counter = 1
    while os.path.exists(saved_path):
        name, ext = os.path.splitext(filename)
        saved_path = os.path.join(app.config["UPLOAD_FOLDER"], f"{name}_{counter}{ext}")
        counter += 1

    file.save(saved_path)

    db = get_db()
    params = (title, artist, os.path.basename(saved_path))
    if is_postgres():
        cursor = execute(
            db,
            "INSERT INTO tracks (title, artist, filename) VALUES (?, ?, ?) RETURNING id",
            params,
        )
        track_id = cursor.fetchone()["id"]
    else:
        cursor = execute(
            db,
            "INSERT INTO tracks (title, artist, filename) VALUES (?, ?, ?)",
            params,
        )
        track_id = cursor.lastrowid
    db.commit()

    return jsonify(
        {
            "id": track_id,
            "title": title,
            "artist": artist,
            "url": f"/audio/{os.path.basename(saved_path)}",
        }
    ), 201


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/rate", methods=["POST"])
def rate_song():
    data = request.get_json(force=True, silent=True) or {}
    user_id = current_voter_id()
    title = (data.get("title") or "").strip()
    artist = (data.get("artist") or "").strip()
    album = (data.get("album") or "").strip()
    rating = (data.get("rating") or "").strip().lower()

    if not title:
        return jsonify({"error": "title is required"}), 400
    if rating not in ("up", "down"):
        return jsonify({"error": "rating must be 'up' or 'down'"}), 400

    db = get_db()
    existing = execute(
        db,
        "SELECT id, rating FROM ratings WHERE user_id = ? AND title = ? AND artist = ? AND album = ?",
        (user_id, title, artist, album),
    ).fetchone()

    if existing is None:
        execute(
            db,
            "INSERT INTO ratings (user_id, title, artist, album, rating) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, artist, album, rating),
        )
    elif existing["rating"] != rating:
        execute(
            db,
            "UPDATE ratings SET rating = ? WHERE id = ?",
            (rating, existing["id"]),
        )
    db.commit()

    return jsonify(get_rating_summary(title, artist, album, user_id))


@app.route("/rate-status", methods=["GET"])
def rate_status():
    user_id = current_voter_id()
    title = (request.args.get("title") or "").strip()
    artist = (request.args.get("artist") or "").strip()
    album = (request.args.get("album") or "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    return jsonify(get_rating_summary(title, artist, album, user_id))


def get_rating_summary(title, artist, album, user_id):
    db = get_db()
    params = [title, artist, album]
    counts = execute(
        db,
        "SELECT rating, COUNT(*) AS n FROM ratings WHERE title = ? AND artist = ? AND album = ? GROUP BY rating",
        params,
    ).fetchall()
    up_count = sum(row["n"] for row in counts if row["rating"] == "up")
    down_count = sum(row["n"] for row in counts if row["rating"] == "down")

    user_row = execute(
        db,
        "SELECT rating FROM ratings WHERE user_id = ? AND title = ? AND artist = ? AND album = ?",
        [user_id] + params,
    ).fetchone()

    return {
        "up_count": up_count,
        "down_count": down_count,
        "user_rating": user_row["rating"] if user_row else None,
    }


@app.route("/tracks/<int:track_id>", methods=["DELETE"])
def delete_track(track_id):
    db = get_db()
    row = execute(
        db, "SELECT filename FROM tracks WHERE id = ?", (track_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "Track not found"}), 404

    execute(db, "DELETE FROM tracks WHERE id = ?", (track_id,))
    db.commit()

    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], row["filename"])
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return jsonify({"deleted": track_id})


@app.route("/health")
def health():
    execute(get_db(), "SELECT 1").fetchone()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=5000,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
