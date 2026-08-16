# SpotifyStats 双运行面生产部署

本目录用一套代码、同一组 commit SHA 镜像、一个 FastAPI Backend 和一份
SQLite 数据目录提供两种运行面：

| 运行面 | Compose 服务 | loopback 端口 | 能力 |
|---|---|---:|---|
| `private-admin` | `web` | 3001 | 设置、导入、编辑、AI、Spotify OAuth 等完整功能 |
| `public-readonly` | `public-web` | 3002 | 经后端白名单批准的统计、榜单和详情浏览 |

两个 Web 网关都只绑定宿主机 loopback；Backend 不映射宿主端口。外部 HTTPS
入口是独立的运维层，可以是 Tailscale Serve、域名反向代理或其他受控入口。
部署和模式切换脚本不会自动启用、关闭或修改任何 Tailscale、Funnel、域名、
证书或云防火墙配置。

`public-web` 的人类访问门禁可在 `protected` 和 `public` 之间显式切换。
`protected` 强制 HTTP Basic Auth；`public` 打开链接即可访问，适合明确愿意
对外展示数据的场景。该开关只控制“能否看到”；后端 public-readonly 白名单、
写操作阻断和 SQLite 只读连接始终是不可绕过的数据完整性边界。健康检查
端点不返回个人数据，两种模式下都可无凭据访问。

## 部署模式

`.env` 中的 `DEPLOYMENT_MODE` 决定保持哪些 loopback 网关运行：

| 模式 | 运行服务 | 用途 |
|---|---|---|
| `full` | `backend + web` | 只保留完全版 |
| `showcase` | `backend + public-web` | 只保留简化版 |
| `dual` | `backend + web + public-web` | 同一服务器同时提供两种入口 |

快速切换：

```bash
./set-deployment-mode.sh full
./set-deployment-mode.sh showcase
./set-deployment-mode.sh dual
```

切换复用当前 `IMAGE_TAG`，不会重建数据库，也不会触碰外部 HTTPS 入口。脚本会
停止非目标 Web 容器、验证目标运行面的能力和端口边界；失败时恢复原模式。

## 展示入口密码

切换简化版访问方式：

```bash
./set-showcase-access-mode.sh protected
./set-showcase-access-mode.sh public
```

当 `showcase` 或 `dual` 正在运行时，脚本只会重建 `public-web` 并执行完整
边界验收；验收失败会自动恢复原模式。它不修改完全版、数据库、
Tailscale、Tunnel、域名或防火墙。非法配置会让展示网关启动失败，不会
退化为意外公开。

首次进入 `showcase` 或 `dual` 时，部署脚本会在服务器本地准备 32 位
随机密码，供 `protected` 模式使用：

```bash
./showcase-auth.sh ensure
./showcase-auth.sh show
./showcase-auth.sh rotate viewer
```

明文凭据保存为 `secrets/showcase.credentials`（`600`），Nginx 只读挂载
`secrets/showcase.htpasswd`。两者均不得上传 Git、镜像或 Actions artifact；仓库
`.gitignore` 已排除整个生产 secrets 目录。`rotate` 后需重启 `public-web` 或重新
执行当前模式切换，旧密码才会从运行中网关撤销。

## 无域名临时 HTTPS 分享

短期手机和朋友验收可以使用 Cloudflare Quick Tunnel：

```bash
./temporary-showcase.sh start
./temporary-showcase.sh status
./showcase-auth.sh show

# 分享结束后
./temporary-showcase.sh stop
./set-deployment-mode.sh full
```

`start` 会先切换 `dual`，并沿用当前 `SHOWCASE_ACCESS_MODE`，然后下载固定
版本的 Cloudflare 官方二进制并校验 SHA-256，
只把随机 `trycloudflare.com` HTTPS 地址转发到 `127.0.0.1:3002`。它不会占用宿主机
80/443，不会启用 Tailscale，也不会暴露 3001/3002/8000。systemd unit 故意不设
开机自启，因此服务器重启不会静默创建新的分享地址；代码自动部署也不会启动它。

Quick Tunnel 只用于临时测试：URL 在隧道重启后可能变化，官方限制最多 200 个并发
中的请求，并且不支持 SSE。长期分享应改用自有域名和正式受管理 Tunnel/反向代理，
但仍只允许其访问展示端口 3002。

## 封面缓存

封面使用标准 HTTP 浏览器缓存，而不进入 Service Worker 的离线个人数据
缓存。当前有效期为 7 天，同时允许 30 天 `stale-while-revalidate`；本地文件
支持 ETag 条件请求和 `304 Not Modified`。两种访问模式都返回 `private` 缓存
指令：同一浏览器会复用封面，但共享 CDN 不会保留可能在切回 `protected`
后仍可被绕过访问的旧副本。若未来使用可编程清理的正式 CDN，再单独开启共享
封面缓存。`/api/` 个人统计仍不由 Service Worker 持久化。

## 首次部署

