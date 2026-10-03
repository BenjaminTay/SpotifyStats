# 全站封面优化实施与验收

> 问题 ID：`SS-2026-10-03-001`
> 状态：S0–S5 已完成；本地默认完整全栈 PASS，业务版本 `814ea7cb` 已正式发布，生产资产、实际 HTTPS 与四视口交互验收完成。
> 最后核验：2026-10-03。
> 实施基线：本地 `7b9a1f4e`；生产 `3a4e6310`（2026-10-03 SSH 核验，三服务 healthy）。

## S0 基线和收益依据

前轮现场检查：首页 11 张均原图，其中三个小图显示 54px；播放记录当时挂载 68 张均原图，典型显示 40px；播放排行 20 张均缩略图。音乐档案和当前年度 V2 原图消费由有效组件确认；年度页面零图片的初始观察不作为图片加载验收。

本轮读取生产首页六张样本，保持内容和比例，使用既有 quality=78/method=4 对比：

| 原图 | 原图 bytes / 尺寸 | 160 bytes | 320 bytes | 640 bytes |
| --- | --- | --- | --- | --- |
| albums/2334 | 85,652 / 469×640 | 3,342 | 9,742 | 32,940 |
| albums/20464 | 81,676 / 640×640 | 2,440 | 6,636 | 17,870 |
| albums/20438 | 44,544 / 640×640 | 1,642 | 5,116 | 13,488 |
| artists/68 | 56,673 / 640×640 | 2,626 | 6,808 | 17,688 |
| artists/1 | 90,644 / 538×640 | 3,406 | 9,298 | 25,966 |
| albums/1225 | 126,174 / 640×640 | 2,792 | 8,700 | 32,978 |

640 保持这批源图尺寸，体积降低约 61.5–78.1%；320 显著适用于中图。该结果证明中大图编码优化有收益，不代表用户网络下的实际加载时间。原始 JSON 在本地忽略目录 `output/playwright/cover-images/variant-feasibility.json`。

用户实际入口：`https://stats.benjaminlei.site`。修复前核心页 cold/warm 各三次已采集，结果见 S4。

## S1–S3 实施

### 当前有效入口库存

| 区域 | 组件/消费链 | 基础档位 |
| --- | --- | --- |
| 首页双版 | `HomePrimitives` + Desktop/Phone 显式场景 | 行 160；旁卡 320；主视觉/大卡 640 |
| 播放统计/排行 | `RecentPlaysSection`、`StatsTables`、`MobileRankList` → 公共封面 | 160 |
| 播放记录 | `PlaybackRecordsPrimitives`、`DiscoverySection`、`HourlySegmentsCard` | 160 |
| 音乐档案双版 | 公共实体行、Library、OtherMedia、ArchiveCover | 行 160；Phone 封套 320；Desktop 封套 640 |
| 年度 V2 双版 | `YearlyReviewPrimitives` → 八章、Phone epilogue 明确覆盖 | 小图 160、中图 320、手机大卡 640 |
| 音乐查找 | Quick Open / 完整页 → `MusicSearchResults` 公共封面 | 160 |
| 音乐详情 | header / phone hero / sheet、版本列表、成员排行 | 摘要 320、专辑手机大图 640、行 160 |
| Billboard 六区域 | 周榜、冠军、总榜、年榜、Records、Versus 共用已有 helper | 160 |
| 设置及兼容入口 | ArtistIdentity、TrackCreditManager、VersionMerge、LegacyTrackDetailRedirect | 160 |
| 社区 | PostCard / PostDetail、AccountAvatar / account banner | 预览 320、多图详情 640、单图完整展示原图；静态头像/banner 原来源 |

高 DPR 首次渲染会提高档位：160 在 DPR > 2 使用 320；320 在 DPR > 1.5 使用 640。纯 URL 映射与显示选择分开；保留 query/hash 和旧 `.thumb.webp` 文件。没有虚假 `srcset` 宽度，也没有先加载原图再改 URL。

