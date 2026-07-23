#!/bin/sh
set -eu

secret_key_file=${SECRET_KEY_FILE:-/run/radioclaude-secrets/secret-key}

if [ -z "${SECRET_KEY:-}" ]; then
  if [ ! -s "$secret_key_file" ]; then
    umask 077
    python -c "import secrets; print(secrets.token_hex(32))" > "$secret_key_file"
  fi
  SECRET_KEY=$(sed -n '1p' "$secret_key_file")
  export SECRET_KEY
fi

python -c "from app import init_db; init_db()"

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  app:app
