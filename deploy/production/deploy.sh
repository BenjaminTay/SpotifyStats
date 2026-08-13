#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
NEW_TAG="${1:-}"

cd "$DEPLOY_DIR"

if [[ ! "$NEW_TAG" =~ ^[0-9a-f]{7,64}$ ]]; then
  echo "用法：$0 <git-commit-sha>" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。请先复制 .env.example 并填写生产配置。" >&2
  exit 1
fi

if grep -Eq 'replace-with|example-tailnet' "$ENV_FILE"; then
  echo ".env 仍含占位值，拒绝部署。" >&2
  exit 1
fi

current_tag="$(sed -n 's/^IMAGE_TAG=//p' "$ENV_FILE" | tail -n 1)"
gateway_port="$(sed -n 's/^APP_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
gateway_port="${gateway_port:-3001}"

set_image_tag() {
  local tag="$1"
  if grep -q '^IMAGE_TAG=' "$ENV_FILE"; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$tag/" "$ENV_FILE"
  else
    printf '\nIMAGE_TAG=%s\n' "$tag" >> "$ENV_FILE"
  fi
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_until_healthy() {
  local attempts=48
  while (( attempts > 0 )); do
    if curl --fail --silent --show-error --max-time 5 \
      "http://127.0.0.1:$gateway_port/api/health" >/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 5
  done
  return 1
}

release_is_safe() {
  wait_until_healthy || return 1

  if ! ss -lnt | awk '{print $4}' | grep -qx "127.0.0.1:$gateway_port"; then
    echo "网关端口未限制在 127.0.0.1:$gateway_port，拒绝发布。" >&2
    return 1
  fi

  compose exec -T backend python - <<'PY'
import sqlite3

conn = sqlite3.connect("/app/data/spotify_stats.db")
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"database integrity_check failed: {result}")
PY
}

if compose ps --status running --services 2>/dev/null | grep -qx backend; then
  "$DEPLOY_DIR/backup.sh"
fi

set_image_tag "$NEW_TAG"
if ! compose pull || ! compose up -d --remove-orphans || ! release_is_safe; then
  echo "新版本健康检查失败：$NEW_TAG" >&2
  compose logs --tail 160 >&2 || true

  if [[ "$current_tag" =~ ^[0-9a-f]{7,64}$ && "$current_tag" != "$NEW_TAG" ]]; then
    echo "正在回滚到：$current_tag" >&2
    set_image_tag "$current_tag"
    if ! compose pull || ! compose up -d --remove-orphans || ! release_is_safe; then
      echo "回滚后的健康检查仍未通过，需要人工检查。" >&2
    fi
  fi
  exit 1
fi

if [[ "$current_tag" =~ ^[0-9a-f]{7,64}$ && "$current_tag" != "$NEW_TAG" ]]; then
  printf '%s\n' "$current_tag" > .previous-image-tag
fi
printf '%s\n' "$NEW_TAG" > .current-image-tag

echo "部署完成：$NEW_TAG"
