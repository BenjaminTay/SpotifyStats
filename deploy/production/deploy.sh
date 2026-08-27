#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
NEW_TAG="${1:-}"
MODE_OVERRIDE=""
IMAGE_SOURCE_OVERRIDE=""

usage() {
  cat >&2 <<'EOF'
用法：deploy.sh <git-commit-sha> [--mode full|showcase|dual] [--image-source registry|local]

不提供 --mode 时沿用 .env 中的 DEPLOYMENT_MODE。部署只管理 Docker
loopback 网关，不会启用或关闭 Tailscale、Funnel、域名或云防火墙入口。
registry 会先拉取精确 SHA 镜像；local 只接受已校验并载入本机的精确 SHA 镜像，
且启动和回滚均禁止访问 registry。
EOF
}

shift || true
while (( $# > 0 )); do
  case "$1" in
    --mode)
      [[ $# -ge 2 && -z "$MODE_OVERRIDE" ]] || { usage; exit 2; }
      MODE_OVERRIDE="$2"
      shift 2
      ;;
    --image-source)
      [[ $# -ge 2 && -z "$IMAGE_SOURCE_OVERRIDE" ]] || { usage; exit 2; }
      IMAGE_SOURCE_OVERRIDE="$2"
      shift 2
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

cd "$DEPLOY_DIR"
umask 077

if [[ ! "$NEW_TAG" =~ ^[0-9a-f]{7,64}$ ]]; then
  usage
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。请先复制 .env.example 并填写生产配置。" >&2
  exit 1
fi

if grep -Eq 'example-tailnet|SPOTIFY_STATS_(TOKEN_KEY|GATEWAY_TOKEN)=replace-with' "$ENV_FILE"; then
  echo ".env 仍含 URL、数据加密密钥或网关密钥占位值，拒绝部署。" >&2
  exit 1
fi

get_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
}

valid_mode() {
  [[ "$1" == "full" || "$1" == "showcase" || "$1" == "dual" ]]
}

valid_image_source() {
  [[ "$1" == "registry" || "$1" == "local" ]]
}

valid_showcase_access_mode() {
  [[ "$1" == "protected" || "$1" == "public" ]]
}

ensure_gateway_token() {
  local token
  token="$(get_env SPOTIFY_STATS_GATEWAY_TOKEN)"
  if [[ -z "$token" ]]; then
    if ! command -v openssl >/dev/null 2>&1; then
      echo "缺少 SPOTIFY_STATS_GATEWAY_TOKEN，且服务器没有 openssl 可用于安全生成。" >&2
      return 1
    fi
    token="$(openssl rand -hex 32)"
    set_env SPOTIFY_STATS_GATEWAY_TOKEN "$token"
    echo "已在服务器 .env 中生成独立网关密钥。"
  fi
  if [[ ! "$token" =~ ^[A-Za-z0-9_-]{32,128}$ ]]; then
    echo "SPOTIFY_STATS_GATEWAY_TOKEN 必须是 32-128 位 base64url 安全字符。" >&2
    return 1
  fi
  set_env SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED 1
}

ensure_gateway_token

current_tag="$(get_env IMAGE_TAG)"
current_mode="$(get_env DEPLOYMENT_MODE)"
current_image_source="registry"
if [[ -f "$DEPLOY_DIR/.current-image-source" ]]; then
  current_image_source="$(<"$DEPLOY_DIR/.current-image-source")"
fi
if ! valid_image_source "$current_image_source"; then
  echo "当前镜像来源记录无效：$current_image_source" >&2
  exit 1
fi
if ! valid_mode "$current_mode"; then
  # Releases before deployment profiles always started both loopback gateways.
  current_mode="dual"
  set_env DEPLOYMENT_MODE "$current_mode"
  echo "旧部署未记录 DEPLOYMENT_MODE；按原有双网关行为迁移为 dual。"
fi
showcase_access_mode="$(get_env SHOWCASE_ACCESS_MODE)"
if ! valid_showcase_access_mode "$showcase_access_mode"; then
  showcase_access_mode="protected"
  set_env SHOWCASE_ACCESS_MODE "$showcase_access_mode"
  echo "旧部署未记录 SHOWCASE_ACCESS_MODE；安全迁移为 protected。"
fi

target_mode="${MODE_OVERRIDE:-$current_mode}"
if ! valid_mode "$target_mode"; then
  echo "无效部署模式：$target_mode（只能是 full、showcase 或 dual）。" >&2
  exit 2
fi
if [[ -n "$IMAGE_SOURCE_OVERRIDE" ]]; then
  target_image_source="$IMAGE_SOURCE_OVERRIDE"
elif [[ "$current_tag" == "$NEW_TAG" ]]; then
  target_image_source="$current_image_source"
else
  target_image_source="registry"
fi
if ! valid_image_source "$target_image_source"; then
  echo "无效镜像来源：$target_image_source（只能是 registry 或 local）。" >&2
  exit 2
fi
if [[ "$target_mode" == "showcase" || "$target_mode" == "dual" ]]; then
  "$DEPLOY_DIR/showcase-auth.sh" ensure
fi

gateway_port="$(get_env APP_GATEWAY_PORT)"
gateway_port="${gateway_port:-3001}"
public_gateway_port="$(get_env PUBLIC_GATEWAY_PORT)"
public_gateway_port="${public_gateway_port:-3002}"

compose_all() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
    --profile full --profile showcase --profile dual "$@"
}

compose_mode() {
  local mode="$1"
  shift
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile "$mode" "$@"
}

compose_mode_for_tag() {
  local tag="$1"
  local mode="$2"
  shift 2
  IMAGE_TAG="$tag" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
    --profile "$mode" "$@"
}

services_for_mode() {
  case "$1" in
    full) printf '%s\n' backend web ;;
    showcase) printf '%s\n' backend public-web ;;
    dual) printf '%s\n' backend web public-web ;;
  esac
}

