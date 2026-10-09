#!/usr/bin/env bash
# Sourced by deploy.sh: install only prepared, source-fenced detail facts on stage.
music_detail_image_supported() {
  local status=0
  docker run --rm --init --network none "$1" python -c \
    'from pathlib import Path; raise SystemExit(0 if Path("scripts/prepare_music_detail_projection.py").is_file() else 42)' || status="$?"
  [[ "$status" -eq 0 ]] && return 0
  [[ "$status" -eq 42 ]] && return 1
  return 2
}

music_detail_command() {
  local image="$1" action="$2" database="$3" manifest="${4:-}"
  local access=",readonly"
  [[ "$action" != import ]] || access=""
  local args=(docker run --rm --init --network none
    -e SPOTIFY_STATS_DB_PATH=/detail-data/"$(basename -- "$database")"
    --mount "type=bind,src=$(dirname -- "$database"),dst=/detail-data$access")
  [[ -z "$manifest" ]] || args+=(--mount "type=bind,src=$manifest,dst=/detail-manifest.json,readonly")
  args+=("$image" python scripts/prepare_music_detail_projection.py --db-path /detail-data/"$(basename -- "$database")")
  case "$action" in
    import) args+=(--import-manifest /detail-manifest.json) ;;
    validate) args+=(--validate-manifest /detail-manifest.json) ;;
    verify) args+=(--verify) ;;
    *) return 2 ;;
  esac
  "${args[@]}"
}

prepare_music_detail_release() {
  local image="$1" staged="$2" status=0
  music_detail_image_supported "$image" || status="$?"
  [[ "$status" -eq 1 ]] && return 0
  [[ "$status" -eq 0 ]] || return "$status"
  # Later releases reuse ready facts already in the Online Backup. The first
  # release needs a private manifest built on an explicitly owned copy.
  if music_detail_command "$image" verify "$staged"; then
    return 0
  fi
  local manifest="$DEPLOY_DIR/backups/music-detail-${NEW_TAG}.json"
  [[ -f "$manifest" ]] || { echo '详情投影缺少精确成品；没有冷建，拒绝激活。' >&2; return 1; }
  music_detail_command "$image" validate "$staged" "$manifest" || return 1
  music_detail_command "$image" import "$staged" "$manifest" || return 1
  music_detail_command "$image" verify "$staged"
}

verify_running_music_detail() {
  compose_all exec -T backend python -c '
from pathlib import Path
import subprocess
import sys
script = Path("scripts/prepare_music_detail_projection.py")
if script.is_file():
    subprocess.run([sys.executable, str(script), "--db-path", "/app/data/spotify_stats.db", "--verify"], check=True)
'
}

billboard_release_enabled=false
billboard_sidecar_changed=false
billboard_sidecar_existed=false
billboard_sidecar_backup=""
billboard_staged_sidecar=""
billboard_release_manifest=""

checkpoint_live_database() {
  docker run --rm --init --network none \
    --mount "type=bind,src=$DEPLOY_DIR/data,dst=/app/data" "$1" python -c '
import sqlite3
import sys
connection = sqlite3.connect(sys.argv[1], timeout=30)
try:
    checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
finally:
    connection.close()
if checkpoint[0] != 0 or checkpoint[1] != checkpoint[2]:
    raise SystemExit("live database checkpoint did not complete")
' /app/data/spotify_stats.db
}

verify_stopped_billboard_exact() {
  docker run --rm --init --network none \
    -e SPOTIFY_STATS_DB_PATH=/app/data/spotify_stats.db \
    --mount "type=bind,src=$DEPLOY_DIR/data,dst=/app/data,readonly" "$1" python -c '
from backend.core.access_surface import set_public_readonly_db_guard
from backend.services.billboard_snapshot_service import billboard_default_snapshots_ready
set_public_readonly_db_guard(True)
if not billboard_default_snapshots_ready():
    raise SystemExit("previous Billboard publications are not exact-ready")
'
}

