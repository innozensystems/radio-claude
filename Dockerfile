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
RUN mkdir -p /app/data /app/uploads

# Expose port for production
EXPOSE 5000

# Run with Gunicorn for production
RUN pip install --no-cache-dir gunicorn

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
