# 音乐档案后端与多端交付

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。音乐档案从首屏白名单、收藏统计到Desktop、Phone及旧链路退役合并记录。Phase 0初步候选与后续正式分母分别保留，旧账号聚合的阶段兼容不代表当前入口。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [音乐档案 Phase 0 与 archive-overview 交付记录](#音乐档案-phase-0-与-archive-overview-交付记录)
- [音乐档案统计后端交付记录](#音乐档案统计后端交付记录)
- [音乐档案 Desktop / Compact 交付记录](#音乐档案-desktop--compact-交付记录)
- [音乐档案 Phone 交付记录](#音乐档案-phone-交付记录)
- [音乐档案 Phase 4 退役与收口交付记录](#音乐档案-phase-4-退役与收口交付记录)

## 音乐档案 Phase 0 与 archive-overview 交付记录

原记录：`2026-08-13-account-archive-phase-0-delivery.md`。

日期：2026-08-13
分支：`codex/account-archive-rebuild`
范围：数据止损、来源治理、严格首屏接口与只读证据；不包含正式页面 UI。

### 结论

本批次已建立可继续重构的本地优先底座：重复导入 `YourLibrary.json` 不再清掉已有收藏日期；收藏日期明确记录为 `oauth / manual / legacy`；新接口只返回音乐档案首屏所需白名单字段，不包含 profile、原始搜索词、prompts、inferences 或 banned item 明细；接口运行时不调用 Spotify Web API。

本阶段曾暂时保留旧 `/api/account` 与 `/api/account/collection-insights` 作兼容；新页面从一开始只消费分拆后的严格接口。两条旧路由现已在 Phase 4 正式删除，见同日 Phase 4 交付记录。

### 已落地

- Migration 31：新增 `saved_tracks.added_date_source` 与 `account_archive_state` 两类 revision。
- `YourLibrary` 导入：按 `track_uri` 携带已有日期与来源；返回保留/缺失日期数；失败 importer 回滚未提交写入。
- Spotify 显式同步：只补空日期，来源记为 `oauth`；不覆盖 `manual / legacy` 现有日期；更新后提升日期 revision 并清理相关缓存。
- `GET /api/account/archive-overview`：严格 Pydantic 契约、最多四个封面角色、覆盖期、数据状态、日期来源、关联与时长覆盖。
- 缓存：以账号导入 revision、日期 revision、收藏/播放边界和实体治理 revision 组成的 opaque data revision 分流；TTL 300 秒。
- `scripts/account_archive_probe.py`：只读核验真实 SQLite，可设置期望收藏数和日期数作为回归门槛。

### 真实 SQLite 只读证据

数据库：原 worktree 的 `data/spotify_stats.db`，以 SQLite `mode=ro` + `query_only` 打开，未执行 Migration 31，未修改数据。

| 指标 | 结果 |
|---|---:|
| 收藏歌曲 | 800 |
| 有收藏日期 | 800（100%） |
| 可关联本地播放历史 | 762（95.3%） |
| 有准确曲长 | 800（100%） |
| 已知收藏曲总时长 | 195,475,714 ms |
| 收藏专辑 / 艺人 / 节目 | 250 / 59 / 3 |
| 歌单 / 歌单曲目 | 27 / 681 |
| 收藏日期范围 | 2022-06-30T17:25:48Z 至 2026-05-12T07:32:42Z |
| 播放日期范围 | 2022-07-01 至 2026-07-24 |
| 7 / 30 / 90 / 365 天仅按右边界筛选的初步候选 | 800 / 800 / 794 / 584 |
| 非法收藏日期 | 0 |

由于现有日期生成时尚未记录来源，Migration 31 会诚实回填为 `legacy`，不会倒推为 `oauth`。今后通过显式 Spotify 同步新增的日期才标记为 `oauth`。

> 后续 `collection-cohorts` 已加入 URI 匹配、规范曲目去重、左侧数据覆盖和有效播放语义，正式合格分母修正为 761 / 761 / 755 / 560。上表只保留为 Phase 0 初步只读候选证据，不能作为正式回访率分母。

### 接口预算验收

在真实数据上通过独立 FastAPI app 挂载同一路由、覆盖只读连接后采样：

| 指标 | 预算 | 结果 |
|---|---:|---:|
| HTTP 状态 | 200 | 200 |
| raw response | ≤ 40 KB | 1,936 bytes |
| 冷响应 | ≤ 750 ms | 约 157–200 ms |
| 热响应 p95 | ≤ 75 ms | 约 6–9 ms |
| 缓存采样 | revision 分流 | 1 miss / 11 hits |

真实数据状态为 `partial`，原因不是日期缺失，而是仍有 38 首收藏无法关联到本地曲目/播放事实。收藏浏览与收藏时间线可用，收藏—播放交叉分析按 95.3% 覆盖明确降级。

### 自动验证

- account archive 新增单元/接口测试：11 项通过。
- migration 全量幂等与核心表测试：通过。
- account route response model / OpenAPI schema 契约：通过。
- Ruff check、Ruff format check、`git diff --check`：通过。

### 下一批

统一上下文、统计接口、多端页面及旧链退役均由后续章节完成，见[统计后端](#音乐档案统计后端交付记录)、[Phone](#音乐档案-phone-交付记录)和[Phase 4](#音乐档案-phase-4-退役与收口交付记录)。


## 音乐档案统计后端交付记录

原记录：`2026-08-13-account-archive-journey-cohorts-delivery.md`。

分支：`codex/account-archive-rebuild`
范围：统一统计上下文、收藏旅程、收藏前后关系、固定窗回访、关系矩阵、90 天回归、有限发现路径、当前收藏库分页和播客/视频摘要；不包含正式页面 UI。

### 已落地

- `account_archive_filter_v2`：统一 `min_ms`、连续合并、动态阈值、默认 5 分钟实际空闲边界、L1/L2/L3、UTC 观察边界、北京时间展示日期和数据 revision。
- `GET /api/account/collection-journey`：年度/季度收藏增长、准确曲长、发行年份跨度和第 100 / 200 / 400 / 800 首等倍增收藏里程碑。
- `GET /api/account/collection-cohorts`：记录期内首次播放到收藏、对称 30 天事件窗、四个互补生命力窗口、兼容固定窗回访、-4…12 周事件曲线和互斥关系状态。
- `GET /api/account/returns`：相邻有效播放至少间隔 90 天、且后一事件发生在收藏后的回归；最近回归、最长间隔和当前沉睡推荐均按规范实体去重。
- `GET /api/account/discovery`：NFKC 查询去重、5 分钟搜索 burst、burst 级时段分布、interaction 类型覆盖和严格顺序的曲目发现有限漏斗。
- `GET /api/account/library/{entity_type}`：歌曲、专辑、艺人、歌单四类当前快照的服务端搜索、排序和分页；默认 20、最大 50，响应不返回 Spotify URI。
- `GET /api/account/other-media`：播客有效收听与节目回访摘要、视频有效播放摘要、带封面的本地可识别视频歌曲 Top 3，以及兼容音频/视频时长对照。
- Extended Streaming History 的 `ts` 按播放停止时间解释；关系窗口使用 `ts - ms_played` 作为逻辑事件开始时间，避免把按下收藏时正在播放的同一次事件算作回访。
- 所有新接口均为严格 Pydantic 白名单，不调用在线 provider；重统计使用 revision-keyed TTL cache，收藏库以短 SQL 分页直接读取。

完整统计定义见 `docs/reference/account-archive-statistics.md`。

### 真实 SQLite 只读结果

原交付快照使用旧的无界上下文；2026-08-15 起默认上下文改为 `min_ms=30000`、`merge_enabled=true`、`dynamic_threshold=true`、`max_merge_gap_minutes=5`、`merge_level=2`。下列历史数值尚未按新口径重写，不应与当前页面直接对账。

#### 收藏旅程

| 指标 | 结果 |
|---|---:|
| 当前收藏 | 800 |
| 有效收藏日期 | 800 |
| 准确曲长覆盖 | 800 / 800 |
| 已知总时长 | 195,475,714 ms，约 54.3 小时 |
| 发行年份跨度 | 1952—2026 |
| 2022 / 2023 / 2024 / 2025 / 2026 新增 | 109 / 104 / 275 / 215 / 97 |
| 收藏里程碑 | 第 100 首 Fancy / 第 200 首 NASA / 第 400 首 Because of You / 第 800 首 永恆的主題 |

#### 收藏关系

| 指标 | 结果 |
|---|---:|
| 当前收藏原始行 | 800 |
| 可匹配本地曲目 | 762 |
| L2 规范收藏实体 | 762 |
| 无法关联 | 38 |
| 当前上下文有效逻辑播放 | 64,986 |
| 可计算“记录期首次播放→收藏” | 704 |
| 无观察到收藏前播放 | 58 |
| 同日 / 1–7 / 8–30 / 31–90 / 90+ 天 | 200 / 134 / 81 / 75 / 214 |
| 对称 30 天完整样本 | 723 |
| 前窗 / 后窗有效事件 | 1,937 / 8,580 |
| 前更多 / 相等 / 后更多 | 62 / 45 / 616 |

底层兼容固定窗结果：

| 窗口 | 合格实体 | 有回访 | 当前收藏回访率 |
|---|---:|---:|---:|
| 7 天 | 761 | 726 | 95.4% |
| 30 天 | 761 | 749 | 98.4% |
| 90 天 | 755 | 750 | 99.3% |
| 365 天 | 560 | 560 | 100.0% |

消费页面改用互补的生命力窗口：

| 窗口 | 合格实体 | 有播放 | 比例 |
|---|---:|---:|---:|
| 收藏后 7 天内 | 761 | 726 | 95.4% |
| 收藏后第 8–30 天 | 761 | 672 | 88.3% |
| 收藏半年后至观察期末 | 685 | 636 | 92.8% |
| 收藏一年后至观察期末 | 560 | 498 | 88.9% |

当前关系状态：最近 90 天活跃收藏 513，沉睡收藏 249，最近 90 天至少 5 次但未收藏的规范曲目 94，无法关联收藏 38。

#### 找回音乐

| 指标 | 结果 |
|---|---:|
| 可进行相邻事件分析的收藏实体 | 761 |
| 至少一次 90 天回归的实体 | 526 |
| 回归事件总数 | 1,188 |
| 多次回归实体 | 302 |
| 最近 30 / 90 天回归实体 | 53 / 196 |
| 当前沉睡实体 | 249 |
| 已观察最长回归间隔 | 643 天 |

回归事件要求后一事件严格晚于收藏时间。收藏时正在播放、但逻辑开始时间早于 `added_date` 的同一次播放不会被误计为回归。历史上发生过回归的实体仍可能在当前锚点再次进入沉睡，两者不是互斥的终身标签。

#### 发现路径

| 指标 | 结果 |
|---|---:|
| 原始搜索行 / 精确去重后 | 2,239 / 2,235 |
| NFKC + casefold + 空白规范查询 | 1,023 |
| 5 分钟搜索 burst | 235 |
| 去重 interaction 记录 / 所在 burst | 84 / 76 |
| 曲目 interaction burst | 28 |
| 可映射本地规范曲目 | 24 |
| 1 小时内出现对应有效播放 | 20 |
| 严格按“搜索→播放→30 天内进入当前收藏” | 1 |

时段分布按 burst 首事件统计，不按 2,235 条输入过程行加权。最终一级只表示当前收藏快照中仍可观察到、且事件顺序完整的证据，不输出转化率。

#### 当前收藏库

| 类型 | 当前总数 | 首屏 raw JSON | 真实只读构建 |
|---|---:|---:|---:|
| 歌曲 | 800 | 4,979 bytes | 约 69 ms |
| 专辑 | 250 | 4,434 bytes | 约 68 ms |
| 艺人 | 59 | 3,393 bytes | 约 9 ms |
| 歌单 | 27 | 8,013 bytes | 约 7 ms |

四类均按每页 20 条采样。歌单数量来自真实成员表，每个歌单只带最多 3 条预览；本地实体无法映射时仍保留收藏项，但不生成失效详情深链。四类响应均已断言不含 `spotify:` 与 URI 字段。

#### 播客与视频

| 指标 | 结果 |
|---|---:|
| 播客原始行 / 有效逻辑事件 | 125 / 51 |
| 播客有效时长 | 65,908,148 ms，约 18.3 小时 |
| 节目数 / 活跃月份 / 跨日回访节目 | 6 / 8 / 1 |
| 视频原始行 / 有效逻辑事件 | 957 / 45 |
| 视频有效时长 | 8,377,329 ms，约 2.3 小时 |
| 视频映射曲目 / 活跃日 | 31 / 25 |
| 本地可识别视频 Top 3 | Opalite 4 次 / we can't be friends (wait for your love) 3 次 / Praying 2 次 |
| 同窗音频有效逻辑事件 | 64,948 |
| 同窗音频有效时长 | 14,791,730,868 ms，约 4,108.8 小时 |

视频的 45 是经过连续合并、动态阈值和长片段拆分后的逻辑事件数，不等同于简单筛选 `ms_played >= 30s` 的原始行数。未映射事件仍进入视频总次数与总时长，但只有本地可识别歌曲进入带封面的 Top 3。音频和视频在合并前使用 `content_type` 边界隔离，兼容对照基于同一观察窗和有效时长。播客 Top 3 可补充本地节目 publisher 与直接图片 URL；当前真实 `saved_shows` 没有节目封面字段，因此页面不伪造占位封面。播客响应不返回单集名称，媒体响应不返回平台或 URI。

### 必须保留的解释边界

这些高回访率没有被人为压低，因为计算结果应忠实反映数据；但输入只包含“导出时仍在收藏”的幸存曲目，缺少已取消收藏历史，存在明显幸存者偏差。正式 UI 必须使用“当前收藏回访率”，不能写“收藏留存率”“收藏让播放增长”或概括所有历史收藏。

对称窗口同样只是事件关联：收藏通常发生在兴趣上升阶段，且不存在随机对照，后窗事件更多不能解释成收藏行为造成播放增加。

### 性能与体积

真实 SQLite、独立 FastAPI app、只读连接采样：

| 接口 | raw JSON | 冷响应 | 热响应 p95 |
|---|---:|---:|---:|
| `collection-journey` | 3,429 bytes | 约 53 ms | 约 27.5 ms |
| `collection-cohorts` | 10,681 bytes | 约 566 ms | 约 27.7 ms |
| `returns` | 5,913 bytes | 约 515 ms | 约 29.8 ms |
| `discovery` | 2,472 bytes | 约 539 ms | 约 48.2 ms |
| `library/tracks`（20 条） | 4,979 bytes | 约 69 ms | 约 24.6 ms |
| `library/albums`（20 条） | 4,434 bytes | 约 68 ms | 约 62.1 ms |
| `library/artists`（20 条） | 3,393 bytes | 约 9 ms | 约 9.1 ms |
| `library/playlists`（20 条） | 8,013 bytes | 约 7 ms | 约 7.2 ms |
| `other-media` | 1,619 bytes | 约 663 ms | 约 38.6 ms |

`collection-cohorts` 低于 120 KB / 1.5 s 预算；`returns`、`discovery`、四类收藏分页与 `other-media` 均低于 80 KB；所有重统计冷构建低于 1.5 s，已采样接口热响应低于 75 ms。

### 后续交付状态

页面及人工验收结果统一见[Phone](#音乐档案-phone-交付记录)与[Phase 4合入收口](#音乐档案-phase-4-退役与收口交付记录)，不重复列后续交付清单。


## 音乐档案 Desktop / Compact 交付记录

原记录：`2026-08-13-account-archive-desktop-delivery.md`。

> 日期：2026-08-13
> 分支：`codex/account-archive-rebuild`
> 范围：`/account` 的 Desktop / Compact 页面、前端数据层、收藏库交互与真实浏览器验收；Phone 的后续交付见同日独立记录

### 1. 交付结论

Desktop 与 Compact 已从旧“账号中心”切换为本地优先的“音乐档案”。新页面不再把 Spotify 在线身份放在首屏，也不请求旧 `/api/account` 聚合或 `/api/profile`；没有配置 Spotify OAuth 时仍可完整打开核心档案。

页面使用“私人唱片档案”而非通用 dashboard 的视觉模型：纸张纹理、编号章节、唱片封套与编辑式排版承担主体层级，玻璃材质只用于导航和工具控件。Desktop 使用粘性纵向索引，Compact 使用粘性横向章节条；Phone 将在下一阶段单独实现“口袋音乐档案”。

### 2. 已交付内容

- 档案封面：收藏歌曲、专辑、艺人、歌单和四个收藏故事；人工验收后不再展示数据范围、截止日与状态说明。
- 收藏旅程：每年收藏歌曲、收藏总时长、发行年代跨度，以及第 100 / 200 / 400 / 800 首等倍增收藏里程碑；不重复封面的最早与最近收藏。
- 播放多久后收藏：首次播放到收藏的时间分布，以及收藏前后 30 天的播放次数对比。
- 收藏后再次播放：7 天内、第 8–30 天、半年后和一年后四个互补生命力指标，以及近 90 天听过、没听、常听未收藏三类关系。
- 找回音乐：回归概览、代表回归与沉睡收藏，不把“尚未回访”写成放弃。
- 搜索与发现：展示搜索次数、时段与“点开歌曲 → 1 小时内播放 → 30 天内收藏”三步动作，不向浏览器发送原始查询词。
- 收藏库：歌曲、专辑、艺人、歌单四类服务端搜索、排序和分页，每页最多 20 条，状态写入 URL。
- 音乐之外：播客和视频的保守累计事实；两卡统一使用标题条加 Top 3，播客只显示本地已有封面，视频补充带封面的本地可识别歌曲；没有单集时长时不伪造完播率。

### 3. 前端结构与状态

- `AccountCenterPage` 只负责 presentation 分流；本记录交付时 Phone 尚使用旧组件，现已由 `AccountArchivePhoneRoute` 接管，见 Phone 交付记录。
- 所有 GET 读取通过 TanStack Query 和 `queryKeys.account.archive*`；默认 `staleTime=5min`、`gcTime=30min`。
- 各章节使用 IntersectionObserver 渐进加载；直接打开 `?section=library` 时会在请求和布局变化结束前保持章节锚点，避免 URL 被错误回写到前一章。
- 收藏库使用 `library`、`sort`、`search`、`page` 查询参数，可分享并支持浏览器前进/后退。
- Spotify 导出项使用不可逆稳定键作为列表身份；本地 catalogue id 只负责详情深链，避免多个 Spotify 版本映射到同一本地实体时出现重复键。
- route container 为 91 行，数据 hooks、导航协调、统计模型和 presentation 分层放置，符合 Phase 5 薄路由约束。

### 4. 验收证据

自动化结果：

- 账号档案后端单元测试：30 passed。
- 前端定向矩阵：5 files / 126 passed，覆盖新 route、query hooks、Phase 5 架构与旧 Phone 回归。
- 新增/修改文件 ESLint：通过。
- `npm run build`：通过；账号页面异步 JS 约 84.31 kB raw / 21.14 kB gzip，CSS 约 30.62 kB raw / 5.62 kB gzip。

真实数据浏览器验收：

- 1280、1024、768 三个视口横向溢出均为 0。
- 亮色与暗色主题均完成目视检查。
- 冷打开 `?section=library` 后 URL 保持不变，目标章节顶部稳定在约 80 px。
- 专辑切换后 URL 为 `library=albums&sort=name`；搜索 `Taylor` 后服务端返回 27 条、首屏渲染 20 条。
- 请求日志只出现 `/api/account/archive-overview`、journey / cohorts / returns / discovery / library / other-media 等新链路，没有精确命中旧 `/api/account` 或 `/api/profile`。
- 唯一浏览器控制台错误来自当前 worktree 复用另一 worktree `node_modules` 时 Vite 对 `@fs` 字体路径的 403 限制；生产构建已正常输出 Inter 字体资源，不属于页面运行错误。

### 5. 后续状态

Phone及合入后的人工验收已完成，见[Phone交付](#音乐档案-phone-交付记录)和[Phase 4](#音乐档案-phase-4-退役与收口交付记录)。


## 音乐档案 Phone 交付记录

原记录：`2026-08-13-account-archive-phone-delivery.md`。

> 日期：2026-08-13
> 集成状态：已进入 `main`
> 范围：`/account` 的独立 Phone presentation、全屏收藏库、移动门禁与合并后的人工验收收口

### 1. 交付结论

Phone 已从旧账号 Hero 和桌面内容折叠壳切换为独立“口袋音乐档案”。它与 Desktop / Compact 共享本地统计事实、TanStack Query、过滤参数、URL 和格式化模型，但不会同时挂载桌面长列表或宽图。

页面使用既有 `/account` 路由，二级导航与正文统一命名为“音乐档案”。运行时只读取本地档案接口；没有 Spotify Client ID、token 或外网访问时，当前 SQLite 支持的章节仍可打开。

### 2. 页面与交互

- 封面：两张有明确角色的收藏封套、黑胶拼贴，以及收藏歌曲、专辑、艺人和歌单四项事实；不再显示覆盖期或数据状态。
- 章节：粘性横向编号条直达收藏旅程、播放多久后收藏、收藏后再次播放、找回音乐、搜索与发现、收藏库和音乐之外；章节状态写入 URL，当前项会自动滚到可见区域，两侧渐隐提示仍有章节。
- 收藏旅程：用第 100 / 200 / 400 / 800 首等倍增里程碑替代封面已经出现的最早与最近收藏。
- 收藏关系：正文展示收藏前后 30 天次数对比、“首次播放后隔了最久才收藏”的歌曲，以及 2×2 排列的 7 天内、第 8–30 天、半年后、一年后四个互补生命力指标；不展示逐周“可观察”曲线或隐藏横滑指标。
- 搜索与发现：显示去重后的星期分布、24 小时时段带和三步动作链，不展示原始查询词或内部映射数量。
- 找回音乐：歌曲名称最多展示两行，艺人和“多少天后 / 多少天未出现”进入同一正文列，不再用右侧窄列遮挡标题。
- 收藏库：正文预览 Top 5；完整目录通过 Portal 覆盖 App Shell，每页 10 条，支持类型、搜索、排序、前后翻页、直接跳页和 URL 恢复。
- 音乐之外：播客与视频卡统一使用紧凑头部加封面 Top 3；播客只显示本地已有封面，视频展示带封面和详情深链的本地可识别歌曲，不再突出悬殊的音频总时长对照。
- 全屏行为：Escape 和关闭按钮可退出，背景滚动被锁定，关闭后焦点回到原触发按钮；收藏库打开时 App Root 设置 `inert`。
- 视觉：延续暖纸、编辑红、细档案线与衬线标题；玻璃只留给现有 Shell 和临时控制层。承担含义的辅助文字统一不低于 10px，只有纯装饰序号保留 9px。

`AccountCenterPage` 现只按 `useViewportMode()` 在 `AccountArchivePhoneRoute` 与 `AccountArchiveDesktopRoute` 间互斥分流。新 Phone route 不再导入旧 profile、收藏人格、习惯人格，也不请求精确 `/api/account` 或 `/api/profile`。

### 3. 自动化证据

- 本轮修改范围 ESLint：通过。
- 前端完整回归：69 files / 504 tests passed；其中 Phone 档案 4 项组件测试覆盖本地端点隔离、收藏库跳页与焦点恢复、章节自动居中和长标题排版。
- `npm run build`：通过；账号页面异步 JS 约 55.94 kB raw / 12.35 kB gzip，CSS 约 56.12 kB raw / 8.76 kB gzip，包含两套互斥 presentation 样式。
- 真实页面 360×800、390×844、430×932 的 `documentElement.scrollWidth - innerWidth` 均为 0；390px 生命力四格为 174×142px，360px 为 161×142px。
- 390px 完整收藏库搜索、关闭、页码与跳页输入/提交控件均不低于 44px；第 1 页可直接跳到第 40 / 80 页，列表窗口更新为 391–400，关闭后背景滚动与触发按钮焦点恢复。

### 4. 真实浏览器检查

- 本轮完成亮色 360 / 390 / 430 目视复验；暗色 390 沿用初始交付验收结果。
- 364×751 人工评论复验中，封面“音乐 / 档案”行高从过度压缩恢复到清晰的双行排版；“开始翻阅”上下留白统一为 18px。
- 点击“再次播放”“收藏库”“音乐之外”后，URL、滚动位置和章节高亮一致；390px 最后一个“音乐之外”入口位于 291–366px，360px 位于 261–336px，均完整可见。
- 完整收藏库真正覆盖 Top Bar 与 Bottom Nav；页码按钮打开直接跳页面板，第 1 页可跳至第 40 页，关闭后焦点恢复到“打开完整收藏库”。
- `Running Up That Hill (A Deal With God) - 2018 Remaster` 在 390px 使用两行标题和 251px 正文列；“1240 天未出现”进入艺人下方元信息，不再遮挡标题。
- 播客与视频卡在 390px 分别约 354px、372px 高，均以总时长头部加 Top 3 组织；视频封面正常显示，播客只在本地有封面时渲染。
- 请求只命中新 `/api/account/archive-overview`、journey、cohorts、returns、discovery、library、other-media 链路，没有精确命中旧 `/api/account` 或 `/api/profile`。

历史截图产物已按本地输出清理策略移除；本报告保留文本验收结论和检查范围，不再维护已失效的本地截图路径。

### 5. 后续状态

旧UI、兼容路由与重型服务退役及合入结果统一见[Phase 4](#音乐档案-phase-4-退役与收口交付记录)。


## 音乐档案 Phase 4 退役与收口交付记录

原记录：`2026-08-13-account-archive-phase-4-delivery.md`。

> 日期：2026-08-13
> 分支：`codex/account-archive-rebuild`
> 范围：旧账号 UI、重型聚合服务、HTTP 兼容路由、AI 消费者、预热、OpenAPI 与项目文档；分支合并状态在本记录末尾补记

### 1. 交付结论

音乐档案重构已完成最后一阶段。运行时只剩新的本地档案页面和严格分拆接口；旧人格、chemistry、Habits、Marquee、粉丝等级和关键词迁移页面已删除，旧重型 `/api/account` 聚合与 `/api/account/collection-insights` 已从 FastAPI 和 OpenAPI 退役。

Spotify OAuth 仍只是 Settings 中可选的收藏日期补全能力。打开 `/account`、浏览收藏库、查看关系与回访均不要求 Spotify Client ID、token 或外网；部署到国内服务器时，音乐档案本身不新增 Spotify 运行时依赖。

### 2. 删除与保留边界

已删除：

- `backend/services/account_service.py`：旧收藏人格、chemistry、关键词迁移与整页大聚合；
- `GET /api/account`、`GET /api/account/collection-insights` 及两个宽松 response model；
- `frontend/src/features/account/`、`frontend/src/features/mobile/account/`、`frontend/src/pages/account/`；
- `frontend/src/hooks/useAccount.ts`、`frontend/src/types/account.ts` 及旧 query keys/type exports；
- 旧 M6 account Hero、人格标签、Habits disclosure 样式和只验证旧组件的测试。

明确保留：

- `/api/profile`、`/api/insights/tiers`、`/api/insights/marquee`、Podcast、Video 与 Wrapped Hub 等独立只读兼容/透明度接口；它们不再是音乐档案页面依赖；
- AI 工具名 `account_summary` 与 `account_collection_insights`，仅作为既有 planner、recipe 和 golden harness 的稳定标识；
- `/account` 路由继续保留；后续人工验收已将二级导航和页面正文统一命名为“音乐档案”。

架构测试新增反向护栏：旧 account、mobile account 和 page account 模块树必须保持为空；Phone route 不能导入 `useProfile` 或旧 `useAccount`。

### 3. AI 与预热迁移

`account_summary` 现在组合 archive overview，并按参数补充固定窗关系和不含原始查询词的 discovery 摘要。`account_collection_insights` 组合 overview、journey、cohorts 与 returns，返回收藏规模、覆盖率、固定观察窗、关系矩阵、回归和沉睡事实；两者均不再返回人格或 chemistry。

Project Context 提升为 `spotify-stats-project-context-v2`，明确当前收藏只是快照，禁止把关系事实包装成收藏人格或因果结论。启动 warmup 也只预热 `archive-overview`，不再构建旧整页聚合。

### 4. 契约与体积对比

| 项目 | 旧链路 | 当前链路 |
|---|---:|---:|
| 首屏 HTTP | `/api/account` | `/api/account/archive-overview` |
| raw payload | 约 456 KB | 1,936 bytes |
| 冷响应 | 约 1.8–4.2 s | 约 157–200 ms |
| 热响应 | 约 14 ms | 热 p95 约 6–9 ms |
| 响应契约 | `extra=allow` 大聚合 | `extra=forbid` 白名单 DTO |
| 长列表 | 随 summary 整批返回 | 服务端分页，Desktop 20 / Phone 10 |
| Spotify 运行时请求 | 旧页面混有身份/在线语义 | 0；只读本地 SQLite |

新页面的重章节继续渐进加载。已有真实数据采样显示，journey、cohorts、returns、discovery、other-media 和四类收藏分页 raw JSON 均低于各自 80/120 KB 预算，重统计冷构建低于 1.5 s，采样热响应低于 75 ms。当前生产构建的账号异步 JS 为 61.81 kB raw / 14.85 kB gzip，CSS 为 57.38 kB raw / 8.94 kB gzip；旧组件此前已经不在运行时依赖图，本阶段删除的主要收益是代码与契约收口，而不是虚报额外 bundle 降幅。

### 5. 验收证据

- 后端迁移定向矩阵：58 passed；扩展档案 + AI 回归为 82 passed，覆盖 archive 全领域、AI 工具、Project Context、warmup、旧路由 404 与账号 response models。
- 前端退役与页面定向矩阵：4 files / 113 passed；完整前端回归 68 files / 496 passed。
- TypeScript + Vite production build：通过；仅保留项目既有的大 chunk 提示。
- OpenAPI operation audit：192 operations，110 safe GET smoke / 73 targeted contract / 9 controlled，0 unaccounted。
- OpenAPI parameter boundary audit：89 obligations，0 unaccounted。
- 项目 Phase 5 基线：unit 876 passed / 2 skipped，contract 325 passed，backend Ruff 通过，前端 68 files / 496 passed，production build 通过。
- 全量基线额外发现并修复收藏库“不支持的实体排序”422 仍返回字符串的问题；现在返回带 `loc=[query, sort]` 的标准 validation detail，API boundary probe 通过。
- 生成的 OpenAPI snapshot 与 TypeScript types 已刷新，旧两条路径和旧 response model 不再出现。
- 既有 Phone / Desktop 实页证据继续成立：五视口 route matrix、可访问控件、长列表、Chromium / Firefox / WebKit 均已通过，页面请求日志未命中旧聚合或 `/api/profile`。

### 6. 集成状态

本批次最初在 `/Users/benjaminlei/Code/202605-SpotifyStats-account-archive` 的 `codex/account-archive-rebuild` 上独立完成。首页完成后，两边通过单独的冲突预检合并进入 `main`；其后的 Desktop / Phone 人工验收修复均在合并后的工作树继续收口。
