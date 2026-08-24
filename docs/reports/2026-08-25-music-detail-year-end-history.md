# 音乐详情页年榜历史交付与验收

> 状态：**Pass（功能范围）**
> 证据日期：2026-08-25
> 范围：歌曲、L1/L2/L3 专辑、艺人详情的年榜投影、API、榜单成绩 KPI、年度历史与响应式展示。

## 交付结论

- 三类详情的“榜单成绩”同时保留周榜趋势/历史，并在周榜历史下增加独立年榜历史。
- “年榜最佳”和“年榜入榜”位于榜单成绩页顶部统计组，与最高排名、在榜周数、走势点数、在榜跨度同级；详情 Hero 不展示年榜内容。
- 年榜名次沿用现有 Billboard 的 Playfair Display 衬线数字；完整年度不显示冗余状态，阶段年度在年份旁使用轻量“进行中”标记，年榜最佳来自阶段年度时仍明确提示。
- 年榜历史移除独立“覆盖范围”列；桌面排名使用周榜同款两位数字与色阶，上榜播放使用同宽 70px 视觉条，积分与周数统一为无衬线数值配小单位。Phone 改为年度头、两项主要指标和四项周成绩的三层卡片。
- 本次不增加年榜趋势图：单实体年度点稀疏，且阶段年度与完整年度连线会造成连续、可直接比较的错觉。
- `summary` 不读取年榜投影；`overview/full` 才读取持久化摘要与历史，详情 GET 不触发完整 Billboard 或 Year-End 冷构建。

## 数据与生命周期

- migration 46 新增年榜投影 state、年度覆盖 meta 和实体年度成绩三张表。
- migration 47 修复短暂发布过的 v46 覆盖状态约束，保证已应用旧 v46 的数据库可前向修复。
- 年榜投影由精确音乐查找周账本派生，并复用公共 Year-End 指标、计分、覆盖和排序函数。
- shared-full、同周/跨周 delta、旧 snapshot 复用、重发失效和 pruning 均接入投影生命周期；投影失败独立记录和重试，不把已可用的核心搜索 snapshot 降为 failed。
- 启动跳过条件同时检查六套精确 snapshot 与六套当前版本投影；旧库只有 ready snapshot 时会幂等排入一个 snapshot-set 后台任务并先标记 `pending/warming`。处理器失败会把残留 pending 转为 failed，成功后再次启动不重复排队。

## 升级路径纠正

最初的交付验收只证明了新建/维护路径可以生成投影，没有覆盖“旧主库已经有六套 ready snapshot，但迁移后账本与投影为空”的真实升级状态。因此当时页面仍返回 `unavailable`，此前的完成口径在这条升级路径上不成立。

本次修复补上组合 readiness 与启动自动排队，并用隔离副本从上述精确旧库状态完成端到端复验。开发后端的自动重载在修复代码保存后已经先触发了主库后台回填，时间早于随后手工创建的备份；因此不能声称该备份是即时回填前备份。项目仍保留较早的 `spotify_stats.after-jolin-external-id-20260824.db`，并在回填后使用 SQLite Online Backup 新增 `data/backups/spotify_stats.after-year-end-upgrade-20260825.db`，后者完整性检查为 `ok`。

## 真实数据库副本证据

主库与 SQLite Online Backup 隔离副本均包含 92,908 条 plays，已应用 migration 46/47。主库后台任务 `005161ec-1db` 一次完成回填；隔离副本先清空周账本与投影、保留 ready snapshot，再由当前启动流程自动生成。

| 检查 | 结果 |
|---|---:|
| `integrity_check` | `ok` |
| 投影状态 | 6 / 6 `ready` |
| 年度覆盖行 | 30 |
| 实体年度成绩 | 3,300 |
| track / album / artist | 1,500 / 900 / 900 |

隔离副本只出现一个新的升级任务 `b6f70ff4-dee`：启动后依次观察到 `pending/running`、部分 ready、最终 6 / 6 ready；周账本 90,448 行、年度覆盖 30 行、实体年度成绩 3,300 行。停止并再次启动同一副本后没有新增任务，证明自动补建幂等。主库当前同样为 6 / 6 ready，Online Backup 的 `integrity_check` 为 `ok`。

副本 `foreign_key_check` 为 7,831 条，与原始数据库检查基线相同，均为既存 AI task 引用问题；本次投影没有增加差值，因此不能表述为全库 FK clean。

真实实体抽查：

- 单曲 `Espresso`：2024 年榜 `#28`，完整年度。
- 专辑 `Short n' Sweet`：最佳 2025 `#4`；2026 `#9` 为阶段年度；共 3 个年度入榜。
- 艺人 `Sabrina Carpenter`：最佳 2025 `#4`；2026 `#4` 为阶段年度；共 3 个年度入榜。

## API 与性能

- 三类详情 OpenAPI 均声明 `year_end_status`、`year_end_summary`、`year_end_history`，前端 OpenAPI 快照与生成类型已同步。
- 当前主库实测：三类 `summary` 按设计返回 `unavailable / null / []`；对应 `overview` 返回 `ready` 和年榜历史。
- 当前主库直连抽样：track summary 190.27ms / overview 11.57ms，album summary 39.84ms / overview 9.79ms，artist summary 18.55ms / overview 11.50ms，三类首屏均小于 500ms。
- 抽样详情请求前后后台音乐查找任务数保持 47，不会因详情 GET 触发构建。

项目级 `loading_performance_probe.py` 总状态为 **Partial**：本功能相关的三类 summary 门禁均 Pass；整体仍被既存 home warm 123.51ms（门槛 80ms）、track stats 客户端观测 1026ms（服务端计时约 2.4ms）和 artist stats cold 1577.69ms（门槛 1500ms）阻断。这些失败不在本次年榜路径，但未被描述为全局性能 Pass。

## 浏览器验收

使用真实开发前后端和 Playwright 验收 1440×1000 Desktop 与 390×844 Phone：

- track、album、artist 的 Hero 均无年榜文案或旧徽章。
- 三类页面均显示“年榜最佳 / 年榜入榜”，且位于排名趋势之前的统计组。
- album Desktop 显示无覆盖列的年度表格；Phone 显示三层年度卡片且桌面表格不挂载为可见内容。
- 周榜历史在上、年榜历史在下；2026 阶段标签可见。
- Desktop 三行上榜播放视觉条均为 70px，与周榜历史一致；Phone 视觉条随卡片主指标区域自适应。
- Desktop 与 Phone 的 `body.scrollWidth === body.clientWidth`，无横向溢出。
- 年榜 KPI 名次与年度历史名次的计算字体均为 `Playfair Display Variable` 回退链。
- 控制台 0 error、0 warning；仅有开发提示和既有 ECharts info log。

## 自动化验证

- 后端 unit：**1,360 passed**。
- 后端 contract：**375 passed**。
- 修复相关维护、投影与启动升级定向测试：**39 passed**。
- 前端：**74 files / 565 tests passed**。
- 前端生产构建：**Pass**（保留既有大 chunk warning）。
- Ruff 定向检查：**Pass**。
- 文档审计：**Pass，69 个当前 Markdown**。
- `git diff --check`：**Pass**。

未运行项目默认完整 `fullstack_verification_check.sh`，因此本报告只给出本功能范围的 Pass，不声称项目级默认全栈门禁 Pass。未执行 commit 或 push。
