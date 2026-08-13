#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"

cd "$DEPLOY_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
  exit 1
fi

get_env() {
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
}

mode="$(get_env DEPLOYMENT_MODE)"
gateway_port="$(get_env APP_GATEWAY_PORT)"
gateway_port="${gateway_port:-3001}"
public_gateway_port="$(get_env PUBLIC_GATEWAY_PORT)"
public_gateway_port="${public_gateway_port:-3002}"
private_url="$(get_env APP_PUBLIC_URL)"
showcase_url="$(get_env PUBLIC_SHOWCASE_URL)"

if [[ "$mode" != "full" && "$mode" != "showcase" && "$mode" != "dual" ]]; then
  echo "DEPLOYMENT_MODE 无效：$mode" >&2
  exit 1
fi

compose_all() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
    --profile full --profile showcase --profile dual "$@"
}

port_is_loopback_only() {
  local port="$1"
  local matches
  matches="$(ss -lntH | awk -v port=":$port" '$4 ~ port "$" {print $4}')"
  [[ -n "$matches" ]] || return 1
  ! grep -Evq "^(127\.0\.0\.1|\[::1\]):${port}$" <<<"$matches"
}

port_is_closed() {
  ! ss -lntH | awk '{print $4}' | grep -Eq ":$1$"
}

check_surface() {
  local port="$1"
  local expected="$2"
  local response
  curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:$port/api/health" >/dev/null
  port_is_loopback_only "$port" || {
    echo "FAIL: $port 未严格限制在 loopback。" >&2
    return 1
  }
  response="$(curl --fail --silent --show-error --max-time 5 \
    "http://127.0.0.1:$port/api/runtime/capabilities")"
  [[ "$response" == *"\"surface\":\"$expected\""* ]] || {
    echo "FAIL: $port 未进入 $expected。" >&2
    return 1
  }
}

check_showcase_write_block() {
  local status
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --max-time 5 -X PUT "http://127.0.0.1:$public_gateway_port/api/settings" \
    -H 'Content-Type: application/json' -d '{}')"
  [[ "$status" == "403" ]] || {
    echo "FAIL: 简化版写操作返回 HTTP $status，预期 403。" >&2
    return 1
  }
}

compose_all ps

case "$mode" in
  full)
    check_surface "$gateway_port" private-admin
    port_is_closed "$public_gateway_port" || {
      echo "FAIL: full 模式不应监听 $public_gateway_port。" >&2
      exit 1
    }
    ;;
  showcase)
    check_surface "$public_gateway_port" public-readonly
    check_showcase_write_block
    port_is_closed "$gateway_port" || {
      echo "FAIL: showcase 模式不应监听 $gateway_port。" >&2
      exit 1
    }
    ;;
  dual)
    check_surface "$gateway_port" private-admin
    check_surface "$public_gateway_port" public-readonly
    check_showcase_write_block
    ;;
esac

compose_all exec -T backend python - <<'PY'
import sqlite3

conn = sqlite3.connect("/app/data/spotify_stats.db")
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"database integrity_check failed: {result}")
PY

if [[ "${VERIFY_EXTERNAL_INGRESS:-0}" == "1" ]]; then
  if [[ ( "$mode" == "full" || "$mode" == "dual" ) && -n "$private_url" ]]; then
    curl --fail --silent --show-error --max-time 15 "$private_url/api/health" >/dev/null
  fi
  if [[ ( "$mode" == "showcase" || "$mode" == "dual" ) && -n "$showcase_url" ]]; then
    curl --fail --silent --show-error --max-time 15 "$showcase_url/api/health" >/dev/null
  fi
fi

echo "生产部署验证通过：模式 $mode。"
