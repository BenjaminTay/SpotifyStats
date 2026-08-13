#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "尚未安装 Tailscale。请先按官方 Linux 安装说明安装并执行 sudo tailscale up。" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
  exit 1
fi

gateway_port="$(sed -n 's/^APP_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
gateway_port="${gateway_port:-3001}"

if ! curl --fail --silent --max-time 5 "http://127.0.0.1:$gateway_port/api/health" >/dev/null; then
  echo "本地生产入口尚未健康：127.0.0.1:$gateway_port" >&2
  exit 1
fi

sudo tailscale serve --bg "http://127.0.0.1:$gateway_port"
sudo tailscale serve status
