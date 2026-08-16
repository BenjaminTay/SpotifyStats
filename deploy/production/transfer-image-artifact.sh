#!/usr/bin/env bash
set -Eeuo pipefail

readonly ARTIFACT_DIR="${1:-}"
readonly REVISION="${2:-}"
readonly MODE="${3:-}"
readonly MANIFEST_SHA256="${4:-}"
readonly REMOTE="${5:-}"
readonly SERVER_PORT="${6:-}"
readonly SSH_KEY="${7:-}"
readonly RESULT_FILE="${8:-}"
readonly STAGING_DIR="/opt/spotify-stats/releases/incoming/$REVISION/$MODE"

usage() {
  echo "用法：transfer-image-artifact.sh <artifact-dir> <revision> <smoke|release> <manifest-sha256> <user@host> <port> <ssh-key> <result-file>" >&2
}

if [[ "$#" -ne 8 || ! "$REVISION" =~ ^[0-9a-f]{40}$ ]] ||
   [[ "$MODE" != "smoke" && "$MODE" != "release" ]] ||
   [[ ! "$MANIFEST_SHA256" =~ ^[0-9a-f]{64}$ ]] ||
   [[ ! "$SERVER_PORT" =~ ^[1-9][0-9]{0,4}$ ]] ||
   [[ -z "$REMOTE" || "$REMOTE" == -* || -z "$RESULT_FILE" ]]; then
  usage
  exit 2
fi
if [[ -L "$ARTIFACT_DIR" || ! -d "$ARTIFACT_DIR/layout/blobs/sha256" ]] ||
   [[ ! -f "$ARTIFACT_DIR/transport-manifest.json" || -L "$ARTIFACT_DIR/transport-manifest.json" ]] ||
   [[ ! -f "$SSH_KEY" || -L "$SSH_KEY" ]]; then
  echo "Artifact 或 SSH key 不满足安全前置条件。" >&2
  exit 1
fi

ssh_args=(-p "$SERVER_PORT" -i "$SSH_KEY")
ssh "${ssh_args[@]}" "$REMOTE" bash -s -- "$REVISION" "$MODE" <<'REMOTE_PREPARE'
set -Eeuo pipefail
revision="$1"
mode="$2"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$mode" == "smoke" || "$mode" == "release" ]]
for tool in rsync docker sha256sum gzip df timeout python3 tar; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "服务器缺少 image CAS transport 必需命令：$tool" >&2
    exit 1
  fi
done
releases_root="/opt/spotify-stats/releases"
staging_dir="$releases_root/incoming/$revision/$mode"
if [[ -L "$staging_dir" ]]; then
  echo "拒绝 staging 符号链接：$staging_dir" >&2
  exit 1
fi
sudo install -d -m 700 -o "$USER" -g "$USER" \
  "$releases_root" "$releases_root/blobs" "$releases_root/blobs/sha256" \
  "$releases_root/locks" "$releases_root/records" "$releases_root/state" \
  "$releases_root/incoming" "$staging_dir" "$staging_dir/layout" "$staging_dir/upload"
docker ps --no-trunc --format '{{.ID}}\t{{.Image}}\t{{.Names}}' | LC_ALL=C sort > "$staging_dir/live-containers.before"
REMOTE_PREPARE

(
  cd "$ARTIFACT_DIR"
  rsync --archive --relative --checksum --partial --partial-dir=.metadata-partial --delay-updates \
    --timeout=300 \
    -e "ssh -p $SERVER_PORT -i $SSH_KEY" \
    ./transport-manifest.json ./layout/index.json ./layout/manifest.json \
    ./layout/oci-layout ./layout/repositories \
    "$REMOTE:$STAGING_DIR/"
)
rsync --archive --checksum --partial --partial-dir=.scripts-partial --delay-updates --timeout=300 \
  -e "ssh -p $SERVER_PORT -i $SSH_KEY" \
  deploy/production/image_transport.py \
  deploy/production/load-release-images.sh \
  deploy/production/publish-release-images.sh \
  "$REMOTE:$STAGING_DIR/"

