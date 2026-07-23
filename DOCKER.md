# Docker Setup for Radio Claude

This project includes Docker configurations for both development and production environments.

## Quick Start

### Development Container

Run with hot-reload and Flask debug mode:

```bash
docker run -it -p 5000:5000 radioclaude:dev
```

Or with docker-compose:

```bash
docker compose up
```

Access the app at `http://localhost:5001`.

Changes to local files trigger automatic reload. Run tests inside the container:

```bash
docker compose exec radioclaude-dev pytest
```

### Production Container

Production uses Nginx as its public web server, Gunicorn for the Flask
application, and PostgreSQL for persistent relational data. Set a strong
database password before starting the stack:

```bash
export POSTGRES_PASSWORD='replace-with-a-strong-password'
docker compose --profile prod up --build nginx
```

If `SECRET_KEY` is not provided, the application generates one on first
startup and stores it in the persistent `app_secrets` Docker volume. An
externally managed `SECRET_KEY` environment variable takes precedence.

Access the app at `http://localhost:5001`.

PostgreSQL data persists in the `postgres_data` Docker volume. Uploaded audio
persists in the `uploads_data` Docker volume. Nginx is the only service with a host port; the
Gunicorn and PostgreSQL services are internal to the Compose network.

Stop the stack without deleting PostgreSQL data:

```bash
docker compose --profile prod down
```

To also delete the PostgreSQL volume and all database data:

```bash
docker compose --profile prod down --volumes
```

## Published Production Image

Pushes and merges to `main` run tests and publish a multi-architecture
production image to GitHub Container Registry:

```text
ghcr.io/<owner>/<repository>:latest
ghcr.io/<owner>/<repository>:sha-<full-git-sha>
```

Use the SHA tag for a reproducible deployment or rollback. The workflow is
defined in `.github/workflows/cd.yml` and authenticates with `GITHUB_TOKEN`.

## Building Images Standalone

Build dev image:

```bash
docker build --target dev -t radioclaude:dev .
```

Build prod image:

```bash
docker build --target prod -t radioclaude:prod .
```

## Running Containers Directly

Dev container with live code reload:

```bash
docker run -it --rm \
  -p 5000:5000 \
  -v $(pwd):/app \
  -v /app/__pycache__ \
  -e FLASK_ENV=development \
  radioclaude:dev
```

Use Docker Compose for production because the application requires the
PostgreSQL and Nginx services.

## File Structure

- `Dockerfile` — multi-stage build (dev and prod targets)
- `docker-compose.yml` — orchestrates dev and prod services
- `docker/nginx.conf` — Nginx reverse-proxy configuration
- `docker/start-prod.sh` — initializes PostgreSQL and starts Gunicorn
- `.dockerignore` — excludes unnecessary files from build context

## Notes

- Dev image runs Flask with debug mode explicitly enabled for hot-reload
- Prod image runs as an unprivileged user with Gunicorn behind Nginx
- Both share the same base layer to minimize total image size
- PostgreSQL and uploaded audio persist across production container restarts
- Development and automated tests continue to use SQLite
