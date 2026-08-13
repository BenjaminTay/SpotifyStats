#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
NEW_TAG="${1:-}"
MODE_OVERRIDE=""

usage() {
  cat >&2 <<'EOF'
用法：deploy.sh <git-commit-sha> [--mode full|showcase|dual]

不提供 --mode 时沿用 .env 中的 DEPLOYMENT_MODE。部署只管理 Docker
loopback 网关，不会启用或关闭 Tailscale、Funnel、域名或云防火墙入口。
EOF
}

if [[ "${2:-}" == "--mode" && -n "${3:-}" && -z "${4:-}" ]]; then
  MODE_OVERRIDE="$3"
elif [[ -n "${2:-}" ]]; then
  usage
  exit 2
fi

cd "$DEPLOY_DIR"
umask 077

if [[ ! "$NEW_TAG" =~ ^[0-9a-f]{7,64}$ ]]; then
  usage
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。请先复制 .env.example 并填写生产配置。" >&2
  exit 1
fi

if grep -Eq 'example-tailnet|SPOTIFY_STATS_(TOKEN_KEY|GATEWAY_TOKEN)=replace-with' "$ENV_FILE"; then
  echo ".env 仍含 URL、数据加密密钥或网关密钥占位值，拒绝部署。" >&2
  exit 1
fi

get_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
}

valid_mode() {
  [[ "$1" == "full" || "$1" == "showcase" || "$1" == "dual" ]]
}

ensure_gateway_token() {
  local token
  token="$(get_env SPOTIFY_STATS_GATEWAY_TOKEN)"
  if [[ -z "$token" ]]; then
    if ! command -v openssl >/dev/null 2>&1; then
      echo "缺少 SPOTIFY_STATS_GATEWAY_TOKEN，且服务器没有 openssl 可用于安全生成。" >&2
      return 1
    fi
    token="$(openssl rand -hex 32)"
    set_env SPOTIFY_STATS_GATEWAY_TOKEN "$token"
    echo "已在服务器 .env 中生成独立网关密钥。"
  fi
  if [[ ! "$token" =~ ^[A-Za-z0-9_-]{32,128}$ ]]; then
    echo "SPOTIFY_STATS_GATEWAY_TOKEN 必须是 32-128 位 base64url 安全字符。" >&2
    return 1
  fi
  set_env SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED 1
}

ensure_gateway_token

current_tag="$(get_env IMAGE_TAG)"
current_mode="$(get_env DEPLOYMENT_MODE)"
if ! valid_mode "$current_mode"; then
  # Releases before deployment profiles always started both loopback gateways.
  current_mode="dual"
  set_env DEPLOYMENT_MODE "$current_mode"
  echo "旧部署未记录 DEPLOYMENT_MODE；按原有双网关行为迁移为 dual。"
fi

target_mode="${MODE_OVERRIDE:-$current_mode}"
if ! valid_mode "$target_mode"; then
  echo "无效部署模式：$target_mode（只能是 full、showcase 或 dual）。" >&2
  exit 2
fi

gateway_port="$(get_env APP_GATEWAY_PORT)"
gateway_port="${gateway_port:-3001}"
public_gateway_port="$(get_env PUBLIC_GATEWAY_PORT)"
public_gateway_port="${public_gateway_port:-3002}"

compose_all() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
    --profile full --profile showcase --profile dual "$@"
}

compose_mode() {
  local mode="$1"
  shift
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile "$mode" "$@"
}

services_for_mode() {
  case "$1" in
    full) printf '%s\n' backend web ;;
    showcase) printf '%s\n' backend public-web ;;
    dual) printf '%s\n' backend web public-web ;;
  esac
}

activate_mode() {
  local mode="$1"
  local -a services
  mapfile -t services < <(services_for_mode "$mode")

  case "$mode" in
    full)
      compose_all rm -sf public-web >/dev/null 2>&1 || true
      ;;
    showcase)
      compose_all rm -sf web >/dev/null 2>&1 || true
      ;;
  esac

  compose_mode "$mode" up -d --remove-orphans "${services[@]}"
}

pull_mode() {
  local mode="$1"
  local -a services
  mapfile -t services < <(services_for_mode "$mode")
  compose_mode "$mode" pull "${services[@]}"
}

wait_until_healthy() {
  local port="$1"
  local attempts=48
  while (( attempts > 0 )); do
    if curl --fail --silent --show-error --max-time 5 \
      "http://127.0.0.1:$port/api/health" >/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 5
  done
  return 1
}

