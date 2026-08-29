# 设置重建状态与数据导入治理完整修复方案

> 状态：`IMPLEMENTED / PASS（功能范围）`；后续 descendant 默认完整全栈门禁已通过，本文已归档
> 实施日期：2026-08-27
> 创建日期：2026-08-26
> 适用范围：设置页统计重建、数据导入前检查、导入后健康治理
> 当前规则入口：[`../../reference/data-import-and-health.md`](../../reference/data-import-and-health.md)、[`../../reference/playback-stats-rules.md`](../../reference/playback-stats-rules.md)
> 本地提交：`62f48299cb4c0995c30b80ecb1e91932daa9b93f`，尚未 push、未获得对应生产部署证据
> 后续门禁：descendant `dc7055a7e97b01474022af04624497d4b2ee6064` 通过默认完整全栈门禁；后续业务代码提交 `0b23c442` 未重跑整站门禁

## 1. 结论

本轮应分成三条相互独立、按优先级推进的修复链路：

1. **P0：修复“统计口径有改动待生效”反复出现。** 根因是重建成功后只修改了设置页的局部状态，没有同步 TanStack Query 中的设置缓存；页面重新挂载时会在默认 5 分钟 `staleTime` 内继续读取旧的 `rebuild_pending=true`。
2. **P0：修正健康检查的事实口径。** 当前“最近专辑缺少 Album Project”把不应建立项目的 single / compilation 也纳入候选，造成假阳性；必须复用 Album Project 构建器的同一套资格判定。
3. **P1：重做数据治理和导入准备的信息架构。** 先告诉用户“数据能否正常使用、是否影响当前统计、要不要现在处理”，再按需展开技术细节；导入前检查则改造成“检查数据包 → 查看建议 → 确认导入”的明确流程。

历史外键残留的实际清理没有与本轮 UI 修复捆绑执行。本轮只新增可审计的只读预览；Phase 6 已由 2026-08-27 的另一项独立授权任务完成数据库副本验证、停机备份、事务清理和审计，详见当前规则文档。本轮没有再次执行清理。

## 2. 已核实的当前事实

以下数字是 2026-08-26 对当前数据库的只读快照，不是永久产品常量：

| 项目 | 当前事实 | 产品解释 |
|---|---:|---|
| 播放记录 | 92,908 | 核心播放统计可用 |
| SQLite 完整性 | `ok` | 数据库文件本身没有完整性错误 |
| `rebuild_pending` | `false` | 后端和数据库已完成重建，反复提示来自前端旧缓存 |
| 外键残留总数 | 7,831 | 主要是没有当前播放引用的历史实体残留，不等于 7,831 条播放损坏 |
| 曲目缺少艺人实体 | 3,098 条关系，涉及 828 个艺人 ID | 当前播放影响为 0 |
| 专辑缺少艺人实体 | 1,590 条关系，涉及同一批 828 个艺人 ID | 当前 source-album 播放影响为 0 |
| AI / 对话历史外键残留 | 43 | 与音乐和播放统计无关 |
| 曲目缺少专辑实体 | 2 | 当前播放影响为 0 |
| 播放缺少曲目实体 | 237 | 这些原始播放无法进入实体排行，必须保留并单独说明，不能自动删除 |
| “最近专辑缺少 Album Project” | UI 报 17 | 只读复算后 17 个均为 single / compilation，属于健康检查假阳性 |

因此，当前状态不应笼统显示“部分完成”。更准确的首页结论是：

> **核心统计正常，有历史数据可整理。** 当前发现的艺人/专辑关系残留不影响已有播放统计；另有 237 条原始播放缺少曲目实体，已保留但不会进入歌曲、专辑或艺人排行。

## 3. 用户术语的统一解释

### 3.1 专辑引用了不存在的艺人实体