1. 在服务器创建 `/opt/spotify-stats/{data,backups}`，目录权限设为 `700`。
2. 将本目录文件放到 `/opt/spotify-stats/`，复制 `.env.example` 为 `.env`。
3. 至少填写 `APP_PUBLIC_URL`、独立的 `SPOTIFY_STATS_TOKEN_KEY`、镜像仓库配置，
   并选择 `DEPLOYMENT_MODE`。
4. 使用 SQLite Online Backup API 生成一致性 `spotify_stats.db`，再把数据库、
   `covers/`、`account/`、`streaming/` 和 seed JSON 传入
   `/opt/spotify-stats/data/`。
5. 执行 `./deploy.sh <commit-sha>`，再运行 `./verify.sh`。
6. 最后按需单独配置外部 HTTPS 入口。Tailscale 是可选项；只有明确需要时才运行
   `configure-tailscale.sh` 或 `configure-public-funnel.sh`。
7. 运行 `./install-backup-timer.sh` 安装每日 SQLite 在线备份，并配置异机备份。

建议预先生成网关密钥：

```bash
openssl rand -hex 32
```

将结果写入 `SPOTIFY_STATS_GATEWAY_TOKEN`。为兼容现有服务器，`deploy.sh` 在该项
完全缺失时会用服务器上的 OpenSSL 本地生成，不会输出密钥；旧部署没有
`DEPLOYMENT_MODE` 时按旧版两个 Web 容器均运行的事实迁移为 `dual`。

## 可信网关边界

生产环境设置：

```dotenv
SPOTIFY_STATS_TRUSTED_GATEWAY_REQUIRED=1
SPOTIFY_STATS_GATEWAY_TOKEN=<32-128 位 base64url 安全随机值>
```

Compose 把同一密钥注入 Backend 和 Nginx 官方镜像的 runtime template。模板仅在
容器启动时生成实际配置，密钥不写入 Git、Docker 镜像或 Actions 构建产物；
`NGINX_ENVSUBST_FILTER` 只允许替换该密钥，避免改写 `$host`、`$uri` 等 Nginx
变量。部署脚本限制密钥字符集，避免配置注入。

Compose 同时把不可变 `IMAGE_TAG` 作为 `SPOTIFY_STATS_RELEASE_SHA` 注入 Backend，
能力响应因此可以直接核对两个运行面是否确实来自同一 Git commit。

两个网关分别强制覆盖：

```text
X-SpotifyStats-Surface: private-admin | public-readonly
X-SpotifyStats-Gateway-Token: <server-local secret>
```

浏览器提供的同名 Header 会被覆盖。Backend 同时校验运行面与网关密钥；缺少或
伪造凭据不能获得完全版权限。`public-readonly` 的前端隐藏只改善体验，后端显式
API 白名单、写操作阻断和只读数据连接才是最终安全边界。

## 数据边界

- `.dockerignore` 排除整个 `data/`、备份和环境密钥；镜像中不得含 SQLite、封面
  或 Spotify 原始导出。
- `./data:/app/data` 是宿主持久挂载，两种运行面在**同一 Backend 进程组**中读取
  同一 SQLite 文件，因此统计口径和 schema 始终一致。
- 同一服务器的两个 Web 网关不各自打开 SQLite；所有请求都进入同一个 Backend。
- **不能把 SQLite 文件通过 NFS、SMB、对象存储挂载或双向文件同步给多台在线
  Backend 共享写入。**SQLite 的文件锁、WAL 和崩溃一致性不适合这种部署。
- 如果未来将公开版部署到另一台服务器，应使用经过裁剪的只读快照并做单向、原子
  替换；如果需要多服务器实时读写，应迁移到 PostgreSQL 等客户端/服务器数据库。

## 安全边界

- Backend 只在 Docker 私网可达；3000、3001、3002、8000 均不得直接开放公网。
- `SPOTIFY_STATS_REQUIRE_AUTH` 只保护部分写接口，不能代替整站身份边界。
- 完全版的外部入口必须另有身份认证，例如私有 tailnet 或带身份验证的反向代理。
- 简化版禁用设置、编辑、导入、AI、Spotify OAuth、歌词、元数据治理、后台任务和
  未批准的写操作；安全的结构化分析 POST 仍可按白名单执行只读计算。
- 简化版年度总结只读取精确持久缓存，封面请求不得触发外部搜索、写库或后台下载。
- `X-Robots-Tag: noindex` 只降低收录概率，不是身份验证；公开链接可被转发。
- HTTP Basic Auth 必须使用 HTTPS；Quick Tunnel 或正式 TLS 入口负责传输加密。不要
  通过服务器 IP 的明文 HTTP 暴露展示密码。

## 发布、回滚与 GitHub Actions

GitHub Actions 的流程是：

```text
push main
→ 后端/前端测试
→ full/showcase/dual 静态部署矩阵
→ 构建同一 SHA 的 API/Web 镜像
→ 上传一天保留的私有 CAS Artifact
→ rsync 仅传服务器缺失的镜像 blob
→ 服务器 docker load、推送 TCR 并按 digest 拉回核验
→ SSH 执行 deploy.sh <sha>
```

