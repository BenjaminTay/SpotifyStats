#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"

cd "$DEPLOY_DIR"

gateway_port="$(sed -n 's/^APP_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
gateway_port="${gateway_port:-3001}"
public_url="$(sed -n 's/^APP_PUBLIC_URL=//p' "$ENV_FILE" | tail -n 1)"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
curl --fail --silent --show-error "http://127.0.0.1:$gateway_port/api/health"
echo

if ! ss -lnt | awk '{print $4}' | grep -qx "127.0.0.1:$gateway_port"; then
  echo "FAIL: $gateway_port 未限制在 loopback。" >&2
  exit 1
fi

if command -v tailscale >/dev/null 2>&1; then
  sudo tailscale serve status
fi

if [[ -n "$public_url" ]]; then
  curl --fail --silent --show-error --max-time 15 "$public_url/api/health"
  echo
fi

echo "生产入口验证通过。"