数据库中的某些历史专辑还保存着一个艺人 ID，但 `artists` 表里已经找不到对应艺人。当前快照中，这些专辑没有被现有播放用作 source album，所以不影响当前统计；它们更接近历史元数据残留，而不是正在发生的数据损坏。

### 3.2 曲目引用了不存在的艺人实体

某些历史曲目的主艺人或署名关系仍指向已经不存在的艺人 ID。当前快照中这些曲目没有现有播放，因此不会影响当前歌曲或艺人排行。修复时仍要先检查下游引用，不能只按数量批量删除。

### 3.3 数据库存在其他历史外键关系残留

这是对“父记录已经不存在、子记录还留着”的笼统技术描述。目前 43 条全部来自 AI 任务、工具调用和聊天会话历史，与音乐统计无关。UI 应拆分领域并明确影响，不能和播放数据问题混在同一个警告中。

### 3.4 导入前检查

它不是正式写入数据库，而是对本地 Spotify 数据包做一次只读演练，包括：

- 文件是否能解析、是否缺少必要字段；
- 音频、视频和账号档案文件是否齐全；
- 文件内是否有完全重复记录；
- 不同文件的日期范围是否重叠，以及重叠是否真的包含相同记录；
- 当前数据库与数据包能否按指纹逐条比较；
- 系统建议增量导入还是完整替换；
- 在临时 staging 数据库中能否完成导入准备。

当前数据库还没有可比较的源指纹 baseline，因此“新增 92,908 条”不能按字面理解成 92,908 条新播放。准确含义是：**这是首次建立逐条识别基线，本轮无法计算真实新增/移除差异。**

## 4. 修复原则与边界

### 4.1 必须保持的原则

- 后端数据库是重建状态的最终事实源；前端不得用页面局部状态长期覆盖它。
- 健康检查与实际构建逻辑必须复用同一资格判定，禁止维护两套相似口径。
- “能否使用”和“是否整洁”分开：历史残留不能把核心统计降级成不可用。
- 原始 `plays` 和导入源事实不自动删除；无法归属的播放保留在总量和审计范围中。
- 所有实际清理先做只读预览，再在数据库副本验证，最后才允许对主库执行。
- 导入继续保持两阶段：基础播放写入完成后，再执行元数据维护、Album Project、Billboard 和缓存失效/预热。

### 4.2 本方案不做的事

- 不把历史孤儿记录静默补成猜测出来的艺人或专辑。
- 不因为 UI 显示难看就删除真实数据。
- 不把搜索快照或年度报告的后台预热伪装成基础导入失败。
- 不在首次修复中引入一键自动清理。
- 不改变播放次数、收听时长、专辑项目或艺人统计的现行规则。

## 5. 目标状态模型

### 5.1 设置与统计重建

短期保持现有 `rebuild_pending` 兼容字段，同时让重建接口返回可直接写入查询缓存的权威状态：

```json
{
  "status": "ok",
  "rebuild_pending": false,
  "completed_at": "2026-08-26T...",
  "aggregation": { "status": "ready" },
  "background_tasks": [
    { "name": "search_snapshots", "status": "warming" },
    { "name": "yearly_reviews", "status": "warming" }
  ]
}
```

产品层分清三种状态：

| 状态 | 含义 | UI |
|---|---|---|
| `rebuild_pending=true` | 设置已保存，但新统计口径尚未应用 | 显示“需要应用改动” |
| 聚合 `running/failed` | 用户已发起重建，核心聚合正在执行或失败 | 显示进度或错误与重试 |
| 后台 `warming` | 核心统计已可用，搜索快照/年度数据继续预热 | 仅显示非阻塞说明，不再显示“待生效” |

中期可以把这些字段收敛为 `stats_maintenance` 对象，但第一版不要求破坏现有 API。

### 5.2 数据健康结果

保留现有 `ok / partial / blocked` 兼容字段，新增面向产品的维度：

```text
safe_to_use: true | false
impact_scope: current_stats | source_exclusion | historical_only | non_music
severity: blocking | action_required | maintenance | info
action: retry | review | preview_cleanup | no_action
```

