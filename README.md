# Radio Claude

A single-page Flask app that plays a live HLS audio stream in the browser and lets listeners rate tracks. No build step — just vanilla JavaScript, HTML, and CSS.

## Features

- **Live HLS stream playback** with native support or an `hls.js` fallback
- **Now-playing metadata** polled every 5 seconds from the stream server
- **Track history** showing the last five played tracks
- **Thumbs up/down ratings** per track, aggregated across listeners
- **Per-listener identity** via a signed, HttpOnly cookie
- **Audio upload library** with database-backed metadata, playable on demand
- **Flask debug server** for local development

## Stack

- **Flask** — Python web framework
- **SQLite / PostgreSQL** — SQLite locally and PostgreSQL in production
- **Gunicorn + Nginx** — production application and reverse-proxy servers
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

## Docker Compose

Docker Compose provides development and production configurations. Install
[Docker Desktop](https://docs.docker.com/desktop/) or another Docker runtime
with the Compose plugin before continuing.

Build and start the development container:

```bash
docker compose up --build
```

Open [http://localhost:5001](http://localhost:5001). The project directory is
mounted into the container, so local code changes trigger Flask's development
reload.

Run the test suite in the development container:

```bash
docker compose exec radioclaude-dev pytest
```

Stop the containers:

```bash
docker compose down
```

Production runs Nginx in front of Gunicorn and uses PostgreSQL. Set a database
password, then start the Nginx service and its dependencies:

```bash
export POSTGRES_PASSWORD='replace-with-a-strong-password'
docker compose --profile prod up --build nginx
```

The first production startup generates a signing key in the persistent
`app_secrets` volume. Set `SECRET_KEY` explicitly before startup if secrets are
managed externally.

Open [http://localhost:5001](http://localhost:5001). PostgreSQL data is stored
in the named `postgres_data` Docker volume, while uploaded audio persists in
the named `uploads_data` volume. Gunicorn and PostgreSQL are only reachable
inside the Compose network; Nginx is the public entry point.

Stop the production stack without deleting its database:

```bash
docker compose --profile prod down
```

## Testing

Backend routes are covered by a pytest suite in `tests/backend/`. Each test runs against an isolated temp SQLite database, not `data/app.db`.

```bash
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

Security-sensitive Flask behavior is covered by focused regression tests in
`tests/backend/test_security.py` and runs as part of pytest.

Docker, Compose, and Nginx security invariants are checked separately:

```bash
./tests/infrastructure/security_checks.sh
```

The infrastructure script validates the Compose model, non-root production
image configuration, local-only development port, internal-only application
and database services, Nginx limits, and upload-size configuration.

There's no frontend test suite — it was scoped (Playwright e2e against mocked HLS/metadata endpoints) but skipped as not worth the added toolchain for this project's size.

## Project structure

```
.
├── app.py                 # Flask app: routes, database, upload handling
├── requirements.txt       # Python dependencies
├── requirements-dev.txt   # Dev/test dependencies (pytest)
├── pytest.ini             # pytest config
├── Dockerfile             # Development and production application images
├── docker-compose.yml     # Development and production service definitions
├── docker/
│   ├── nginx.conf         # Production reverse-proxy configuration
│   └── start-prod.sh      # Database initialization and Gunicorn startup
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
| `GET` | `/health` | Application and database health check |

## Frontend behavior

- Loads the live HLS stream at `https://d3d4yli4hf5bmh.cloudfront.net/hls/live.m3u8`.
- Uses native HLS where reliable and an AAC `hls.js` path in Chromium.
- Polls `https://d3d4yli4hf5bmh.cloudfront.net/metadatav2.json` every 5 seconds to update the now-playing display and a five-track history list.
- Displays a track timer that resets whenever the polled metadata changes.
- Ratings use a signed, HttpOnly voter cookie issued by the server.

## Development notes

- The SQLite database and `uploads/` directory are created automatically on first run.
- Setting `DATABASE_URL` to a PostgreSQL URL switches the application to PostgreSQL.
- `app.config["MAX_CONTENT_LENGTH"]` is set to 32 MB for uploads.
- Flask debug mode is enabled only when `FLASK_DEBUG=1`.
- The `.gitignore` excludes `data/`, `uploads/`, `.venv/`, `__pycache__/`, `.env`, and `.env.local`.
- `RadioClaude_Style_Guide.txt` documents the brand palette and UI patterns.
