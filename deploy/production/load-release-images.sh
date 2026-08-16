#!/usr/bin/env bash
set -Eeuo pipefail

readonly RELEASES_ROOT="/opt/spotify-stats/releases/incoming"
readonly REVISION="${1:-}"
readonly MAX_ARCHIVE_BYTES=21474836480
readonly MIN_DOCKER_HEADROOM_BYTES=1073741824

usage() {
  echo "用法：load-release-images.sh <40-char-git-commit-sha>" >&2
}

if [[ "$#" -ne 1 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  usage
  exit 2
fi

readonly STAGING_DIR="$RELEASES_ROOT/$REVISION"
readonly ARCHIVE_PATH="$STAGING_DIR/spotify-stats-images-$REVISION.tar.gz"
readonly SHA256_PATH="$ARCHIVE_PATH.sha256"
readonly BYTES_PATH="$ARCHIVE_PATH.bytes"
readonly API_IMAGE="spotify-stats-api:transport-smoke-$REVISION"
readonly WEB_IMAGE="spotify-stats-web:transport-smoke-$REVISION"

for path in "$STAGING_DIR" "$ARCHIVE_PATH" "$SHA256_PATH" "$BYTES_PATH"; do
  if [[ -L "$path" ]]; then
    echo "拒绝符号链接：$path" >&2
    exit 1
  fi
done
if [[ ! -d "$STAGING_DIR" || ! -f "$ARCHIVE_PATH" || ! -f "$SHA256_PATH" || ! -f "$BYTES_PATH" ]]; then
  echo "incoming 目录缺少镜像归档或完整性 sidecar：$STAGING_DIR" >&2
  exit 1
fi

expected_sha256="$(tr -d '[:space:]' < "$SHA256_PATH")"
expected_bytes="$(tr -d '[:space:]' < "$BYTES_PATH")"
if [[ ! "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] ||
   [[ ! "$expected_bytes" =~ ^[1-9][0-9]*$ ]] ||
   (( expected_bytes > MAX_ARCHIVE_BYTES )); then
  echo "镜像归档 sidecar 格式无效或归档超过 20 GiB 安全上限。" >&2
  exit 1
fi

actual_sha256="$(sha256sum "$ARCHIVE_PATH" | cut -d ' ' -f 1)"
archive_bytes="$(stat --format='%s' "$ARCHIVE_PATH")"
if [[ "$actual_sha256" != "$expected_sha256" ]]; then
  echo "镜像归档 SHA-256 不匹配。" >&2
  exit 1
fi
if [[ "$archive_bytes" != "$expected_bytes" ]]; then
  echo "镜像归档容量不匹配：actual=$archive_bytes expected=$expected_bytes" >&2
  exit 1
fi
gzip --test "$ARCHIVE_PATH"

docker_root="$(docker info --format '{{.DockerRootDir}}')"
if [[ -z "$docker_root" || ! -d "$docker_root" ]]; then
  echo "无法解析 DockerRootDir。" >&2
  exit 1
fi
available_bytes="$(df --output=avail -B1 "$docker_root" | tail -n 1 | tr -d ' ')"
if [[ ! "$available_bytes" =~ ^[0-9]+$ ]]; then
  echo "无法读取 Docker 存储可用容量。" >&2
  exit 1
fi
required_bytes="$((archive_bytes * 4 + MIN_DOCKER_HEADROOM_BYTES))"
if (( available_bytes < required_bytes )); then
  echo "Docker 存储空间不足：available=$available_bytes required=$required_bytes" >&2
  exit 1
fi

timeout --signal=TERM --kill-after=30s 20m \
  bash -o pipefail -c 'gzip --decompress --stdout "$1" | docker load' _ "$ARCHIVE_PATH"
for image in "$API_IMAGE" "$WEB_IMAGE"; do
  docker image inspect "$image" >/dev/null
  architecture="$(docker image inspect --format '{{.Architecture}}' "$image")"
  operating_system="$(docker image inspect --format '{{.Os}}' "$image")"
  revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")"
  if [[ "$architecture" != "amd64" || "$operating_system" != "linux" ]]; then
    echo "镜像平台不正确：$image ($operating_system/$architecture)" >&2
    exit 1
  fi
  if [[ "$revision" != "$REVISION" ]]; then
    echo "镜像 revision label 不正确：$image ($revision)" >&2
    exit 1
  fi
done

echo "非生产 smoke 镜像归档已校验并载入：revision=$REVISION bytes=$archive_bytes"
