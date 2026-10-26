# AI Agent V3至V5实施验收

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。V3、V4和V5作为连续演进记录。V4年度报告性能FAIL、writer回退和各版全仓Partial保持原结论；V5问答与年度报告范围通过，后续主线集成与生产发布仍按正文补记日期分别判断。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [AI Agent Quality V3 实施验收报告](#ai-agent-quality-v3-实施验收报告)
- [AI Agent Quality V4 实施验收报告](#ai-agent-quality-v4-实施验收报告)
- [AI Agent Performance V5 实施与验收报告](#ai-agent-performance-v5-实施与验收报告)

## AI Agent Quality V3 实施验收报告

原记录：`2026-08-31-ai-agent-quality-v3-acceptance.md`。

验收日期：2026-08-31
实现状态：`IMPLEMENTED`
验证状态：`PASS（AI 功能范围）`
仓库状态：代码 `COMMITTED 1b75ae3d`；文档提交另计
当前交付状态：`SUPERSEDED_BY_V5`；V3 实现已经 V4/V5 继承，并随 `b0d674bd` 进入 `origin/main` 与 dual 生产环境

### 验收范围

本报告验证 AI 问答的路由、模型—工具—观察循环、证据校验、运行中转向、Provider 降级、真实数据库读取和前端呈现。它不代表生产部署，也不代表线上 SQLite 被修改。

### 数据和安全边界

- 来源库只通过 SQLite Online Backup 复制到 `/tmp/spotify-agent-v3.rNsd2m/spotify_stats.db`。
- 副本 `PRAGMA quick_check=ok`，119 张表、92,908 条 `plays`，文件大小 444,588,032 bytes。
- 所有真实 Agent 工具均为已注册只读工具；未执行任意 SQL、任意 URL、设置、导入、缓存或歌单写入。
- Provider 配置只核对启用状态、Provider、模型和 Key 存在性/长度；未输出 Key 值。
- 本报告对应的 V3 验收轮当时没有 push、部署或修改生产库；当前交付状态以上述 V5 集成结论为准。

### 真实模型门禁

使用当前配置的 DeepSeek 模型和真实数据库副本运行变更集 11 题：

- `Pass 11 / Partial 0 / Fail 0`
- 覆盖相对时间、个人榜单专辑比较、跨年 Top 5 表格、深夜歌曲、社区搜索、数据覆盖外年份和四个只读安全边界。
- 全部题目 `evidence_coverage=1.0`，没有最终 validation issue。

代表性结果：

| 用例 | 结果 | 工具与范围 | 总耗时 |
|---|---|---|---:|
| P0-01 去年夏天 | Pass | `analysis_charts` + `analysis_stats`，`2025-06-01..2025-08-31` | 91.8s |
| P0-03 专辑偏好 + 个人榜单 | Pass | 1 次 `compare_entities` | 22.7s |
| P0-04 2023–2025 Top 5 | Pass | 3 次 `analysis_charts`，受控并行 | 56.1s |
| P0-08 深夜歌曲 | Pass | `listening_hours` | 18.2s |
| P0-10 社区检索 | Pass | `community_feed_search` | 99.5s |
| P0-11 数据覆盖外年份 | Pass | `analysis_charts` + `wrapped_yearly` | 14.0s |
| 安全边界 5 题 | Pass | 0 工具、安全策略直接拒绝 | 16–53ms |

这说明“能工作”已经成立，但不能把它描述为所有问题都快。社区和部分分析工具的冷路径仍是下一阶段性能重点。

### 真实运行中转向

初始问题要求比较 GUTS 与 The Life of a Showgirl 的播放和个人 Billboard；第一步完成后，Inbox 收到：

> 只看今年，不要看 Billboard，再比较播放时长

最终状态与结果：

- Inbox 在下一 Step 被消费，动作是 `replace_constraints`。
- 时间范围裁剪为 `2026-01-01..2026-08-21`；请求的 2026 年末超出本地数据截止日，因此保留 requested/effective 两套日期。
- `excluded_dimensions=[personal_billboard]`，工具参数 `include_billboard=false`。
- 旧的 lifetime + Billboard 工具证据通过 `tool_evidence_invalidated` 失效。
- 最终只保留 1 个新约束下的 `compare_entities`：GUTS 271 次 / 14.3 小时 / 周均 8.14；The Life of a Showgirl 524 次 / 31.3 小时 / 周均 15.74。
- Evidence Sufficiency 的 cumulative、intensity、recency、fairness 均为 `covered`；`evidence_coverage=1.0`、`validation_issues=[]`。
- 最终答案不包含 Billboard、Power Score、榜单列或 `None` 空值。

### 性能修复证据

- 修复前，真实 `compare_entities` 全部时间冷构建约 120.2s；读取精确 ready 的已发布快照后约 0.7–1.0s，定制 2026 窗口约 1.6s。
- 模型首步通常只占数秒，原主要失败来自工具冷构建和总预算后丢弃已成功证据。
- 新运行时在工具成功后即使总预算耗尽，也以 `budget_degraded_fallback` 发布可追溯答案，而不是把任务标成 error。

### 浏览器验收

在真实后端与本地前端开发服务上检查 `/ai-insights?mode=chat`：

- Desktop：AI 模式切换、思考模式、问题输入、历史会话、Markdown 回答、证据卡片和工具轨迹均可见。
- Markdown 比较答案真实渲染为语义 `<table>`，不是纯文本表格。
- 390×844：`documentScrollWidth=documentClientWidth=390`；520px 表格位于 256px、`overflow-x:auto` 的局部容器中，不造成页面横向溢出；输入框宽 279px。
- 移动顶部导航、对话历史抽屉、底部主导航均可访问。
- 浏览器 console 的 error/warn 为 0。

由于通过浏览器新发真实问题会再次把个人播放问题和证据发送给已配置的外部模型，本轮没有为纯 UI 观察重复发起一轮；真实转向通过相同 HTTP/SSE/任务数据链路验收，约束状态组件另由前端测试覆盖。

### 自动化验证

- Agent 单元：258 passed。
- Agent 相关契约：33 passed。
- AI 前端定向：17 passed；生产 build Pass。
- 静态问题矩阵：141 题、P0 12 题、黄金问题 12 题，Pass。
- Ruff：Pass。
- 定向 mypy：Pass。
- 整仓 unit：1,526 passed / 2 skipped / 5 failed。5 项均为本分支基线已有的 Album Project OpenAPI smoke/operation/parameter 审计缺口；对应修复存在于原工作树的用户 dirty 文件，本工作树为保护其来源没有复制或提交，因此整仓 unit 标记为 `PARTIAL（非 AI 失败）`。
- 整仓 contract：415 passed。
- 整仓 frontend：78 files / 615 tests passed；生产 build Pass。
- 全递归 mypy：662 个文件中存在 29 个文件的 116 项既有类型债务，标记为 `PARTIAL`；本轮 9 个源文件定向 mypy Pass，提交 hook 对全部 15 个 staged Python 文件 Pass。

### 验收结论

`PASS（AI 功能范围）`：当前实现已经具备最小真实 Agent 的成立条件——模型决策、结构化工具调用、观察反馈、会话状态、运行中转向、事件事实源、证据充分性和安全降级均在真实数据库与真实模型上闭环。

未声明为 Pass 的范围：生产部署、线上数据库、跨主机 Worker、通用 Agent 能力，以及仍为分钟级的冷工具性能。

整仓门禁总状态为 `PARTIAL`，原因仅是上述 5 项基线 OpenAPI 审计缺口；AI 功能范围、完整 contract 和完整 frontend 均为 Pass。

## AI Agent Quality V4 实施验收报告

原记录：`2026-08-31-ai-agent-quality-v4-acceptance.md`。

实现状态：`IMPLEMENTED`
问答质量：`PASS`
恢复与流式：`PASS`
年度报告质量：`PASS（确定性写作回退）`
年度报告性能：`FAIL`
仓库：代码 `6437bdea`、`bc75a1ce`；文档提交另计
当前交付：`SUPERSEDED_BY_V5`；V4 实现已由 V5 完成性能收口，并随 `b0d674bd` 进入 `origin/main` 与 dual 生产环境

### 安全数据边界

- 生产数据只通过 SQLite Online Backup 复制到 `/tmp/spotify-agent-v4.D9nvlF/spotify_stats.db`，没有修改 live DB。
- 副本 `PRAGMA quick_check=ok`，119 张表、92,908 条 `plays`，444,588,032 bytes；schema 由 67 在副本内迁移到 70。
- Provider 只核对 enabled、provider、model 和 Key 存在性/长度，未输出 Key 值。
- 全部 Agent 工具来自只读 allowlist；没有任意 SQL、任意 URL、设置、导入、缓存门禁绕过或歌单写入。

### 真实模型问答门禁

增强后的 `changed` 门禁强制检查五维答案契约、`tool_evidence_v2`、constraint fingerprint、validation issue 和 evidence coverage。结果：`Pass 11 / Partial 0 / Fail 0`。

| 用例 | 结果 | 总耗时 | 工具耗时 | 工具数 |
|---|---|---:|---:|---:|
| P0-01 去年夏天曲风 | Pass | 20.3s | 7.8s | 2 |
| P0-03 专辑偏好 + 个人榜单 | Pass | 17.3s | 0.4s | 1 |
| P0-04 2023–2025 Top 5 | Pass | 50.2s | 16.2s | 5 |
| P0-08 深夜歌曲 | Pass | 49.1s | 33.0s | 1 |
| P0-10 社区 Olivia Rodrigo | Pass | 15.9s | 0.15s | 2 |
| P0-11 2010 无数据 | Pass | 21.4s | 4.6s | 3 |
| 写操作/SQL/外部榜单/API Key 5 题 | Pass | 14–31ms | 0 | 0 |

P0-10 的社区工具从首次真实运行约 227.1 秒降到 0.1–0.2 秒。它返回 `scoped_chart_snapshot` 与 LKG freshness，并明确完整帖子正文仍需完整 Feed 的限制。P0-11 明确回答该范围没有播放记录，不再把空排行当作已覆盖证据。

### Constraint Patch 与转向

真实任务 `7d86aff0401a` 在第一次工具调用后接收“只看今年，不要看 Billboard，再比较播放时长”：

- Patch schema 2，`operation=replace`，新增 `hours`，排除 `personal_billboard`。
- requested range 为 2026 全年，effective range 按数据截止日裁剪到 2026-08-21。
- 旧证据失效 1 份；最终只消费新约束下的 `compare_entities`。
- GUTS：271 次 / 14.3 小时 / 周均 8.14；The Life of a Showgirl：524 次 / 31.3 小时 / 周均 15.74。
- 最终答案契约 `pass`，`validation_issues=[]`，不包含 Billboard。

### 崩溃恢复与 SSE

恢复任务 `c8cab4bac4a7`：

- 首进程完成 3 次 `analysis_charts` 后被终止，task 保持 `running`、`attempt_count=1`。
- 仅在隔离副本把该任务 lease 置为过期，模拟 90 秒租约自然到期；新进程启动后接管为 `attempt_count=2`。
- trajectory 记录 `run_resumed={next_step:3, completed_call_count:3}`；恢复后只补跑 `analysis_stats` 和 `listening_hours`，原 3 个工具无重复。
- 最终 task `done`，Answer Contract `pass`，5 份 `tool_evidence_v2` 均有 constraint fingerprint。

SSE 对同一完成任务从 `v1:p11386:t2755:a1` 重连，只收到答案分片 `a2/a3/a4` 与完成事件；没有重放旧 progress 或 tool 事件。

### 年度报告真实验收

2025 年 `visual_yearly_artifact + agent_synthesis_v2` 经三轮暴露—修复完成质量闭环：

1. 首轮 599 秒虽返回 `done`，但 critic/fact 为 false、checkpoint 为 0，确认原软门禁会伪装成功。
2. 第二轮 651 秒被新硬门禁正确标记 `error`，没有缓存；6 个章节 checkpoint 已通过，仅缺月度趋势图观察。
3. 最终任务 `4dea3aca6edb` 在 677 秒完成并缓存：6 节、3345 字，critic、fact validation、final artifact quality、6/6 section checkpoint 全部 Pass；13 份 `tool_evidence_v2` 全部带 constraint fingerprint。

最终 metadata：`fallback_level=agent_writer_quality_fallback`、`writer_pipeline_status=fallback_visual_composer`。模型研究 Agent 实际调用年度/分析/Billboard 等只读工具，模型 writer 两次返回空内容，因此最终正文使用确定性长篇回退。报告事实质量 Pass，但纯模型写作只能标 Partial；677 秒性能标 Fail。

### 浏览器验收

真实后端 8014 + 本地前端 5184，页面 `/ai-insights?mode=chat`：

- Desktop 1280×720：无页面横向溢出；console error/warn 为 0。
- 通过 UI 提交“社区里 Olivia Rodrigo 相关帖子有哪些？”，任务 `592dd41eaad3` 在约 16 秒完成；页面显示 Agent 阶段、当前约束、最终答案和两条社区查询轨迹。
- 390×844：`scrollWidth=innerWidth=390`，无横向溢出；修复后 9 个可见按钮/开关全部至少 44px，思考模式 90×44、发送按钮 44×44；console error/warn 为 0。
- 开发服务因 worktree 复用原仓库 `node_modules`，Vite 终端报告字体文件超出 serve allow list；生产 build 正常打包字体，因此这是本地 worktree dev-server 环境边界，不是浏览器 console 或生产构建失败。

### 自动化验证

- 静态问题矩阵：141 题、P0 12、黄金问题 12，Pass。
- 变更相关单元：100 passed。
- 整仓 unit：1607 passed / 2 skipped。
- 整仓 contract：417 passed。
- 前端：78 files / 619 tests passed；production build Pass。
- 变更文件 Ruff / format：Pass；scoped Mypy（10 源文件，`follow-imports=skip`）：Pass；scoped ESLint：Pass。
- 整仓 Ruff：11 项既有脚本问题；整仓 ESLint：173 errors / 11 warnings；递归 Mypy 仍会进入未触碰模块并报告既有 Pandas/Literal 类型债务。它们不由本次改动引入，因此整仓静态门禁标 `PARTIAL（baseline）`。
- Git hooks：Ruff、format、Mypy、secret scan 均 Pass。

### 验收结论

V4 已达到“最小但真实、可工作的问答 Agent”：真实模型决策、工具观察、结构化转向、证据门禁、无数据语义、崩溃恢复、SSE 续传和响应式 UI 均闭环。

总体状态为 `PARTIAL`，不是因为问答正确性，而是年度报告的 677 秒冷路径与模型 writer 空完成仍不满足可交互的 Agent 体验。下一阶段应优先建设 revision/filter 精确的年度 ready snapshot、单次共享报告上下文和分章节 writer，不应通过增加模型权限、多 Agent 或任意 SQL 来掩盖性能问题。

## AI Agent Performance V5 实施与验收报告

原记录：`2026-08-31-ai-agent-performance-v5-acceptance.md`。

- 验收日期：2026-08-31—2026-09-01
- 实现状态：`IMPLEMENTED`
- 问答质量与性能：`PASS`
- 年度报告质量与性能：`PASS`
- 崩溃恢复与 SSE：`PASS`
- 响应式浏览器：`PASS`
- 默认完整全栈：`PARTIAL`
- 仓库：原验收分支 `codex/ai-agent-performance-v5`；实现提交 `e39c754a`、`919231fe`、`d75a562f`；2026-09-12 本地集成，2026-09-13 随 `b0d674bd` 推进到 `origin/main`
- 远端：`PUSHED（origin/main，代码发布基线 b0d674bd8a211c559aba023bbb92f18a98c80ba6）`
- 部署：`DEPLOYED（dual，b0d674bd8a211c559aba023bbb92f18a98c80ba6）`

### 2026-09-12 本地集成与 2026-09-13 发布补记

V5 已与当前本地主线完成隔离合并和回归，不再是待合并功能分支。集成保留主线的 L2/L3、全部收听时长、Billboard v4 与搜索发布门禁，并通过 migration 72/73 的幂等 repair 兼容主线与 Agent 分支曾经各自占用 schema 69 的两种历史。合并后的本地验证为：后端 unit 1672 passed / 2 skipped、contract 419 passed，前端 78 files / 622 tests 和 production build 通过。2026-09-12，集成候选先发布到远端 `codex/agent-v5-main-integration` 运行 No Deploy 门禁；2026-09-13，完整集成线随 `b0d674bd` 推进到 `origin/main` 并完成 dual 模式生产发布。

本次发布确认三个生产容器健康、私有与公开入口可用、数据库 `integrity_check=ok` 且 92,908 条播放事实保持不变；音乐搜索 migration 73、四变体快照和语义查询运行门禁通过。V5 的问答、年度报告、恢复和 SSE 结论仍以本报告记录的独立真实验收为准，生产发布只更新代码交付状态。

### 目标与结论

V5 不扩张为通用多 Agent 平台，而是把 V4 已经成立的最小真实 Agent 补成可日常使用的产品链路：继续采用模型决策—只读工具—观察—再决策循环和可重放事件日志，同时解决年度报告重复冷构建、模型 writer 空完成、真实库迁移兼容和移动端状态反馈。

本轮实测结论：问答 33/33 通过，年度报告冷/热路径均满足门禁，分章节模型写作不再全部退回确定性模板，崩溃后可以从工具 checkpoint 恢复，SSE 可以从复合 cursor 续传；AI 页面能明确展示章节回退数量。它已经达到“最小但真实、可工作的应用内 Agent”，但仍严格限定为本地播放分析领域和后端注册的只读工具，不等于通用 Coding Agent。

### 架构变化

#### 共享年度上下文

- 新增 revision、filter、year 精确绑定的年度上下文快照，记录 context key、构建次数、缓存命中和分阶段耗时。
- 报告研究、章节写作和最终校验消费同一份共享上下文，避免每一章节重复扫表。
- Agent 上下文只读取已发布 Year-End 投影或语义 LKG；不在交互热路径冷建完整个人 Billboard。
- 艺人排行只加载 credited artist frame；详情比较允许读取与同一语义范围一致的 LKG。

#### 分章节 Writer 与事实门禁

- 章节按计划分别生成、校验和 checkpoint；最终报告只有在 critic、事实校验和 artifact 质量全部通过后才缓存。
- DeepSeek 研究步骤显式开启 thinking，章节正文显式关闭 thinking，避免思考 token 吞尽正文额度。该参数行为按 DeepSeek 官方 [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) 文档核对。
- writer 返回的无证据数字会被确定性剔除并重新审计；标题缺失时只回退计划标题。
- 单章失败允许确定性补齐，但前端显示“X 个章节已用本地数据补齐”，不把混合产物伪装成纯模型结果。

#### 兼容、观测和门禁

- V5 分支先把 schema 升至 72 并幂等补建 Agent 事件日志；2026-09-12 与主线集成后再升至 73，以双向 repair 收敛 migration 69 曾被不同功能占用的两种既有数据库历史。
- 显式日期范围统一归一为 `period=custom`，防止空年份误读为 lifetime 数据。
- 记录 context、section writer、provider、tool 和总任务耗时，并提供问答与年度报告性能评估脚本。
- 前端增加共享上下文、分章节写作阶段标签和章节回退状态；390px 下报告区全部按钮达到 44×44px 最小触控目标。
- Vite 开发服务显式允许 worktree `node_modules` symlink 的真实路径，修复字体资源被 filesystem allow-list 拒绝而产生的 403。

### 安全数据与 Provider 边界

- 真实数据来自 SQLite Online Backup 副本 `/tmp/spotify-agent-v5-acceptance.A40Fss/spotify_stats.db`；副本有 92,908 条 `plays`，`PRAGMA quick_check=ok`。
- V5 工作树中的 `data/spotify_stats.db` 和 `data/yearly_review_cache.db` 仅为指向 `/tmp` 验收副本的忽略 symlink；没有修改 live SQLite。
- Provider 只核对启用状态、provider/model 字段和 Key 存在性/长度，未输出 Key 值。
- Agent 权限仍是后端 read-only allowlist；没有开放任意 SQL、任意 URL、设置、导入、缓存写门禁或歌单写入。

### 真实模型问答验收

最终文件：`/tmp/spotify-agent-v5-acceptance.A40Fss/question-33-final-v2.json`。

- 33/33 `Pass`，`Partial=0`，`Fail=0`，通过率 100%。
- Turn P95：42.087 秒，门禁为不超过 60 秒。
- Tool P95：21.672 秒，门禁为不超过 45 秒。
- 写操作、任意 SQL、外部榜单和 API Key 等安全题全部拒绝执行。
- P0-11 的 2010 范围明确返回无本地播放数据；修复前该题错误落入 lifetime，是本轮真实验收暴露并修复的问题。
- 静态矩阵为 141 题，含 P0 12 题与 golden 12 题，检查 Pass。

### 年度报告性能与质量验收

最终文件：`/tmp/spotify-agent-v5-acceptance.A40Fss/report-performance-acceptance-final.json`。

| 路径 | 任务 | 总耗时 | context | 模型接受章节 | 确定性补齐 | 质量门禁 |
|---|---|---:|---|---:|---:|---|
| 冷路径 | `5b32007990d6` | 123.825s | 新建 1 次 | 6 | 0 | 全部 Pass |
| 热路径 | `c57bfe5f5cb7` | 81.472s | 精确命中、构建 0 次 | 4 | 2 | 全部 Pass |

- 冷路径门禁不超过 240 秒，热路径不超过 180 秒，单次最多 2 个章节回退；全部满足。
- 独立冷 context probe 为 43.116 秒；优化前同一报告链路的 Year-End 冷构建曾单独耗时 279.312 秒。
- 优化前首轮完整报告耗时 483.917 秒且 6/6 章节回退；最终冷路径降至 123.825 秒且 0 章节回退。
- 这组数字只代表 2026-08-31 的本机、当前真实副本和当前 Provider，不自动成为生产 SLA。

### 崩溃恢复与 SSE

恢复任务：`b275123ab0e3`。

- 首进程在 3 次 `analysis_charts` 已持久化后终止，任务保持 `running`、`attempt_count=1`。
- 仅在隔离副本把该任务 lease 置为过期；新进程接管后为 `attempt_count=2`。
- trajectory 记录 `run_resumed={next_step:3, completed_call_count:3}`。
- 恢复后只新增 1 次 `analysis_stats` 和 1 次 `listening_hours`；3 次年度排行没有重复。
- 最终状态 `done`，5 个 Answer Contract 维度全部通过，`validation_issues=[]`。
- SSE 从 `v1:p11825:t2933:a1` 重连，只收到 `a2`、`a3`、`a4` 和 `task.completed`；旧 progress/tool 事件均为 0。

### 浏览器验收

环境：真实副本后端 `8015`、V5 前端 `5185`。

- Desktop 1280×720 问答页：`scrollWidth=clientWidth=1280`，console warning/error 为 0。
- Phone 390×844 问答页：`scrollWidth=clientWidth=390`，15 个首屏可见交互目标均至少 44×44px，console warning/error 为 0。
- Phone 390×844 年度报告：缓存报告正常渲染 3,321 字和“2 个章节已用本地数据补齐”；无横向溢出、无超出视口元素、console warning/error 为 0。
- 首次检查发现“去年 / 今年 / 复制”宽度只有 40–41px；修复后年度报告区全部可见按钮至少 44×44px。
- 自动路由矩阵覆盖 22 个默认页面、5 个动态详情页的桌面/手机视口，以及 6 个代表页面的五档视口；共 84 项，console error/warning、横向溢出均为 0。
- 控件清单在种子副本上检查 20 个页面、桌面/手机共 40 个场景，合计 1,567 个控件和 289 个主要触控目标，未发现命名或尺寸违规。

### 自动化验证

- 变更相关回归：215 passed。
- 后端 unit：1645 passed / 2 skipped。
- 后端 contract：419 passed。
- 前端：78 files / 622 tests passed；production build Pass。
- `python3 scripts/docs_audit.py`：Pass。
- `PATH=<project-venv>/bin:$PATH sh scripts/phase5_check.sh`：Pass。
- 默认完整全栈：`PARTIAL`。同一次默认运行的 quality、backend、API 阶段通过：后端 2,686 passed / 3 skipped，OpenAPI 220 项无遗漏，参数义务 102 项无遗漏，API smoke 147/147，API boundary 113/113；浏览器阶段在修复前因 worktree 字体 403 和真实库冷构建超时而失败。
- 修复后的 `browser-routes` 局部阶段 Pass：54 个默认/动态双视口检查加 30 个五档视口检查全部通过。
- 浏览器核心交互 Pass；真实副本上的 ECharts hover、legend 与 dataZoom 三项热路径重跑全部通过。
- `browser-inventory` 的控件清单 Pass，但长列表夹具中 4 个场景因页数/数据量不足而 Fail；`browser-compat` 的三引擎全部通过 28 个桌面/手机路由标记、搜索快捷键和三项核心导航，随后共同因种子年度报告没有“语言”标签而 Fail。
- 提交钩子：Ruff、format、Mypy、secret scan 全部 Pass。

Phase 5 首次直接调用系统 Python 时因系统环境缺少 `opencc` 退出；改用项目 venv 后完整通过。第二次 contract 运行出现一次测试后台线程在临时 SQLite 已回收后写入的 `disk I/O error` warning，但退出码和 419 个断言均通过，首次独立 contract 运行没有复现；因此记录为非阻断 teardown 抖动，不作为功能 Pass 的替代证据。

完整全栈之所以保留 `PARTIAL`，不是 Agent 核心链路未通过：真实模型问答、报告、恢复、SSE、手工响应式和相关自动化均已 Pass。未闭合的是仓库级门禁中既有确定性统计的真实库冷路径，以及种子夹具缺少长列表和年度“语言”交互数据。按项目约定，局部阶段和组合证据不能替代一次默认完整模式全绿。

### 已知边界

- 仍是领域 Agent，不支持任意 SQL、文件、终端、网页或第三方写操作。
- 报告允许最多 2 个章节使用确定性补齐；界面会明确提示，不能把它理解为 100% 模型写作。
- 当前性能依赖已发布 Year-End 投影/LKG；当语义快照不存在时会明确降级，而不是在请求线程冷建完整榜单。
- 真实库 `/api/home/overview`、`/api/analysis/records` 和 Year-End 等既有确定性冷路径可能超过浏览器脚本等待窗口；本轮观测到 records 冷请求约 100.30 秒，属于后续独立性能治理范围。
- 当前全栈种子夹具不足以同时覆盖长列表翻页、搜索多结果和年度“语言”交互；本轮仅在 `/tmp` 副本补齐验收前提，没有把测试数据写入仓库。
- 原 V5 专项验收当时没有 push、生产部署或修改 live DB；2026-09-13 后续集成线已推进到 `origin/main`，并随 `b0d674bd` 完成 dual 生产发布。本报告的真实模型和浏览器数字仍只代表当时的独立验收轮。

### 最终结论

V5 把“Agent 架构存在”提升为“真实数据下可以稳定完成任务”：问答以模型决定工具并根据观察继续，报告复用精确上下文并逐章写作，所有事实仍由确定性 builder/tool 提供，运行过程可恢复、可续传、可度量、可向用户解释回退。Agent V5 的功能、质量、性能和恢复目标已完成；仓库级默认完整全栈仍为 Partial，剩余项明确收敛到既有冷路径与验收夹具，而不是隐藏在 Agent 实现中。
