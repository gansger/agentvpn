#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
CADDYFILE="$ROOT_DIR/infrastructure/reverse-proxy/Caddyfile"
PUBLIC_DOMAIN="${PUBLIC_DOMAIN:-validation.example.com}"

case "$PUBLIC_DOMAIN" in
  *://*|*/*|*" "*|"")
    echo "PUBLIC_DOMAIN must be a domain without scheme, path, or spaces" >&2
    exit 2
    ;;
esac

docker run --rm \
  --env "PUBLIC_DOMAIN=$PUBLIC_DOMAIN" \
  --mount "type=bind,source=$CADDYFILE,target=/etc/caddy/Caddyfile,readonly" \
  caddy:2.10-alpine \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
