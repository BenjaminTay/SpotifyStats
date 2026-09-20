# 阶段 2B：Community 请求去重与详情非核心按需读取

> 2026-09-19；HEAD faa5e4e4，dirty。**Partial：本地定向实现、92,908 plays 副本测量及双端 production build 验证**。阶段 0/0.5/1/2A 和安全收口保留为基线。

## 已实现

- Community 设置 ready 前不请求 feed/trending/post；三个入口复用规范化 Billboard 参数和 Query key，保留筛选、搜索与无限分页。设置失败显示错误，未启用预取。
- Summary 与基础 stats 仍并行；排名、实体排行和 Recent plays 按实际视口启用；日历只在首次打开时加载。Recent plays 改为 TanStack Query，失败不显示为空结果。
- 排名原先位于 Desktop 约 572px，初始即在视口内；为满足初始排名请求为 0，将原排名区块放到基础图表后。数据、控件和功能保留。
- 修正 album-project summary 补齐 artist 后基础 stats key 变化造成的重复请求；项目 plays/play-dates 的底层 key 加入 project identity。
- [当前触发与 key 合同](../reference/deferred-read-contract.md)。未改后端产品代码、阶段 2A 投影、migration 74 或统计规则。

## 测量口径与原始证据

证据目录：`/Users/benjaminlei/.codex/visualizations/2026/09/19/01a0b92d-b0b5-7cb0-9bb9-f058d37d2cf7/spotifystats-stage2b`。完整参数、请求顺序/并发起止时刻、HTTP 状态、raw bytes、实际 HTTP Content-Length、编码、失败及触发标签见 `before.json`、`after.json`、`api-samples.json` 和 `request-waterfalls.md`。后者采用阶段 0 `spotify-performance/1` 字段；builder/singleflight 次数未暴露，保持 null。

本轮新建 Online Backup：`/tmp/spotifystats-stage2b/main.db`，92,908 plays，max play_id=2,298,810；默认 12 条快照在该临时 DB namespace 重建。before 是当前阶段 2A production build 的本轮新测；after 是阶段 2B production build。API 指向同一自有本地服务，所有非 loopback、非 GET/HEAD 浏览器请求阻断。Desktop=1280×900，Phone=390×844（互斥 presentation）。

以下为每页每 presentation 单个 observed value，后端同进程；不报告 P95，不称独立进程 cold。首轮/失败样本单独保留，不纳入成功性能结果。core-ready 依据正确路由、核心 DOM 事实和对应成功 API；主链路样本中所有 API 均 200，无错误页/404。实际完成条件不是固定等待，沿用 5 秒 core 预算与 30 秒 API 预算。

## 初始未滚动请求与传输量

请求数包含 runtime/capabilities 和 settings。B 为字节，encoded 为网络实际编码 body，未使用本地 gzip 重压缩。Community 随机互动数导致少量字节浮动。

| 页面 | presentation | API 数 before → after | raw B before → after | encoded B before → after | core-ready ms before → after |
|---|---|---:|---:|---:|---:|
| community | Desktop | 6 → 4 | 55223 → 28024 | 10752 → 5862 | 637 → 2490 |
| account | Desktop | 6 → 4 | 52117 → 26439 | 10195 → 5597 | 641 → 556 |
| post | Desktop | 6 → 4 | 5226 → 3035 | 3344 → 2087 | 512 → 432 |
| artist | Desktop | 8 → 4 | 201552 → 67113 | 28222 → 10840 | 597 → 577 |
| album | Desktop | 10 → 5 | 125192 → 29767 | 18627 → 6624 | 693 → 672 |
| track | Desktop | 7 → 4 | 94521 → 28767 | 12419 → 5268 | 550 → 620 |
| analysis | Desktop | 5 → 3 | 270225 → 206470 | 44078 → 34903 | 398 → 408 |
| community | Phone | 6 → 4 | 55208 → 28020 | 10760 → 5848 | 605 → 474 |
| account | Phone | 6 → 4 | 52115 → 26436 | 10180 → 5590 | 567 → 467 |
| post | Phone | 6 → 4 | 5237 → 3034 | 3353 → 2093 | 560 → 438 |
| artist | Phone | 8 → 4 | 201552 → 67113 | 28222 → 10840 | 596 → 486 |
| album | Phone | 10 → 5 | 125192 → 29767 | 18627 → 6624 | 503 → 803 |
| track | Phone | 7 → 4 | 94521 → 28767 | 12419 → 5268 | 490 → 535 |
| analysis | Phone | 5 → 3 | 270225 → 206470 | 44078 → 34903 | 407 → 407 |

