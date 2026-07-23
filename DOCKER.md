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

Run with Gunicorn (production WSGI server):

```bash
docker compose --profile prod up radioclaude-prod
```

Access the app at `http://localhost:5001`.

Data and uploads persist in `./data` and `./uploads` directories.

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

Prod container with persistent volumes:

```bash
docker run -d --rm \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  -e FLASK_ENV=production \
  radioclaude:prod
```

## File Structure

- `Dockerfile` — multi-stage build (dev and prod targets)
- `docker-compose.yml` — orchestrates dev and prod services
- `.dockerignore` — excludes unnecessary files from build context

## Notes

- Dev image runs Flask with `debug=True` for hot-reload and error pages
- Prod image uses Gunicorn with 4 workers for concurrent requests
- Both share the same base layer to minimize total image size
- Volumes for `data/` and `uploads/` persist data across container restarts
- SQLite database is stored in `data/app.db` (created automatically)
