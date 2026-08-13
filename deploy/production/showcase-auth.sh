#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="$DEPLOY_DIR/secrets"
CREDENTIALS_FILE="$SECRETS_DIR/showcase.credentials"
HTPASSWD_FILE="$SECRETS_DIR/showcase.htpasswd"
action="${1:-ensure}"
username="${2:-viewer}"

usage() {
  cat >&2 <<'EOF'
用法：showcase-auth.sh ensure|rotate [username]|show

ensure             缺失时生成展示入口凭据，不输出明文
rotate [username]  生成新密码并替换现有凭据，不输出明文
show               明确打印当前用户名和密码

凭据只保存在服务器 secrets/ 目录；htpasswd 哈希会只读挂载到展示网关。
EOF
}

if [[ "$action" != "ensure" && "$action" != "rotate" && "$action" != "show" ]]; then
  usage
  exit 2
fi
if [[ ! "$username" =~ ^[A-Za-z0-9_.-]{1,32}$ ]]; then
  echo "用户名只能包含 1-32 位字母、数字、点、下划线或连字符。" >&2
  exit 2
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "缺少 openssl，无法生成展示入口凭据。" >&2
  exit 1
fi

umask 077
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

read_credential() {
  local key="$1"
  sed -n "s/^${key}=//p" "$CREDENTIALS_FILE" | tail -n 1
}

write_credentials() {
  local target_username="$1"
  local password="$2"
  local password_hash credentials_tmp htpasswd_tmp

  password_hash="$(printf '%s\n' "$password" | openssl passwd -apr1 -stdin)"
  credentials_tmp="$(mktemp "$SECRETS_DIR/.showcase.credentials.XXXXXX")"
  htpasswd_tmp="$(mktemp "$SECRETS_DIR/.showcase.htpasswd.XXXXXX")"
  printf 'SHOWCASE_USERNAME=%s\nSHOWCASE_PASSWORD=%s\n' \
    "$target_username" "$password" > "$credentials_tmp"
  printf '%s:%s\n' "$target_username" "$password_hash" > "$htpasswd_tmp"
  chmod 600 "$credentials_tmp"
  # Docker resolves the bind mount as root, while the Nginx worker reads the
  # mounted file as an unprivileged user. The parent host directory stays 700.
  chmod 644 "$htpasswd_tmp"
  mv -f "$credentials_tmp" "$CREDENTIALS_FILE"
  mv -f "$htpasswd_tmp" "$HTPASSWD_FILE"
}

case "$action" in
  ensure)
    if [[ -f "$CREDENTIALS_FILE" && -f "$HTPASSWD_FILE" ]]; then
      exit 0
    fi
    if [[ -f "$CREDENTIALS_FILE" ]]; then
      existing_username="$(read_credential SHOWCASE_USERNAME)"
      existing_password="$(read_credential SHOWCASE_PASSWORD)"
      if [[ -n "$existing_username" && -n "$existing_password" ]]; then
        write_credentials "$existing_username" "$existing_password"
        exit 0
      fi
    fi
    password="$(openssl rand -hex 16)"
    if [[ ${#password} -lt 20 ]]; then
      echo "随机密码生成失败。" >&2
      exit 1
    fi
    write_credentials "$username" "$password"
    echo "已生成展示入口凭据；请在服务器运行 ./showcase-auth.sh show 查看。"
    ;;
  rotate)
    password="$(openssl rand -hex 16)"
    if [[ ${#password} -lt 20 ]]; then
      echo "随机密码生成失败。" >&2
      exit 1
    fi
    write_credentials "$username" "$password"
    echo "展示入口凭据已轮换；请重启 public-web 后运行 ./showcase-auth.sh show 查看。"
    ;;
  show)
    if [[ ! -f "$CREDENTIALS_FILE" || ! -f "$HTPASSWD_FILE" ]]; then
      echo "展示入口凭据尚未生成。" >&2
      exit 1
    fi
    printf '用户名：%s\n密码：%s\n' \
      "$(read_credential SHOWCASE_USERNAME)" \
      "$(read_credential SHOWCASE_PASSWORD)"
    ;;
esac
