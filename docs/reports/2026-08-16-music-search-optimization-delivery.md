# 音乐查找性能与体验优化交付报告

日期：2026-08-16
范围：M0–M5
结论：**Pass — M0–M5、remediation 与生产发布前门禁通过**

首轮验收发现的六变体覆盖、`merge_enabled / include_compilations` 语义和高命中热路径缺口，已按
`docs/plans/2026-08-16-music-search-remediation-plan.md` 完整修复。真实主库六个支持变体全部 ready，
无 pending/running 重建任务；代码、数据迁移、浏览器、生产镜像、受控副本预建与联合回滚结论均为
Pass。远程生产是否已运行某个版本，必须以对应 commit SHA 的 GitHub Actions production deployment
记录为准，不能由本地报告或镜像构建结果代替。

> 后续实现状态：本文记录的两阶段搜索、六变体统计事实和历史性能证据继续有效；其中“每个新 SHA
> 都执行完整六变体 one-shot”的发布策略已被
> `docs/plans/2026-08-16-music-search-direction-realignment.md` 取代。当前本地实现以 migration 35/36
> 拆分确定性候选版本与统计 fingerprint，并加入可续建发布、简繁、短 CJK 与有限模糊匹配；远程
> 生产仍需对应 SHA 验证后才能更新本文结论。2026-08-17 的远程尝试在 GitHub 托管 runner 向 TCR
> 上传 API image layers 时有界失败，deploy 未执行，生产仍运行旧版本。

## 1. 交付结果

音乐查找已从“每次输入同步加载 lifetime 播放帧并计算完整 Billboard”改为两阶段读取：

1. `response_mode=candidates` 从版本化派生索引返回轻量候选、准确总数、分页和稳定
   `entity_key`；
2. `/api/music/search/context` 只从精确筛选快照读取播放次数与个人 Billboard 摘要。

候选请求不再调用 `load_period_plays()` 或 `compute_billboard_data()`。上下文未就绪时显式返回
`warming / stale / unavailable / failed`，前端不会把“未加载”伪装成 0 次播放。旧 response 默认保持
兼容，Settings 治理消费者显式使用只限私有运行面的 `eligibility=any_local`。

## 2. 数据层与语义

- migration 32/33 建立索引、FTS5 trigram、快照 metadata 和 entity context；migration 34 新增 O(1)
  `music_search_revision_state`、`semantic_base_key`、变体诊断列和 builder version，并把旧快照统一标记
  stale。派生表可删除重建，不改原始音乐表。
- 搜索文档覆盖歌曲 L1/L2/L3、album project、专辑 fallback、canonical artist、已批准 alias、
  有效署名艺人和专辑 secondary text。
- 标准化事实源执行 NFKC、Unicode casefold、空白折叠及常见引号、破折号、CJK 全角标点统一；
  默认不猜简繁体，只接受可注入、可版本化的显式扩展。
- 排序固定为名称 exact、prefix、token、secondary/alias、trigram substring；播放热度仅作同层
  tie-breaker。
- `current` 资格只接受同一 `semantic_base_key`、精确变体、`ready` 且 builder v2 的 snapshot；最终
  fingerprint 叠加 merge level 与动态阈值，基础语义包含 5 分钟间隔、精选集、三类 Top N、榜单
  周边界及播放/榜单/元数据/设置/身份/署名/索引 revision。
- 歌曲、专辑、艺人在 L1/L2/L3 下逐项对照详情统计和 Billboard 详情。专辑使用 album project +
  canonical artist，不再以旧搜索的原始专辑名称计数作为权威事实。
- Billboard raw、staged、LRU 和 latest snapshot cache 全链纳入 `merge_enabled`；关闭合并时强制走
  精确 raw 路径，`include_compilations` 同样贯穿搜索 lookup。六变体 × 三实体及非默认设置契约通过。

## 3. 失效、重建与公开只读

- 导入维护、统计设置、版本归并、艺人身份和曲目署名变化显式 bump 持久 revision，统一失效搜索
  documents 与六变体 snapshot；失败 mutation 不 bump。每个 `semantic_base_key` 只排一个
  `snapshot-set` job，按 L2T/L1T/L3T/L2F/L1F/L3F 顺序独立发布，单变体失败不回滚已 ready 结果。