图片失败状态绑定源 URL 或图片 key：首页、年度隐藏失败图片换实体恢复；Phone 行、详情、设置头像和社区账号头像切换恢复。列表 lazy/async、首页关键 Hero eager/high；保留既有尺寸和布局。

### 例外与非当前入口

- 旧 `pages/yearly-review` 六组件由旧 `CustomSummary` 组合；当前页面只使用 V2。`AlbumEraOverviewSection`、`AlbumReleaseCompositionSection`、`AlbumEnrichmentView` 无当前详情入口，未恢复旧页签。
- 社区九张静态头像 400×400 合计 161,666B；十张静态 banner 1280×426 合计 814,539B。它们不属于音乐封面路由，维持原 URL，头像 lazy/async、首屏 banner async。
- Spotify profile 头像、LLM provider logo、外部节目/帖子图片不通过本地派生接口；合理的原图完整查看保持原图。CSS 背景只有内嵌 NoiseOverlay SVG，无音乐封面背景漏项。

### 后端与资产

固定 160/320/640；原图字节不变、保比例不放大。GET 不编码、不触发公开写任务，缺失/过期短缓存回退，命中 WebP 七天 private 缓存及 304。生成时比较源状态，派生文件记录源 mtime，避免发布窗口源替换被误认 current。

本地验收使用 SQLite Online Backup 副本，从 schema 81 加性升级至 85，源正式库保持 81；两者播放记录均 94,760。隔离 covers 4,358 张原图，生成 13,074 个变体，`failed=0`。派生目录约 260MiB；该数字属于本地副本，不等同生产资产数量。

完整 quality 首次发现 HEAD 已存在的四个测试文件八处 `Callable.cache_clear` 类型错误，最小替换为无默认值 `getattr(..., 'cache_clear')()`，保留原严格清理行为；对应 43 项测试、定向 mypy/ruff 通过。没有更改业务或降低门禁。

## S4 本地验收

后端图片定向 44 项通过；前端最终专项 5 文件 / 91 项及 build 通过。主体实现阶段提交 `f139ec4d8754cc79f30d2b819956021e23e63572`，提交 hooks 全部通过；验收发现的版本来源封面修正随后续验收阶段收口。

首次默认完整门禁 `20261002T172345.686091Z-a98818adb0b2`：preflight、quality、backend 通过，API 因隔离副本缺失 ready 搜索统计快照失败，浏览器阶段未运行，整体为 **FAIL**。未降低标准或把局部结果改称完整 Pass。只在该隔离副本运行既有重建工具，四变体均 ready，播放记录仍为 94,760；第二轮 `20261003T013737.134181Z-8f78c476dd5c`：preflight、quality、backend、API 均通过（3,168 seeded + 187 integration，搜索 warm P95 19.776ms），browser-routes 的年度 mobile 因 sidecar `store_prepared_key` 单次 SQLite `disk I/O error` 500 而失败，整体仍 **FAIL**。副本 quick_check=ok、磁盘 68GiB 可用；重启自己创建的后端，统一 `/private/tmp` canonical DB/年度 sidecar 路径，随后 4 路并发 × 20 请求均 200。该复测不证明路径别名是唯一原因；失败结论按原运行记录保留。后续环境清理了 `/tmp` 和旧门禁临时目录，旧原始日志已不可用，不声称它们仍可重查。

第三轮 `20261003T020457.982894Z-73929d0d39cf` 的 preflight/quality 通过，但 backend 被另一工作区正在执行的共享门禁锁阻止（`BLOCKED`）。未终止其他任务或绕过共享锁；资源可用后包含浏览器发现的版本封面修正重新执行默认完整门禁，结果见下一段。

