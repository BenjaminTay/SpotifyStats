#!/usr/bin/env bash
set -Eeuo pipefail

readonly RELEASES_ROOT="/opt/spotify-stats/releases"
readonly REVISION="${1:-}"
readonly MANIFEST_SHA256="${2:-}"
readonly HELPER="/opt/spotify-stats/image_transport.py"

if [[ "$#" -ne 2 || ! "$REVISION" =~ ^[0-9a-f]{40}$ || ! "$MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "用法：activate-release-images.sh <40-char-git-commit-sha> <manifest-sha256>" >&2
  exit 2
fi
if [[ ! -f "$HELPER" || -L "$HELPER" ]]; then
  echo "缺少安全的 CAS helper：$HELPER" >&2
  exit 1
fi

python3 "$HELPER" activate \
  --releases-root "$RELEASES_ROOT" \
  --revision "$REVISION" \
  --manifest-sha256 "$MANIFEST_SHA256"
