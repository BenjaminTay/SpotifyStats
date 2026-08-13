# SpotifyStats 个人云部署

本目录用于单用户长期运行：Docker Compose 只把 Web 入口绑定到服务器
`127.0.0.1:3001`，FastAPI 不映射宿主机端口；Tailscale Serve 在私人 tailnet
内提供 HTTPS。不得使用 Tailscale Funnel，也不得把 3000/8000/3001 开放到公网。

## 首次部署

1. 在服务器创建 `/opt/spotify-stats/{data,backups}`，目录权限设为 `700`。
2. 将本目录文件放到 `/opt/spotify-stats/`，复制 `.env.example` 为 `.env`，
   设置 `APP_PUBLIC_URL` 和独立的 `SPOTIFY_STATS_TOKEN_KEY`。
3. 使用 SQLite backup API 生成一致性 `spotify_stats.db`，再把数据库、`covers/`、
   `account/`、`streaming/` 和 seed JSON 传入 `/opt/spotify-stats/data/`。
4. 运行 `./deploy.sh <commit-sha>`。
5. 安装并登录 Tailscale，在 tailnet 中启用 MagicDNS 与 HTTPS，再运行
   `./configure-tailscale.sh`。手机也必须登录同一 tailnet。
6. 运行 `./install-backup-timer.sh` 安装每日 SQLite 在线备份。
7. 执行 `./verify.sh`，再从手机访问 `APP_PUBLIC_URL` 并添加到主屏幕。

## 安全边界

- `.dockerignore` 排除整个 `data/`；镜像仓库中不得存在 SQLite、封面或 Spotify 导出。
- Web 只监听 loopback，Backend 只在 Docker 私网可达；私人访问由 tailnet 身份控制。
- `SPOTIFY_STATS_REQUIRE_AUTH` 在该模式下关闭，因为它只保护部分写端点；整站边界由
  Tailscale 提供。若未来改成公网域名，必须先新增真正的整站认证层。
- `tailscale serve` 是私网入口；不要启用 `tailscale funnel`。
- `*.ts.net` 证书名称会进入 Certificate Transparency 日志，机器名不要包含隐私信息。

## 备份与恢复

- `./backup.sh` 使用 SQLite Online Backup API，并对备份执行 `integrity_check`。
- `.env` 的 `BACKUP_RETENTION_DAYS` 控制服务器本地保留天数。
- `spotify-stats-backup.timer` 每天执行一次在线备份，错过计划时间后会补跑。
- 服务器内备份不能替代异机备份；应定期把 `/opt/spotify-stats/backups/` 加密同步到
  另一处存储。
- 恢复命令为 `./restore.sh backups/<file>.db --confirm`。脚本会先备份当前数据库、
  停止 Backend、替换数据库并重新执行健康检查。

## 发布与回滚

- GitHub Actions 使用 commit SHA 构建不可变 API/Web 镜像，再通过 SSH 执行
  `deploy.sh`。
- 发布前自动在线备份；新版本健康检查失败时自动回到上一 SHA。
- 手动回滚使用 `./rollback.sh`，也可显式提供目标 SHA。