port_is_loopback_only() {
  local port="$1"
  local matches
  matches="$(ss -lntH | awk -v port=":$port" '$4 ~ port "$" {print $4}')"
  [[ -n "$matches" ]] || return 1
  ! grep -Evq "^(127\.0\.0\.1|\[::1\]):${port}$" <<<"$matches"
}

port_is_closed() {
  local port="$1"
  ! ss -lntH | awk '{print $4}' | grep -Eq ":${port}$"
}

assert_surface() {
  local port="$1"
  local expected="$2"
  local response
  response="$(curl --fail --silent --show-error --max-time 5 \
    "http://127.0.0.1:$port/api/runtime/capabilities")" || return 1
  if [[ "$response" != *"\"surface\":\"$expected\""* ]]; then
    echo "端口 $port 的运行面不是 $expected。" >&2
    return 1
  fi
}

verify_private_gateway() {
  wait_until_healthy "$gateway_port" || return 1
  if ! port_is_loopback_only "$gateway_port"; then
    echo "完全版网关未严格绑定 loopback 端口 $gateway_port。" >&2
    return 1
  fi
  assert_surface "$gateway_port" private-admin
}

verify_showcase_gateway() {
  wait_until_healthy "$public_gateway_port" || return 1
  if ! port_is_loopback_only "$public_gateway_port"; then
    echo "简化版网关未严格绑定 loopback 端口 $public_gateway_port。" >&2
    return 1
  fi
  assert_surface "$public_gateway_port" public-readonly || return 1

  local write_status
  write_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --max-time 5 -X PUT "http://127.0.0.1:$public_gateway_port/api/settings" \
    -H 'Content-Type: application/json' -d '{}')"
  if [[ "$write_status" != "403" ]]; then
    echo "简化版写操作返回 HTTP $write_status，预期 403。" >&2
    return 1
  fi
}

release_is_safe() {
  local mode="$1"

  compose_mode "$mode" exec -T backend python - <<'PY'
import sqlite3

conn = sqlite3.connect("/app/data/spotify_stats.db")
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"database integrity_check failed: {result}")
PY

  case "$mode" in
    full)
      verify_private_gateway || return 1
      port_is_closed "$public_gateway_port" || {
        echo "full 模式仍监听简化版端口 $public_gateway_port。" >&2
        return 1
      }
      ;;
    showcase)
      verify_showcase_gateway || return 1
      port_is_closed "$gateway_port" || {
        echo "showcase 模式仍监听完全版端口 $gateway_port。" >&2
        return 1
      }
      ;;
    dual)
      verify_private_gateway || return 1
      verify_showcase_gateway || return 1
      ;;
  esac
}

restore_previous_release() {
  if [[ ! "$current_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
    echo "没有合法的上一镜像 SHA，无法自动回滚。" >&2
    return 1
  fi
  echo "正在恢复镜像 $current_tag 和部署模式 $current_mode。" >&2
  set_env IMAGE_TAG "$current_tag"
  set_env DEPLOYMENT_MODE "$current_mode"
  pull_mode "$current_mode" && activate_mode "$current_mode" && release_is_safe "$current_mode"
}

if compose_all ps --status running --services 2>/dev/null | grep -qx backend && \
  [[ "$current_tag" != "$NEW_TAG" ]]; then
  "$DEPLOY_DIR/backup.sh"
fi

set_env IMAGE_TAG "$NEW_TAG"
set_env DEPLOYMENT_MODE "$target_mode"

if ! pull_mode "$target_mode" || ! activate_mode "$target_mode" || ! release_is_safe "$target_mode"; then
  echo "新版本或部署模式验收失败：$NEW_TAG / $target_mode" >&2
  compose_all logs --tail 160 >&2 || true
  if ! restore_previous_release; then
    echo "自动恢复未通过，需要人工检查。" >&2
  fi
  exit 1
fi

if [[ "$current_tag" =~ ^[0-9a-f]{7,64}$ && \
      ( "$current_tag" != "$NEW_TAG" || "$current_mode" != "$target_mode" ) ]]; then
  printf '%s\n' "$current_tag" > .previous-image-tag
  printf '%s\n' "$current_mode" > .previous-deployment-mode
fi
printf '%s\n' "$NEW_TAG" > .current-image-tag
printf '%s\n' "$target_mode" > .current-deployment-mode

echo "部署完成：$NEW_TAG（模式：$target_mode）"
echo "外部 HTTPS 入口未被修改；如需对外访问，请单独配置受控入口。"
