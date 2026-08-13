#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
mode="${1:-}"

usage() {
  cat >&2 <<'EOF'
用法：set-deployment-mode.sh full|showcase|dual

full      只运行 private-admin loopback 网关
showcase  只运行 public-readonly loopback 网关
dual      同时运行两个 loopback 网关

该命令不会启用、关闭或修改 Tailscale、Funnel、域名、反向代理和云防火墙。
EOF
}

if [[ "$mode" != "full" && "$mode" != "showcase" && "$mode" != "dual" ]]; then
  usage
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
  exit 1
fi

image_tag="$(sed -n 's/^IMAGE_TAG=//p' "$ENV_FILE" | tail -n 1)"
if [[ ! "$image_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
  echo ".env 中没有合法 IMAGE_TAG，无法切换模式。" >&2
  exit 1
fi

exec "$DEPLOY_DIR/deploy.sh" "$image_tag" --mode "$mode"
