"""Flask single-page app with SQLite and audio tracks."""

import os
import sqlite3

from flask import Flask, g, jsonify, render_template, request, send_from_directory

DATABASE = os.path.join(os.path.dirname(__file__), "data", "app.db")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")

os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB
app.config["DATABASE"] = DATABASE


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db(db_path=None):
    with sqlite3.connect(db_path or app.config["DATABASE"]) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    return render_template("index.html")


@app.route("/tracks", methods=["GET"])
def list_tracks():
    db = get_db()
    rows = db.execute(
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
    cursor = db.execute(
        "INSERT INTO tracks (title, artist, filename) VALUES (?, ?, ?)",
        (title, artist, os.path.basename(saved_path)),
    )
    db.commit()
    track_id = cursor.lastrowid

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
    user_id = (data.get("user_id") or "").strip()
    title = (data.get("title") or "").strip()
    artist = (data.get("artist") or "").strip()
    album = (data.get("album") or "").strip()
    rating = (data.get("rating") or "").strip().lower()

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not title:
        return jsonify({"error": "title is required"}), 400
    if rating not in ("up", "down"):
        return jsonify({"error": "rating must be 'up' or 'down'"}), 400

    db = get_db()
    existing = db.execute(
        "SELECT id, rating FROM ratings WHERE user_id = ? AND title = ? AND artist = ? AND album = ?",
        (user_id, title, artist, album),
    ).fetchone()

    if existing is None:
        db.execute(
            "INSERT INTO ratings (user_id, title, artist, album, rating) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, artist, album, rating),
        )
    elif existing["rating"] != rating:
        db.execute(
            "UPDATE ratings SET rating = ? WHERE id = ?",
            (rating, existing["id"]),
        )
    db.commit()

    return jsonify(get_rating_summary(title, artist, album, user_id))


@app.route("/rate-status", methods=["GET"])
def rate_status():
    user_id = (request.args.get("user_id") or "").strip()
    title = (request.args.get("title") or "").strip()
    artist = (request.args.get("artist") or "").strip()
    album = (request.args.get("album") or "").strip()

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    if not title:
        return jsonify({"error": "title is required"}), 400

    return jsonify(get_rating_summary(title, artist, album, user_id))


def get_rating_summary(title, artist, album, user_id):
    db = get_db()
    params = [title, artist, album]
    counts = db.execute(
        "SELECT rating, COUNT(*) AS n FROM ratings WHERE title = ? AND artist = ? AND album = ? GROUP BY rating",
        params,
    ).fetchall()
    up_count = sum(row["n"] for row in counts if row["rating"] == "up")
    down_count = sum(row["n"] for row in counts if row["rating"] == "down")

    user_row = db.execute(
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
    row = db.execute("SELECT filename FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Track not found"}), 404

    db.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    db.commit()

    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], row["filename"])
    if os.path.exists(audio_path):
        os.remove(audio_path)

    return jsonify({"deleted": track_id})


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
