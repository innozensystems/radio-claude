# Multi-stage build for dev and prod releases
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Dev stage - includes test dependencies
FROM base as dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Expose port for Flask dev server
EXPOSE 5000

# Run with debug mode
CMD ["python", "app.py"]

# Prod stage - minimal runtime
FROM base as prod

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories for data and uploads
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /app/data /app/uploads /run/radioclaude-secrets \
    && chown -R app:app /app /run/radioclaude-secrets
RUN chmod +x /app/docker/start-prod.sh

# Expose port for production
EXPOSE 5000

# Initialize the database, then run the application behind Nginx.
USER app
CMD ["/app/docker/start-prod.sh"]