activate_mode() {
  local mode="$1"
  local image_source="${2:-registry}"
  local -a services
  mapfile -t services < <(services_for_mode "$mode")

  case "$mode" in
    full)
      compose_all rm -sf public-web >/dev/null 2>&1 || true
      ;;
    showcase)
      compose_all rm -sf web >/dev/null 2>&1 || true
      ;;
  esac

  if [[ "$image_source" == "local" ]]; then
    compose_mode "$mode" up -d --pull never --remove-orphans "${services[@]}"
  else
    compose_mode "$mode" up -d --remove-orphans "${services[@]}"
  fi
}

pull_mode() {
  local mode="$1"
  local -a services
  mapfile -t services < <(services_for_mode "$mode")
  compose_mode "$mode" pull "${services[@]}"
}

pull_mode_for_tag() {
  local tag="$1"
  local mode="$2"
  local -a services
  mapfile -t services < <(services_for_mode "$mode")
  compose_mode_for_tag "$tag" "$mode" pull "${services[@]}"
}

backend_image_for_tag() {
  local tag="$1"
  local registry namespace repository
  registry="$(get_env TCR_REGISTRY)"
  namespace="$(get_env TCR_NAMESPACE)"
  repository="$(get_env API_REPOSITORY)"
  registry="${registry:-ccr.ccs.tencentyun.com}"
  namespace="${namespace:-teacher-honor}"
  repository="${repository:-spotify-stats-api}"
  printf '%s/%s/%s:%s\n' "${registry%/}" "$namespace" "$repository" "$tag"
}

web_image_for_tag() {
  local tag="$1"
  local registry namespace repository
  registry="$(get_env TCR_REGISTRY)"
  namespace="$(get_env TCR_NAMESPACE)"
  repository="$(get_env WEB_REPOSITORY)"
  registry="${registry:-ccr.ccs.tencentyun.com}"
  namespace="${namespace:-teacher-honor}"
  repository="${repository:-spotify-stats-web}"
  printf '%s/%s/%s:%s\n' "${registry%/}" "$namespace" "$repository" "$tag"
}