- 启动时 private-admin 只排缺失或过期的 snapshot-set；已有精确 ready 直接命中。公开 GET 从不冷
  构建、不排队、不写库，候选冲突基础参数明确返回 `unsupported_candidate_filter` 422。
- public-readonly 显式允许候选与 context GET，但拒绝 `any_local`；契约测试在请求前后逐表比对
  index、snapshot 与 background job 状态，确认零副作用。
- `scripts/rebuild_music_search_index.py`、`scripts/rebuild_music_search_derived_data.py` 支持显式维护；
  `scripts/music_search_performance_probe.py` 以 URI `mode=ro` + `query_only` 运行，并隐藏原始查询与
  实体内容。
- 启动 catch-up 由 `SPOTIFY_STATS_SEARCH_STARTUP_REBUILD` 独立控制，不再借用缓存 warmup 开关；生产
  默认开启，副本预建容器显式关闭。精确六变体已经 ready 时，维护入口只做校验，不重建 context，
  重启也不会重复排队。
- 验收发现普通连接 `foreign_keys=OFF` 时旧 meta 裁剪不会级联删除 context；prune 已改为先显式删
  context 再删 meta，并补回归。真实库 15,175 条搜索孤儿在 165MiB Online Backup 保护下清为 0；
  其余 7,831 条历史非搜索外键问题未纳入本轮。

## 4. 前端体验

- 完整页和 Quick Open 共用 220ms 防抖、IME composition 门禁、短查询策略、AbortSignal、
  `retry: 0`、语义 query key 与 keep-previous-data。
- 只有 successful `warming / stale` 会按 2/4/8/10 秒退避观察；`ready / unavailable / failed`、网络
  error、页面隐藏和卸载都会停止。候选 placeholder 只允许同一完整 filter key，context 还要求
  ready + fingerprint + 排序去重 entity keys，旧变体统计不会串到新候选。
- Quick Open 每类最多 3 条，默认不选首条；支持 Cmd/Ctrl+K、editable target 排除、方向键、Enter、
  Escape、focus trap、live count 和关闭后焦点归还。
- `/music/search` 的全部视图每类预览 5 条并显示准确总数；单类型每页 20 条，URL 完整保存
  `q / kind / page`，显示例如 `21–40 / 255 · 第 2 / 13 页`。
- 候选与 context 独立加载，旧候选在更新时保留；统计区域预留固定高度，context 不可用不影响
  深链，不显示虚假的 0 次播放。
- Phone 显式入口使用一次性 autofocus intent；从详情 Back 不重新弹键盘，并恢复查询、页码和
  结果区滚动位置。
- 匹配文本使用 React `<mark>` 节点安全高亮，不使用 `innerHTML`；label、subtitle 与 alias 根据后端
  `match_field` 显示。高亮沿用 NFKC/casefold/标点规则并映射回原始 grapheme；Firefox 等没有可构造
  `Intl.Segmenter` 的环境使用组合符、variation selector、Emoji modifier 与 ZWJ 安全 fallback。
  private-admin 最近查看最多 6 条，public capability 下不读取也不写入相关 localStorage。

## 5. 真实性能

真实主库事实副本：91,286 条播放、12,362 首歌曲、5,316 张专辑、1,189 位艺人；SQLite 3.51.0，
FTS5/trigram runtime 可用。probe 覆盖 exact、prefix、多 token、高命中、Unicode、CJK 和单类型第 2 页
七类固定非敏感查询，每类热身后重复 60 次，共 420 个样本：

| 路径 | M0 基线 | 最终 P50 | 最终 P95 | 最大响应 |
|---|---:|---:|---:|---:|
| Service candidates | 214.479ms | 15.499ms | 67.271ms | 5,490 B |
| HTTP candidates | — | 15.780ms | 40.741ms | 5,490 B |
| Service context | unavailable | 0.168ms | 0.295ms | 3,998 B |
| HTTP context | unavailable | 6.034ms | 6.921ms | 3,998 B |
| 旧完整搜索 warm | 6,466.721ms | 不再进入交互热路径 | — | — |
| 旧完整搜索 cold | 13,951.602ms | 不再进入交互热路径 | — | — |

