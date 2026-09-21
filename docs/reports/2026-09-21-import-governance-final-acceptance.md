# 数据导入处理与治理 S6 最终验收报告

> 日期：2026-09-21
> 规划：S0–S6 全部实施
> 实现状态：IMPLEMENTED
> 验证状态：PASS（真实隔离副本 + 故障恢复 + 性能 + API + 浏览器 + 默认完整 fullstack）
> Git：S0–S5 已提交 `ae6febc`、`d37c9af`、`37c8431`；S6 与收口随本报告所在提交交付；UNPUSHED
> 部署：NOT_DEPLOYED

## 结论

导入事故修复规划的 S0–S6 已全部完成。串流输入、播放事实、指纹基线、活动来源和派生阶段由同一批次与代际证据串联；事实提交后的派生失败不会再默认整库回滚；关键任务不依赖封面队列排空；played 与全量治理范围分别可见；Settings 提供可刷新、可重启恢复的持久导入工作台。

最终真实副本从 92,908 条旧事实导入至 94,760 条，新增 1,852、删除 0，保留 2 条迟到记录。三次独立副本运行全部通过 14 项语义对账、四套公开搜索快照、replacement 对照和再次导入 noop。正式 `data` 没有再次导入；本轮没有 push 或部署。

## S0–S5 交付状态

| 阶段 | 结论 | 主要证据 |
| --- | --- | --- |
| S0 | PASS | 父子元数据写入、played/all 范围与 92,908→94,760 事故基线固化；见 [S0 报告](2026-09-21-import-remediation-s0-baseline.md) |
| S1 | PASS | 不可变批次、活动来源 resolver、独立控制库、发布日志、writer lease、成套恢复和 noop 零写入 |
| S2 | PASS | 持久阶段、attempt/证据、generation/revision fence、启动恢复和结构化错误 |
| S3 | PASS | 优先级与资源 lane、target 去重、依赖顺序、1,204 个封面排队不阻塞关键任务 |
| S4 | PASS | played 6,642 个身份无硬问题；全量 6,675 个身份含 33 个治理项；238 条未匹配音频完整分类 |
| S5 | PASS | Phone/Compact/Desktop 共用持久工作台、历史、报告、重试和三维结果；见 [S1–S5 报告](2026-09-21-import-remediation-s1-s5.md) |

## 真实副本正确性

三个样本均从同一经核对旧种子创建相互独立的 SQLite、原始来源、缓存与控制目录；元数据/provider 输入冻结，不向 Spotify 发出验收请求。

| 样本 | 总 wall ms | 增量链路 ms | noop 预检 ms | 峰值 RSS | 结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| sample-1 | 341,005.436 | 85,917.299 | 6,528.769 | 2,025.56 MiB | PASS |
| sample-2 | 312,395.238 | 72,021.779 | 5,256.846 | 2,037.16 MiB | PASS |
| sample-3 | 314,862.506 | 71,619.504 | 5,196.540 | 2,034.84 MiB | PASS |
| median | 314,862.506 | 72,021.779 | 5,256.846 | 2,034.84 MiB | PASS |

每个样本同时满足：

- 旧基线 92,908 条可初始化且相同输入为 noop；新包关系为 `snapshot_superset`，新增 1,852、删除 0、最终 94,760。
- 两条早于旧最大时间的迟到记录保留；开放边缘周不发布周榜，但非榜单事实仍进入统计。
- 事实集合、原始时长、年度分区、credits、track groups、Album Projects、Billboard、Home/Archive、Power、Records、Year-End 与四套搜索快照共 14 项语义对账一致。
- 再次导入关系为 `identical`；播放事实、语义 revision、派生调度和数据库备份均不写入。
- L2/L3 × fixed/dynamic 四套公开搜索 target 全部 ready；兼容 L1 不冒充当前必需公开集合。

原始样本使用 `import_governance_real_acceptance_v1`。其中字段名 `peak_rss_kib` 在 macOS 上实际保存 `ru_maxrss` 的字节值；上表按字节换算 MiB。脚本已升级为 v2，以 bytes/MiB 明确输出；没有为了改字段名重跑三次昂贵样本或改写原始证据。

## 恢复、隔离与状态边界