verify_local_release_image() {
  local image="$1"
  local expected_revision="$2"
  local architecture operating_system revision
  docker image inspect "$image" >/dev/null 2>&1 || {
    echo "本机缺少精确发布镜像：$image" >&2
    return 1
  }
  architecture="$(docker image inspect --format '{{.Architecture}}' "$image")"
  operating_system="$(docker image inspect --format '{{.Os}}' "$image")"
  revision="$(docker image inspect --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}' "$image")"
  if [[ "$operating_system/$architecture" != "linux/amd64" || \
        "$revision" != "$expected_revision" ]]; then
    echo "本机发布镜像身份不正确：$image platform=$operating_system/$architecture revision=$revision" >&2
    return 1
  fi
}

prepare_images_for_tag() {
  local tag="$1"
  local mode="$2"
  local image_source="$3"
  if [[ "$image_source" == "registry" ]]; then
    pull_mode_for_tag "$tag" "$mode"
    return
  fi
  verify_local_release_image "$(backend_image_for_tag "$tag")" "$tag"
  verify_local_release_image "$(web_image_for_tag "$tag")" "$tag"
}

create_offline_backup() {
  local image="$1"
  local output_path="$2"
  if [[ -e "$output_path" ]]; then
    echo "离线备份目标已存在，拒绝覆盖：$output_path" >&2
    return 1
  fi
  install -m 600 /dev/null "$output_path"
  if ! docker run --rm --init --network none \
      --mount "type=bind,src=$DEPLOY_DIR/data,dst=/source,readonly" \
      "$image" python -c '
import sqlite3
import sys
from pathlib import Path
from shutil import copyfile

source_dir = Path("/tmp/offline-source")
source_dir.mkdir()
for name in (
    "spotify_stats.db",
    "spotify_stats.db-wal",
    "spotify_stats.db-shm",
):
    mounted = Path("/source") / name
    if mounted.exists():
        copyfile(mounted, source_dir / name)
source = sqlite3.connect(
    "file:/tmp/offline-source/spotify_stats.db?mode=ro", uri=True, timeout=30
)
target_path = "/tmp/spotify_stats.backup.db"
target = sqlite3.connect(target_path)
with target:
    source.backup(target)
integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
target.close()
source.close()
if integrity != "ok":
    raise SystemExit(f"backup integrity_check failed: {integrity}")
with open(target_path, "rb") as stream:
    while chunk := stream.read(1024 * 1024):
        sys.stdout.buffer.write(chunk)
' > "$output_path"
  then
    rm -f -- "$output_path" "$output_path-journal" \
      "$output_path-wal" "$output_path-shm"
    echo "离线备份容器执行失败；已移除未完成副本。" >&2
    return 1
  fi
  if [[ ! -s "$output_path" ]]; then
    rm -f -- "$output_path" "$output_path-journal" \
      "$output_path-wal" "$output_path-shm"
    echo "离线备份未生成有效数据库文件。" >&2
    return 1
  fi
}

replace_live_database() {
  local source_path="$1"
  install -m 600 "$source_path" "$DEPLOY_DIR/data/spotify_stats.db.release"
  mv -f -- "$DEPLOY_DIR/data/spotify_stats.db.release" \
    "$DEPLOY_DIR/data/spotify_stats.db"
  rm -f -- "$DEPLOY_DIR/data/spotify_stats.db-wal" \
    "$DEPLOY_DIR/data/spotify_stats.db-shm"
}

wait_until_healthy() {
  local port="$1"
  local attempts=48
  while (( attempts > 0 )); do
    if curl --fail --silent --show-error --max-time 5 \
      "http://127.0.0.1:$port/api/health" >/dev/null; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 5
  done
  return 1
}

port_is_loopback_only() {
  local port="$1"
  local matches
  matches="$(ss -lntH | awk -v port=":$port" '$4 ~ port "$" {print $4}')"
  [[ -n "$matches" ]] || return 1
  ! grep -Evq "^(127\.0\.0\.1|\[::1\]):${port}$" <<<"$matches"
}

