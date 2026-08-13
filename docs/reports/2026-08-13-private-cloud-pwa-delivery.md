# 个人私有云与 PWA Phase B 交付报告

> 日期：2026-08-13
>
> 发布提交：`df7dc68b224afb30673586dd7e1d3f130c50fe1a`
>
> GitHub Actions：`Deploy private production` run `31685472071`

## 1. 结论

个人私有云生产基线已经部署到既有腾讯云 Ubuntu 服务器，与教师项目隔离运行。SpotifyStats Backend 不映射宿主机端口，Web 只绑定 `127.0.0.1:3001`；服务器公网 80 继续由教师项目占用。个人 SQLite、封面和原始导出位于 `/opt/spotify-stats/data/`，不进入 Git、Docker 构建上下文或镜像仓库。

代码验证、SHA 镜像发布、SSH 部署、容器健康、SQLite 完整性、真实数据计数、PWA 静态文件和首份在线备份均已通过。Tailscale 节点已加入私人 tailnet；私网 HTTPS Serve 的 tailnet 开关和手机实体设备安装仍需要账号侧最终确认，因此不能把物理手机验收写成已完成。

## 2. 生产结构

| 层级 | 生产结果 |
| --- | --- |
| 发布 | `main` push 后验证、构建 API/Web SHA 镜像、上传 TCR、SSH 执行发布脚本 |
| Backend | 只存在于 Docker `application` 私网，宿主机不开放 8000 |
| Web | 仅 `127.0.0.1:3001 -> container:3000` |
| 私网入口 | `https://spotify-stats.tail8916b1.ts.net`，由 Tailscale Serve 终止 HTTPS |
| 数据 | `/opt/spotify-stats/data/` 宿主持久化挂载 |
| 备份 | `/opt/spotify-stats/backups/`，SQLite Online Backup + `integrity_check` |
| 回滚 | 当前/上一 commit SHA 记录、健康检查失败自动恢复上一 SHA |

明确禁止 Tailscale Funnel，也不开放 3000、3001 或 8000 公网端口。当前整站访问身份边界由私人 tailnet 提供；项目内置 `SPOTIFY_STATS_REQUIRE_AUTH` 只保护部分写端点，不能当作整站认证。

## 3. 数据迁移与密钥边界

- 迁移前使用 SQLite Online Backup API 生成一致性生产快照。
- 生产快照删除 `spotify_user_token`、LLM API key 和 LLM profile 密钥；本地数据库未被修改。
- 服务器生产环境使用新生成的独立 `SPOTIFY_STATS_TOKEN_KEY`，环境文件权限为 `600`。
- Spotify Client ID/Secret 与 Genius token 只写入服务器 `.env`，没有进入提交差异或 Actions artifact。
- `.dockerignore` 排除整个 `data/`、`backups/`、数据库、环境文件和缓存目录；Backend 镜像不再执行 `COPY data/`。

## 4. 自动发布证据

首次 `Deploy private production` run `31685472071`：

- `verify`：3 分 31 秒，Backend unit/contract、Ruff、Frontend test/build 和私人部署契约通过。
- `build`：50 分 54 秒，首次冷构建并发布两个 `linux/amd64` SHA 镜像；主要耗时为重依赖镜像首次构建和跨区上传，后续由 GitHub BuildKit cache 复用。
- `deploy`：44 秒，SSH 文件同步、TCR 登录、镜像拉取、Compose 启动、健康检查、loopback 监听约束和数据库完整性检查通过。
- 同一 SHA 的既有 `Phase 5 Baseline` run `31685471998` 也成功结束。

## 5. 服务器独立验收

| 检查项 | 结果 |
| --- | --- |
| API/Web 容器 | 两个容器均为 `healthy` |
| 运行镜像 | API/Web 均为完整 `df7dc68b...` SHA tag |
| 健康接口 | `http://127.0.0.1:3001/api/health` 返回 `{"status":"ok"}` |
| 宿主机监听 | SpotifyStats 只有 `127.0.0.1:3001`；无公网 3000/3001/8000 |
| SQLite | `PRAGMA integrity_check = ok` |
| 真实播放数 | `91,286` |
| 生产 Spotify token | `0` 条，需要从生产 HTTPS 入口重新连接 |
| 封面文件 | `3,552` |
| PWA 文件 | 首页、`manifest.webmanifest`、`sw.js` 均返回 200 |
| 既有教师项目 | Web/API 继续健康，公网首页返回 200 |

首次服务器在线备份为 `spotify-stats-20260813T100842Z.db`，大小 84,500,480 字节，`integrity_check=ok`，包含 91,286 条播放。`spotify-stats-backup.timer` 已启用，每日 03:20 后随机延迟最多 20 分钟执行，`Persistent=true`。

## 6. 尚未替代的边界

- 服务器内每日备份不能替代异机备份；后续应把备份加密同步到另一处私人存储。
- Spotify Developer Dashboard 需要精确登记 `https://spotify-stats.tail8916b1.ts.net/api/spotify/auth/callback`，之后从生产入口重新连接 Spotify。
- 手机需要安装 Tailscale、登录同一账号、打开生产 HTTPS 地址，再从 Safari/Chrome 添加到主屏幕；这一物理设备流程必须由真实手机验收。
- `*.ts.net` 证书名称会出现在 Certificate Transparency 日志中；当前机器名不包含个人隐私信息。
- GitHub Actions 的部分第三方 Action 出现 Node.js 20 runtime 弃用提示，不影响本次发布结果，但应在后续维护中升级主版本。