环境恢复后，在忽略目录 `output/cover-acceptance/runtime/` 重建主库与六个 sidecar 的 Online Backup 副本，并显式隔离所有缓存路径。源库仍为 schema 81，副本 85；五张原始表数量一致，三尺寸 13,074 文件失败 0，搜索四变体和 2022–2026 年度缓存 ready。默认完整门禁 `20261003T064109.521824Z-87d6bf4f6ce8` 使用固定 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e`，默认八个必需阶段同轮全部 **PASS**，总耗时 1,512,891ms（约 25.2 分钟）；前端 722 passed / 4 skipped、后端 seed 3,178 passed + integration 187 passed，API smoke 157/157、boundary 113/113，热 P95 全部小于 500ms，Chromium/Firefox/WebKit 全通过。未运行 optional；不推断 production preview 或物理手机已通过。新门禁和资源证据保存在 `output/cover-acceptance/`，不再放入会被环境清理的临时目录。

初轮浏览器覆盖 24 个 URL × 四视口 × cold/warm 共 192 样本；Desktop/Phone 五个核心页各三对共 60 样本。初始首页 warming 和统计 API 未准备样本单列，最终重测目标图片均无破图、无待加载。Compact 排行按设计隐藏封面；对决需添加对象；Phone 设置首页无图，但版本归并子页成员图片已实际验收。Phone 390×844 DPR 3、Compact 768×1024 DPR 2、Desktop 1280×900 DPR 1/2；这些是桌面 Chromium 模拟视口，不声称手机真机通过。

| 相同实体配对图片集合 | Desktop 原 / 新 bytes（减少） | Phone 原 / 新 bytes（减少） |
| --- | --- | --- |
| 首页，共同 8 个封面 ID | 646,210 / 223,611（65.40%） | 639,382 / 107,614（83.17%） |
| 播放记录，40 / 21 个共同实体 | 4,576,830 / 154,449（96.63%） | 2,565,445 / 269,333（89.50%） |
| 音乐档案，32 / 17 个共同实体 | 3,466,976 / 225,537（93.49%） | 2,031,486 / 255,731（87.41%） |
| 年度 2026，同副本旧前端与修复前端，26 / 24 个共同实体 | 2,996,053 / 219,970（92.66%） | 2,708,114 / 556,107（79.47%） |

体积按相同 route/viewport 的共同 cover type/id 配对；同一实体请求不同尺寸时累加实际 URL，每个实体取三次 cold 样本中位数后再汇总。首页整体含保留原始尺寸的大视觉，不能把其整体 65.40% 减少当作小图集合目标。

已有播放排行 Desktop 15 张共同封面仍为 50,590B；Phone 采用 DPR 3 较清晰的 320 档位，50,590B → 149,996B（增加 196.49%）。本次不会把它表述为既有榜单的额外体积收益。

以上是图片体积，不能用本地页面耗时与公网基线相减推断线上速度。屏幕密度不同会选择不同档位，因此手机体积可能比 Desktop 高；最终线上速度在 S5 独立测量。

真实交互已覆盖 Phone 年度章节、展开月账本及切六月、档案进入收藏库/翻页/切艺人/实体链接、Settings 版本组成员、对决添加两个实体。关闭的 `<details>` 图片原被探针误判可见，已改用 `checkVisibility`；屏外延迟挂载图片在重新进入视口后加载，未改为 eager。独立交互 context 拦截一张封面，确认占位及切换实体后恢复；该 context 未用于速度与缓存指标。

真实多版本 Track 1563 展开发现接口版本行仍返回 Spotify 原图，即使 albums/602 已有本地缓存。修正 `details.py` 的 legacy/L1 曲目版本、L2/L3、专辑版本和来源拆分，复用既有智能封面 resolver；仅 provider 有源时保持外部 URL，无来源不凭 ID 伪造封面。来源拆分按目标 album ID 查询，移除全表封面映射。43 项相关契约（含新 10 参数项）、正式 mypy hook、ruff 通过；不写原始表、图片或更改统计 builder。

复验两版本统计 32/2、94%/6%、主版本和实体链接正确；Desktop 两张 32px 行图均 `.thumb.webp`，Phone DPR 3 均 `.320.webp`，无坏图/待加载，两行共用一次资源请求（6,797B / 23,742B）。对决补测完整终态：两实体统计及只读计算均 200，pending API 为空，图片与实际数值正常。

Private 本地年度页面按既有行为自动 POST 派生缓存 prewarm；在隔离副本中 2022–2026 已 ready，未修改原始播放数据。探针不主动调用管理写接口，不把全部页面导航称作纯 GET。原始 JSON、截图、交互请求及对比汇总保存在本地忽略目录 `output/playwright/cover-images/`。已实际检查 Desktop、Phone、Compact、高 DPR 截图；源图本身分辨率不足单列，不放大派生图伪装细节。

### 用户 HTTPS 修复前基线

fresh browser context 为 cold，同一 context 普通 reload 为 warm（保留浏览器 HTTP cache，未通过 request interception 禁用缓存）。三次中位数如下；bytes 是唯一本地图片 encoded body，并不表示 warm 仍重新传输全部图片：

| 页面 | Desktop cold bytes / 首屏稳定 ms | Phone cold bytes / 首屏稳定 ms |
| --- | --- | --- |
| 首页 | 639,363 / 5,395 | 557,028 / 4,410 |
| 播放记录 | 4,576,830 / 9,907 | 2,565,445 / 9,183 |
| 音乐档案 | 3,466,976 / 5,794 | 2,031,486 / 4,416 |
| 播放排行 | 50,590 / 4,829 | 50,590 / 4,369 |

首页随机回归卡片可能换图，须按共同封面 ID 配对体积，不能简单逐次相减。首屏稳定时间包含 API 与浏览器准备，关键图片完成时间另行登记。已有图片样本均无坏图。

修复前生产 2022–2026 年度接口均返回 404 `年度总结尚未由管理入口生成`，此基线不能当零图片通过或计算图片收益。已在隔离副本生成真实 2026 V2 artifact，用 HEAD 旧前端（5184）和修复前端（5173）对同一 API 测年度章节；生产随后通过已有私有入口仅准备 2026 年，再测公开真实内容。

## S5 发布及线上验收

### 固定版本发布

业务版本 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e` 经[正式流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37105334591)发布，所有 jobs success；北京时间 2026-10-03 15:25 部署完成。CI 质量、三模式、镜像 CAS 校验/传输、digest pull、dual 运行时门禁通过。正式备份 `spotify-stats-pre-release-814ea7cb8cde-20261003T072312Z.db`；搜索预检精确复用，`source_equivalent_exact_statistics_resume`，运行时 v12 四变体 ready、orphans=0。当前与回退镜像分别固定 `814ea7cb` / `3a4e6310`，未执行回滚。