健康页顶部不直接复述技术状态，而按以下顺序形成结论：

1. 当前统计是否安全可用；
2. 有多少问题会影响当前统计；
3. 有多少只是历史残留；
4. 系统建议用户现在做什么。

### 5.3 Album Project 资格

从现有 Album Project resolver 提取无副作用的共享判定函数，例如：

```python
resolve_project_eligibility(source_album, spotify_links) -> EligibilityResult
```

构建器和健康检查必须同时调用它。结果至少包括：

- `eligible: bool`
- `resolved_album_type: album | single | compilation | unknown`
- `reason_code`
- `evidence`（名称匹配、播放权重、曲目数兜底等）

不得继续使用“任意链接为 album 或本地曲目数不少于 7”作为独立健康口径。

## 6. 后端修复设计

### 6.1 P0-A：设置重建状态一致性

涉及入口：`backend/api/settings.py`、设置 service / repository、相关 contract tests。

实施内容：

1. 重建成功后，在同一完成路径中持久化 `rebuild_pending=false`。
2. 重建响应返回权威 `rebuild_pending` 和核心/后台任务状态。
3. `GET /api/settings` 每次从持久化设置事实组装响应，模块级 `_current` 最多作为受 revision 约束的缓存，不能成为独立事实源。
4. 重建失败时不得提前清除 pending；返回可重试错误并保留失败原因。
5. 同一时刻的重复重建请求使用现有 singleflight / 任务锁，避免并发清除和覆盖状态。

### 6.2 P0-B：健康检查假阳性

涉及入口：`backend/domains/metadata/import_health.py`、`backend/domains/playback/album_projects.py`。

实施内容：

1. 提取并复用 Album Project 资格判定。
2. 只有 `eligible=true` 且确实缺少 membership 的近期专辑才进入 `unresolved_recent_albums`。
3. single / compilation 计入“按规则无需建立项目”的信息性计数，不视为问题。
4. 检查曲目和专辑引用时，同时返回：总残留数、当前播放可达数、受影响播放数、唯一缺失实体数。
5. 把 AI / chat 历史残留与音乐领域残留拆开。
6. `plays` 缺少曲目实体单独标记为 `source_exclusion`，明确“保留原始事实，但不进入实体排行”。

### 6.3 P1-A：健康 API 产品化

在现有健康接口上做向后兼容扩展：

- `summary.safe_to_use`
- `summary.headline`
- `summary.current_stats_issue_count`
- `summary.historical_issue_count`
- `summary.informational_count`
- 每个 issue 增加 `impact_scope`、`severity`、`user_title`、`user_explanation`、`recommended_action`

增加只读详情/预览能力，建议使用：

```text
GET /api/import/health/issues/{issue_code}/samples?limit=50&cursor=...
POST /api/import/governance/cleanup-preview
```

`cleanup-preview` 只生成计划，不执行删除；返回每类目标行数、样例 ID、当前播放可达性、下游依赖、建议动作和不可自动处理原因。

### 6.4 P1-B：导入前检查语义

为 preflight 响应增加：

```text
comparison_status: comparable | baseline_missing | incompatible
record_delta_comparable: bool
overlap_classification: duplicate_records | boundary_only | review_required
```

兼容期可以继续返回现有数值字段，但当前端看到 `record_delta_comparable=false` 时不得展示常规“新增/移除”指标。后续主版本可把不可比较的差异值改为 `null`。

对于日期范围重叠：

- `shared_record_count > 0`：需要用户关注的重复风险；
- `shared_record_count = 0`：仅是文件边界重叠，显示为中性信息；
- 无法计算共享记录：标记“需要复核”，不能自动当成错误。

### 6.5 P2：实际清理执行器（独立审批）

只有只读预览验收通过后再实现，且与本轮 P0/P1 分开交付。执行器必须具备：

