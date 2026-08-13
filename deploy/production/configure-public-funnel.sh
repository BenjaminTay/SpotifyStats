#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "尚未安装 Tailscale。" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
  exit 1
fi

public_gateway_port="$(sed -n 's/^PUBLIC_GATEWAY_PORT=//p' "$ENV_FILE" | tail -n 1)"
public_gateway_port="${public_gateway_port:-3002}"
credentials_file="$DEPLOY_DIR/secrets/showcase.credentials"

if [[ ! -f "$credentials_file" ]]; then
  echo "缺少展示入口访问凭据。" >&2
  exit 1
fi
showcase_username="$(sed -n 's/^SHOWCASE_USERNAME=//p' "$credentials_file" | tail -n 1)"
showcase_password="$(sed -n 's/^SHOWCASE_PASSWORD=//p' "$credentials_file" | tail -n 1)"

if ! curl --fail --silent --max-time 5 \
  "http://127.0.0.1:$public_gateway_port/api/health" >/dev/null; then
  echo "公共只读入口尚未健康：127.0.0.1:$public_gateway_port" >&2
  exit 1
fi

surface="$(curl --fail --silent --max-time 5 \
  --user "$showcase_username:$showcase_password" \
  "http://127.0.0.1:$public_gateway_port/api/runtime/capabilities")"
if [[ "$surface" != *'"surface":"public-readonly"'* ]]; then
  echo "公共网关未被后端识别为 public-readonly，拒绝启用 Funnel。" >&2
  exit 1
fi

status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --user "$showcase_username:$showcase_password" \
  --max-time 5 -X PUT "http://127.0.0.1:$public_gateway_port/api/settings" \
  -H 'Content-Type: application/json' -d '{}')"
if [[ "$status" != "403" ]]; then
  echo "公共入口写操作未被拒绝（HTTP $status），拒绝启用 Funnel。" >&2
  exit 1
fi

sudo tailscale funnel --bg --https=8443 "http://127.0.0.1:$public_gateway_port"
sudo tailscale funnel status
