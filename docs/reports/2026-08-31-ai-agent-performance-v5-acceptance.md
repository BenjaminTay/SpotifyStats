# AI Agent Performance V5 实施与验收报告

- 验收日期：2026-08-31—2026-09-01
- 实现状态：`IMPLEMENTED`
- 问答质量与性能：`PASS`
- 年度报告质量与性能：`PASS`
- 崩溃恢复与 SSE：`PASS`
- 响应式浏览器：`PASS`
- 默认完整全栈：`PARTIAL`
- 仓库：分支 `codex/ai-agent-performance-v5`；实现提交 `e39c754a`、`919231fe`、`d75a562f`；文档与移动端收口提交另计
- 远端：`UNPUSHED`
部署：`NOT_DEPLOYED`

## 目标与结论

V5 不扩张为通用多 Agent 平台，而是把 V4 已经成立的最小真实 Agent 补成可日常使用的产品链路：继续采用模型决策—只读工具—观察—再决策循环和可重放事件日志，同时解决年度报告重复冷构建、模型 writer 空完成、真实库迁移兼容和移动端状态反馈。

本轮实测结论：问答 33/33 通过，年度报告冷/热路径均满足门禁，分章节模型写作不再全部退回确定性模板，崩溃后可以从工具 checkpoint 恢复，SSE 可以从复合 cursor 续传；AI 页面能明确展示章节回退数量。它已经达到“最小但真实、可工作的应用内 Agent”，但仍严格限定为本地播放分析领域和后端注册的只读工具，不等于通用 Coding Agent。

## 架构变化

### 共享年度上下文

- 新增 revision、filter、year 精确绑定的年度上下文快照，记录 context key、构建次数、缓存命中和分阶段耗时。
- 报告研究、章节写作和最终校验消费同一份共享上下文，避免每一章节重复扫表。
- Agent 上下文只读取已发布 Year-End 投影或语义 LKG；不在交互热路径冷建完整个人 Billboard。
- 艺人排行只加载 credited artist frame；详情比较允许读取与同一语义范围一致的 LKG。

### 分章节 Writer 与事实门禁

- 章节按计划分别生成、校验和 checkpoint；最终报告只有在 critic、事实校验和 artifact 质量全部通过后才缓存。
- DeepSeek 研究步骤显式开启 thinking，章节正文显式关闭 thinking，避免思考 token 吞尽正文额度。该参数行为按 DeepSeek 官方 [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) 文档核对。
- writer 返回的无证据数字会被确定性剔除并重新审计；标题缺失时只回退计划标题。
- 单章失败允许确定性补齐，但前端显示“X 个章节已用本地数据补齐”，不把混合产物伪装成纯模型结果。

### 兼容、观测和门禁

- schema 最新版本升至 72，并幂等补建 Agent 事件日志，修复既有数据库中 migration 69 已被其他功能占用的升级冲突。
- 显式日期范围统一归一为 `period=custom`，防止空年份误读为 lifetime 数据。
- 记录 context、section writer、provider、tool 和总任务耗时，并提供问答与年度报告性能评估脚本。
- 前端增加共享上下文、分章节写作阶段标签和章节回退状态；390px 下报告区全部按钮达到 44×44px 最小触控目标。
- Vite 开发服务显式允许 worktree `node_modules` symlink 的真实路径，修复字体资源被 filesystem allow-list 拒绝而产生的 403。

## 安全数据与 Provider 边界

- 真实数据来自 SQLite Online Backup 副本 `/tmp/spotify-agent-v5-acceptance.A40Fss/spotify_stats.db`；副本有 92,908 条 `plays`，`PRAGMA quick_check=ok`。
- V5 工作树中的 `data/spotify_stats.db` 和 `data/yearly_review_cache.db` 仅为指向 `/tmp` 验收副本的忽略 symlink；没有修改 live SQLite。
- Provider 只核对启用状态、provider/model 字段和 Key 存在性/长度，未输出 Key 值。
- Agent 权限仍是后端 read-only allowlist；没有开放任意 SQL、任意 URL、设置、导入、缓存写门禁或歌单写入。

## 真实模型问答验收

最终文件：`/tmp/spotify-agent-v5-acceptance.A40Fss/question-33-final-v2.json`。

- 33/33 `Pass`，`Partial=0`，`Fail=0`，通过率 100%。
- Turn P95：42.087 秒，门禁为不超过 60 秒。
- Tool P95：21.672 秒，门禁为不超过 45 秒。
- 写操作、任意 SQL、外部榜单和 API Key 等安全题全部拒绝执行。
- P0-11 的 2010 范围明确返回无本地播放数据；修复前该题错误落入 lifetime，是本轮真实验收暴露并修复的问题。
- 静态矩阵为 141 题，含 P0 12 题与 golden 12 题，检查 Pass。