1. 主库 Online Backup 和备份校验；
2. 预览 token / 数据 revision 校验，防止预览后数据已变化；
3. 单事务、子表优先的确定性清理顺序；
4. 每个表的删除数、保留数和原因审计；
5. 执行前后 `PRAGMA foreign_key_check`、核心统计计数和聚合等价性对比；
6. 任一断言失败整笔回滚；
7. 不自动删除 `plays`，不自动猜测缺失父实体。

音乐实体残留、AI 任务日志和聊天历史应使用不同保留策略，不能用一个“清理全部”按钮处理。

## 7. 前端修复设计

### 7.1 设置页重建状态

涉及入口：`frontend/src/hooks/useSettings.ts`、`frontend/src/pages/SettingsPage.tsx`、query keys 和相关测试。

实施内容：

1. 删除 `rebuildPendingOverride` 这类页面局部真相。
2. 设置保存成功时，把服务器返回的新设置写入 settings query cache；若返回不完整，则精确 invalidation 并 refetch。
3. 重建成功时立刻把响应中的 `rebuild_pending=false` 写入同一 query cache，然后做一次后台 refetch 校验。
4. 离开设置页再返回、页面刷新或另一个组件消费设置时都读取同一个缓存事实。
5. 后台预热使用独立提示，不继续复用“统计口径待生效”。

### 7.2 数据健康治理首页

推荐信息结构：

```text
┌ 数据可正常使用 ──────────────────────────┐
│ 92,908 条播放已可统计                    │
│ 核心统计问题 0 · 历史残留 3 类 · 说明项 1 │
└──────────────────────────────────────────┘

需要现在处理（仅有时显示）
建议整理（默认折叠）
  - 历史曲目/专辑关系残留   当前播放影响：0
    [查看原因] [预览可整理内容]
说明
  - 237 条播放缺少曲目实体，原始记录已保留

技术详情（高级，默认折叠）
```

设计要求：

- 不再用整页琥珀色表达“有任何非零项”。
- 卡片标题用用户语言，技术表名和外键放进“技术详情”。
- 每张卡必须显示影响范围、受影响播放数和建议动作。
- 无动作的问题不显示主按钮。
- 历史残留的默认动作是“预览”，不是“立即清理”。
- Desktop 可以执行治理；Phone 至少显示结论、影响和“请在电脑端处理”的具体原因，不能完全隐藏状态。

### 7.3 “导入前检查”改为“检查本地数据包”

入口采用三步流程：

```text
1 检查数据包  →  2 查看导入建议  →  3 确认并导入
```

结果页分成四个区块：

1. **是否可以继续**：可继续 / 需要补文件 / 需要人工确认。
2. **系统建议**：增量导入、完整替换或首次建立识别基线，并说明原因。
3. **发现了什么**：真实重复、仅日期边界重叠、账号档案状态。
4. **文件详情**：音频、视频、账号档案按组折叠，显示文件名、年份/日期范围和数量。

首次 baseline 的推荐文案：

> 这是首次建立数据识别基线。当前数据包与数据库总量和日期范围一致，但还不能逐条比较新增或移除记录。系统会先创建数据库快照，再执行一次完整替换并保存基线，方便以后安全地做增量导入。

此状态下：

- 隐藏“复用 0 / 新增 92,908 / 移除 0”；
- 主按钮改为“建立导入基线（推荐）”；
- 明确说明会先备份、再完整替换；
- `shared_record_count=0` 的日期重叠显示为“文件时间范围相邻或交叠，未发现相同记录”，不用警告色。

### 7.4 视觉与交互规范

- 使用现有设计 token、卡片和状态组件，不新增平行设计系统。
- 状态颜色只表达行动等级：红色=阻塞，琥珀=需要操作，蓝/灰=说明，绿色=可正常使用。
- 一屏只保留一个主操作；详情、样例和技术信息按需展开。
- 长文件列表默认按类型聚合，避免 13 个相似卡片连续堆叠。
- 异步检查显示正在执行的阶段和预计原因，不用只有一个持续 10–16 秒的无解释 spinner。
- 所有展开按钮、状态标签和主操作满足键盘、读屏和 44×44px 触控目标要求。

