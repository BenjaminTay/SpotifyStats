#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"

cd "$DEPLOY_DIR"

gateway_port="$(sed -n 's/^APP_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
gateway_port="${gateway_port:-3001}"
public_url="$(sed -n 's/^APP_PUBLIC_URL=//p' "$ENV_FILE" | tail -n 1)"
public_gateway_port="$(sed -n 's/^PUBLIC_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
public_gateway_port="${public_gateway_port:-3002}"
showcase_url="$(sed -n 's/^PUBLIC_SHOWCASE_URL=//p' "$ENV_FILE" | tail -n 1)"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
curl --fail --silent --show-error "http://127.0.0.1:$gateway_port/api/health"
echo

if ! ss -lnt | awk '{print $4}' | grep -qx "127.0.0.1:$gateway_port"; then
  echo "FAIL: $gateway_port 未限制在 loopback。" >&2
  exit 1
fi

curl --fail --silent --show-error "http://127.0.0.1:$public_gateway_port/api/health"
echo

if ! ss -lnt | awk '{print $4}' | grep -qx "127.0.0.1:$public_gateway_port"; then
  echo "FAIL: $public_gateway_port 未限制在 loopback。" >&2
  exit 1
fi

surface="$(curl --fail --silent --show-error \
  "http://127.0.0.1:$public_gateway_port/api/runtime/capabilities")"
if [[ "$surface" != *'"surface":"public-readonly"'* ]]; then
  echo "FAIL: 公共入口未进入 public-readonly。" >&2
  exit 1
fi

write_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  -X PUT "http://127.0.0.1:$public_gateway_port/api/settings" \
  -H 'Content-Type: application/json' -d '{}')"
if [[ "$write_status" != "403" ]]; then
  echo "FAIL: 公共入口写操作返回 $write_status，预期 403。" >&2
  exit 1
fi

if command -v tailscale >/dev/null 2>&1; then
  sudo tailscale serve status
  sudo tailscale funnel status || true
fi

if [[ -n "$showcase_url" ]]; then
  curl --fail --silent --show-error --max-time 15 "$showcase_url/api/health"
  echo
fi

if [[ -n "$public_url" ]]; then
  curl --fail --silent --show-error --max-time 15 "$public_url/api/health"
  echo
fi

echo "生产入口验证通过。"
