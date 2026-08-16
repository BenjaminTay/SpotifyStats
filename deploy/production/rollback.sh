#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
target_tag="${1:-}"
target_mode=""
target_image_source=""

if [[ -z "$target_tag" && -f "$DEPLOY_DIR/.previous-image-tag" ]]; then
  target_tag="$(<"$DEPLOY_DIR/.previous-image-tag")"
  if [[ -f "$DEPLOY_DIR/.previous-deployment-mode" ]]; then
    target_mode="$(<"$DEPLOY_DIR/.previous-deployment-mode")"
  fi
  if [[ -f "$DEPLOY_DIR/.previous-image-source" ]]; then
    target_image_source="$(<"$DEPLOY_DIR/.previous-image-source")"
  fi
fi

if [[ ! "$target_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
  echo "没有可用的上一版本。也可以执行：$0 <git-commit-sha>" >&2
  exit 2
fi

if [[ -n "$target_mode" ]]; then
  if [[ "$target_mode" != "full" && "$target_mode" != "showcase" && "$target_mode" != "dual" ]]; then
    echo "上一部署模式记录无效：$target_mode" >&2
    exit 1
  fi
  if [[ -n "$target_image_source" ]]; then
    if [[ "$target_image_source" != "registry" && "$target_image_source" != "local" ]]; then
      echo "上一镜像来源记录无效：$target_image_source" >&2
      exit 1
    fi
    exec "$DEPLOY_DIR/deploy.sh" "$target_tag" \
      --mode "$target_mode" --image-source "$target_image_source"
  fi
  exec "$DEPLOY_DIR/deploy.sh" "$target_tag" --mode "$target_mode"
fi

# 显式 SHA 没有对应模式事实，因此保留当前模式，避免猜测或意外开放入口。
exec "$DEPLOY_DIR/deploy.sh" "$target_tag"