artist 主矩阵为 3,423 次有效播放的艺人；另补充更大艺人样本如下。单次时延并非全部下降；本批验收改善是请求时机、重复次数与首屏传输量，不以 warm 缓存或抽样波动声称后端计算提速。

### 大艺人补充样本

| presentation | 核心有效播放 | 初始 API before → after | raw B before → after | encoded B before → after | core-ready before → after |
|---|---:|---:|---:|---:|---|
| Desktop | 16590 | 8 → 4 | 221447 → 156238 | 33088 → 23722 | 5 秒预算失败 → 564 ms |
| Phone | 16590 | 8 → 4 | 408111 → 156238 | 60760 → 23722 | 784 → 627 ms |

大艺人 Desktop before 还出现一次 rank context 30 秒取消及随后重试；均保留在 `action-artist-before.json`，不能把重试后的成功当成首次成功。after 两端均无错误、取消和重复。该补充样本的第一次目标 stats 与后续 warm 状态不同，不能据此单独估计性能提升比例。

## 请求图与交互验收

### Community 三类路由（两端一致）

- before：settings 未完成时 fallback feed/trending（post 页为 post/trending）先启动；settings 返回后最终参数再启动一轮。每个页面 4 个 Community 请求。
- after：settings 成功 → feed + trending 并发；account 同样一轮、含 accounts；post 仅目标 post + trending，无 feed。每个页面 2 个 Community 请求。
- 两端每个页面 settings 完成前 Community 请求均为 0；实际过滤参数包括全部最终 Billboard context。完整请求参数/时刻保存在 waterfall。
- 请求取消 signal 由 Query 交给 API client。设置错误、等价 key、账号/post 路由次数、分页 offset、旧搜索迟到响应在自动测试中覆盖。

### 详情与播放统计

| 入口 | 初始 after | 接近排名区 | 接近排行区 | 接近 Recent plays | 日历首次 / 重开 |
|---|---|---|---|---|---|
| 歌曲（Desktop/Phone） | summary + 基础 stats | 1 rank context | 不适用 | 1 plays | 1 / 0 play-dates |
| 专辑项目（Desktop/Phone） | summary + 基础 stats，保留既有 project 视图读取 | 1 rank context | 1 album rankings | 1 plays | 1 / 0 play-dates |
| 艺人（Desktop/Phone，含大艺人） | summary + 基础 stats | 1 rank context | 1 track rankings；切换后 1 album rankings | 1 plays | 1 / 0 play-dates |
| 播放统计（Desktop/Phone） | analysis stats | 不适用 | 不适用 | 1 plays | 1 / 0 play-dates |

所有入口初始 rank context / rankings / plays / play-dates 均为 0。实际滚动中，artist/album 排行区和 Recent plays 顶部可以同时进入视口，此时两者同时请求；这是两个区域均满足观察条件，不是首屏预加载。rank context 单独接近时只新增 rank 请求。播放统计 Phone 的观察回调在首个探针 action 标签切换后才执行，补充 `action-analysis-after.json` 显式等待对应请求出现，确认滚动新增 plays、打开日历新增 dates，重开为 0。

基准 14 个 after 样本和补充大艺人样本均无 HTTP 错误、404、取消、重复 URL；每次请求与迟到响应均保留在样本中。新旧 key 竞态通过可控制 Promise 验证：旧实体/过滤/周期结果不会替换当前数据。分页、搜索、日期选择、错误状态及 artist track/album 切换通过组件测试；真实浏览器检查两端初始、排名、排行类型切换、Recent plays、日历关闭重开。所有截图与 DOM 记录均无横向溢出。

## 功能与事实对账

