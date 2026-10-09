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

列表封面使用持久化的 160px WebP 缩略图，摘要与大卡片按展示尺寸使用
320px / 640px；完整展示仍可使用原图。新下载的封面同时生成三种尺寸；
已有封面在首次发布此功能后，于服务器的
`/opt/spotify-stats` 目录运行一次：

```bash
docker compose -f compose.yml exec -T backend python scripts/backfill_cover_thumbnails.py
```

上述旧命令默认只补 160px。补建新增尺寸可分批执行：

```bash
docker compose -f compose.yml exec -T backend python scripts/backfill_cover_thumbnails.py --sizes 320 640 --limit 200
```

`--limit` 限制本批需要生成的原图数量，已有有效派生文件不消耗额度；重复执行
会向后推进。输出 `processed` 按源图计数，`generated/skipped/failed` 按变体
计数；失败以非零退出码报告，应检查具体文件后再继续。最终执行同尺寸扫描，
确认 `processed=0 failed=0`。补建期间观察 CPU、RSS 和磁盘，避免与重型快照
构建同时执行。原图完整保留，尺寸选择和例外见[封面传输规则](../../docs/reference/cover-artwork-delivery.md)。

脚本只读取原图并在 `data/covers/thumbnails/` 写入派生文件，不修改 SQLite；
重复运行会跳过当前版本。补建完成前，缩略图地址会暂时返回原图并使用
60 秒私有缓存。两种运行面的网关透传后端的缓存头。

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
7. 运行 `./install-backup-timer.sh` 安装每周日 03:20（另有最多 20 分钟随机延迟）的 SQLite 在线备份。服务器 `.env` 中的 `BACKUP_RETENTION_DAYS=28` 只清理普通定时备份；备份完成并通过完整性检查后才清理过期文件。发布前和恢复前备份不会被普通轮转清理。

重要数据导入前，先运行 `SPOTIFY_STATS_BACKUP_NAME="spotify-stats-pre-import-$(date -u +%Y%m%dT%H%M%SZ).db" ./backup.sh` 并确认成功；导入完成后再以 `spotify-stats-post-import-` 前缀运行一次。普通周备份之间的其他写入最多可能损失约一周。修改本文件或 timer 模板后，须重新安装 timer，并用 `systemctl cat spotify-stats-backup.timer` 核对服务器生效规则。

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

GitHub Actions 分为日常质量检查、部署契约检查和正式发布三条边界：

- `ci-quality.yml`：Pull Request 和常规分支 push 的后端、前端、文档与构建检查。
- `production-deployment-contract.yml`：只在 Docker、部署脚本、生产测试或 workflow 变化时运行；只做契约检查，不连接服务器、不部署。
- `production-release.yml`：`main` push 或手动触发的正式发布。
- `production-image-transport-rehearsal.yml`：手动镜像传输演练；不部署、不重启线上服务。

```text
push main
→ CI 质量检查
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
   候选，统计 fingerprint 没有变化时四个变体必须精确复用；当前四个 Year-End 投影也必须已准备，
   缺失时直接拒绝，不能在候选预算内补建周榜明细或年度统计。准备副本同源移植当前四个 fingerprint
   的搜索 context、周榜明细和年度投影，保留目标其他历史 key；
3. 只有搜索兼容基线 migration 69 及目标镜像当前 schema（本次90）、当前语义精确四个 fingerprint、搜索 builder v12、Billboard 聚合 v6、
   收听时长策略 `all_music_intervals_v1`、搜索 context orphan=0、
   `integrity_check=ok` 以及宿主容量全部通过，才保留预检副本；报告写入
   `backups/music-search-preflight-<sha>-<timestamp>.json`；
4. 停止 Backend 后再创建一份 quiescent Online Backup，并与第一份源备份逐字节比较；若预检期间
   数据发生变化，恢复旧服务并拒绝用旧副本覆盖；
5. 原子替换 SQLite 后启动新 SHA，执行 runtime 精确四变体、精确/模糊/简繁/短 CJK 搜索、网关、
   端口、能力与写操作门禁；
6. 任一新版本验收失败，同时恢复发布前 SQLite、上一 SHA 和上一 deployment mode。

旧生产库第一次升级到 migration 69 时，先单独运行手动
`one-time-search-snapshot-bootstrap.yml` 在 Online Backup 副本建立目标镜像当前 Billboard 聚合与四套搜索统计；该 workflow 需要显式输入
`INITIALIZE_SEARCH_SNAPSHOTS`，且不部署应用。完成一次性引导后，
正常 UI、部署脚本、查询匹配或 Git SHA 变化不得再次冷建四套统计。

若只读容量诊断确认当前 Backend 的驻留缓存导致 `MemAvailable` 低于冷建门槛，可在同一次显式
Break Glass 调用中启用 `restart_current_backend`。workflow 只重启当前 Backend 容器，要求容器 ID
与镜像 ID 前后不变并等待其恢复 `healthy`，然后才创建 Online Backup；该选项会造成短暂 API
中断，但不会更换镜像、修改生产数据库或绕过容量门禁。
引导报告下载对瞬时 SSH 断连最多重试 5 次；重试只读取隐私安全报告，不会重复修改生产数据。

一次性统计引导默认要求 `MemAvailable >= 2304MiB`，覆盖当前真实库约 1.83GiB 的冷建峰值并留出
约 20% 余量。正常发布固定使用
`--statistics-reuse-only`，四套统计或其当前年度投影不能精确复用时会在任何候选/统计重建前失败，因此独立使用
`SEARCH_PREFLIGHT_REUSE_MIN_AVAILABLE_MIB=640` 的候选索引预算。前者应覆盖当前四变体真实冷建峰值
约 1.83GiB，后者相对候选重建峰值 318.984MiB 保留约 2 倍预算；两者都不得在没有新实测的
情况下继续调低。可用磁盘始终要求 `>= max(1GiB, 数据库大小 × 4)`。发布脚本不会在 live DB 上
执行首次四变体冷构建，也不会启用或关闭任何外部 HTTPS 入口。

手动命令：

```bash
./deploy.sh <commit-sha>
./deploy.sh <commit-sha> --mode dual
./rollback.sh
./rollback.sh <commit-sha>
./validate-deployment-config.sh all
./validate-deployment-config.sh --common-only
./validate-deployment-config.sh --profile-only full
./validate-deployment-config.sh --profile-only showcase
./validate-deployment-config.sh --profile-only dual
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
- 当前服务端 Settings 推导出的四个搜索 fingerprint 精确存在且全部 `ready + builder v12`；
- `agg_config` 为目标镜像当前 `billboard_aggregation_v6_legacy_year`，且时长策略为 `all_music_intervals_v1`；
- `music_search_entity_context` 不存在指向已删除 snapshot meta 的孤儿。

