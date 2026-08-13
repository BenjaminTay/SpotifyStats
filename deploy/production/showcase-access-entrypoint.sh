#!/usr/bin/env sh
set -eu

mode="${SHOWCASE_ACCESS_MODE:-protected}"
output="${SHOWCASE_ACCESS_CONFIG_PATH:-/etc/nginx/includes/showcase-access.conf}"

case "$mode" in
  protected)
    auth_lines='auth_basic "SpotifyStats Showcase";
auth_basic_user_file /etc/nginx/auth/showcase.htpasswd;'
    ;;
  public)
    auth_lines='auth_basic off;'
    ;;
  *)
    echo "SHOWCASE_ACCESS_MODE 只能是 protected 或 public，当前为：$mode" >&2
    exit 1
    ;;
esac

output_dir="$(dirname -- "$output")"
mkdir -p "$output_dir"
tmp="$(mktemp "$output_dir/.showcase-access.XXXXXX")"
trap 'rm -f "$tmp"' EXIT HUP INT TERM
printf '%s\n' "$auth_lines" > "$tmp"
chmod 644 "$tmp"
mv -f "$tmp" "$output"
trap - EXIT HUP INT TERM
