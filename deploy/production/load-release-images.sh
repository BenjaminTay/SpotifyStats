#!/usr/bin/env bash
set -Eeuo pipefail

readonly RELEASES_ROOT="/opt/spotify-stats/releases"
readonly REVISION="${1:-}"
readonly MODE="${2:-}"
readonly MANIFEST_SHA256="${3:-}"
readonly MIN_HEADROOM_BYTES=1073741824

usage() {
  echo "用法：load-release-images.sh <40-char-git-commit-sha> <smoke|release> <manifest-sha256>" >&2
}

if [[ "$#" -ne 3 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]] ||
   [[ "$MODE" != "smoke" && "$MODE" != "release" ]] ||
   [[ ! "$MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  usage
  exit 2
fi

readonly STAGING_DIR="$RELEASES_ROOT/incoming/$REVISION/$MODE"
readonly TRANSPORT_HELPER="$STAGING_DIR/image_transport.py"
readonly ARCHIVE_PATH="$STAGING_DIR/docker-save.tar"
readonly API_IMAGE="spotify-stats-api:transport-$REVISION"
readonly WEB_IMAGE="spotify-stats-web:transport-$REVISION"

for path in "$STAGING_DIR" "$TRANSPORT_HELPER" "$STAGING_DIR/transport-manifest.json"; do
  if [[ -L "$path" ]]; then
    echo "拒绝符号链接：$path" >&2
    exit 1
  fi
done
if [[ ! -d "$STAGING_DIR" || ! -f "$TRANSPORT_HELPER" ]]; then
  echo "incoming 目录缺少 CAS transport helper：$STAGING_DIR" >&2
  exit 1
fi

read -r total_blob_bytes missing_bytes < <(
  python3 - "$STAGING_DIR/transport-manifest.json" "$STAGING_DIR/plan-result.json" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
plan = json.load(open(sys.argv[2], encoding="utf-8"))
print(manifest["total_blob_bytes"], plan["missing_bytes"])
PY
)
if [[ ! "$total_blob_bytes" =~ ^[1-9][0-9]*$ || ! "$missing_bytes" =~ ^[0-9]+$ ]]; then
  echo "CAS 容量元数据无效。" >&2
  exit 1
fi

available_release_bytes="$(df --output=avail -B1 "$RELEASES_ROOT" | tail -n 1 | tr -d ' ')"
required_release_bytes="$((total_blob_bytes + MIN_HEADROOM_BYTES))"
if (( available_release_bytes < required_release_bytes )); then
  echo "release CAS 重建空间不足：available=$available_release_bytes required=$required_release_bytes" >&2
  exit 1
fi

python3 "$TRANSPORT_HELPER" materialize \
  --staging "$STAGING_DIR" \
  --releases-root "$RELEASES_ROOT" \
  --revision "$REVISION" \
  --mode "$MODE" \
  --manifest-sha256 "$MANIFEST_SHA256"

archive_bytes="$(stat --format='%s' "$ARCHIVE_PATH")"
docker_root="$(docker info --format '{{.DockerRootDir}}')"
if [[ -z "$docker_root" || ! -d "$docker_root" ]]; then
  echo "无法解析 DockerRootDir。" >&2
  exit 1
fi
available_docker_bytes="$(df --output=avail -B1 "$docker_root" | tail -n 1 | tr -d ' ')"
required_docker_bytes="$((archive_bytes * 2 + MIN_HEADROOM_BYTES))"
if (( available_docker_bytes < required_docker_bytes )); then
  echo "Docker 存储空间不足：available=$available_docker_bytes required=$required_docker_bytes" >&2
  exit 1
fi

timeout --signal=TERM --kill-after=30s 20m docker load --input "$ARCHIVE_PATH"

verify_image() {
  local image_ref="$1"
  local architecture operating_system revision
  docker image inspect "$image_ref" >/dev/null
  architecture="$(docker image inspect --format '{{.Architecture}}' "$image_ref")"
  operating_system="$(docker image inspect --format '{{.Os}}' "$image_ref")"
  revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_ref")"
  if [[ "$operating_system/$architecture" != "linux/amd64" || "$revision" != "$REVISION" ]]; then
    echo "载入镜像身份不正确：$image_ref platform=$operating_system/$architecture revision=$revision" >&2
    return 1
  fi
}

verify_image "$API_IMAGE"
verify_image "$WEB_IMAGE"
api_image_id="$(docker image inspect --format '{{.Id}}' "$API_IMAGE")"
web_image_id="$(docker image inspect --format '{{.Id}}' "$WEB_IMAGE")"
python3 "$TRANSPORT_HELPER" record-load \
  --staging "$STAGING_DIR" \
  --releases-root "$RELEASES_ROOT" \
  --revision "$REVISION" \
  --mode "$MODE" \
  --manifest-sha256 "$MANIFEST_SHA256" \
  --api-image-id "$api_image_id" \
  --web-image-id "$web_image_id"

echo "CAS Docker save 已重建并载入：mode=$MODE revision=$REVISION archive_bytes=$archive_bytes missing_bytes=$missing_bytes"