静态发布门禁可在开发机或 CI 执行：

```bash
./validate-deployment-config.sh full
./validate-deployment-config.sh showcase
./validate-deployment-config.sh dual
```

## 日期精度规则升级的发布准备

schema88→89和聚合v4→v6需要先在明确副本准备当前聚合，再按正常仅复用合同验证四套统计与Year-End。宿主独立预检常量必须与目标后端builder同步，旧v4不得重标成v6。预检期间源仅发生无关写入时，重基先升级quiescent副本到staged登记的迁移合同，再核对包含日期观测审计的source marker；恢复点不迁移。

正式发布续建使用日期尚未补证、与迁移后正式源等价的候选。已补证候选不能覆盖旧正式源；日期证据在新版本的备份/预览/有界维护阶段单独安装，随后在生产自身文件身份准备sidecar。见[2026-10-08副本演练](../../docs/reports/2026-10-08-release-date-production-rehearsal.md)及[正式交付](../../docs/reports/2026-10-08-release-date-production-delivery.md)：76a4968/schema89、固定92来源/78项目补证及年度/API/两视口专项已完成。维护期间OOM及详情内存增长独立跟踪；逐年受监管新进程完成剩余年度是本轮运维缓解，不代表资源问题已代码修复。

## 榜单对决个人排名发布

支持 `entity_rank_context_v2` 的目标镜像在激活前、启动后均要求当前服务端 L2/L3 × dynamic/fixed 四个默认配置为 `exact-ready`。普通发布只读取已发布排名，缺失、过期、损坏或来源不一致即拒绝；不调用全库 builder，不排队补建。首次发布须先在目标 SHA 的已迁移 Online Backup 副本构建四份排名，私密 manifest 与数据库、封面一样不得进入 Git、镜像或公开 CI artifact。

在明确副本执行（替换路径和完整 SHA）：

```bash
python scripts/versus_rank_publication.py build \
  --closed-source \
  --source-db /safe/spotify_stats.copy.db \
  --analysis-cache /safe/versus-analysis.db \
  --manifest /safe/versus-ranks-<sha>.json --release-sha <sha>
```

`export` 模式只导出已有 exact 发布；`validate` 只核对源、版本、family、规范化过滤条件、payload 校验与形状；`install`（或 `import`）在目标只读源上重算文件 lineage key，四配置单事务写入 Analysis sidecar。部署使用 `--require-defaults`，拒绝不完整集合；`verify` 独立读取全部四默认配置。

源连接始终使用 SQLite URI `mode=ro`。`--closed-source` 仅用于已停服主库或静态副本，并要求不存在 WAL 文件；此时以 `immutable=1` 读取闭库备份的 WAL header，无需改写源库的 journal mode 或生成 WAL/SHM。部署 helper 只在停服或静态预检阶段、确认无 WAL 时传此参数；运行中验证使用普通只读连接。闭库模式另核对文件身份、大小和修改时间，安装提交前源文件变化会回滚整批 sidecar 发布。

首版将 manifest 通过已有 SSH/SCP 访问上传为服务器 `/opt/spotify-stats/backups/versus-ranks-<完整目标SHA>.json`，权限 `600`。生产 workflow 使用现有部署 SSH 凭证检查这一私密服务器文件，不新增 GitHub Secret，也不从 Git 或公开 artifact 获取数据。`deploy.sh` 自动发现此精确 SHA 路径，亦可显式传 `--versus-rank-manifest <path>` 或 `VERSUS_RANK_MANIFEST`。没有 manifest 时，只允许从当前 live DB 的目标 builder exact-ready 发布导出并重绑到替换后的 lineage；源发生变化即失败。

