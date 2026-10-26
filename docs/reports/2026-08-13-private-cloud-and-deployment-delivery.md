# 私有云与双运行面部署交付

2026-10-26按主题合并。先记录私有云与PWA初次部署，再记录同日双运行面合同；私有HTTPS、loopback网关与物理手机验收分别保留当时结论。

## 阅读顺序

- [个人私有云与 PWA Phase B 交付报告](#个人私有云与-pwa-phase-b-交付报告)
- [SpotifyStats 双运行面交付报告](#spotifystats-双运行面交付报告)

## 个人私有云与 PWA Phase B 交付报告

原记录：`2026-08-13-private-cloud-pwa-delivery.md`。

> 日期：2026-08-13
>
> 当前生产提交：`4bd6eb7135230d9df30fe4a22d8a025357902509`
>
> GitHub Actions：`Deploy private production` run `31685472071`

### 1. 结论

个人私有云生产基线已经部署到既有腾讯云 Ubuntu 服务器，与教师项目隔离运行。SpotifyStats Backend 不映射宿主机端口，Web 只绑定 `127.0.0.1:3001`；服务器公网 80 继续由教师项目占用。个人 SQLite、封面和原始导出位于 `/opt/spotify-stats/data/`，不进入 Git、Docker 构建上下文或镜像仓库。

代码验证、SHA 镜像发布、SSH 部署、容器健康、SQLite 完整性、真实数据计数、PWA 静态文件、首份在线备份和 Tailscale 私网 HTTPS 均已通过。Tailscale Serve 明确标记为 `tailnet only`，没有启用 Funnel。手机实体设备安装仍需要同一 tailnet 内的真实设备确认，因此不能把物理手机验收写成已完成。

### 2. 生产结构

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

### 3. 数据迁移与密钥边界

- 迁移前使用 SQLite Online Backup API 生成一致性生产快照。
- 生产快照删除 `spotify_user_token`、LLM API key 和 LLM profile 密钥；本地数据库未被修改。
- 服务器生产环境使用新生成的独立 `SPOTIFY_STATS_TOKEN_KEY`，环境文件权限为 `600`。
- Spotify Client ID/Secret 与 Genius token 只写入服务器 `.env`，没有进入提交差异或 Actions artifact。
- `.dockerignore` 排除整个 `data/`、`backups/`、数据库、环境文件和缓存目录；Backend 镜像不再执行 `COPY data/`。

### 4. 自动发布证据

首次 `Deploy private production` run `31685472071`：

- `verify`：3 分 31 秒，Backend unit/contract、Ruff、Frontend test/build 和私人部署契约通过。
- `build`：50 分 54 秒，首次冷构建并发布两个 `linux/amd64` SHA 镜像；主要耗时为重依赖镜像首次构建和跨区上传，后续由 GitHub BuildKit cache 复用。
- `deploy`：44 秒，SSH 文件同步、TCR 登录、镜像拉取、Compose 启动、健康检查、loopback 监听约束和数据库完整性检查通过。
- 同一 SHA 的既有 `Phase 5 Baseline` run `31685471998` 也成功结束。

### 5. 服务器独立验收

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
| 私网 HTTPS | 首页和健康接口返回 200，健康正文为 `{"status":"ok"}` |
| TLS 证书 | Let's Encrypt，SAN 精确为 `spotify-stats.tail8916b1.ts.net` |
| PWA 文件 | 首页、`manifest.webmanifest`、`sw.js` 均返回 200；manifest 为 `application/manifest+json` |
| 公网隔离 | 公网 IP 的 3001 连接超时，宿主机仍只监听 `127.0.0.1:3001` |
| 既有教师项目 | Web/API 继续健康，公网首页返回 200 |

首次服务器在线备份为 `spotify-stats-20260813T100842Z.db`，大小 84,500,480 字节，`integrity_check=ok`，包含 91,286 条播放。`spotify-stats-backup.timer` 已启用，每日 03:20 后随机延迟最多 20 分钟执行，`Persistent=true`。

### 6. 尚未替代的边界

- 服务器内每日备份不能替代异机备份；后续应把备份加密同步到另一处私人存储。
- Spotify Developer Dashboard 需要精确登记 `https://spotify-stats.tail8916b1.ts.net/api/spotify/auth/callback`，之后从生产入口重新连接 Spotify。
- 手机需要安装 Tailscale、登录同一账号、打开生产 HTTPS 地址，再从 Safari/Chrome 添加到主屏幕；这一物理设备流程必须由真实手机验收。
- `*.ts.net` 证书名称会出现在 Certificate Transparency 日志中；当前机器名不包含个人隐私信息。
- GitHub Actions 的部分第三方 Action 出现 Node.js 20 runtime 弃用提示，不影响本次发布结果，但应在后续维护中升级主版本。

## SpotifyStats 双运行面交付报告

原记录：`2026-08-13-dual-deployment-profile-delivery.md`。

日期：2026-08-13\
范围：后端访问策略、公共只读连接、前端能力守卫、生产部署模式、CI 门禁与文档

### 交付结论

项目已从“Tailscale 专用双入口”收口为与入口技术无关的双运行面：同一次 commit SHA
发布同一组镜像，由生产配置选择 `full`、`showcase` 或 `dual`。模式切换只调整
loopback Docker 网关，不会自动恢复 Tailscale、Funnel 或其他公网分享。

### 已交付能力

#### 可信运行面

- 私人和简化网关分别固定 `private-admin`、`public-readonly`；
- 两个 runtime Nginx template 注入服务器本地网关密钥；
- Backend 在生产校验 `X-SpotifyStats-Gateway-Token`；
- 浏览器 Header 会被网关覆盖，未知入口 fail closed；
- 网关密钥不进入仓库、镜像或 Actions artifact。

#### 公共只读

- 公共 API 采用显式允许策略，新 operation 默认不公开；
- 所有未批准写操作拒绝，敏感功能不对公共面呈现；
- 公共数据连接启用请求级 SQLite 只读保护；
- 年度总结、封面和其他 cache-first 页面不得由公共访问触发后台写入。

#### 部署与发布

- Compose profiles：`full`、`showcase`、`dual`；
- `set-deployment-mode.sh` 一条命令切换；
- `deploy.sh` 沿用当前模式，并同时回滚镜像和模式；
- 旧服务器缺网关密钥时在服务器本地安全生成；
- 旧服务器缺 mode 时按旧双容器行为迁移为 `dual`；
- Actions 以一个 SHA 构建 API/Web，增加三模式静态矩阵；
- Actions 上传运行时模板、模式切换和验证脚本；
- `verify.sh` 不再默认探测或操作 Tailscale。

### 数据部署事实

`dual` 模式不是两套应用数据：两个 Web 网关都进入同一个 Backend，Backend 使用
同一个 `/opt/spotify-stats/data` 持久目录。两种运行面的 schema、缓存 key 和统计
语义因此保持一致。

这不等于支持把 SQLite 放到多台服务器共享：不得通过 NFS、SMB、对象存储挂载或
双向同步让多个在线 Backend 操作同一个 SQLite 文件。跨服务器展示应使用只读快照；
跨服务器实时读写需要迁移 PostgreSQL。

### 运维命令

```bash
cd /opt/spotify-stats
./set-deployment-mode.sh full
./set-deployment-mode.sh showcase
./set-deployment-mode.sh dual
./verify.sh
./validate-deployment-config.sh all
```

外部入口仍由运维人员单独决定。停止某个外部入口不影响 GitHub 后续更新镜像；自动
发布也不会自行重新开启该入口。

### 验收证据

发布前本地门禁：

- Phase 5 基线：`910 unit + 326 contract`；
- 前端：`71` 个测试文件、`514` 项测试，生产构建通过；
- 生产部署契约：`16` 项通过；
- `validate-deployment-config.sh all`：`full/showcase/dual` 全部通过；
- Ruff check / format check、Shell 语法与 `git diff --check`：通过；
- 两份 Nginx runtime template 已在真实服务器的现行 Web 镜像中完成 `nginx -t`；
- 对本地真实 `spotify_stats.db` 与 `yearly_review_cache.db` 执行代表性公开读取、
  被拒写入、AI/未知路由隐藏和未可信入口测试，前后 SHA-256 完全一致。

线上发布与真实服务器验收：

- 主分支发布 SHA：`71839871452811993a4c6b8ecd61a43483c28104`；
- [Phase 5 Baseline](https://github.com/BenjaminTay/SpotifyStats/actions/runs/31703679803)
  与 [生产部署流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/31703679954)
  均成功，三模式矩阵、镜像构建和服务器部署全部通过；
- 在服务器依次实切 `dual -> showcase -> full`，每个模式的 `verify.sh` 均通过；
- `dual` 下私人面为 `private-admin/full`、展示面为
  `public-readonly/showcase`，两端的 release SHA 和 policy version 一致；
- 展示面设置写入返回 `403`，AI 与未知 GET 返回 `404`；代表性公开读取前后，
  `spotify_stats.db` 与 `yearly_review_cache.db` 的 SHA-256 均未变化；
- `showcase` 下只监听 `127.0.0.1:3002`，`full` 下只监听
  `127.0.0.1:3001`，Backend 的 `8000` 未映射到宿主机；
- 最终已恢复 `full`，公开 3002 端口关闭，Tailscale 保持 `Stopped`，未恢复任何
  外部分享入口；
- 主数据库和年度缓存执行 `PRAGMA quick_check` 均为 `ok`，发布前在线备份已生成。

GitHub Actions 当前仅有 actions 运行时 Node.js 20 被强制升级到 Node.js 24 的弃用提示，
不影响本次门禁、构建与部署结果；后续可随上游 action 大版本升级单独处理。