## 8. 分阶段实施顺序

| 阶段 | 优先级 | 交付物 | 完成门禁 |
|---|---|---|---|
| Phase 0：回归锁定 | P0 | 当前错误场景 fixture、API/cache 回归测试、真实库只读基线报告 | 测试先稳定复现旧问题 |
| Phase 1：重建状态修复 | P0 | 后端权威响应、前端 query cache 同步、移除局部 override | 重建后跳转离开并返回不再提示 |
| Phase 2：健康口径修复 | P0 | 共享 Album Project 资格判定、影响范围计数、领域拆分 | 当前快照 17 个假阳性归零，正例仍能报错 |
| Phase 3：健康治理 UI | P1 | 新 summary/issue 契约、健康首页、详情抽屉、Phone 摘要 | 用户无需理解外键即可判断能否使用和是否处理 |
| Phase 4：导入准备 UI | P1 | comparison status、重叠分级、三步流程、文件分组 | baseline 缺失时不再显示虚假新增数 |
| Phase 5：只读清理预览 | P1/P2 | 样例分页、可达性、依赖和预计动作报告 | 对主库零写入，报告可复核、可导出 |
| Phase 6：受控清理 | P2，另行授权 | 备份、revision 锁、事务执行、审计与回滚 | 数据库副本和完整全栈门禁通过后才可触及主库 |

Phase 1 与 Phase 2 可以在同一开发迭代中完成，但必须分别验收；Phase 6 不属于前五阶段的默认完成条件。

## 9. 测试与验收矩阵

### 9.1 后端单元测试

- `rebuild_pending` 只在核心重建成功后清除；失败时保留。
- `GET /api/settings` 与持久化状态一致，不受旧模块缓存污染。
- single、compilation 不进入缺少 Album Project 的问题集合。
- 混合 Spotify 链接时，健康检查与构建器给出相同资格结果。
- 名称匹配 single 不因另一个弱关联 album 链接被误判。
- 真实 album 正例缺 membership 时仍能被检出。
- `album_type=unknown` 且曲目数达到兜底阈值的行为有明确 fixture。
- 音乐外键、AI/chat 外键和缺 track 的 plays 被分到正确影响范围。
- preflight 的 `baseline_missing`、边界重叠和真实重复分类正确。

### 9.2 后端契约测试

- 重建响应新增字段向后兼容。
- 健康 summary 和 issue 字段稳定、枚举受约束。
- cleanup preview 零写入，并受分页/数量上限约束。
- 不可比较时 `record_delta_comparable=false`。

### 9.3 前端测试

- 保存设置 → pending=true → 重建成功 → pending=false。
- 重建后在 5 分钟 `staleTime` 内离开设置页再返回，banner 不复现。
- 后台 warming 不显示“口径待生效”。
- `safe_to_use=true` 且只有历史残留时显示绿色可用结论。
- 受影响播放为 0 时明确展示 0，不使用模糊“可能影响”。
- baseline 缺失时隐藏差异 KPI，显示建立基线说明。
- `shared_record_count=0` 使用中性状态。
- 文件按音频/视频/账号档案分组并可展开。
- Desktop 与 Phone 都能读取结论；Phone 不提供危险写操作。

### 9.4 真实数据库副本验收

只在副本上执行完整导入、维护或清理演练：

- 对当前快照，17 个错误 Album Project 告警应归零。
- 3,098 / 1,590 / 43 / 2 / 237 的分类和可达性统计可复算。
- 修复健康口径前后，92,908 条播放总量和现有实体统计不发生变化。
- cleanup preview 不改变任何表的 `data_version` 或行数。
- 若未来执行清理，前后播放总量、逻辑事件数、时长、Billboard 和六套搜索快照按规则等价；任何差异都阻塞发布。

