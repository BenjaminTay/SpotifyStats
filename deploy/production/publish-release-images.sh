#!/usr/bin/env bash
set -Eeuo pipefail

readonly PRODUCTION_DIR="/opt/spotify-stats"
readonly ENV_FILE="$PRODUCTION_DIR/.env"
readonly REVISION="${1:-}"
readonly SMOKE_TAG="transport-smoke-$REVISION"

if [[ "$#" -ne 1 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  echo "用法：publish-release-images.sh <40-char-git-commit-sha>" >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
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
  echo "TCR registry、namespace 或 repository 配置不安全。" >&2
  exit 1
fi

readonly API_LOCAL_IMAGE="spotify-stats-api:$SMOKE_TAG"
readonly WEB_LOCAL_IMAGE="spotify-stats-web:$SMOKE_TAG"
readonly API_REMOTE_IMAGE="${registry%/}/$namespace/$api_repository:$SMOKE_TAG"
readonly WEB_REMOTE_IMAGE="${registry%/}/$namespace/$web_repository:$SMOKE_TAG"

for image_ref in "$API_REMOTE_IMAGE" "$WEB_REMOTE_IMAGE"; do
  if [[ "$image_ref" != *":transport-smoke-$REVISION" ]] ||
     [[ "$image_ref" == *":$REVISION" || "$image_ref" == *":main" || "$image_ref" == *":latest" ]]; then
    echo "拒绝向生产标签发布 smoke 镜像：$image_ref" >&2
    exit 1
  fi
done

verify_image() {
  local image_ref="$1"
  local architecture operating_system revision
  docker image inspect "$image_ref" >/dev/null
  architecture="$(docker image inspect --format '{{.Architecture}}' "$image_ref")"
  operating_system="$(docker image inspect --format '{{.Os}}' "$image_ref")"
  revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_ref")"
  if [[ "$operating_system/$architecture" != "linux/amd64" ]]; then
    echo "镜像平台不正确：$image_ref ($operating_system/$architecture)" >&2
    return 1
  fi
  if [[ "$revision" != "$REVISION" ]]; then
    echo "镜像 revision label 不正确：$image_ref ($revision)" >&2
    return 1
  fi
}

push_with_retry() {
  local image_ref="$1"
  local attempt
  for attempt in 1 2; do
    echo "Pushing non-production smoke image $image_ref (attempt $attempt/2)"
    if timeout --signal=TERM --kill-after=30s 5m docker push "$image_ref" &&
       timeout --signal=TERM --kill-after=10s 1m docker manifest inspect "$image_ref" >/dev/null; then
      return 0
    fi
    if [[ "$attempt" -lt 2 ]]; then
      sleep "$((attempt * 10))"
    fi
  done
  return 1
}

pull_and_verify() {
  local image_ref="$1"
  docker image rm "$image_ref" >/dev/null 2>&1 || true
  timeout --signal=TERM --kill-after=30s 5m docker pull --platform linux/amd64 "$image_ref"
  timeout --signal=TERM --kill-after=10s 1m docker manifest inspect "$image_ref" >/dev/null
  verify_image "$image_ref"
}

verify_image "$API_LOCAL_IMAGE"
verify_image "$WEB_LOCAL_IMAGE"
docker tag "$API_LOCAL_IMAGE" "$API_REMOTE_IMAGE"
docker tag "$WEB_LOCAL_IMAGE" "$WEB_REMOTE_IMAGE"
push_with_retry "$API_REMOTE_IMAGE"
push_with_retry "$WEB_REMOTE_IMAGE"
pull_and_verify "$API_REMOTE_IMAGE"
pull_and_verify "$WEB_REMOTE_IMAGE"

for image_ref in "$API_REMOTE_IMAGE" "$WEB_REMOTE_IMAGE" "$API_LOCAL_IMAGE" "$WEB_LOCAL_IMAGE"; do
  docker image rm "$image_ref" >/dev/null 2>&1 || true
done
echo "TCR 非生产 smoke 镜像已完成 push、pull、manifest、platform 与 revision 校验。"