服务器三容器均 healthy，公开 HTTPS 与 loopback 均返回新 SHA 和 `public-readonly/showcase`；settings/editing/imports/ai 等禁用。后端不映射公网端口，网关保持 127.0.0.1:3001/3002；未修改外层 HTTPS/Tailscale。

### 资产与线上验收

发布前基线：schema 85；plays 94,760、tracks 10,026、track_artists 10,496；4,360 张原图合 510,381,092B。原图逐文件 size/mtime 清单保存在 `output/cover-acceptance/production-before.json`。发布后先等待启动预热结束，再按 200 张待生成原图分批补建 320/640；失败即停，CPU/RSS 同步采集。补建 22 个生成批次 + 最后零待生成扫描，新增 8,720 个文件，failed=0，耗时 307.32 秒。160/320/640 各 4,360 文件且全部 current；体积分别为 18,186,416 / 54,375,226 / 174,244,560B。原图逐文件 size/mtime 清单完全一致，原始表数量保持 94,760 / 10,026 / 10,496。连续 Docker stats 采样中，后端容器（含补建子进程）峰值 CPU 130.17%、内存 1,048.58MiB；磁盘仍约 17GiB 可用，未与年度冷构建同时执行。

HTTPS 和通过 SSH 隧道读取的服务器 public loopback 分别验证 albums/2334、artists/1 三档样本：WebP/MIME 正确，长边 160/320/640、保持源比例且不放大，七天 private 缓存及各六次 ETag 条件请求均 304。非方图 640 档与源尺寸相同，字节分别 32,940 / 25,966B。