候选 SQL phase P95 为 66.601ms，HTTP context snapshot lookup P95 为 0.417ms；候选 P95 ≤80ms、
context P95 ≤20ms、响应 ≤8KiB 全部通过。SQL trace 确认候选/context 不访问 `plays` 或 Billboard
aggregate，不加载完整 eligible set；窗口函数在一个有界 SQL 中完成排序、准确总数和分页。

真实副本六变体首次完整构建总计 978,623.54ms（约 16 分 19 秒），按 L2T/L1T/L3T/L2F/L1F/L3F
分别约 79.57/326.52/48.71/56.57/398.67/68.59 秒，峰值 RSS 约 1.22GiB。该重任务只在显式维护链
运行，不进入 GET；默认变体优先发布，其余变体逐个可用。

初版生产目标 `linux/amd64` 镜像在 Online Backup 副本上的发布前 one-shot 为 892,501.479ms，峰值
RSS 1,569.547MiB；真实服务器只有 1,349MiB `MemAvailable`，2,560MiB 门禁在写库/停服前正确
拦截。审计确认六个不同语义的 Pandas/Billboard cache 会累积，且主播放帧与艺人 fan-out lifetime
DataFrame 同时驻留。变体独立发布后释放 `billboard/db` cache 并 GC，再将两类帧改为顺序计算后，
最终同规模 one-shot 为 983,317.824ms（约 16 分 23.3 秒），snapshot 979,524.788ms，峰值 RSS
876.758MiB，较初版降低约 44%。SQLite 由 172,511,232 B 增至 205,463,552 B（增量
32,952,320 B，约 31.43MiB），WAL 最终为 0，六变体实体数量与契约保持一致。历史实现中两次独立
索引重建会生成不同 generation ID 并隔离 semantic base；该行为现已被解耦实现取代。generation ID
只用于候选索引原子发布和诊断，不再进入统计 semantic base/fingerprint。

默认容量门禁据最终实测改为 1,280MiB，相对峰值保留约 403MiB（约 46%）余量；真实服务器样本
1,349MiB 相对峰值约有 472MiB 余量，低于 1,280MiB 时仍 fail closed。磁盘继续要求
`max(1GiB, DB × 4)`。对同一 ready 副本再次运行 `--snapshot-only --require-all-ready` 仅
313.549ms，snapshot elapsed 为 0、DB/WAL 增量为 0，分类为
`revalidated_existing_snapshot_set`。

机器可读 probe 在验收临时目录生成，报告不含 raw query、实体内容或播放历史行；大体积临时数据库
与采样文件在结果写入本文后清理，不作为仓库产物提交。

## 6. 浏览器与视觉验收

- Chromium、Firefox、Playwright WebKit（Safari-family）均通过 Desktop Quick Open 与 Phone 搜索：
  快捷键、默认无选择、ArrowDown、Tab focus trap、Escape、焦点归还、显式 Phone autofocus、
  reduced-motion 和零横向溢出。
- 首轮 R5 在 Firefox 捕获 `Intl.Segmenter is not a constructor` 空白页；能力探测/fallback 修复后，
  三引擎整组重新通过，不以单次 Chromium 成功替代跨浏览器结论。
- 360 / 390 / 430 / 640（1280 设备 200% reflow 等价）/ 768 / 1024 / 1280 均为 0px 页面横溢；
  分页按钮均为 44×44px。
- 真实 Back 验收从 `page=2` 的 600px 位置点击当前视口内结果进入详情后返回，URL、
  `21–40 / 255` 页码和 600px 滚动位置全部恢复；普通 query/kind/page PUSH/REPLACE 不复用旧位置。
- 截图：`output/playwright/music-search-2026-08-16/search-desktop-1280.png`、
  `search-phone-390.png`；最终三浏览器 JSON 为
  `output/playwright/music-search-r5/cross-browser-final.json`。

## 7. 生产与回滚门禁

- `linux/amd64` API/Web 生产目标重新构建通过；最终本地 release API 镜像 ID 为 `20ba481c1c66`
  （约 409MB），Web 镜像 ID 为
  `a6d23a181fc7`（约 67.8MB）。API 中 SQLite 3.46.1、`ENABLE_FTS5=true`，trigram 建表、写入和
  `MATCH` 实测通过；build proxy 未进入最终镜像环境或 history。
