#!/bin/bash
# Let's Encrypt 초기 인증서 발급 (한 번만 실행)
set -euo pipefail

if [ -z "${DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
    echo "Usage: DOMAIN=example.com LETSENCRYPT_EMAIL=you@email.com ./init-letsencrypt.sh"
    exit 1
fi

COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "=== Requesting certificate for $DOMAIN ==="

# 1. Start nginx with temporary self-signed cert
docker compose $COMPOSE_FILES up -d frontend

# 2. Request certificate
docker compose $COMPOSE_FILES run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$LETSENCRYPT_EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# 3. Reload nginx with real cert
docker compose $COMPOSE_FILES exec frontend nginx -s reload

echo "=== Certificate issued for $DOMAIN ==="
