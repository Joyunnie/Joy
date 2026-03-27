#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/pharma/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

mkdir -p "$BACKUP_DIR"

FILENAME="pharma_$(date +%Y%m%d_%H%M%S).sql.gz"
FILEPATH="$BACKUP_DIR/$FILENAME"

echo "Backup start: $FILEPATH"

docker compose $COMPOSE_FILES exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILEPATH"

SIZE=$(du -h "$FILEPATH" | cut -f1)
echo "Backup complete: $FILENAME ($SIZE)"

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "pharma_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "Deleted $DELETED old backups (>${RETENTION_DAYS} days)"
fi