- 首轮镜像内容门禁发现 `/app/backend/tests/fixtures/seed.db` 被带入。`.dockerignore` 已递归排除
  `.db/.sqlite/.sqlite3` 与 WAL/SHM/journal 旁车，构建期 `validate_container_image.py` 同时按文件名
  和 SQLite magic header 阻断伪装数据库；重建后 `/app` 扫描通过。
- `deploy/production/validate-deployment-config.sh all` 验证 full、showcase、dual 三模式服务矩阵、
  loopback 端口、可信网关与 public access 配置，结果通过。
- 首轮 M5 的旧 HEAD `48210b28` 镜像读取 migration 33 数据证据继续有效；本轮另用 schema 33 在线
  备份演练 33→34、幂等重跑、34→33 restore，均为 `quick_check=ok`。恢复后的 plays/meta/context/job
  计数与备份时点逐项一致。
- 真实库定点清理前新增 Online Backup：
  `data/backups/spotify-stats-before-search-orphan-cleanup-20260816T080700Z.db`（165MiB）；备份保留
  15,175 条旧搜索孤儿、六个 ready 变体和 61,145 条 context，可直接恢复清理前状态。
- 生产脚本现在先拉取目标 SHA 镜像并做发布前 Online Backup，再在明确的非 production DB 副本中
  关闭 startup rebuild 执行 one-shot；只有 migration 34、精确 6/6 fingerprint、builder v2、全表
  context orphan=0、完整性与容量全部通过，才允许进入切换阶段。
- 副本预建期间旧 Backend 保持服务。真正切换前先停 Backend、再做第二份 quiescent Online Backup；
  两份源备份逐字节不一致即拒绝以旧副本覆盖，要求静默维护窗口重试。新版本验收失败会同时恢复
  发布前 SQLite、旧镜像 SHA 与旧 deployment mode。
- 真实后端容器在一份发布候选副本上连续启动两次，active search jobs 始终为 0；candidate/context
  均返回同一 ready fingerprint。前后完整逻辑 dump SHA 相同，background job 总数与数据库内容均
  未变化，证明 ready 状态下 startup catch-up 和 public GET 不写库。

远程发布由 GitHub Actions 通过既有 SSH secrets 执行，且不改变外部 HTTPS 入口。最终运行状态、
目标 deployment mode 与服务器容量是否通过，以对应 commit SHA 的 production deployment job 为
唯一权威证据。

## 8. 自动化验证

- 后端：`pytest -m unit` 1,032 passed；`pytest -m contract` 356 passed。session 级 fixture 在本地从
  真实库做 Online Backup、在 clean CI 显式从 portable seed 建立临时库；两者都不会让测试 job/
  generation 写入真实主库。
- API：safe smoke 128/128，boundary probe 111/111；OpenAPI GET 127/140 covered、13 个明确排除、
  0 unaccounted，parameter audit 91 obligations / 0 unaccounted；生成类型已刷新。
- 前端：全量 Vitest 73 files / 541 tests，
  production build、变更范围 ESLint 和 `git diff --check -- frontend` 通过。
- 质量：Ruff check/format、12 个本轮 Python 文件 targeted mypy、detect-secrets 与全仓
  `git diff --check` 通过。全仓既有 ESLint（177 项）和 mypy（136 项）债务未在本轮扩域修复；
  本轮变更范围没有新增对应错误。
- 生产：API/Web `linux/amd64` 构建、镜像 SQLite 内容门禁、FTS5/trigram doctor、
  `validate-deployment-config.sh all/full/showcase/dual` 与三浏览器 smoke 通过。

## 9. 远程发布前置条件

本地 Pass 不等于可以无条件切换远程生产。发布前按以下风险分级处理：

