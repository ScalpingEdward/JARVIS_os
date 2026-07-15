#!/usr/bin/env sh
set -eu

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DIR:-./backups}/$STAMP"
mkdir -p "$DEST"

docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-jarvis}" "${POSTGRES_DB:-jarvis}" > "$DEST/postgres.sql"
docker run --rm -v jarvis_os_jarvis_data:/source:ro -v "$(pwd)/$DEST:/backup" alpine sh -c 'cd /source && tar czf /backup/jarvis-data.tar.gz .'

echo "Backup created: $DEST"
