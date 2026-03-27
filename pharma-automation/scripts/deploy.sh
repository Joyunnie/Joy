#!/bin/bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/pharma}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

cd "$PROJECT_DIR"

echo "=== $(date) Deploy start ==="

# 1. Pull latest code
git pull origin main

# 2. Build and restart
docker compose $COMPOSE_FILES --env-file .env build
docker compose $COMPOSE_FILES --env-file .env up -d

# 3. Wait for backend health
echo "Waiting for backend..."
for i in $(seq 1 30); do
    if docker compose $COMPOSE_FILES exec -T cloud curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend healthy"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Backend not healthy after 30s"
        docker compose $COMPOSE_FILES logs --tail=20 cloud
        exit 1
    fi
    sleep 1
done

echo "=== $(date) Deploy complete ==="