由既有私有入口仅请求 2026 年确定性 prewarm，约 78.87 秒确认 ready、公网读取 200；没有请求 LLM 或其他年份冷构建。用户实际 HTTPS 浏览器三次冷/热及四视口结果已完成，见以下记录。公开边界按既有合同分别核验：展示过滤参数 GET `/api/settings` 200；PUT settings 和 POST 年度 prewarm 均 403；LLM profiles 禁用接口 404。HTTPS 与服务器 loopback 结果一致。浏览器首轮被其他工作区共享锁阻止，记录 BLOCKED 后等待；其自行释放后才取得本任务官方锁开始采样，未干预或绕过。


### 真实 HTTPS 核心三次冷/热

五核心 × Desktop/Phone × 三对 cold/warm 共 60 样本，全部 images_observed；broken/pending/本地原图请求均为 0，逐屏滚动到底。相同实体配对结果：

| 页面 | Desktop 旧 / 新 body bytes（减少） | Phone 旧 / 新 body bytes（减少） |
| --- | --- | --- |
| 首页，共同 7 个 ID | 557,028 / 200,395（64.02%） | 557,028 / 100,231（82.01%） |
| 播放记录，40 / 21 个 ID | 4,576,830 / 154,449（96.63%） | 2,565,445 / 269,333（89.50%） |
| 音乐档案，32 / 17 个 ID | 3,466,976 / 225,537（93.49%） | 2,031,486 / 255,731（87.41%） |
| 已优化播放排行，15 / 15 个 ID | 50,590 / 50,590（不变） | 50,590 / 149,996（增加 196.49%） |

三次 cold 首屏图片请求 responseEnd 中位数，播放记录 Desktop 9,098.8 → 4,522.5ms、Phone 8,489.4 → 4,586.9ms；首屏稳定时间约 9,906.6 → 5,163.0ms、9,183.3 → 5,314.7ms。首页 Phone 与档案 Phone 整体首屏耗时没有明显改善，不声称所有页面同比提速。探针可见性和回访方法有所改进，稳定时间包含 API/内容准备；上述是本机到同一真实 HTTPS 的观测，不把全部差值归因于压缩，也不外推物理手机网络。

30 组冷/热对中 672 个相同本地图片 URL 的 warm transferSize 全部为 0；首页随机回归卡片新增 URL 单列。其余四核心 warm 图片 transfer 三次中位均 0。编码 body 仍可由 Resource Timing 返回，不等于热缓存重新传输。

年度旧公网基线为 404，故不计算公网年度前后收益。新年度 2026 Desktop/Phone 均真实有图并完成三对；首屏为排版和 CSS 年度封面，无 img，因此首屏图片 responseEnd=null 是正确空值，完整章节图片另计。三次实际文件和截图见忽略目录 `output/playwright/cover-images/s5/`。

core 探针 JSON 含 completed_at 和完整 60 样本；ignored 启动 wrapper 在探针结束后因运行中追加分支发生尾部 shell EOF，官方锁随其退出释放。保留该执行尾部错误，不声称 wrapper exit0，也未重复已完整完成的测量。后续 public 矩阵使用语法检查通过且运行期间不再改动的 wrapper；该问题未影响应用源码、采样期间锁或 core 结果。

### 公开四视口矩阵与交互