preserve_live_database_inode() {
  local image="$1" live="$DEPLOY_DIR/data/spotify_stats.db"
  [[ -f "$live" && -z "$rollback_live_inode_path" ]] || return 1
  checkpoint_live_database "$image" || return 1
  [[ ! -s "$live-wal" ]] || return 1
  rm -f -- "$live-wal" "$live-shm" || return 1
  rollback_live_inode_dir="$(mktemp -d "$DEPLOY_DIR/data/.rollback-inode.XXXXXX")" || return 1
  rollback_live_inode_path="$rollback_live_inode_dir/spotify_stats.db"
  # Same-filesystem hard link keeps the exact old schema, facts and identity.
  # A link failure must never silently fall back to a new-inode copy.
  ln -- "$live" "$rollback_live_inode_path" || return 1
  [[ "$live" -ef "$rollback_live_inode_path" ]] || return 1
  verify_stopped_billboard_exact "$image"
}

restore_live_database_inode() {
  local live="$DEPLOY_DIR/data/spotify_stats.db"
  [[ -n "$rollback_live_inode_path" && -f "$rollback_live_inode_path" ]] || {
    echo '原数据库 inode 恢复文件缺失；拒绝伪装成精确回滚。' >&2
    return 1
  }
  rm -f -- "$live-wal" "$live-shm" || return 1
  mv -f -- "$rollback_live_inode_path" "$live" || return 1
}

cleanup_live_database_inode() {
  [[ -n "$rollback_live_inode_dir" && -d "$rollback_live_inode_dir" ]] || return 0
  if [[ -f "$rollback_live_inode_path" ]]; then
    if [[ "$release_completed" == true || \
          "$rollback_live_inode_path" -ef "$DEPLOY_DIR/data/spotify_stats.db" ]]; then
      rm -f -- "$rollback_live_inode_path"
    else
      echo "保留可恢复的原数据库 inode：$rollback_live_inode_path" >&2
      return 0
    fi
  fi
  rmdir -- "$rollback_live_inode_dir"
}

billboard_release_command() {
  local image="$1" action="$2" database="$3" sidecar="$4" manifest="${5:-}"
  [[ ! -e "$database-wal" ]] || { echo 'Billboard 重绑要求已闭库并完成 WAL checkpoint。' >&2; return 1; }
  local access=",readonly"
  [[ "$action" != import ]] || access=""
  local args=(docker run --rm --init --network none
    -e SPOTIFY_STATS_DB_PATH=/app/data/spotify_stats.db
    --mount "type=bind,src=$database,dst=/app/data/spotify_stats.db,readonly"
    --mount "type=bind,src=$(dirname -- "$sidecar"),dst=/billboard-output$access")
  if [[ "$action" == export ]]; then
    install -m 600 /dev/null "$manifest"
    args+=(--mount "type=bind,src=$manifest,dst=/billboard-manifest.json")
  elif [[ -n "$manifest" ]]; then
    args+=(--mount "type=bind,src=$manifest,dst=/billboard-manifest.json,readonly")
  fi
  args+=("$image" python scripts/prepare_billboard_publications.py
    --db-path /app/data/spotify_stats.db --cache-path /billboard-output/"$(basename -- "$sidecar")")
  case "$action" in
    import) args+=(--import-manifest /billboard-manifest.json) ;;
    export) args+=(--export /billboard-manifest.json) ;;
    validate) args+=(--validate-manifest /billboard-manifest.json) ;;
    verify) args+=(--verify) ;;
    *) return 2 ;;
  esac
  "${args[@]}"
}

