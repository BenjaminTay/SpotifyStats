#!/usr/bin/env bash
set -Eeuo pipefail

readonly PRODUCTION_DIR="/opt/spotify-stats"
readonly RELEASES_ROOT="$PRODUCTION_DIR/releases"
readonly ENV_FILE="$PRODUCTION_DIR/.env"
readonly HELPER="$PRODUCTION_DIR/image_transport.py"

if [[ "$#" -ne 0 ]]; then
  echo "用法：bootstrap-current-release-images.sh" >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" || -L "$ENV_FILE" || ! -f "$HELPER" || -L "$HELPER" ]]; then
  echo "缺少安全的生产 .env 或 CAS helper。" >&2
  exit 1
fi
if python3 "$HELPER" has-current --releases-root "$RELEASES_ROOT"; then
  echo "CAS retention 已有 current，跳过 bootstrap。"
  exit 0
fi

get_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

revision="$(get_env IMAGE_TAG)"
registry="$(get_env TCR_REGISTRY)"
namespace="$(get_env TCR_NAMESPACE)"
api_repository="$(get_env API_REPOSITORY)"
web_repository="$(get_env WEB_REPOSITORY)"
registry="${registry:-ccr.ccs.tencentyun.com}"
namespace="${namespace:-teacher-honor}"
api_repository="${api_repository:-spotify-stats-api}"
web_repository="${web_repository:-spotify-stats-web}"
if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]] ||
   [[ ! "$registry" =~ ^[A-Za-z0-9.-]+(:[0-9]+)?$ ]] ||
   [[ ! "$namespace" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
   [[ ! "$api_repository" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]] ||
   [[ ! "$web_repository" =~ ^[a-z0-9]+([._-][a-z0-9]+)*$ ]]; then
  echo "当前 IMAGE_TAG 或镜像仓库配置不满足 bootstrap 契约。" >&2
  exit 1
fi

api_ref="${registry%/}/$namespace/$api_repository:$revision"
web_ref="${registry%/}/$namespace/$web_repository:$revision"
verify_current() {
  local image_ref="$1"
  local platform label
  docker image inspect "$image_ref" >/dev/null
  platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image_ref")"
  label="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_ref")"
  if [[ "$platform" != "linux/amd64" || "$label" != "$revision" ]]; then
    echo "当前 exact ref 无法作为离线 previous：$image_ref platform=$platform revision=$label" >&2
    return 1
  fi
}
verify_current "$api_ref"
verify_current "$web_ref"

api_id="$(docker image inspect --format '{{.Id}}' "$api_ref")"
web_id="$(docker image inspect --format '{{.Id}}' "$web_ref")"
api_size="$(docker image inspect --format '{{.Size}}' "$api_ref")"
web_size="$(docker image inspect --format '{{.Size}}' "$web_ref")"
required_bytes="$((api_size + web_size + 1073741824))"
sudo install -d -m 700 -o "$USER" -g "$USER" \
  "$RELEASES_ROOT/incoming" "$RELEASES_ROOT/incoming/$revision"
available_bytes="$(df --output=avail -B1 "$RELEASES_ROOT/incoming" | tail -n 1 | tr -d ' ')"
if (( available_bytes < required_bytes )); then
  echo "bootstrap 当前镜像的磁盘空间不足：available=$available_bytes required=$required_bytes" >&2
  exit 1
fi

staging="$RELEASES_ROOT/incoming/$revision/bootstrap"
if [[ -L "$staging" ]]; then
  echo "拒绝 bootstrap 符号链接：$staging" >&2
  exit 1
fi
sudo install -d -m 700 -o "$USER" -g "$USER" "$staging"
archive="$staging/docker-save.tar"
artifact="$staging/artifact"
if [[ -e "$archive" || -e "$artifact" ]]; then
  echo "bootstrap staging 已包含旧产物，拒绝覆盖：$staging" >&2
  exit 1
fi
timeout --signal=TERM --kill-after=30s 20m docker image save "$api_ref" "$web_ref" --output "$archive"
python3 "$HELPER" build-artifact \
  --archive "$archive" \
  --artifact "$artifact" \
  --revision "$revision" \
  --mode release \
  --api-ref "$api_ref" \
  --web-ref "$web_ref"
manifest_sha256="$(sha256sum "$artifact/transport-manifest.json" | cut -d ' ' -f 1)"
python3 "$HELPER" seed-bootstrap \
  --artifact "$artifact" \
  --archive "$archive" \
  --releases-root "$RELEASES_ROOT" \
  --revision "$revision" \
  --manifest-sha256 "$manifest_sha256" \
  --api-image-id "$api_id" \
  --web-image-id "$web_id"
find "$staging" -depth -mindepth 1 -delete
sudo rmdir -- "$staging"
sudo rmdir --ignore-fail-on-non-empty "$RELEASES_ROOT/incoming/$revision"
echo "当前生产镜像已种入 CAS 并保留可加载 archive：revision=$revision"
