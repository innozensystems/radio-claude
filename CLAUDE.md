# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Radio Claude — a single-page Flask app that plays a live HLS audio stream in the browser and lets listeners rate tracks. There is no build step; the frontend is vanilla JavaScript, HTML, and CSS.

## Common commands

Run the app (also initializes the SQLite database):

```bash
source .venv/bin/activate
set -a
source .env
set +a
python3 app.py
```

The server starts on `http://127.0.0.1:5000` with Flask debug mode enabled.

Install or refresh dependencies:

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Install dev dependencies and run the backend test suite:

```bash
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
./tests/infrastructure/security_checks.sh
```

There is no frontend test suite, lint config, or formatter configured. Frontend testing was scoped (Playwright e2e against mocked HLS/metadata endpoints) but deliberately skipped — not worth the added toolchain for this project's size.

## Architecture

- **Entry point:** `app.py` — a plain Flask application that serves the SPA, REST endpoints, and uploaded audio files.
- **Database:** SQLite file at `data/app.db`. Tables are created automatically by `init_db()` when `app.py` runs.
  - `tracks` — library of uploaded audio files (`title`, `artist`, `filename`).
  - `ratings` — thumbs-up/down votes keyed by `user_id`, `title`, `artist`, `album` with a unique constraint on that tuple.
- **Templates:** `templates/index.html` renders the initial page.
- **Static assets:** `static/js/player.js`, `static/css/style.css`, and `static/img/`.
- **Uploads:** user-uploaded audio files go to `uploads/`.
- **Tests:** `tests/backend/` — pytest suite covering `/tracks`, `/audio`, `/rate`, `/rate-status`. Each test gets an isolated SQLite DB and uploads dir via `tmp_path` (never touches `data/app.db`). Enabled by making `DATABASE` configurable through `app.config["DATABASE"]` instead of a hardcoded module constant.

### Backend routes

- `GET /` — serves `index.html`.
- `GET /tracks` — lists uploaded tracks as JSON.
- `POST /tracks` — upload an audio file (multipart/form-data). Deduplicates filenames by appending `_1`, `_2`, etc.
- `DELETE /tracks/<id>` — removes a track from the DB and deletes its file from `uploads/`.
- `GET /audio/<filename>` — streams an uploaded file.
- `POST /rate` — records or updates a user's up/down rating.
- `GET /rate-status` — returns aggregate up/down counts plus the current user's rating.

### Frontend behavior

- Reads `STREAM_URL`, `HLS_FALLBACK_URL`, `METADATA_URL`, and `COVER_URL`
  from the runtime environment; no provider endpoints belong in source.
- Uses native HLS where reliable and the configured fallback HLS rendition
  with a pinned `hls.js` version in Chromium.
- Polls the configured metadata endpoint every 5 seconds during active
  playback to update the now-playing display and five-track history.
- Displays a track timer that resets whenever the polled metadata changes.
- Ratings use a signed, HttpOnly voter cookie issued by the server.

## Development notes

- Copy `.env.example` to `.env` and use only stream sources the operator is
  authorized to embed. Never commit real endpoints, signed URLs, or media.
- The `.gitignore` excludes local `.env.*` files but retains `.env.example`.
- `app.config["MAX_CONTENT_LENGTH"]` is set to 32 MB for uploads.
- Flask debug mode is enabled only when `FLASK_DEBUG=1`.
- `RadioClaude_Style_Guide.txt` documents brand colors, typography, and UI patterns, but the current CSS does not fully follow it.
