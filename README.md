# Radio Claude

A single-page Flask app that plays a live HLS audio stream in the browser and lets listeners rate tracks. No build step — just vanilla JavaScript, HTML, and CSS.

## Features

- **Live HLS stream playback** with native support or an `hls.js` fallback
- **Now-playing metadata** polled every 3 seconds from the stream server
- **Track history** showing the last five played tracks
- **Thumbs up/down ratings** per track, aggregated across listeners
- **Per-listener identity** via a UUID stored in `localStorage`
- **Audio upload library** with SQLite-backed metadata, playable on demand
- **Flask debug server** for local development

## Stack

- **Flask** — Python web framework
- **SQLite** — file-based database for tracks and ratings
- **Vanilla JavaScript + HTML/CSS** — no build step or frontend framework
- **hls.js** — HLS fallback loaded from CDN

## Quick start

1. Create and activate a virtual environment, then install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python3 -m pip install -r requirements.txt
   ```

2. Start the server (this also initializes the SQLite database):

   ```bash
   source .venv/bin/activate
   python3 app.py
   ```

3. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Testing

Backend routes are covered by a pytest suite in `tests/backend/`. Each test runs against an isolated temp SQLite database, not `data/app.db`.

```bash
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

There's no frontend test suite — it was scoped (Playwright e2e against mocked HLS/metadata endpoints) but skipped as not worth the added toolchain for this project's size.

## Project structure

```
.
├── app.py                 # Flask app: routes, database, upload handling
├── requirements.txt       # Python dependencies
├── requirements-dev.txt   # Dev/test dependencies (pytest)
├── pytest.ini             # pytest config
├── tests/
│   └── backend/           # pytest suite for Flask routes
├── data/                  # SQLite database (created at runtime)
├── uploads/               # Uploaded audio files (created at runtime)
├── templates/
│   └── index.html         # Single-page app shell
├── static/
│   ├── js/player.js       # Stream player, metadata polling, ratings UI
│   ├── css/style.css      # App styles
│   └── img/               # Logos, covers, mascot
├── RadioClaude_Style_Guide.txt  # Brand colors, typography, UI patterns
└── README.md              # This file
```

## Backend API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Serve the SPA (`index.html`) |
| `GET`  | `/tracks` | List uploaded tracks as JSON |
| `POST` | `/tracks` | Upload an audio file (`multipart/form-data`); deduplicates filenames by appending `_1`, `_2`, etc. |
| `DELETE` | `/tracks/<id>` | Remove a track from the library and delete its file |
| `GET`  | `/audio/<filename>` | Stream an uploaded audio file |
| `POST` | `/rate` | Record or update a user's up/down rating for a track |
| `GET`  | `/rate-status` | Aggregate up/down counts plus the current user's rating |

## Frontend behavior

- Loads the live HLS stream at `https://d3d4yli4hf5bmh.cloudfront.net/hls/live.m3u8`.
- Uses native HLS support when available; otherwise falls back to `hls.js` from CDN.
- Polls `https://d3d4yli4hf5bmh.cloudfront.net/metadatav2.json` every 3 seconds to update the now-playing display and a five-track history list.
- Displays a track timer that resets whenever the polled metadata changes.
- Ratings use a `user_id` generated once and stored in `localStorage`.

## Development notes

- The SQLite database and `uploads/` directory are created automatically on first run.
- `app.config["MAX_CONTENT_LENGTH"]` is set to 32 MB for uploads.
- Flask runs with `debug=True` in the `__main__` block.
- The `.gitignore` excludes `data/`, `uploads/`, `.venv/`, `__pycache__/`, `.env`, and `.env.local`.
- `RadioClaude_Style_Guide.txt` documents the brand palette and UI patterns.
