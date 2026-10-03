# 全站封面优化实施与验收

> 问题 ID：`SS-2026-10-03-001`
> 状态：实施中；以下阶段按现场证据继续更新。
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

首次默认完整门禁 `20261002T172345.686091Z-a98818adb0b2`：preflight、quality、backend 通过，API 因隔离副本缺失 ready 搜索统计快照失败，浏览器阶段未运行，整体为 **FAIL**。未降低标准或把局部结果改称完整 Pass。只在该隔离副本运行既有重建工具，四变体均 ready，播放记录仍为 94,760；第二轮 `20261003T013737.134181Z-8f78c476dd5c`：preflight、quality、backend、API 均通过（3,168 seeded + 187 integration，搜索 warm P95 19.776ms），browser-routes 的年度 mobile 因 sidecar `store_prepared_key` 单次 SQLite `disk I/O error` 500 而失败，整体仍 **FAIL**。副本 quick_check=ok、磁盘 68GiB 可用；重启自己创建的后端，统一 `/private/tmp` canonical DB/年度 sidecar 路径，随后 4 路并发 × 20 请求均 200。该复测不证明路径别名是唯一原因，失败日志仍保留。

第三轮 `20261003T020457.982894Z-73929d0d39cf` 的 preflight/quality 通过，但 backend 被另一工作区正在执行的共享门禁锁阻止（`BLOCKED`）。未终止其他任务或绕过共享锁；包含浏览器发现后的版本封面修正，待资源可用后重新执行默认完整门禁。

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
| 播放排行 | 50,590 / 4,829 | 待最终配对汇总 |

首页随机回归卡片可能换图，须按共同封面 ID 配对体积，不能简单逐次相减。首屏稳定时间包含 API 与浏览器准备，关键图片完成时间另行登记。已有图片样本均无坏图。

生产 2022–2026 年度接口均返回 404 `年度总结尚未由管理入口生成`，此基线不能当零图片通过或计算图片收益。已在隔离副本生成真实 2026 V2 artifact，用 HEAD 旧前端（5184）和修复前端（5173）对同一 API 测年度章节；生产验收将由已有私有入口有界准备年度 artifact，再测公开真实内容。

## S5 发布及线上验收

待填写固定 SHA、Actions、Online Backup、补建资源与 HTTP/浏览器结果。