port_is_closed() {
  local port="$1"
  ! ss -lntH | awk '{print $4}' | grep -Eq ":${port}$"
}

assert_surface() {
  local port="$1"
  local expected="$2"
  local -a auth_args=()
  local response
  if [[ "$expected" == "public-readonly" && "$showcase_access_mode" == "protected" ]]; then
    load_showcase_credentials || return 1
    auth_args=(--user "$showcase_username:$showcase_password")
  fi
  response="$(curl --fail --silent --show-error --max-time 5 \
    "${auth_args[@]}" \
    "http://127.0.0.1:$port/api/runtime/capabilities")" || return 1
  if [[ "$response" != *"\"surface\":\"$expected\""* ]]; then
    echo "端口 $port 的运行面不是 $expected。" >&2
    return 1
  fi
}

load_showcase_credentials() {
  local credentials_file="$DEPLOY_DIR/secrets/showcase.credentials"
  if [[ ! -f "$credentials_file" ]]; then
    echo "缺少展示入口凭据：$credentials_file" >&2
    return 1
  fi
  showcase_username="$(sed -n 's/^SHOWCASE_USERNAME=//p' "$credentials_file" | tail -n 1)"
  showcase_password="$(sed -n 's/^SHOWCASE_PASSWORD=//p' "$credentials_file" | tail -n 1)"
  [[ -n "$showcase_username" && -n "$showcase_password" ]]
}

verify_private_gateway() {
  wait_until_healthy "$gateway_port" || return 1
  if ! port_is_loopback_only "$gateway_port"; then
    echo "完全版网关未严格绑定 loopback 端口 $gateway_port。" >&2
    return 1
  fi
  assert_surface "$gateway_port" private-admin
}

verify_showcase_gateway() {
  wait_until_healthy "$public_gateway_port" || return 1
  if ! port_is_loopback_only "$public_gateway_port"; then
    echo "简化版网关未严格绑定 loopback 端口 $public_gateway_port。" >&2
    return 1
  fi
  assert_surface "$public_gateway_port" public-readonly || return 1

  local unauthenticated_status expected_status
  unauthenticated_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "http://127.0.0.1:$public_gateway_port/api/runtime/capabilities")"
  if [[ "$showcase_access_mode" == "protected" ]]; then
    expected_status="401"
  else
    expected_status="200"
  fi
  if [[ "$unauthenticated_status" != "$expected_status" ]]; then
    echo "简化版 $showcase_access_mode 请求返回 HTTP $unauthenticated_status，预期 $expected_status。" >&2
    return 1
  fi

  local write_status
  local -a auth_args=()
  if [[ "$showcase_access_mode" == "protected" ]]; then
    load_showcase_credentials || return 1
    auth_args=(--user "$showcase_username:$showcase_password")
  fi
  write_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "${auth_args[@]}" \
    --max-time 5 -X PUT "http://127.0.0.1:$public_gateway_port/api/settings" \
    -H 'Content-Type: application/json' -d '{}')"
  if [[ "$write_status" != "403" ]]; then
    echo "简化版写操作返回 HTTP $write_status，预期 403。" >&2
    return 1
  fi
}

release_is_safe() {
  local mode="$1"
  local require_search_gate="${2:-1}"

  compose_mode "$mode" exec -T backend python - <<'PY'
import sqlite3

conn = sqlite3.connect("/app/data/spotify_stats.db")
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"database integrity_check failed: {result}")
PY

  if [[ "$require_search_gate" == "1" ]]; then
    compose_mode "$mode" exec -T backend python - \
      < "$DEPLOY_DIR/verify-music-search-runtime.py"
  fi

  case "$mode" in
    full)
      verify_private_gateway || return 1
      port_is_closed "$public_gateway_port" || {
        echo "full 模式仍监听简化版端口 $public_gateway_port。" >&2
        return 1
      }
      ;;
    showcase)
      verify_showcase_gateway || return 1
      port_is_closed "$gateway_port" || {
        echo "showcase 模式仍监听完全版端口 $gateway_port。" >&2
        return 1
      }
      ;;
    dual)
      verify_private_gateway || return 1
      verify_showcase_gateway || return 1
      ;;
  esac
}