Backend 停服期间先核对已完成搜索预检的副本和目标排名，再对主库及已存在的 Billboard/Analysis sidecar 逐库执行 `wal_checkpoint(TRUNCATE)`；任一忙锁或未合并帧即拒绝继续。全部连接关闭、确认三库 WAL 为空后才清理对应 WAL/SHM 并硬链接保留原主库 inode，以旧镜像严格验证旧 Billboard 和四默认排名；随后备份完整 Analysis sidecar。未保留原 inode 时拒绝排名备份。替换主库后按目标 manifest 安装并验证四默认 ready，最后才激活新镜像。安装或后续网关验收失败时，联合恢复原主库 inode、完整 sidecar、上一 SHA 和部署模式；原 key 的 lineage 随 inode 恢复，不再导出、重绑或改写旧排名发布。旧镜像启动前的共同闭库门禁仍要求旧排名与 Billboard exact-ready，缺失或漂移即拒绝激活。功能出现前的旧镜像不调用不存在的排名模块。停止后的原源副本单独保留，不用已升级搜索预检副本作为旧代码恢复点。

## 音乐详情附属投影发布

支持 schema90 的镜像要求默认 L2/L3 × dynamic/fixed 四变体的详情附属投影 exact-ready。首次发布只在明确 Online Backup 副本运行 `scripts/prepare_music_detail_projection.py --db-path <副本> --build-on-copy`，随后以 `--export <manifest>` 导出；该私密数据文件放置于服务器 `backups/music-detail-<完整目标SHA>.json`，权限600，不得提交Git或进入镜像/公开artifact。

正常发布优先复用已迁移预检副本的投影；缺失时只验证、安装预先准备的manifest，来源lineage、治理digest、四过滤指纹及内容校验必须全部一致。`music-detail-release.sh`只在原子替换前修改stage副本，绝不在公开GET或正常发布冷建；runtime以 `--verify` 只读检查。回退恢复发布前完整数据库与旧SHA，因此详情附属表与榜单发布一起回退。`--owned-copy`用于明确owned副本目录与默认路径重合的特殊环境，不能作为正式库冷建许可。

stage校验显式使用 `--closed-source`：先拒绝任何遗留WAL，再以 `mode=ro&immutable=1`、`query_only`读取已闭库副本，操作前后核验文件身份，避免WAL模式主文件在只读挂载中尝试创建辅助文件。适配器保持已提交读取，不强制开启事务，以兼容 Analysis/Billboard revision 的原事务拒绝及 data_version 检查；闭库一致性由 immutable 和前后完整文件状态封锁保证。该参数不能用于运行中数据库或详情写操作；runtime继续普通只读连接，读取已提交WAL。详情stage导入容器使用宿主UID/GID，避免临时导入控制目录成为root私有而无法清理；正式Backend用户及已有排名侧库维护权限保持。

L3 来源日期精度修复将 Billboard 持久成品独立升级到 `billboard_persistent_snapshot_v4_l3_release_precision`（搜索 v12 不变）。首次在另一个 owned Online Backup 路径用 `scripts/prepare_billboard_publications.py --db-path <副本> --cache-path <独立旁库> --build-on-copy` 准备四组合、六个常规 family 及各组合实际可用年榜，再 `--export <manifest>`；私密成品上传 `backups/billboard-<完整目标SHA>.json`，权限600。以后只从停服 live 的 exact-ready 成品导出复用，缺失即拒绝发布。

Billboard manifest 保留全部事实依赖、分析 COMMON/RECORDS revision vector、日期与署名 policy，允许重绑数据库路径和 inode；不得删除事实 revision 来接受漂移。先验证并导入 stage sidecar；主库提升产生新 inode 后，再以同 manifest 重绑到 live key，独立 verify 后才激活。失败时联合恢复原主库、Billboard/Analysis sidecar、旧 SHA 和模式。闭库重绑拒绝遗留 WAL，运行中检查使用普通只读连接。默认详情目标读取不依赖完整 Billboard sidecar，legacy full/list/release 继续原成品门禁。

自动发布失败恢复在停服并 checkpoint 后保留原数据库的同文件系统硬链接，回退使用原 inode，避免旧 v3 与排名精确 key 因复制到新 inode 失效。共同闭库门禁以普通公开只读 guard、immutable 和前后文件状态读取已经 checkpoint 且无 WAL 的主库及旁库，严格验证旧 Billboard 和实际四默认排名；任意残留 WAL、缺成品或来源变化均拒绝。旧镜像启动后继续普通只读 exact-ready 检查，读取已提交 WAL；不能仅凭 LKG/健康响应宣称恢复成功。发布成功清理该 owned 链接；失败且尚未恢复时保留路径供恢复。此保护只覆盖本次发布失败的自动联合恢复，成功后人工 `rollback.sh` 部署旧 v3 的成品恢复尚未验证。
