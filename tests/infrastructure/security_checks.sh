#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$project_root"

POSTGRES_PASSWORD=validation docker compose --profile prod config --quiet

grep -q '^USER app$' Dockerfile
grep -q '127.0.0.1:5001:5000' docker-compose.yml
grep -q 'server_tokens off;' docker/nginx.conf
grep -q 'limit_req_zone ' docker/nginx.conf
grep -q 'limit_conn_zone ' docker/nginx.conf
grep -q 'client_max_body_size 32m;' docker/nginx.conf

if sed -n '/radioclaude-prod:/,/^  [a-z]/p' docker-compose.yml | grep -q 'ports:'; then
  echo "radioclaude-prod must not publish a host port" >&2
  exit 1
fi

if sed -n '/postgres:/,/^  [a-z]/p' docker-compose.yml | grep -q 'ports:'; then
  echo "postgres must not publish a host port" >&2
  exit 1
fi

echo "Infrastructure security checks passed"
