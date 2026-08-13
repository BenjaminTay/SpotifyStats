#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_tag="${1:-}"

if [[ -z "$target_tag" && -f "$DEPLOY_DIR/.previous-image-tag" ]]; then
  target_tag="$(<"$DEPLOY_DIR/.previous-image-tag")"
fi

if [[ ! "$target_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
  echo "没有可用的上一版本。也可以执行：$0 <git-commit-sha>" >&2
  exit 2
fi

export ALLOW_PRIVATE_ONLY_RELEASE=1
exec "$DEPLOY_DIR/deploy.sh" "$target_tag"