ssh "${ssh_args[@]}" "$REMOTE" \
  "python3 '$STAGING_DIR/image_transport.py' plan --staging '$STAGING_DIR' --releases-root /opt/spotify-stats/releases --revision '$REVISION' --mode '$MODE' --manifest-sha256 '$MANIFEST_SHA256'"

plan_file="$(mktemp)"
ssh "${ssh_args[@]}" "$REMOTE" "cat '$STAGING_DIR/plan-result.json'" > "$plan_file"
missing_bytes="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["missing_bytes"])' "$plan_file")"
missing_count="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["missing_count"])' "$plan_file")"
if [[ ! "$missing_bytes" =~ ^[0-9]+$ || ! "$missing_count" =~ ^[0-9]+$ ]]; then
  echo "服务器 CAS plan 结果无效。" >&2
  exit 1
fi

ssh "${ssh_args[@]}" "$REMOTE" bash -s -- "$REVISION" "$MODE" "$missing_bytes" <<'REMOTE_CAPACITY'
set -Eeuo pipefail
revision="$1"
mode="$2"
missing_bytes="$3"
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$mode" == "smoke" || "$mode" == "release" ]]
[[ "$missing_bytes" =~ ^[0-9]+$ ]]
staging_dir="/opt/spotify-stats/releases/incoming/$revision/$mode"
available_bytes="$(df --output=avail -B1 "$staging_dir" | tail -n 1 | tr -d ' ')"
required_bytes="$((missing_bytes + 1073741824))"
if (( available_bytes < required_bytes )); then
  echo "CAS missing blobs 空间不足：available=$available_bytes required=$required_bytes" >&2
  exit 1
fi
REMOTE_CAPACITY

shard_root="$(mktemp -d)"
pids=()
logs=()
for shard in 0 1 2 3; do
  list="$shard_root/missing-blobs.$shard.txt"
  log="$shard_root/rsync.$shard.log"
  ssh "${ssh_args[@]}" "$REMOTE" "cat '$STAGING_DIR/missing-blobs.$shard.txt'" > "$list"
  while IFS= read -r relative_path; do
    [[ -z "$relative_path" ]] && continue
    if [[ ! "$relative_path" =~ ^layout/blobs/sha256/[0-9a-f]{64}$ ]] ||
       [[ ! -f "$ARTIFACT_DIR/$relative_path" || -L "$ARTIFACT_DIR/$relative_path" ]]; then
      echo "远端 missing blob list 包含无效路径：$relative_path" >&2
      exit 1
    fi
  done < "$list"
  if [[ ! -s "$list" ]]; then
    continue
  fi
  (
    cd "$ARTIFACT_DIR"
    LC_ALL=C rsync --archive --relative --files-from="$list" --checksum --compress \
      --partial --partial-dir=".rsync-partial-$shard" --delay-updates \
      --stats --no-human-readable --timeout=300 \
      -e "ssh -p $SERVER_PORT -i $SSH_KEY" \
      ./ "$REMOTE:$STAGING_DIR/upload/" > "$log" 2>&1
  ) &
  pids+=("$!")
  logs+=("$log")
done

failed=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    failed=1
  fi
done
if (( failed != 0 )); then
  for log in "${logs[@]}"; do
    sed -n '1,240p' "$log" >&2
  done
  exit 1
fi

transferred_wire_bytes=0
for log in "${logs[@]}"; do
  shard_wire_bytes="$(awk -F: '/^Total bytes sent:/ {gsub(/[^0-9]/, "", $2); print $2}' "$log" | tail -n 1)"
  shard_wire_bytes="${shard_wire_bytes:-0}"
  transferred_wire_bytes="$((transferred_wire_bytes + shard_wire_bytes))"
done

ssh "${ssh_args[@]}" "$REMOTE" \
  "bash '$STAGING_DIR/load-release-images.sh' '$REVISION' '$MODE' '$MANIFEST_SHA256'"
{
  printf 'missing_count=%s\n' "$missing_count"
  printf 'missing_bytes=%s\n' "$missing_bytes"
  printf 'transferred_wire_bytes=%s\n' "$transferred_wire_bytes"
} > "$RESULT_FILE"
