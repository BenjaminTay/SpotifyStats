#!/usr/bin/env bash
# Sourced by deploy.sh: no cold builder and no change to the deployment surface.

versus_rank_image_supported() {
  docker run --rm --init --network none "$1" python -c \
    'from pathlib import Path; raise SystemExit(0 if Path("scripts/versus_rank_publication.py").is_file() else 42)'
  local status="$?"
  [[ "$status" -eq 0 ]] && return 0
  [[ "$status" -eq 42 ]] && return 1
  echo "无法核验目标镜像的个人排名发布能力，拒绝跳过门禁。" >&2
  return 2
}

versus_rank_command() {
  local image="$1" action="$2" source_path="$3" manifest="$4" revision="$5"
  local command=(docker run --rm --init --network none
    --mount "type=bind,src=$(dirname -- "$source_path"),dst=/rank-source,readonly"
    --mount "type=bind,src=$DEPLOY_DIR/data,dst=/rank-data")
  if [[ "$action" != "verify" ]]; then
    if [[ "$action" == "export" ]]; then
      install -m 600 /dev/null "$manifest"
      command+=(--mount "type=bind,src=$manifest,dst=/rank-manifest.json")
    else
      command+=(--mount "type=bind,src=$manifest,dst=/rank-manifest.json,readonly")
    fi
  fi
  command+=("$image" python scripts/versus_rank_publication.py "$action"
    --source-db "/rank-source/$(basename -- "$source_path")" --analysis-cache /rank-data/analysis_cache.db)
  # Every caller runs after Backend stop or against a closed preflight copy.
  # A remaining WAL uses ordinary strict mode=ro; it must never be ignored.
  if [[ ! -e "$source_path-wal" ]]; then
    command+=(--closed-source)
  fi
  if [[ "$action" != "verify" ]]; then
    command+=(--manifest /rank-manifest.json --release-sha "$revision" --require-defaults)
  fi
  "${command[@]}"
}

prepare_versus_rank_release() {
  local image="$1" source_path="$2"
  if versus_rank_image_supported "$image"; then
    :
  else
    local status="$?"
    [[ "$status" -eq 1 ]] || return "$status"
    # Rollbacks to images preceding the rank family cannot run its installer.
    # Their existing deployment and health gates remain authoritative.
    versus_rank_enabled="false"
    return 0
  fi
  versus_rank_enabled="true"
  if [[ -n "$VERSUS_RANK_MANIFEST" ]]; then
    [[ -f "$VERSUS_RANK_MANIFEST" ]] || {
      echo "指定的个人排名 manifest 不存在，拒绝发布。" >&2
      return 1
    }
    versus_rank_release_manifest="$VERSUS_RANK_MANIFEST"
  elif [[ -f "$DEPLOY_DIR/backups/versus-ranks-${NEW_TAG}.json" ]]; then
    versus_rank_release_manifest="$DEPLOY_DIR/backups/versus-ranks-${NEW_TAG}.json"
  else
    # Exact current publications can be exported and rebound across the
    # database replacement. This command only reads; missing/stale means fail.
    versus_rank_release_manifest="$release_stage_dir/versus-ranks-${NEW_TAG}.json"
    versus_rank_command "$image" export "$DEPLOY_DIR/data/spotify_stats.db" \
      "$versus_rank_release_manifest" "$NEW_TAG" || return 1
  fi
  versus_rank_command "$image" validate "$source_path" \
    "$versus_rank_release_manifest" "$NEW_TAG"
}

backup_versus_rank_release() {
  local image="$1"
  if [[ "$versus_rank_enabled" != "true" ]]; then
    return 0
  fi
  versus_rank_sidecar_existed="false"
  if [[ -f "$DEPLOY_DIR/data/analysis_cache.db" ]]; then
    versus_rank_sidecar_existed="true"
    versus_rank_sidecar_backup="$DEPLOY_DIR/backups/analysis-pre-release-${NEW_TAG:0:12}-${release_stamp}.db"
    create_offline_backup "$image" "$versus_rank_sidecar_backup" analysis_cache.db || return 1
  fi
  if [[ "$current_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
    if versus_rank_image_supported "$(backend_image_for_tag "$current_tag")"; then
      versus_rank_previous_manifest="$release_stage_dir/versus-ranks-${current_tag}.json"
      versus_rank_command "$(backend_image_for_tag "$current_tag")" export \
        "$DEPLOY_DIR/data/spotify_stats.db" "$versus_rank_previous_manifest" "$current_tag" || return 1
    else
      local status="$?"
      [[ "$status" -eq 1 ]] || return "$status"
    fi
  fi
}

install_versus_rank_release() {
  if [[ "$versus_rank_enabled" != "true" ]]; then
    return 0
  fi
  versus_rank_sidecar_changed="true"
  versus_rank_command "$target_backend_image" install "$DEPLOY_DIR/data/spotify_stats.db" \
    "$versus_rank_release_manifest" "$NEW_TAG" || return 1
  versus_rank_command "$target_backend_image" verify "$DEPLOY_DIR/data/spotify_stats.db" "" "$NEW_TAG"
}

restore_versus_rank_release() {
  if [[ "$versus_rank_sidecar_changed" != "true" ]]; then
    return 0
  fi
  if [[ "$versus_rank_sidecar_existed" == "true" ]]; then
    install -m 600 "$versus_rank_sidecar_backup" "$DEPLOY_DIR/data/analysis_cache.db.release"
    mv -f -- "$DEPLOY_DIR/data/analysis_cache.db.release" "$DEPLOY_DIR/data/analysis_cache.db"
  else
    rm -f -- "$DEPLOY_DIR/data/analysis_cache.db"
  fi
  rm -f -- "$DEPLOY_DIR/data/analysis_cache.db-wal" "$DEPLOY_DIR/data/analysis_cache.db-shm"
  if [[ -n "$versus_rank_previous_manifest" ]]; then
    versus_rank_command "$(backend_image_for_tag "$current_tag")" install \
      "$DEPLOY_DIR/data/spotify_stats.db" "$versus_rank_previous_manifest" "$current_tag" || return 1
    versus_rank_command "$(backend_image_for_tag "$current_tag")" verify \
      "$DEPLOY_DIR/data/spotify_stats.db" "" "$current_tag" || return 1
  fi
}

verify_running_versus_ranks() {
  compose_all exec -T backend python -c '
from pathlib import Path
import subprocess
import sys
script = Path("scripts/versus_rank_publication.py")
if script.is_file():
    subprocess.run([sys.executable, str(script), "verify", "--source-db", "/app/data/spotify_stats.db", "--analysis-cache", "/app/data/analysis_cache.db"], check=True)
'
}
