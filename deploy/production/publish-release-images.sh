#!/usr/bin/env bash
set -Eeuo pipefail

readonly PRODUCTION_DIR="/opt/spotify-stats"
readonly ENV_FILE="$PRODUCTION_DIR/.env"
readonly REVISION="${1:-}"
readonly MODE="${2:-smoke}"

if (( $# < 1 || $# > 2 )) || ! "$REVISION" =~ ^[0-9a-f]{40}$ ||
   [[ "$MODE" != "smoke" && "$MODE" != "release" ]]; then
  echo "用法：publish-release-images.sh <40-char-git-commit-sha> [smoke|release]" >&2
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

if [[ "$MODE" == "smoke" ]]; then
  readonly IMAGE_TAG="transport-smoke-$REVISION"
else
  readonly IMAGE_TAG="$REVISION"
fi
readonly API_LOCAL_IMAGE="spotify-stats-api:transport-$REVISION"
readonly WEB_LOCAL_IMAGE="spotify-stats-web:transport-$REVISION"
readonly API_REMOTE_IMAGE="${registry%/}/$namespace/$api_repository:$IMAGE_TAG"
readonly WEB_REMOTE_IMAGE="${registry%/}/$namespace/$web_repository:$IMAGE_TAG"

for image_ref in "$API_REMOTE_IMAGE" "$WEB_REMOTE_IMAGE"; do
  if [[ "$image_ref" == *":main" || "$image_ref" == *":latest" ]]; then
    echo "拒绝覆盖可变镜像标签：$image_ref" >&2
    exit 1
  fi
  if [[ "$MODE" == "smoke" && "$image_ref" != *":transport-smoke-$REVISION" ]]; then
    echo "非生产 smoke 标签不正确：$image_ref" >&2
    exit 1
  fi
  if [[ "$MODE" == "release" && "$image_ref" != *":$REVISION" ]]; then
    echo "生产发布必须使用精确 commit SHA 标签：$image_ref" >&2
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
  local attempt existing_manifest existing_digest existing_ref source_id existing_id
  if existing_manifest="$(timeout --signal=TERM --kill-after=10s 1m docker manifest inspect --verbose "$image_ref" 2>/dev/null)"; then
    existing_digest="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Descriptor"]["digest"])' <<<"$existing_manifest")"
    if [[ ! "$existing_digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
      echo "远端已有 tag，但 manifest digest 无法验证：$image_ref" >&2
      return 1
    fi
    existing_ref="${image_ref%:*}@$existing_digest"
    timeout --signal=TERM --kill-after=30s 5m docker pull --platform linux/amd64 "$existing_ref"
    source_id="$(docker image inspect --format '{{.Id}}' "$image_ref")"
    existing_id="$(docker image inspect --format '{{.Id}}' "$existing_ref")"
    if [[ "$source_id" != "$existing_id" ]]; then
      echo "远端精确 tag 已存在但 image ID 不同，拒绝覆盖：$image_ref" >&2
      return 1
    fi
    echo "远端精确 tag 已存在且内容一致，跳过 push：$image_ref"
    return 0
  fi
  for attempt in 1 2; do
    echo "Pushing $MODE image $image_ref (attempt $attempt/2)"
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
  local repository manifest_json manifest_digest digest_ref
  manifest_json="$(timeout --signal=TERM --kill-after=10s 1m docker manifest inspect --verbose "$image_ref")"
  manifest_digest="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Descriptor"]["digest"])' <<<"$manifest_json")"
  if [[ ! "$manifest_digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "无法取得远端不可变 manifest digest：$image_ref" >&2
    return 1
  fi
  repository="${image_ref%:*}"
  digest_ref="$repository@$manifest_digest"
  docker image rm "$image_ref" >/dev/null 2>&1 || true
  timeout --signal=TERM --kill-after=30s 5m docker pull --platform linux/amd64 "$digest_ref"
  timeout --signal=TERM --kill-after=10s 1m docker manifest inspect "$digest_ref" >/dev/null
  verify_image "$digest_ref"
  docker tag "$digest_ref" "$image_ref"
}

verify_image "$API_LOCAL_IMAGE"
verify_image "$WEB_LOCAL_IMAGE"
docker tag "$API_LOCAL_IMAGE" "$API_REMOTE_IMAGE"
docker tag "$WEB_LOCAL_IMAGE" "$WEB_REMOTE_IMAGE"
push_with_retry "$API_REMOTE_IMAGE"
push_with_retry "$WEB_REMOTE_IMAGE"
pull_and_verify "$API_REMOTE_IMAGE"
pull_and_verify "$WEB_REMOTE_IMAGE"

if [[ "$MODE" == "smoke" ]]; then
  for image_ref in "$API_REMOTE_IMAGE" "$WEB_REMOTE_IMAGE" "$API_LOCAL_IMAGE" "$WEB_LOCAL_IMAGE"; do
    docker image rm "$image_ref" >/dev/null 2>&1 || true
  done
fi
echo "TCR 镜像已完成 push、pull、manifest、platform 与 revision 校验：mode=$MODE"