- 三类详情、analysis stats、rank context、track/album rankings、plays、play-dates 的完整 JSON，按相同请求参数逐字段比较一致；大艺人两端各 9 个响应也全部一致。见 `comparison.json`、`large-artist-facts.json`。
- Community meta、帖子 ID/顺序/数量、账号/时间、attached_list、linked_entities、images、tags、significance 及 trending 共 12 组逐字段一致。
- Community **不声称两个实时请求的所有字节相等**：`feed_generator.py:620` 每次随机生成互动数，`feed_helpers.py:51` 随机选择措辞；本轮跨越既有核心缓存 TTL，部分 content 改变。差异没有来自前端参数之外的业务修改。
- 用完全相同的已捕获 Community 响应，分别回放到 before/after production build：feed/account/post × Desktop/Phone 的最终 DOM 文本、实体/帖子链接六组全部一致（`replay-comparison.json`）。回放仅作为功能证据，不作为性能数据。
- L2/L3、compilation、项目/artist 身份、双轨时长和左邻上下文计算完全沿用现有后端；基础请求没有新增全局排名。真实副本矩阵为默认 L2，L3 参数与身份及统计规则另由 frontend 定向用例和完整 backend unit 覆盖，不把默认 L2 浏览器样本写成全变体验收。

## 失败与重试保留

- 首次有效 Community HTTP 请求 30.002 秒 ReadTimeout，保留 `routes.log`；后续 `routes-attempt2.log` 成功。Community 首次计算仍可能昂贵，未调整 timeout。
- `before-attempt1.json` 的 Community DOM selector 不匹配及 Phone analysis marker 不匹配属于探针错误；`before-attempt2.json` 的 DOM 对象序列化报错同样不算产品成功样本。修正为真实 article/Phone 标记与布尔判断后重新测量；所有尝试保留。
- `after-attempt1.json` 与全量测试并行时 Community 超过 5 秒 core 预算，保留该失败。最终复测在无本任务测试竞争时执行。
- 前端默认并发运行先暴露既有 mobile-shell 测试缺 Provider，已补测试包装；另有 artist-language-review-dialog 在默认并发下超时/交互失败。保持用例与原超时，限制运行时 worker=2 后完整通过；未修改该无关业务或放宽断言。

## 修改文件与验证

产品文件：`useCommunity.ts`、三个 Community Experience、`EntityStatsPanel.tsx`、`RecentPlaysSection.tsx`、`useAnalysis.ts`、`query-keys.ts`，新增最小 `useDeferredInView.ts`。对应新增/调整 Community readiness、Observer、Recent plays、entity rankings、mobile music/shell 测试。没有修改后端产品文件。

| 检查 | 结果 |
|---|---|
| `.venv/bin/pytest -m unit -q --basetemp=/tmp/spotifystats-stage2b/pytest-unit` | 1754 passed，1085 deselected；61.04s；1 个既有 LibreSSL warning |
| `npm test -- --maxWorkers=2` | 647 passed，4 个既有可选真实投影夹具测试 skipped；全部 83 个 test file 纳入 |
| `npm run build` | TypeScript 与 production build 通过；沿用既有大 chunk 提示 |
| 受影响产品/新测试 ESLint | 通过，无放宽规则 |
| 双端 production build | 14 主样本 + 大艺人两端 + 同响应 Community 六组回放；Partial |
| `python3 scripts/docs_audit.py` / `git diff --check` | 均通过（101 个当前 Markdown；diff 无空白错误） |

## 正式数据与停止边界

`formal-before.json` 与 `formal-after.json` 对正式主库、Billboard、yearly 和 7 个 Home JSON 共 10 个文件逐一比较 SHA-256、大小、mtime，完全一致；Home 文件集合不变。Billboard integrity_check=ok，仍为 7 family / 12 rows：weekly/all_time/full_data/records/power_scores/summaries 各 1，year_end 6。主库保持 schema 73，migration 74 未应用。Online Backup 读取可更新 SQLite SHM 的读锁簿记，该文件不是业务内容或发布快照；未把它写成业务数据修改。

所有 backend pytest 由共享 fail-closed fixture 绑定 session 临时目录；浏览器服务使用临时 main、Billboard、Home、yearly 路径。正式源库只用于 Online Backup 读取。

**本批停止于阶段 2B。** Community 首次计算和分页前全量补全留给阶段 6；未开始阶段 3–6、没有新增持久缓存、算法优化或生产操作；未 commit、push、部署。
