#!/bin/bash
set -euo pipefail

LOG_FILE="${LOG_FILE:-/var/log/pharma_health.log}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost/health 2>/dev/null || echo "000")

if [ "$HTTP_CODE" != "200" ]; then
    echo "$(date) UNHEALTHY (HTTP $HTTP_CODE)" >> "$LOG_FILE"
    cd /opt/pharma
    docker compose $COMPOSE_FILES restart cloud
    echo "$(date) Restarted cloud service" >> "$LOG_FILE"
fi
