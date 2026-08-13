#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="spotify-stats-showcase-tunnel.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
CLOUDFLARED_VERSION="2026.8.0"
# Public checksum for the pinned upstream release, not an application secret.
CLOUDFLARED_SHA256="14ecae0dd17ba74f8055e22b8f5b5acc3cbb5a9c3be4e7d6507fe1c4eadaea95"  # pragma: allowlist secret
CLOUDFLARED_BIN="$DEPLOY_DIR/bin/cloudflared"
CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/download/$CLOUDFLARED_VERSION/cloudflared-linux-amd64"
action="${1:-status}"

usage() {
  cat >&2 <<'EOF'
用法：temporary-showcase.sh start|status|stop

start   切换到 dual，按 SHOWCASE_ACCESS_MODE 启动临时 TryCloudflare HTTPS 地址
status  显示服务状态和当前临时地址
stop    立即停止并禁用临时外部入口；不会修改 Docker 部署模式

Quick Tunnel 仅用于短期测试，地址可能在服务重启后变化。该脚本不会启用 Tailscale，
也不会开放宿主机 80/443、3001、3002 或 8000 端口。
EOF
}

if [[ "$action" != "start" && "$action" != "status" && "$action" != "stop" ]]; then
  usage
  exit 2
fi

latest_url() {
  sudo journalctl -u "$SERVICE_NAME" --no-pager -o cat 2>/dev/null \
    | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true
}

install_cloudflared() {
  local current_sha="" download_tmp
  if [[ -f "$CLOUDFLARED_BIN" ]]; then
    current_sha="$(sha256sum "$CLOUDFLARED_BIN" | awk '{print $1}')"
  fi
  if [[ "$current_sha" == "$CLOUDFLARED_SHA256" ]]; then
    return 0
  fi

  mkdir -p "$DEPLOY_DIR/bin"
  download_tmp="$(mktemp "$DEPLOY_DIR/bin/.cloudflared.XXXXXX")"
  curl --fail --location --show-error --silent --max-time 180 \
    --output "$download_tmp" "$CLOUDFLARED_URL"
  downloaded_sha="$(sha256sum "$download_tmp" | awk '{print $1}')"
  if [[ "$downloaded_sha" != "$CLOUDFLARED_SHA256" ]]; then
    echo "cloudflared 校验失败：$downloaded_sha" >&2
    return 1
  fi
  chmod 755 "$download_tmp"
  mv -f "$download_tmp" "$CLOUDFLARED_BIN"
}

install_service() {
  local unit_tmp
  unit_tmp="$(mktemp)"
  sed \
    -e "s|@USER@|$USER|g" \
    -e "s|@BINARY@|$CLOUDFLARED_BIN|g" \
    > "$unit_tmp" <<'EOF'
[Unit]
Description=Temporary SpotifyStats showcase Quick Tunnel
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=@USER@
ExecStart=@BINARY@ tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:3002
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
  sudo install -m 644 "$unit_tmp" "$SERVICE_FILE"
  sudo systemctl daemon-reload
}

case "$action" in
  start)
    "$DEPLOY_DIR/showcase-auth.sh" ensure
    "$DEPLOY_DIR/set-deployment-mode.sh" dual
    install_cloudflared
    install_service
    # Intentionally do not enable it: a reboot must not silently create a new
    # external URL. Code deployments likewise never start this service.
    sudo systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
    sudo systemctl restart "$SERVICE_NAME"
    url=""
    for _ in $(seq 1 30); do
      url="$(latest_url)"
      [[ -n "$url" ]] && break
      sleep 2
    done
    if [[ -z "$url" ]]; then
      sudo systemctl status "$SERVICE_NAME" --no-pager >&2 || true
      echo "临时隧道未生成地址。" >&2
      exit 1
    fi
    printf '临时展示地址：%s\n' "$url"
    access_mode="$(sed -n 's/^SHOWCASE_ACCESS_MODE=//p' "$DEPLOY_DIR/.env" | tail -n 1)"
    if [[ "$access_mode" == "public" ]]; then
      echo "当前为 public：打开链接即可访问，链接持有者都能查看简化版数据。"
    else
      echo "当前为 protected：访问需要 ./showcase-auth.sh show 所显示的凭据。"
    fi
    ;;
  status)
    state="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || true)"
    printf '状态：%s\n' "${state:-not-installed}"
    url="$(latest_url)"
    [[ -n "$url" ]] && printf '临时展示地址：%s\n' "$url"
    ;;
  stop)
    sudo systemctl disable --now "$SERVICE_NAME" >/dev/null 2>&1 || true
    echo "临时展示入口已关闭。Docker 部署模式未修改。"
    ;;
esac