恢复/队列矩阵共 190 项定向测试通过，并在最终审计中补齐以下边界：

- durable quarantine 只允许所属 run 穿越，其他 writer 继续 fail-closed；`sources_published` 与 gate 清除由同一控制事务/CAS 完成。
- 启动在 migration 前检查恢复与 gate 状态；证据不足时拒绝继续写入，不让迁移成为隔离窗口内的新提交。
- Year-End warming、无 LKG 但仍有活动 job、自动晋升 ready 和 failed/unavailable 分别映射，不返回虚假 ready 或 0。
- 阶段依赖 revision 排除发布账本、job 和错误记录自身的记账变化；重启时可复用已证明的 `core_ready` 早期阶段。
- 新 generation/revision 取代旧任务时，旧输出不得激活；事实提交后的派生失败只重试正确阶段，不重复播放 ETL。

真实 API 使用 `/tmp/spotifystats-s6-api-v2/spotify_stats.db`。无操作执行前后主库状态与 mtime 不变，未创建 import backup。隔离 helper 同步更新 Home 主库身份与 snapshot root，修复了副本被误判为非主库而无法发布公开 Home 快照的问题。

## 性能、API 与浏览器

- ready 基线冷预检三次：5,666.722 / 5,300.994 / 5,539.753 ms，median 5,539.753 ms。
- 独立 21 个 hot 样本：median 69.662 ms、P95 71.258 ms、max 75.725 ms，满足 P95 ≤500 ms。
- 最终默认 fullstack 的 22 轮热 API：Import Preflight median 69.443 ms、P95 70.113 ms；所有监测端点 hot P95 均低于 500 ms。
- API smoke 153/153；OpenAPI 234 operations、0 unaccounted；GET 149/162 覆盖、13 个明确排除、0 unaccounted。
- 独立真实浏览器检查覆盖 Desktop、Compact、Phone：导入 noop 流程、状态/历史、44×44 主要触控目标、无横向溢出、无本机绝对路径泄漏。
- 默认浏览器门禁覆盖完整路由与五档 viewport、桌面/移动交互、图表、长列表、40 组控件 inventory，以及 Chromium、Firefox、WebKit；全部 PASS。

验收中先后发现三处测试合同已落后于新界面/合法状态：导入工作台仍查找旧“串流数据”，移动筛选只接受 unavailable 而不接受 ready，跨浏览器脚本仍使用旧导入文案。三处均改为验证当前非写入合同并补回归测试，随后在同一默认完整 run 中通过。

## 默认完整本地门禁

最终 run：`20260921T124842.178610Z-150a940588e1`，mode=`full`，总耗时 1,399,250 ms。

| 必需阶段 | 状态 | 耗时 ms |
| --- | --- | ---: |
| preflight | PASS | 8,039 |
| quality | PASS | 38,271 |
| backend | PASS | 500,967 |
| api | PASS | 175,055 |
| browser-routes | PASS | 399,742 |
| browser-interactions | PASS | 80,085 |
| browser-inventory | PASS | 45,606 |
| browser-compat | PASS | 151,353 |

门禁明细：Backend seed 2,923 passed；真实 integration 187 passed；Frontend 86 files passed / 1 skipped、669 tests passed / 4 skipped；production build、pre-commit、mypy、ruff、secrets 和文档审计全部通过。

warning 未被虚写为零：seed 有 1 个 LibreSSL/urllib3 环境 warning 与 3 个 AnyIO HTTP 422 弃用 warning；integration 有同一 LibreSSL warning；Vite 保留大 chunk 建议。它们没有改变本次导入合同或门禁结果。

## 数据与交付边界

- 三次真实导入和 API/浏览器使用隔离副本；正式播放事实保持 94,760。开发服务此前仅被动应用 migration 79，没有再次导入或执行治理清理。
- 机器可读 raw samples 保留在本机 `/tmp/spotifystats-s6-real-sample-{1,2,3}.json`，不提交真实数据、SQLite、缓存、恢复点或本机路径明细。
- 原事故 HTTP 500 缺少足够历史堆栈，仍标记为“根因未证实”；本轮交付的是结构化诊断、限定重试和已证明路径，而非猜测根因。
- 没有自动清理 33/238 治理项，没有删除历史恢复点，没有 push、正式数据迁移或部署。