prepare_billboard_release() {
  local image="$1" database="$2" status=0
  music_detail_image_supported "$image" || status="$?"
  [[ "$status" -eq 1 ]] && return 0
  [[ "$status" -eq 0 ]] || return "$status"
  billboard_release_enabled=true
  billboard_staged_sidecar="$release_stage_dir/billboard_cache.db"
  if [[ -f "$DEPLOY_DIR/data/billboard_cache.db" ]]; then
    billboard_sidecar_existed=true
    billboard_sidecar_backup="$DEPLOY_DIR/backups/billboard-pre-release-${NEW_TAG:0:12}-${release_stamp}.db"
    create_offline_backup "$image" "$billboard_sidecar_backup" billboard_cache.db || return 1
    cp -- "$billboard_sidecar_backup" "$billboard_staged_sidecar"
  fi
  local manifest="$DEPLOY_DIR/backups/billboard-${NEW_TAG}.json"
  if [[ ! -f "$manifest" ]]; then
    manifest="$release_stage_dir/billboard-${NEW_TAG}.json"
    billboard_release_command "$image" export "$DEPLOY_DIR/data/spotify_stats.db" \
      "$DEPLOY_DIR/data/billboard_cache.db" "$manifest" || {
      echo 'Billboard 缺少精确成品；没有冷建，拒绝激活。' >&2; return 1;
    }
  fi
  billboard_release_manifest="$manifest"
  billboard_release_command "$image" validate "$database" "$billboard_staged_sidecar" "$manifest" || return 1
  billboard_release_command "$image" import "$database" "$billboard_staged_sidecar" "$manifest" || return 1
  billboard_release_command "$image" verify "$database" "$billboard_staged_sidecar"
}

install_billboard_release() {
  [[ "$billboard_release_enabled" == true ]] || return 0
  billboard_sidecar_changed=true
  install -m 600 "$billboard_staged_sidecar" "$DEPLOY_DIR/data/billboard_cache.db.release" || return 1
  mv -f -- "$DEPLOY_DIR/data/billboard_cache.db.release" "$DEPLOY_DIR/data/billboard_cache.db" || return 1
  rm -f -- "$DEPLOY_DIR/data/billboard_cache.db-wal" "$DEPLOY_DIR/data/billboard_cache.db-shm"
  # Promotion creates another SQLite file identity. Rebind the same validated
  # facts once more; copying stage keys would leave every public GET unavailable.
  billboard_release_command "$target_backend_image" import "$DEPLOY_DIR/data/spotify_stats.db" \
    "$DEPLOY_DIR/data/billboard_cache.db" "$billboard_release_manifest" || return 1
  billboard_release_command "$target_backend_image" verify "$DEPLOY_DIR/data/spotify_stats.db" \
    "$DEPLOY_DIR/data/billboard_cache.db"
}

restore_billboard_release() {
  [[ "$billboard_sidecar_changed" == true ]] || return 0
  if [[ "$billboard_sidecar_existed" == true ]]; then
    install -m 600 "$billboard_sidecar_backup" "$DEPLOY_DIR/data/billboard_cache.db.release" || return 1
    mv -f -- "$DEPLOY_DIR/data/billboard_cache.db.release" "$DEPLOY_DIR/data/billboard_cache.db" || return 1
  else
    rm -f -- "$DEPLOY_DIR/data/billboard_cache.db"
  fi
  rm -f -- "$DEPLOY_DIR/data/billboard_cache.db-wal" "$DEPLOY_DIR/data/billboard_cache.db-shm"
}

verify_running_billboard_release() {
  compose_all exec -T backend python -c '
from pathlib import Path
import subprocess
import sys
script = Path("scripts/prepare_billboard_publications.py")
if script.is_file():
    subprocess.run([sys.executable, str(script), "--db-path", "/app/data/spotify_stats.db", "--cache-path", "/app/data/billboard_cache.db", "--verify"], check=True)
else:
    from backend.core.access_surface import set_public_readonly_db_guard
    from backend.services.billboard_snapshot_service import billboard_default_snapshots_ready
    set_public_readonly_db_guard(True)
    if not billboard_default_snapshots_ready():
        raise SystemExit("previous Billboard publications are not exact-ready")
'
}