restore_previous_release() {
  compose_all stop backend >/dev/null 2>&1 || true
  if [[ "$database_promoted" == "true" && -n "$release_backup_path" && \
        -f "$release_backup_path" ]]; then
    echo "正在恢复发布前 SQLite 备份：$release_backup_path" >&2
    replace_live_database "$release_backup_path" || return 1
  fi
  if [[ ! "$current_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
    echo "没有合法的上一镜像 SHA，无法自动回滚。" >&2
    return 1
  fi
  echo "正在恢复镜像 $current_tag 和部署模式 $current_mode。" >&2
  set_env IMAGE_TAG "$current_tag"
  set_env DEPLOYMENT_MODE "$current_mode"
  prepare_images_for_tag "$current_tag" "$current_mode" "$rollback_image_source" && \
    activate_mode "$current_mode" "$rollback_image_source" && \
    release_is_safe "$current_mode" 0
}

backend_was_running="false"
if compose_all ps --status running --services 2>/dev/null | grep -qx backend; then
  backend_was_running="true"
fi

release_backup_path=""
database_promoted="false"
release_stage_dir=""
cleanup_release_stage() {
  if [[ -n "$release_stage_dir" && -d "$release_stage_dir" ]]; then
    rm -rf -- "$release_stage_dir"
  fi
}
trap cleanup_release_stage EXIT

if ! prepare_images_for_tag "$NEW_TAG" "$target_mode" "$target_image_source"; then
  echo "目标镜像准备失败（source=$target_image_source），生产容器和数据库均未切换。" >&2
  exit 1
fi

rollback_image_source="$current_image_source"
if [[ "$target_image_source" == "local" && "$current_tag" =~ ^[0-9a-f]{7,64}$ ]]; then
  if ! prepare_images_for_tag "$current_tag" "$current_mode" local; then
    echo "local 发布前无法验证当前版本的本机回滚镜像，拒绝进入备份或停服阶段。" >&2
    exit 1
  fi
  rollback_image_source="local"
fi

if [[ "$current_tag" != "$NEW_TAG" ]]; then
  mkdir -p "$DEPLOY_DIR/backups"
  chmod 700 "$DEPLOY_DIR/backups"
  release_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  release_backup_name="spotify-stats-pre-release-${NEW_TAG:0:12}-${release_stamp}.db"
  release_backup_path="$DEPLOY_DIR/backups/$release_backup_name"
  target_backend_image="$(backend_image_for_tag "$NEW_TAG")"

  if [[ "$backend_was_running" == "true" ]]; then
    SPOTIFY_STATS_BACKUP_NAME="$release_backup_name" "$DEPLOY_DIR/backup.sh"
  else
    if [[ ! -f "$DEPLOY_DIR/data/spotify_stats.db" ]]; then
      echo "缺少 $DEPLOY_DIR/data/spotify_stats.db，无法执行数据库预检。" >&2
      exit 1
    fi
    create_offline_backup "$target_backend_image" "$release_backup_path"
  fi

  release_stage_dir="$(mktemp -d "$DEPLOY_DIR/backups/.release-stage.XXXXXX")"
  staged_database="$release_stage_dir/spotify_stats.db"
  cp -- "$release_backup_path" "$staged_database"
  preflight_report="$DEPLOY_DIR/backups/music-search-preflight-${NEW_TAG:0:12}-${release_stamp}.json"
  search_resume_database="$DEPLOY_DIR/backups/music-search-resume.db"
  # Normal releases run with --statistics-reuse-only and fail before any
  # candidate/statistics rebuild if the four exact L2/L3 snapshots cannot be reused.
  # Keep their candidate-only capacity budget independent from the larger
  # one-time statistics bootstrap budget.
  search_preflight_min_mib="$(get_env SEARCH_PREFLIGHT_REUSE_MIN_AVAILABLE_MIB)"
  search_preflight_min_mib="${search_preflight_min_mib:-640}"
  if ! SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB="$search_preflight_min_mib" \
      "$DEPLOY_DIR/preflight-music-search.sh" \
      --db-copy "$staged_database" \
      --resume-db "$search_resume_database" \
      --json-report "$preflight_report" \
      --image "$target_backend_image"; then
    echo "目标镜像的音乐搜索数据库副本预检失败；线上服务和数据库保持原状。" >&2
    exit 1
  fi

  if [[ "$backend_was_running" == "true" ]]; then
    compose_all stop backend
    quiescent_database="$release_stage_dir/quiescent-source.db"
    if ! create_offline_backup "$target_backend_image" "$quiescent_database"; then
      activate_mode "$current_mode" "$rollback_image_source" || true
      echo "停服后的源数据库复核备份失败；没有替换生产数据库。" >&2
      exit 1
    fi
    if cmp -s -- "$release_backup_path" "$quiescent_database"; then
      :
    else
      compare_status="$?"
      if [[ "$compare_status" -ne 1 ]]; then
        activate_mode "$current_mode" "$rollback_image_source" || true
        echo "停服后的源数据库副本无法比较；没有替换生产数据库。" >&2
        exit 1
      fi
      rebase_report="$DEPLOY_DIR/backups/music-search-rebase-${NEW_TAG:0:12}-${release_stamp}.json"
      if ! docker run --rm --init \
          --mount "type=bind,src=$release_backup_path,dst=/baseline.db,readonly" \
          --mount "type=bind,src=$quiescent_database,dst=/quiescent.db" \
          --mount "type=bind,src=$staged_database,dst=/staged.db" \
          --mount "type=bind,src=$DEPLOY_DIR/backups,dst=/reports" \
          "$target_backend_image" \
          python scripts/rebase_music_search_preflight.py \
            --baseline-db /baseline.db \
            --quiescent-db /quiescent.db \
            --staged-db /staged.db \
            --json-output "/reports/$(basename -- "$rebase_report")"; then
        activate_mode "$current_mode" "$rollback_image_source" || true
        echo "预检期间搜索源发生变化或派生表重基失败；没有替换生产数据库。" >&2
        exit 1
      fi
      staged_database="$quiescent_database"
      echo "生产数据库仅发生非搜索写入；已保留最新备份并移植验证过的搜索派生表。"
    fi
  fi

  if ! replace_live_database "$staged_database"; then
    if [[ "$backend_was_running" == "true" ]]; then
      activate_mode "$current_mode" "$rollback_image_source" || true
    fi
    echo "预检副本未能原子发布，生产镜像保持原版本。" >&2
    exit 1
  fi
  database_promoted="true"
fi

set_env IMAGE_TAG "$NEW_TAG"
set_env DEPLOYMENT_MODE "$target_mode"

if ! activate_mode "$target_mode" "$target_image_source" || ! release_is_safe "$target_mode"; then
  echo "新版本或部署模式验收失败：$NEW_TAG / $target_mode" >&2
  compose_all logs --tail 160 >&2 || true
  if ! restore_previous_release; then
    echo "自动恢复未通过，需要人工检查。" >&2
  fi
  exit 1
fi

if [[ "$current_tag" =~ ^[0-9a-f]{7,64}$ && \
      ( "$current_tag" != "$NEW_TAG" || "$current_mode" != "$target_mode" || \
        "$current_image_source" != "$target_image_source" ) ]]; then
  printf '%s\n' "$current_tag" > .previous-image-tag
  printf '%s\n' "$current_mode" > .previous-deployment-mode
  printf '%s\n' "$rollback_image_source" > .previous-image-source
fi
printf '%s\n' "$NEW_TAG" > .current-image-tag
printf '%s\n' "$target_mode" > .current-deployment-mode
printf '%s\n' "$target_image_source" > .current-image-source

echo "部署完成：$NEW_TAG（模式：$target_mode，镜像来源：$target_image_source，简化版访问：$showcase_access_mode）"
echo "外部 HTTPS 入口未被修改；如需对外访问，请单独配置受控入口。"
