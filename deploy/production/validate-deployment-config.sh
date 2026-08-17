#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$DEPLOY_DIR/../.." && pwd)"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
ENV_TEMPLATE="$DEPLOY_DIR/.env.example"
validation_scope="all"
requested_mode="${1:-all}"

case "${1:-}" in
  --common-only)
    validation_scope="common"
    requested_mode="all"
    ;;
  --profile-only)
    validation_scope="profile"
    requested_mode="${2:-}"
    ;;
esac

usage() {
  echo "用法：$0 [full|showcase|dual|all] | --common-only | --profile-only <full|showcase|dual>" >&2
}

if [[ "$validation_scope" != "common" && "$requested_mode" != "all" && "$requested_mode" != "full" && \
      "$requested_mode" != "showcase" && "$requested_mode" != "dual" ]]; then
  usage
  exit 2
fi

if [[ "$validation_scope" != "profile" ]]; then
  for script in "$DEPLOY_DIR"/*.sh; do
    bash -n "$script"
  done

grep -q 'python scripts/validate_container_image.py /app' "$PROJECT_ROOT/Dockerfile"
for pattern in '**/*.db' '**/*.db-wal' '**/*.db-shm' '**/*.db-journal' \
               '**/*.sqlite' '**/*.sqlite-wal' '**/*.sqlite-shm' \
               '**/*.sqlite-journal' '**/*.sqlite.pre-*' '**/*.sqlite3' \
               '**/*.sqlite3-wal' '**/*.sqlite3-shm' '**/*.sqlite3-journal' \
               '**/*.sqlite3.pre-*'; do
  grep -Fxq "$pattern" "$PROJECT_ROOT/.dockerignore"
done

grep -q 'include /etc/nginx/includes/showcase-access.conf' \
  "$DEPLOY_DIR/public-nginx.conf.template"
grep -q 'location = /api/health' "$DEPLOY_DIR/public-nginx.conf.template"
grep -q 'auth_basic off' "$DEPLOY_DIR/public-nginx.conf.template"
grep -q 'add_header Cache-Control "private, max-age=604800' \
  "$DEPLOY_DIR/public-nginx.conf.template"
grep -q './secrets/showcase.htpasswd:/etc/nginx/auth/showcase.htpasswd:ro' \
  "$COMPOSE_FILE"
grep -q './showcase-access-entrypoint.sh:/docker-entrypoint.d/15-showcase-access.sh:ro' \
  "$COMPOSE_FILE"
grep -q 'SPOTIFY_STATS_SEARCH_STARTUP_REBUILD: ${SPOTIFY_STATS_SEARCH_STARTUP_REBUILD:-1}' \
  "$COMPOSE_FILE"
grep -q '^SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=1$' "$ENV_TEMPLATE"
grep -q '^SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB=1280$' "$ENV_TEMPLATE"
grep -q '^SEARCH_PREFLIGHT_REUSE_MIN_AVAILABLE_MIB=640$' "$ENV_TEMPLATE"
grep -q -- '--require-all-ready' "$DEPLOY_DIR/preflight-music-search.sh"
grep -q -- '--statistics-reuse-only' "$DEPLOY_DIR/preflight-music-search.sh"
grep -q 'SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0' \
  "$DEPLOY_DIR/preflight-music-search.sh"
grep -q 'context_orphan_count' "$DEPLOY_DIR/validate-music-search-preflight.py"
grep -q 'required_disk_bytes' "$DEPLOY_DIR/music_search_preflight_capacity.py"
grep -q 'verify-music-search-runtime.py' "$DEPLOY_DIR/verify.sh"
grep -q 'preflight-music-search.sh' "$DEPLOY_DIR/deploy.sh"
grep -q 'Online Backup' "$DEPLOY_DIR/bootstrap-music-search-statistics.sh"
grep -q -- '--statistics-reuse-only' "$DEPLOY_DIR/preflight-music-search.sh"
if grep -q -- '--statistics-reuse-only' \
  "$DEPLOY_DIR/bootstrap-music-search-statistics.sh"; then
  echo "一次性搜索 bootstrap 不得启用 statistics-reuse-only。" >&2
  exit 1
fi

access_config="$(mktemp)"
trap 'rm -f "$access_config"' EXIT
SHOWCASE_ACCESS_MODE=protected SHOWCASE_ACCESS_CONFIG_PATH="$access_config" \
  sh "$DEPLOY_DIR/showcase-access-entrypoint.sh"
grep -q 'auth_basic "SpotifyStats Showcase"' "$access_config"
SHOWCASE_ACCESS_MODE=public SHOWCASE_ACCESS_CONFIG_PATH="$access_config" \
  sh "$DEPLOY_DIR/showcase-access-entrypoint.sh"
grep -q '^auth_basic off;' "$access_config"
if SHOWCASE_ACCESS_MODE=invalid SHOWCASE_ACCESS_CONFIG_PATH="$access_config" \
     sh "$DEPLOY_DIR/showcase-access-entrypoint.sh" >/dev/null 2>&1; then
  echo "非法 SHOWCASE_ACCESS_MODE 未能 fail closed。" >&2
  exit 1
fi

  for template in "$DEPLOY_DIR/private-nginx.conf.template" \
                  "$DEPLOY_DIR/public-nginx.conf.template"; do
    grep -q 'X-SpotifyStats-Gateway-Token "${SPOTIFY_STATS_GATEWAY_TOKEN}"' "$template"
    if grep -Eq 'replace-with|example-tailnet' "$template"; then
      echo "网关模板包含占位密钥或环境地址：$template" >&2
      exit 1
    fi
  done
fi

if [[ "$validation_scope" == "common" ]]; then
  echo "部署公共配置验证通过：common"
  exit 0
fi

validate_mode() {
  local mode="$1"
  local expected="$2"
  local services rendered

  services="$(
    IMAGE_TAG=0123456789abcdef \
    APP_PUBLIC_URL=https://private.invalid \
    SPOTIFY_STATS_TOKEN_KEY=0123456789abcdef0123456789abcdef \
    SPOTIFY_STATS_GATEWAY_TOKEN=0123456789abcdef0123456789abcdef \
      docker compose --env-file "$ENV_TEMPLATE" -f "$COMPOSE_FILE" \
        --profile "$mode" config --services | sort | paste -sd ' ' -
  )"
  if [[ "$services" != "$expected" ]]; then
    echo "$mode 服务矩阵错误：得到 [$services]，预期 [$expected]。" >&2
    return 1
  fi

  rendered="$(
    IMAGE_TAG=0123456789abcdef \
    APP_PUBLIC_URL=https://private.invalid \
    SPOTIFY_STATS_TOKEN_KEY=0123456789abcdef0123456789abcdef \
    SPOTIFY_STATS_GATEWAY_TOKEN=0123456789abcdef0123456789abcdef \
      docker compose --env-file "$ENV_TEMPLATE" -f "$COMPOSE_FILE" \
        --profile "$mode" config
  )"
  grep -q 'SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED: "1"' <<<"$rendered"
  grep -q 'SPOTIFY_STATS_RELEASE_SHA: 0123456789abcdef' <<<"$rendered"
  grep -q 'SPOTIFY_STATS_SEARCH_STARTUP_REBUILD: "1"' <<<"$rendered"
  if [[ "$mode" == "showcase" || "$mode" == "dual" ]]; then
    grep -q 'SHOWCASE_ACCESS_MODE: protected' <<<"$rendered"
  fi
  if grep -Eq '0\.0\.0\.0:(3000|3001|3002|8000)|published: "8000"' <<<"$rendered"; then
    echo "$mode 渲染配置暴露了禁止的宿主端口。" >&2
    return 1
  fi
}

if [[ "$requested_mode" == "all" || "$requested_mode" == "full" ]]; then
  validate_mode full "backend web"
fi
if [[ "$requested_mode" == "all" || "$requested_mode" == "showcase" ]]; then
  validate_mode showcase "backend public-web"
fi
if [[ "$requested_mode" == "all" || "$requested_mode" == "dual" ]]; then
  validate_mode dual "backend public-web web"
fi

echo "部署配置验证通过：$requested_mode"