24 个公开 URL × 四视口 × cold/warm 共 192 样本于 2026-10-03 08:16:52 UTC 完成，wrapper exit0。178 个样本实际观察到图片，另 14 个为预期无可见图：对决初始空队列 8 个、Compact 三类排行冷热 6 个。后者 CSS 隐藏封面，但仍请求 15/20/20 个 160px 派生图，warm transfer 为 0；不可把零可见图片称作零网络请求。矩阵 broken/pending image/本地音乐原图/API ≥400/request failure 均为 0。DOM 清单含 622 个唯一音乐派生 URL 与 9 个社区静态头像；未发现外部音乐封面漏项。

独立交互确认 15 个有效步骤，全部 broken/pending image/pending API 为 0：

- Track 1563 Desktop/Phone 两版本展开，32/2 播放、94%/6% 与两个实体链接正确；行图分别 `.thumb.webp` / `.320.webp`。
- Phone 对决两个实体统计及只读 POST 均 200、found=true；379/315 播放、22.6/15.5 小时及 12/1 胜终态实际出现。
- Phone 年度八章图片、月账本展开、切六月、年度荣誉、完整榜单；音乐档案收藏库两页、艺人列表与 A-Mei Chang 详情链接。
- 专辑详情等待内容高度稳定后，四视口均实际滚动到有限页面终点。社区无限列表按 80 屏有界采样，不声称加载全部无限内容。

最初三个定位器异常（嵌套 main strict violation、精确 heading 等待超时）原样保留；修正忽略目录探针后只补跑对应交互。档案链接早期截图 URL 已变但 React 目标尚未挂载，标为 Partial；最终显式等待目标艺人标题与 hero 后通过，不把早期截图算作目标详情验收，也不纳入速度指标。所有本任务浏览器和官方锁 holder 已退出，未修改其他工作区服务。

已实际检查 Desktop、Phone、Compact、Desktop DPR 2 和版本/月账本/目标艺人截图。详情 4455/1563 首次内容就绪约 19.5/16.9 秒，包含统计 API 准备；不是封面请求自身耗时，本次未改造统计计算。物理手机与限速网络未测，服务器/CDN 的 cold 状态未知；保留高清 Phone 榜单增加体积及部分页面整体首屏无明显改善的边界。

最终服务器复核仍为三容器 healthy、业务 SHA `814ea7cb`、public-readonly。浏览器结束后再采集 `production-final.json`：4,360 张原图逐文件 size/mtime 与发布前完全一致，三档各 4,360 current，plays/tracks/track_artists 仍 94,760/10,026/10,496。该核验是文件 stat 与表数量比较，不称作完整内容哈希或全部数据库内容证明。

### 交付结论与证据

S0–S5 完成，问题 `SS-2026-10-03-001` 闭环。业务发布和线上验收固定 `814ea7cb`；最终文档收口提交不改变生产镜像，不混入其他任务的 Album 元数据迁移。

| 证据 | 本地忽略目录 |
| --- | --- |
| 默认八阶段完整 PASS | `output/cover-acceptance/fullstack-accepted-summary.json`、`gates/20261003T064109.521824Z-87d6bf4f6ce8/` |
| Actions 发布与服务器门禁 | `output/cover-acceptance/release-view.json`、`release-deploy.log` |
| 补建与资源、原图/原始表比较 | `output/cover-acceptance/production-backfill.jsonl`、`production-backfill-resources.json`、`production-before.json`、`production-final.json` |
| 两入口格式、缓存及公开边界 | `output/cover-acceptance/production-https-headers.json`、`production-loopback-headers.json`、`production-public-boundaries.json` |
| 实际 HTTPS 核心/矩阵/交互、截图及汇总 | `output/playwright/cover-images/s5/https-core/core.json`、`https-public/matrix.json`、`https-interactions/report.json`、`result.json`、`result.md` |

原始证据含个人音乐数据，保留在忽略目录，不提交 Git 或打入镜像。报告登记可审查的测量方法、汇总、失败与完成边界。
