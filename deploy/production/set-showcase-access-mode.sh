#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
target_mode="${1:-}"

usage() {
  cat >&2 <<'EOF'
用法：set-showcase-access-mode.sh protected|public

protected  朋友访问需要 HTTP Basic Auth 用户名和密码
public     打开简化版链接即可访问，不要求用户凭据

只修改 public-readonly 简化版入口；完全版、后端白名单和 SQLite 只读防线不变。
EOF
}

if [[ "$target_mode" != "protected" && "$target_mode" != "public" ]]; then
  usage
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE。" >&2
  exit 1
fi

get_env() {
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
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

deployment_mode="$(get_env DEPLOYMENT_MODE)"
if [[ "$deployment_mode" != "full" && "$deployment_mode" != "showcase" && \
      "$deployment_mode" != "dual" ]]; then
  echo "DEPLOYMENT_MODE 无效：$deployment_mode" >&2
  exit 1
fi

previous_mode="$(get_env SHOWCASE_ACCESS_MODE)"
if [[ "$previous_mode" != "protected" && "$previous_mode" != "public" ]]; then
  previous_mode="protected"
  set_env SHOWCASE_ACCESS_MODE "$previous_mode"
fi
if [[ "$previous_mode" == "$target_mode" ]]; then
  echo "简化版访问模式已经是 $target_mode。"
  exit 0
fi

set_env SHOWCASE_ACCESS_MODE "$target_mode"
if [[ "$deployment_mode" == "full" ]]; then
  echo "已记录简化版访问模式：$target_mode；当前 full 模式未运行简化版。"
  exit 0
fi

"$DEPLOY_DIR/showcase-auth.sh" ensure
compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile "$deployment_mode")

if "${compose[@]}" up -d --no-deps --force-recreate public-web && \
   "$DEPLOY_DIR/verify.sh"; then
  echo "简化版访问模式已切换为：$target_mode"
  exit 0
fi

echo "访问模式验收失败，正在恢复：$previous_mode" >&2
set_env SHOWCASE_ACCESS_MODE "$previous_mode"
"${compose[@]}" up -d --no-deps --force-recreate public-web
"$DEPLOY_DIR/verify.sh"
exit 1