| 风险 | 当前证据 | 发布条件 | 推荐处理 |
|---|---|---|---|
| 变更面与审查边界 | 搜索、Billboard、前端、部署与文档跨层修改 | 合并历史必须可按领域审查，干净 checkout 重跑门禁 | 保留“后端语义 / 前端体验 / 生产门禁 / 文档”四个逻辑提交，不把 119 个文件压成一个不可审查提交 |
| 六变体重建资源 | 历史完整冷建约 16 分 23.3 秒、峰值 RSS 876.758MiB；新实现真实副本仅候选重建 4.62 秒且六变体 0ms 复用 | 只有统计 fingerprint 真实变化才允许承担完整六变体成本；普通 SHA 必须走复用 | 保持 MemAvailable/disk fail-closed；使用持久 resume artifact 续建，禁止以延长 timeout 掩盖索引与统计耦合 |
| 既有外键债务 | 搜索孤儿为 0，但全库仍有 7,831 条非搜索违规 | 不得把历史违规误归因于 migration 34，也不得在搜索发布中盲删 | 单独建立数据治理任务，按缺失父表分类、回溯来源、设计修复/保留策略；修复前另做 Online Backup，并逐类对账详情页和统计 |
| 静态检查基线 | 本轮变更范围 ESLint/mypy 通过；全仓仍有既有 ESLint/mypy 错误 | CI 必须能区分既有债务与本次新增错误 | 继续对 changed files 硬门禁，新增 baseline ratchet；全仓清零作为独立治理，不把无关大修混入搜索发布 |
| 前端依赖安全 | Web build 的 npm audit 仍报告 15 项，其中 10 项 high | 公共入口发布前必须完成 direct/transitive、runtime/dev-only 和可利用性分类 | 先执行 `npm audit --json` 与依赖路径核对；优先无破坏升级 direct runtime 依赖，对需要 major upgrade 的项目建立带回归矩阵的独立修复，不直接使用 `--force` |
| 远程运行面 | 本地 staged/rollback 与真实容器零写入已通过；run `31954513187`、`31956683140` 的 verify/profile matrix/API build 通过，但 TCR layer push 三次有界失败，deploy 均跳过；目标 SHA manifest 不存在且 `main` 未覆盖 | 先解除 runner→TCR 上传阻塞，再要求对应 SHA 的 build、双镜像 manifest、SSH deploy、runtime exact gate 全绿 | 首选同地域受控 runner；备选受信 registry 中转并由生产侧按 digest 同步。继续按 commit SHA 发布并保留 workflow 记录；不得手工覆盖 `main`、绕过容量/漂移/六变体/网关/健康门禁或开放 3000/3001/3002/8000 公网端口 |

因此，本轮搜索代码和发布机制已具备按 SHA 的本地/CI 前置条件，但远程生产发布当前为
**Blocked — TCR upload**，不能表述为已经部署。阻塞早于 SSH 与搜索预建，不影响 A–D 的实现结论，
也不能通过延长搜索重建 timeout 处理。目标服务器容量、数据漂移与运行时语义仍由 workflow 自动
fail closed，不能靠人工口头确认放行。历史外键、依赖安全分类与全仓静态债务必须有独立台账和
不新增门禁，但不应与本轮搜索代码混合修复。

## 10. 后续维护规则

1. 不得让候选 GET 重新调用完整播放帧或 Billboard 计算。
2. 新增影响详情事实的设置或治理 mutation，必须 bump 对应持久 revision，并同步扩展 semantic base、
   六变体 snapshot-set 和失效矩阵。
3. public 新 GET 默认不开放；搜索公开路径继续保持纯读取和 fail-closed。
4. 搜索 schema、标准化、排序或 context 语义改变时提升对应版本；reader 必须同时校验 ready 与当前
   builder version，先构建新 generation/snapshot-set 再切换。
5. 性能回归使用只读 probe；候选 warm P95 超过 80ms 或响应超过 8KiB 时阻止发布。
6. rebuild 只能写入与调用连接相同的 JobQueue 数据库；精确 ready 快照必须直接命中，禁止启动或
   热重载重复排队。
7. 快照裁剪不得依赖连接级 `PRAGMA foreign_keys`；必须显式先删 context 再删 meta，并保留
   foreign_keys=OFF 回归。
8. 生产镜像必须继续执行 SQLite 文件名与 magic-header 双门禁；嵌套 fixture 不能重新进入镜像。
9. 生产新 SHA 必须先在 Online Backup 副本执行自适应精确门禁：候选版本变化只重建候选，统计
   fingerprint 变化才构建对应变体；不得直接在 live DB 冷构建。
10. startup catch-up 与 cache warmup 必须保持独立；副本预建关闭前者，正常 private 生产默认开启。
