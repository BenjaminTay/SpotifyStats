#!/usr/bin/env bash
set -Eeuo pipefail

readonly PRODUCTION_DIR="/opt/spotify-stats"
readonly RELEASES_ROOT="$PRODUCTION_DIR/releases"
readonly ENV_FILE="$PRODUCTION_DIR/.env"
readonly HELPER="$PRODUCTION_DIR/image_transport.py"
readonly REVISION="${1:-}"

if [[ "$#" -ne 1 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  echo "用法：seed-verified-smoke-images.sh <40-char-git-commit-sha>" >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" || -L "$ENV_FILE" || ! -f "$HELPER" || -L "$HELPER" ]]; then
  echo "缺少安全的生产 .env 或 CAS helper。" >&2
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
  echo "镜像仓库配置不安全。" >&2
  exit 1
fi

api_ref="${registry%/}/$namespace/$api_repository:transport-smoke-$REVISION"
web_ref="${registry%/}/$namespace/$web_repository:transport-smoke-$REVISION"
pull_verified() {
  local image_ref="$1"
  local repository manifest_json manifest_digest digest_ref platform label
  manifest_json="$(timeout --signal=TERM --kill-after=10s 1m docker manifest inspect --verbose "$image_ref")"
  manifest_digest="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Descriptor"]["digest"])' <<<"$manifest_json")"
  [[ "$manifest_digest" =~ ^sha256:[0-9a-f]{64}$ ]]
  repository="${image_ref%:*}"
  digest_ref="$repository@$manifest_digest"
  timeout --signal=TERM --kill-after=30s 5m docker pull --platform linux/amd64 "$digest_ref"
  platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$digest_ref")"
  label="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$digest_ref")"
  if [[ "$platform" != "linux/amd64" || "$label" != "$REVISION" ]]; then
    echo "已验证 smoke tag 的远端 digest 身份无效：$image_ref" >&2
    return 1
  fi
  docker tag "$digest_ref" "$image_ref"
}
pull_verified "$api_ref"
pull_verified "$web_ref"

staging="$RELEASES_ROOT/incoming/$REVISION/smoke-seed"
if [[ -e "$staging" || -L "$staging" ]]; then
  echo "smoke seed staging 已存在，拒绝覆盖：$staging" >&2
  exit 1
fi
sudo install -d -m 700 -o "$USER" -g "$USER" \
  "$RELEASES_ROOT/incoming" "$RELEASES_ROOT/incoming/$REVISION" "$staging"
archive="$staging/docker-save.tar"
artifact="$staging/artifact"
timeout --signal=TERM --kill-after=30s 20m docker image save "$api_ref" "$web_ref" --output "$archive"
python3 "$HELPER" build-artifact \
  --archive "$archive" --artifact "$artifact" --revision "$REVISION" --mode release \
  --api-ref "$api_ref" --web-ref "$web_ref"
manifest_sha256="$(sha256sum "$artifact/transport-manifest.json" | cut -d ' ' -f 1)"
python3 "$HELPER" seed-cache \
  --artifact "$artifact" \
  --releases-root "$RELEASES_ROOT" \
  --revision "$REVISION" \
  --manifest-sha256 "$manifest_sha256"
find "$staging" -depth -mindepth 1 -delete
sudo rmdir -- "$staging"
sudo rmdir --ignore-fail-on-non-empty "$RELEASES_ROOT/incoming/$REVISION"
echo "已从不可变 digest 校验的 TCR smoke images 补种共享 CAS：revision=$REVISION"
