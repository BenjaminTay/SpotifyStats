# SpotifyStats 个人云双入口部署

本目录用于单用户长期运行，同一份应用和数据通过两个彼此隔离的入口提供：

- `https://<node>.<tailnet>.ts.net`：Tailscale Serve → `127.0.0.1:3001`，仅私人 tailnet 可达，保留设置、导入、编辑、AI 与 Spotify OAuth。
- `https://<node>.<tailnet>.ts.net:8443`：Tailscale Funnel → `127.0.0.1:3002`，互联网可达，只展示已批准的本地统计能力。

FastAPI 只存在于 Docker 私网。两个宿主端口也只监听 loopback，因此不能通过伪造请求头绕过公开网关。公开 Nginx 与后端共同执行只读边界；前端的“公开展示”标识和入口隐藏只用于呈现，不作为授权依据。

## 首次部署

1. 在服务器创建 `/opt/spotify-stats/{data,backups}`，目录权限设为 `700`。
2. 将本目录文件放到 `/opt/spotify-stats/`，复制 `.env.example` 为 `.env`，
   设置私人 `APP_PUBLIC_URL`、公开 `PUBLIC_SHOWCASE_URL` 和独立的
   `SPOTIFY_STATS_TOKEN_KEY`。
3. 使用 SQLite backup API 生成一致性 `spotify_stats.db`，再把数据库、`covers/`、
   `account/`、`streaming/` 和 seed JSON 传入 `/opt/spotify-stats/data/`。
4. 运行 `./deploy.sh <commit-sha>`。
5. 安装并登录 Tailscale，在 tailnet 中启用 MagicDNS 与 HTTPS，再运行
   `./configure-tailscale.sh` 建立私人入口。管理设备必须登录同一 tailnet。
6. 先执行 `./verify.sh`，确认 3001 私人入口与 3002 公共只读网关均健康，
   公共能力发现为 `public-readonly`，写操作返回 403。
7. 运行 `./configure-public-funnel.sh`，只把 8443 映射到 3002；按 Tailscale
   提示在管理页批准 Funnel 后，朋友无需安装 Tailscale 即可访问
   `PUBLIC_SHOWCASE_URL`。
8. 运行 `./install-backup-timer.sh` 安装每日 SQLite 在线备份，并从私人入口
   与公网入口分别完成一次真机验收。

## 安全边界

- `.dockerignore` 排除整个 `data/`；镜像仓库中不得存在 SQLite、封面或 Spotify 导出。
- 两个 Web 网关都只监听 loopback，Backend 只在 Docker 私网可达；3000、3001、
  3002 和 8000 都不得在云防火墙或宿主防火墙中直接开放。
- `SPOTIFY_STATS_REQUIRE_AUTH` 在该模式下关闭，因为它只保护部分写端点；整站边界由
  私人入口的 Tailscale 身份与公共入口的后端访问面策略分别提供。
- 私人 Nginx 强制写入 `private-admin`，公开 Nginx 强制写入 `public-readonly`。
  公共面禁用设置、编辑、导入、AI、Spotify OAuth、歌词、元数据治理、后台任务、
  搜索历史和所有非白名单写操作；仅保留查询和几个无副作用的结构化对决 POST。
- 公共设置响应会移除 Spotify 与 LLM 连接信息；公共年度总结只读精确缓存；公共封面
  只使用已有文件或已知 CDN 地址，不触发 Spotify 搜索、写库或后台下载。
- `X-Robots-Tag: noindex` 只用于降低搜索引擎收录概率，不是访问控制。公开链接可被
  转发，任何持有者都能查看其中的数据。
- 需要停止分享时运行 `sudo tailscale funnel reset`；私人 Serve 仍可继续使用。
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
- 若回滚目标早于公共只读能力，脚本会关闭 Funnel 并以私人入口模式恢复，避免旧后端
  被公开网关继续暴露；升级到兼容版本后再重新执行 `configure-public-funnel.sh`。

## 日常验证

```bash
./verify.sh
curl -sS "$PUBLIC_SHOWCASE_URL/api/runtime/capabilities"
curl -o /dev/null -w '%{http_code}\n' -X PUT \
  "$PUBLIC_SHOWCASE_URL/api/settings" \
  -H 'Content-Type: application/json' -d '{}'
```

预期能力响应的 `surface` 为 `public-readonly`，写操作状态码为 403。公开入口异常时，
先关闭 Funnel，再通过 3002 loopback 检查网关；不要把 Backend 或私人 3001 临时暴露到公网。
