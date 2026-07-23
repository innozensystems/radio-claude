# Radio Claude

A single-page Flask app that plays a live HLS audio stream in the browser and lets listeners rate tracks. No build step — just vanilla JavaScript, HTML, and CSS.

This repository does not include a live stream, metadata feed, or artwork
endpoint. Configure only sources that you own or have permission to use.

> [!IMPORTANT]
> The service will not start until external media URLs are configured.
> Pass authorized endpoint URLs as environment variables when starting the
> local process, Docker Compose stack, or GHCR image.

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

2. Start the server with authorized external service URLs (this also
   initializes the SQLite database):

   ```bash
   source .venv/bin/activate
   STREAM_URL='https://authorized-host.example/path/live.m3u8' \
   HLS_FALLBACK_URL='https://authorized-host.example/path/browser-compatible.m3u8' \
   METADATA_URL='https://authorized-host.example/path/metadata.json' \
   COVER_URL='https://authorized-host.example/path/cover.jpg' \
     python3 app.py
   ```

3. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Stream configuration

The application uses these runtime environment variables:

| Variable | Required | Purpose |
|---|---|---|
| `STREAM_URL` | Yes | Primary HLS stream used by browsers with reliable native HLS |
| `HLS_FALLBACK_URL` | No | Browser-compatible HLS rendition used by `hls.js`; defaults to `STREAM_URL` when omitted |
| `METADATA_URL` | Yes | JSON now-playing metadata and track-history endpoint |
| `COVER_URL` | Yes | Current cover-art image endpoint |

Every supplied value must be an absolute `http://` or `https://` URL. The
application refuses to start when required configuration is missing or any
configured URL is malformed. The configured origins are added to Content
Security Policy at runtime.

Set `HLS_FALLBACK_URL` as well when Chromium needs a different
browser-compatible rendition. Otherwise, omit it and the application will use
`STREAM_URL`.

Pass these values only at runtime. Do not put real endpoints in tracked files,
Docker build arguments, or image layers. The Docker build context excludes
every `.env*` file as an additional safeguard.

Because playback happens directly in the browser, configured URLs are visible
to visitors in the rendered page and network inspector. Runtime configuration
keeps them out of the repository and image; it does not make them secret. Do
not use direct browser playback for a URL that must remain confidential.

Publicly accessible does not necessarily mean licensed for redistribution.
Prefer direct client-side playback from an authorized provider. Do not proxy,
record, rebroadcast, or publish signed/private URLs unless the provider
explicitly permits it.

Removing an endpoint from the current files does not remove it from earlier Git
commits, forks, or already-published container layers. If a previously committed
URL was sensitive, ask the provider to rotate it and handle repository-history
or registry cleanup as a separate, coordinated operation.

## Docker Compose

