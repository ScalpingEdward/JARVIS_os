#!/usr/bin/env sh
set -eu

SOURCE="${1:?Usage: scripts/restore.sh backups/<timestamp>}"
test -f "$SOURCE/postgres.sql"
test -f "$SOURCE/jarvis-data.tar.gz"

docker compose exec -T postgres psql -U "${POSTGRES_USER:-jarvis}" -d "${POSTGRES_DB:-jarvis}" < "$SOURCE/postgres.sql"
docker run --rm -v jarvis_os_jarvis_data:/target -v "$(pwd)/$SOURCE:/backup:ro" alpine sh -c 'rm -rf /target/* && tar xzf /backup/jarvis-data.tar.gz -C /target'

echo "Restore completed from: $SOURCE"
