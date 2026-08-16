#!/usr/bin/env bash
set -Eeuo pipefail

readonly PRODUCTION_DIR="/opt/spotify-stats"
readonly ENV_FILE="$PRODUCTION_DIR/.env"
readonly REVISION="${1:-}"

if [[ "$#" -ne 1 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  echo "用法：prepare-local-release-images.sh <40-char-git-commit-sha>" >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" || -L "$ENV_FILE" ]]; then
  echo "缺少安全的 $ENV_FILE。" >&2
  exit 1
fi

get_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

registry="$(get_env TCR_REGISTRY)"
namespace="$(get_env TCR_NAMESPACE)"
api_repository="$(get_env API_REPOSITORY)"
web_repository="$(get_env WEB_REPOSITORY)"
registry="${registry:-ccr.ccs.tencentyun.com}"
namespace="${namespace:-teacher-honor}"
api_repository="${api_repository:-spotify-stats-api}"
web_repository="${web_repository:-spotify-stats-web}"
if [[ ! "$registry" =~ ^[A-Za-z0-9.-]+(:[0-9]+)?$ ]] ||
   [[ ! "$namespace" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
   [[ ! "$api_repository" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
   [[ ! "$web_repository" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]]; then
  echo "registry、namespace 或 repository 配置不安全。" >&2
  exit 1
fi

prepare_ref() {
  local source_ref="$1"
  local target_ref="$2"
  local source_id target_id platform revision
  source_id="$(docker image inspect --format '{{.Id}}' "$source_ref")"
  platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$source_ref")"
  revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$source_ref")"
  if [[ "$platform" != "linux/amd64" || "$revision" != "$REVISION" ]]; then
    echo "本地 release 源镜像身份无效：$source_ref platform=$platform revision=$revision" >&2
    return 1
  fi
  if docker image inspect "$target_ref" >/dev/null 2>&1; then
    target_id="$(docker image inspect --format '{{.Id}}' "$target_ref")"
    if [[ "$target_id" != "$source_id" ]]; then
      echo "精确 release ref 已存在但 image ID 不同，拒绝覆盖：$target_ref" >&2
      return 1
    fi
  else
    docker tag "$source_ref" "$target_ref"
  fi
  target_id="$(docker image inspect --format '{{.Id}}' "$target_ref")"
  if [[ "$target_id" != "$source_id" ]]; then
    echo "精确 release ref 标记后 image ID 不一致：$target_ref" >&2
    return 1
  fi
}

api_source="spotify-stats-api:transport-$REVISION"
web_source="spotify-stats-web:transport-$REVISION"
api_target="${registry%/}/$namespace/$api_repository:$REVISION"
web_target="${registry%/}/$namespace/$web_repository:$REVISION"
prepare_ref "$api_source" "$api_target"
prepare_ref "$web_source" "$web_target"
echo "已准备 registry-style 本地精确 refs（未登录或访问 registry）：$api_target $web_target"