Docker Compose provides development and production configurations. Install
[Docker Desktop](https://docs.docker.com/desktop/) or another Docker runtime
with the Compose plugin before continuing.

Build and start the development container:

```bash
STREAM_URL='https://authorized-host.example/path/live.m3u8' \
HLS_FALLBACK_URL='https://authorized-host.example/path/browser-compatible.m3u8' \
METADATA_URL='https://authorized-host.example/path/metadata.json' \
COVER_URL='https://authorized-host.example/path/cover.jpg' \
  docker compose up --build
```

Docker Compose passes these runtime values into the application container.

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
export POSTGRES_PASSWORD='a-strong-password'
STREAM_URL='https://authorized-host.example/path/live.m3u8' \
HLS_FALLBACK_URL='https://authorized-host.example/path/browser-compatible.m3u8' \
METADATA_URL='https://authorized-host.example/path/metadata.json' \
COVER_URL='https://authorized-host.example/path/cover.jpg' \
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

## Continuous deployment

Every push or merged pull request to `main` runs the unit and infrastructure
security checks, then builds the production Docker target for AMD64 and ARM64.
The workflow publishes both tags to GitHub Container Registry:

```text
ghcr.io/<owner>/<repository>:latest
ghcr.io/<owner>/<repository>:sha-<full-git-sha>
```

The immutable SHA tag is recommended for deployments and rollbacks. Publishing
uses the repository-provided `GITHUB_TOKEN`; no additional registry password is
required. Package visibility is managed from the repository's Packages
settings.

### Run the production image in standalone mode

To run the production application image locally without Nginx or PostgreSQL:

```bash
docker run --rm \
  -p 127.0.0.1:5001:5000 \
  -e STREAM_URL='https://authorized-host.example/path/live.m3u8' \
  -e HLS_FALLBACK_URL='https://authorized-host.example/path/browser-compatible.m3u8' \
  -e METADATA_URL='https://authorized-host.example/path/metadata.json' \
  -e COVER_URL='https://authorized-host.example/path/cover.jpg' \
  ghcr.io/innozensystems/radio-claude:latest
```

Open [http://localhost:5001](http://localhost:5001). This standalone mode uses
SQLite inside the container and is intended for quick local verification.
Stopping the container removes its database because `--rm` is enabled. Use the
production Compose command above when PostgreSQL, persistent volumes, and Nginx
are required.

### Run the published image with the production stack

For a production-grade local deployment, run the published application image
with PostgreSQL, persistent volumes, and Nginx:

```bash
docker pull ghcr.io/innozensystems/radio-claude:latest

# Tag the published image with the name expected by this Compose project.
docker tag \
  ghcr.io/innozensystems/radio-claude:latest \
  radioclaude-radioclaude-prod:latest

export POSTGRES_PASSWORD='a-strong-password'

# Use the pulled image instead of rebuilding it locally.
STREAM_URL='https://authorized-host.example/path/live.m3u8' \
HLS_FALLBACK_URL='https://authorized-host.example/path/browser-compatible.m3u8' \
METADATA_URL='https://authorized-host.example/path/metadata.json' \
COVER_URL='https://authorized-host.example/path/cover.jpg' \
  docker compose --profile prod up -d --no-build nginx
```

Open [http://localhost:5001](http://localhost:5001). Confirm that PostgreSQL,
Gunicorn, and Nginx are healthy:

```bash
docker compose --profile prod ps
docker compose --profile prod logs -f radioclaude-prod postgres nginx
```

For repeatable deployments, replace `latest` with the immutable
`sha-<full-git-sha>` tag published by the CD workflow. If the PostgreSQL volume
already exists, `POSTGRES_PASSWORD` must match the password used when that
volume was first initialized.

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

- Loads the runtime-configured `STREAM_URL`.
- Uses native HLS where reliable and the runtime-configured
  `HLS_FALLBACK_URL` with `hls.js` in Chromium.
- Polls the runtime-configured `METADATA_URL` every 5 seconds while the page is
  visible, including before playback and while audio is paused, to keep the
  now-playing display and five-track history current.
- Loads current artwork from the runtime-configured `COVER_URL`.
- Displays the known lossless label for the native-HLS path. On the
  Chromium/hls.js path, reads the selected codec from `LEVEL_LOADED` or the
  parsed audio buffer and displays FLAC, AAC, or the reported codec.
- Displays a track timer that resets whenever the polled metadata changes.
- Ratings use a signed, HttpOnly voter cookie issued by the server.

## Development notes

- The SQLite database and `uploads/` directory are created automatically on first run.
- Setting `DATABASE_URL` to a PostgreSQL URL switches the application to PostgreSQL.
- Stream, metadata, and cover endpoints are runtime configuration and are
  intentionally absent from the source and container image.
- `app.config["MAX_CONTENT_LENGTH"]` is set to 32 MB for uploads.
- Flask debug mode is enabled only when `FLASK_DEBUG=1`.
- The `.gitignore` excludes `data/`, `uploads/`, `.venv/`, `__pycache__/`, and
  local `.env*` files.
- `RadioClaude_Style_Guide.txt` documents the brand palette and UI patterns.