服务器调用不带 `--mode`，因此自动发布只更新当前 `.env` 记录的模式，不会因代码
发布重新开启已经停止的完全版、简化版或任何外部入口。

镜像 Artifact 不得包含数据库、`data/`、密钥或原始导出。服务器按 SHA 使用独立
`releases/incoming/<sha>/`，逐 blob 校验文件名 SHA256、镜像 `linux/amd64`、revision label、
image ID 和 manifest；成功发布后才把 CAS retention 的 `current` 滚动为 `previous`。镜像传输、
TCR manifest 核验任一步失败，均不得进入数据库备份和停服阶段；搜索容量检查失败可以保留已完成的
Online Backup，但不得停服或替换数据库。

每个新 SHA 的数据库切换固定为以下 staged 流程：

1. 使用已完成身份核验的目标 API/Web 镜像，由旧 Backend 创建发布前 SQLite Online Backup；
2. 将备份复制到 `backups/.release-stage.*`，在目标 API 镜像中关闭
   `SPOTIFY_STATS_SEARCH_STARTUP_REBUILD`，执行一次
   `rebuild_music_search_derived_data.py --require-all-ready --statistics-reuse-only`；候选版本变化时只重建
   候选，统计 fingerprint 没有变化时六个变体必须精确复用；
3. 只有 migration 36、当前语义精确六个 fingerprint、builder v2、搜索 context orphan=0、
   `integrity_check=ok` 以及宿主容量全部通过，才保留预检副本；报告写入
   `backups/music-search-preflight-<sha>-<timestamp>.json`；
4. 停止 Backend 后再创建一份 quiescent Online Backup，并与第一份源备份逐字节比较；若预检期间
   数据发生变化，恢复旧服务并拒绝用旧副本覆盖；
5. 原子替换 SQLite 后启动新 SHA，执行 runtime 精确六变体、精确/模糊/简繁/短 CJK 搜索、网关、
   端口、能力与写操作门禁；
6. 任一新版本验收失败，同时恢复发布前 SQLite、上一 SHA 和上一 deployment mode。

旧生产库第一次升级到 migration 36 时，先单独运行手动
`bootstrap-production-music-search.yml` 建立六套统计；该 workflow 不部署应用。完成一次性引导后，
正常 UI、部署脚本、查询匹配或 Git SHA 变化不得再次冷建六套统计。

一次性统计引导默认要求 `MemAvailable >= 1280MiB`；正常发布固定使用
`--statistics-reuse-only`，统计不能精确复用时会在任何候选/统计重建前失败，因此独立使用
`SEARCH_PREFLIGHT_REUSE_MIN_AVAILABLE_MIB=640` 的候选索引预算。前者来自六变体峰值
876.758MiB，后者相对候选重建峰值 318.984MiB 保留超过 2 倍预算；两者都不得在没有新实测的
情况下继续调低。可用磁盘始终要求 `>= max(1GiB, 数据库大小 × 4)`。发布脚本不会在 live DB 上
执行首次六变体冷构建，也不会启用或关闭任何外部 HTTPS 入口。

手动命令：

```bash
./deploy.sh <commit-sha>
./deploy.sh <commit-sha> --mode dual
./rollback.sh
./rollback.sh <commit-sha>
./validate-deployment-config.sh all
```

需要单独复核副本时，必须传入非 `deploy/production/data/` 的明确 DB 副本和全新报告路径：

```bash
./preflight-music-search.sh \
  --db-copy /safe/staging/spotify_stats.db \
  --json-report /safe/staging/music-search-preflight.json \
  --image <target-backend-image>
```

脚本只在全部门禁通过后原子更新该副本；拒绝真实 production data 路径、已有报告路径和不安全镜像名。

不带 SHA 的 `rollback.sh` 会同时恢复上一次镜像和上一次模式；显式提供目标 SHA
时，由于没有该 SHA 对应模式的可靠记录，只回滚镜像并保留当前模式。

## 验证

```bash
./verify.sh
VERIFY_EXTERNAL_INGRESS=1 ./verify.sh  # 仅在确实配置了外部入口时使用
```

`verify.sh` 依据当前模式验证：

- 目标容器运行；
- 端口只监听 loopback；
- 非目标 Web 端口没有监听；
- 能力响应分别为 `private-admin` / `public-readonly`；
- 简化版设置写操作返回 403；
- SQLite `PRAGMA integrity_check` 返回 `ok`。
- 当前服务端 Settings 推导出的六个搜索 fingerprint 精确存在且全部 `ready + builder v2`；
- `music_search_entity_context` 不存在指向已删除 snapshot meta 的孤儿。

静态发布门禁可在开发机或 CI 执行：

```bash
./validate-deployment-config.sh full
./validate-deployment-config.sh showcase
./validate-deployment-config.sh dual
```
