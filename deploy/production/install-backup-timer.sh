#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

sudo tee /etc/systemd/system/spotify-stats-backup.service >/dev/null <<EOF
[Unit]
Description=SpotifyStats daily cleanup and weekly SQLite backup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$DEPLOY_DIR
ExecStartPre=+/usr/bin/python3 $DEPLOY_DIR/cleanup-release-files.py --apply
ExecStart=$DEPLOY_DIR/backup.sh --scheduled
EOF

sudo tee /etc/systemd/system/spotify-stats-backup.timer >/dev/null <<'EOF'
[Unit]
Description=Run SpotifyStats maintenance daily

[Timer]
OnCalendar=*-*-* 03:20:00
RandomizedDelaySec=20m
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now spotify-stats-backup.timer
sudo systemctl status spotify-stats-backup.timer --no-pager