### 9.5 浏览器验收

至少覆盖 Desktop 1440×900 和 Phone 390×844：

- 重建完整交互、路由往返和刷新；
- 健康页首屏结论、展开/收起、技术详情和空态；
- preflight 10–16 秒等待期间的阶段反馈；
- baseline、真实重复、边界重叠、阻塞文件四类状态；
- 横向溢出、操作遮挡、滚动位置、键盘焦点、44×44px 触控目标。

### 9.6 项目级门禁

按风险从局部到完整执行：

```bash
.venv/bin/pytest backend/tests/unit/test_import_health.py -q
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q
cd frontend && npm test
cd frontend && npm run build
python3 scripts/docs_audit.py
sh scripts/phase5_check.sh
sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173
```

局部测试通过只能标记为 Partial；默认完整全栈检查全部必需阶段通过，才可标记本地全栈 Pass。

## 10. 发布、兼容与回滚

- Phase 1–4 的 API 以新增字段为主，先后端兼容发布，再切换前端消费。
- 旧前端仍可读取现有 `status` 和 `rebuild_pending`；新前端遇到旧后端时降级为旧展示，但不得自行猜测 `safe_to_use`。
- 若状态修复出现问题，可回滚前端展示，但不能恢复页面局部 override；应继续以 refetch 获取服务器事实。
- 健康口径修复发布后记录一次真实数据库只读报告，确认假阳性消失而正例仍有效。
- 清理执行器若未来上线，默认关闭，必须显式进入预览和确认流程；失败优先回滚数据库，不依赖前端补偿。

## 11. 文件级改动地图

预计涉及但不限于：

| 领域 | 主要文件 |
|---|---|
| 设置 API | `backend/api/settings.py` 及设置持久化 service/repository |
| 健康检查 | `backend/domains/metadata/import_health.py` |
| 专辑资格 | `backend/domains/playback/album_projects.py` 或提取出的共享模块 |
| 导入 preflight | 现有 import API/service 和 response schema |
| 后端测试 | `backend/tests/unit/test_import_health.py`、settings/import contract tests |
| 设置数据层 | `frontend/src/hooks/useSettings.ts`、`frontend/src/api/query-keys.ts` |
| 设置页面 | `frontend/src/pages/SettingsPage.tsx` |
| 健康 UI | settings/import health 相关 feature components |
| preflight UI | `frontend/src/features/settings/components/ImportPreflightPanel.tsx` |
| 前端测试 | settings、import health、preflight、mobile settings tests |
| 当前规则 | `docs/reference/data-import-and-health.md`（实现落地时同步） |
| 交付证据 | `docs/reports/` 下新增带日期验收报告 |

实施时如果这些文件已有并行修改，必须逐 hunk 合并，不能覆盖其他工作。

## 12. 完成定义

只有同时满足以下条件，P0/P1 才算完成：

- 点击应用改动并重建后，路由往返、刷新和缓存有效期内都不再出现旧 pending 提示。
- 数据库、`GET /api/settings`、重建响应和前端 query cache 对 pending 的判断一致。
- 当前真实数据库不再因 17 个 single / compilation 显示 Album Project 未完成。
- 健康页首先明确“核心统计是否可用”，并把当前影响、历史残留、非音乐残留分开。
- “外键关系残留”都有通俗解释、影响数量和建议动作。
- baseline 缺失时不再把 92,908 显示成新增记录。
- 日期范围重叠但共享记录为 0 时不再使用警告语气。
- 文件列表完成分组、折叠和真实文件信息展示。
- Desktop 和 Phone 完成真实视口与交互验收。
- 未经额外授权，没有删除、改写或猜测补全任何真实数据。

Phase 6 的历史数据实际清理必须作为单独任务、单独审批和单独验收，不能被“页面修好了”隐含授权。