## 年度报告性能与质量验收

最终文件：`/tmp/spotify-agent-v5-acceptance.A40Fss/report-performance-acceptance-final.json`。

| 路径 | 任务 | 总耗时 | context | 模型接受章节 | 确定性补齐 | 质量门禁 |
|---|---|---:|---|---:|---:|---|
| 冷路径 | `5b32007990d6` | 123.825s | 新建 1 次 | 6 | 0 | 全部 Pass |
| 热路径 | `c57bfe5f5cb7` | 81.472s | 精确命中、构建 0 次 | 4 | 2 | 全部 Pass |

- 冷路径门禁不超过 240 秒，热路径不超过 180 秒，单次最多 2 个章节回退；全部满足。
- 独立冷 context probe 为 43.116 秒；优化前同一报告链路的 Year-End 冷构建曾单独耗时 279.312 秒。
- 优化前首轮完整报告耗时 483.917 秒且 6/6 章节回退；最终冷路径降至 123.825 秒且 0 章节回退。
- 这组数字只代表 2026-08-31 的本机、当前真实副本和当前 Provider，不自动成为生产 SLA。

## 崩溃恢复与 SSE

恢复任务：`b275123ab0e3`。

- 首进程在 3 次 `analysis_charts` 已持久化后终止，任务保持 `running`、`attempt_count=1`。
- 仅在隔离副本把该任务 lease 置为过期；新进程接管后为 `attempt_count=2`。
- trajectory 记录 `run_resumed={next_step:3, completed_call_count:3}`。
- 恢复后只新增 1 次 `analysis_stats` 和 1 次 `listening_hours`；3 次年度排行没有重复。
- 最终状态 `done`，5 个 Answer Contract 维度全部通过，`validation_issues=[]`。
- SSE 从 `v1:p11825:t2933:a1` 重连，只收到 `a2`、`a3`、`a4` 和 `task.completed`；旧 progress/tool 事件均为 0。

## 浏览器验收

环境：真实副本后端 `8015`、V5 前端 `5185`。

- Desktop 1280×720 问答页：`scrollWidth=clientWidth=1280`，console warning/error 为 0。
- Phone 390×844 问答页：`scrollWidth=clientWidth=390`，15 个首屏可见交互目标均至少 44×44px，console warning/error 为 0。
- Phone 390×844 年度报告：缓存报告正常渲染 3,321 字和“2 个章节已用本地数据补齐”；无横向溢出、无超出视口元素、console warning/error 为 0。
- 首次检查发现“去年 / 今年 / 复制”宽度只有 40–41px；修复后年度报告区全部可见按钮至少 44×44px。
- 自动路由矩阵覆盖 22 个默认页面、5 个动态详情页的桌面/手机视口，以及 6 个代表页面的五档视口；共 84 项，console error/warning、横向溢出均为 0。
- 控件清单在种子副本上检查 20 个页面、桌面/手机共 40 个场景，合计 1,567 个控件和 289 个主要触控目标，未发现命名或尺寸违规。

## 自动化验证

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

## 已知边界

- 仍是领域 Agent，不支持任意 SQL、文件、终端、网页或第三方写操作。
- 报告允许最多 2 个章节使用确定性补齐；界面会明确提示，不能把它理解为 100% 模型写作。
- 当前性能依赖已发布 Year-End 投影/LKG；当语义快照不存在时会明确降级，而不是在请求线程冷建完整榜单。
- 真实库 `/api/home/overview`、`/api/analysis/records` 和 Year-End 等既有确定性冷路径可能超过浏览器脚本等待窗口；本轮观测到 records 冷请求约 100.30 秒，属于后续独立性能治理范围。
- 当前全栈种子夹具不足以同时覆盖长列表翻页、搜索多结果和年度“语言”交互；本轮仅在 `/tmp` 副本补齐验收前提，没有把测试数据写入仓库。
- 本轮没有 push、没有生产部署、没有改 live DB；生产结论仍需独立部署门禁和运行时证据。

## 最终结论

V5 把“Agent 架构存在”提升为“真实数据下可以稳定完成任务”：问答以模型决定工具并根据观察继续，报告复用精确上下文并逐章写作，所有事实仍由确定性 builder/tool 提供，运行过程可恢复、可续传、可度量、可向用户解释回退。Agent V5 的功能、质量、性能和恢复目标已完成；仓库级默认完整全栈仍为 Partial，剩余项明确收敛到既有冷路径与验收夹具，而不是隐藏在 Agent 实现中。
