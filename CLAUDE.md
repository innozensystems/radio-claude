# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Radio Claude — a single-page Flask app that plays a live HLS audio stream in the browser and lets listeners rate tracks. There is no build step; the frontend is vanilla JavaScript, HTML, and CSS.

## Common commands

Run the app (also initializes the SQLite database):

```bash
source .venv/bin/activate
python3 app.py
```

The server starts on `http://127.0.0.1:5000` with Flask debug mode enabled.

Install or refresh dependencies:

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

There is no test suite, lint config, or formatter configured yet.

## Architecture

- **Entry point:** `app.py` — a plain Flask application that serves the SPA, REST endpoints, and uploaded audio files.
- **Database:** SQLite file at `data/app.db`. Tables are created automatically by `init_db()` when `app.py` runs.
  - `tracks` — library of uploaded audio files (`title`, `artist`, `filename`).
  - `ratings` — thumbs-up/down votes keyed by `user_id`, `title`, `artist`, `album` with a unique constraint on that tuple.
- **Templates:** `templates/index.html` renders the initial page.
- **Static assets:** `static/js/player.js`, `static/css/style.css`, and `static/img/`.
- **Uploads:** user-uploaded audio files go to `uploads/`.

### Backend routes

- `GET /` — serves `index.html`.
- `GET /tracks` — lists uploaded tracks as JSON.
- `POST /tracks` — upload an audio file (multipart/form-data). Deduplicates filenames by appending `_1`, `_2`, etc.
- `DELETE /tracks/<id>` — removes a track from the DB and deletes its file from `uploads/`.
- `GET /audio/<filename>` — streams an uploaded file.
- `POST /rate` — records or updates a user's up/down rating.
- `GET /rate-status` — returns aggregate up/down counts plus the current user's rating.

### Frontend behavior

- Loads the live HLS stream at `https://d3d4yli4hf5bmh.cloudfront.net/hls/live.m3u8`.
- Uses native HLS support when available; otherwise falls back to `hls.js` loaded from CDN.
- Polls `https://d3d4yli4hf5bmh.cloudfront.net/metadatav2.json` every 3 seconds to update the now-playing display and a five-track history list.
- Displays a track timer that resets whenever the polled metadata changes.
- Ratings use a `user_id` generated once and stored in `localStorage`.

## Development notes

- The `.gitignore` excludes `data/`, `uploads/`, `.venv/`, `__pycache__/`, `.env`, and `.env.local`.
- `app.config["MAX_CONTENT_LENGTH"]` is set to 32 MB for uploads.
- Flask runs with `debug=True` in the `__main__` block.
- `RadioClaude_Style_Guide.txt` documents brand colors, typography, and UI patterns, but the current CSS does not fully follow it.
