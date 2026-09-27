# AI Agent V6 统一运行时与渐进报告最终本地验收

> 验收日期：2026-09-22—2026-09-27
>
> 源码基线：`49bfadfdd8d87d1bedb7d52b0788f53e0f219cfa`
>
> 工作分支：`codex/ai-agent-v6`
>
> 实现状态：`SIXTH_ROUND_COMPLETE`；验证状态：`LOCAL_PASS`
>
> 仓库状态：实现已本地提交 `8edcd1c8`；远端状态：`UNPUSHED`；部署状态：`NOT_DEPLOYED`
>
> 本文验收数据对应合并前 V6 候选，保留当时版本与迁移编号；后续主分支集成验证见[本地集成报告](2026-09-27-ai-agent-v6-local-integration.md)。

## 1. 结论与边界

2026-09-27 第六轮已关闭 L3 composition 下 `vampire` 快照快路径 381 次、完整 Billboard 与成员事件 380 次的剩余差异。当前候选将搜索统计快照提升为 v12 并拒绝旧 builder LKG，修正单成员完整 builder 的计数来源，同时让快照榜单重建复用通过口径门禁的普通周聚合。12 个代表性组合、动态/固定阈值下全部 493 个有播放的多成员 L3 组、固定 11 题真实模型批次均通过；默认完整 fullstack run `20260927T123442.686018Z-e24f493b421d` 八个必需阶段同轮 `PASS`。当前仅达到本地验收，未 commit、push 或部署。

### 1.1 第二轮修复状态（2026-09-27）

- 已实现并定向验证：模型 dispatch 在网络 I/O 前原子预留并立即占累计调用/unknown 用量；每次 retry/fallback 都重新检查持久取消、lease 和剩余额度，控制流异常不进入 fallback。
- 已实现并定向验证：同一 logical call 首次保存完整不可变 request descriptor；恢复从 descriptor 读取 messages、tools、provider/model 与行为参数，当前配置不兼容时明确停止。
- 已实现并在真实浏览器验证：任务状态使用 generation/state version 调和；章节 HTTP 快照与 SSE 增量共享 generation/sequence 水位，失效递增章节版本并可撤回旧正文。
- 第二轮候选曾取得默认完整 fullstack run `20260926T181037.304893Z-b9a3b8ef2623` 八阶段 `PASS`；第三轮代码变化后的当前门禁状态以第 6 节新 run 为准，不沿用该历史结果。

### 1.2 第三轮恢复与预算补修（2026-09-27）

- 已修复 Chat 恢复无条件把 `current_step + 1` 当作下一步的问题。现在请求已冻结但响应未提交时保留原 step/call ID；响应已提交后不重发，部分工具只补缺失 observation，最后允许步骤的已提交回答可完成确定性校验与发布。
- 冻结请求恢复时核对原 provider/model、工具 schema 和行为参数；新 steer 不进入原请求，而是在原步骤完成后的下一逻辑步消费。provider、schema 或参数不兼容均在新派发前停止。
- 报告研究与章节写作改为先读取已提交响应/observation，再只对新工作检查步骤、调用、工具与有效时间预算。步骤/调用/时间均到上限时，已有响应仍可零 provider/tool 重放；新 logical call 继续被拒绝。取消和 lease 仍约束章节提交与最终发布。
- 实际 `AgentRuntime.run(..., resume=True)` 定向矩阵覆盖进程级中断后同 provider 原 call 重试、provider/schema/参数拒绝、部分工具、最终步骤待发布和 steer 延后；报告覆盖研究与章节在预算耗尽后的零新调用重放。相关恢复/预算/报告集合当前 81 项通过。

### 1.3 第四轮性能、封面与最终门禁（2026-09-27）

- `billboard_entity_detail` 在调用者未显式传参时读取项目设置；显式参数仍保持优先。第四轮曾声称单曲 Agent 视图与旧 full builder 的可比事实逐字段一致；第五轮独立验收已证明该结论不成立，本报告不再复用该旧结论。
- P0-06 配置一致的冷调用由 8.809s 降至 37ms、热调用 3ms；冻结 11 题 V6 批次 11/11，Turn P50/P95 10.000s/13.434s，Model P50/P95 5.703s/8.110s，Tool P50/P95 3.452s/7.740s。P0-06 总耗时 4.205s，其中目标工具 39ms、全部工具 175ms。
- 搜索索引新生成时不再合成无元数据封面 URL；候选与 legacy 读取路径会批量清洗旧代中的失效本地 URL。隔离旧候选代真实浏览器验收要求两个缺失封面艺人显示占位且至少一个真实封面成功加载，Chromium、Firefox、Playwright WebKit 的桌面/手机流程全部通过。
- 默认完整 fullstack run `20260927T065039.674237Z-e75f34dcf895` 未使用 `--only`/`--from`，八个必需阶段同轮通过。

### 1.4 第五轮事实一致性补修（2026-09-27，已完成）

- 独立证据 `/tmp/spotify-agent-v6-independent-review-20260927.json` 在精确 snapshot `d7da0c911f807af2c0292a3b7a1c69758d675e8d8264c95f8a439f8d6a3ecad4` 复现：三首歌的快路径 `total_chart_plays` 小于同一 ledger 历史之和；未上榜歌曲 `Kiss Me More` 已有 47 次有效播放但快路径缺字段。
- 根因已修复：快路径的 `total_chart_plays` 只汇总已发布精确 weekly ledger，并先证明 ledger 与 summary 完整一致；不能证明时回退完整 builder。已上榜、未上榜和零播放实体均返回 `effective_play_count`，未上榜图表不再伪造 `peak_position`。
- 完整 builder 的 L2/L3 `total_plays` 改为版本组聚合，Power 排名直接使用已发布稳定 `power_rank`；Agent 快路径仍有意不展开仅供页面展示的 `meta.version_group`。
- 五实体同参数只读对账中，四个实体可比字段零差异；L2 版本组实体仅存在上述有意的 `meta.version_group` 展示差异。`vampire` 为有效播放 380、榜单播放 299、峰值 1、在榜 37 周、Power 4531 / rank 4；未上榜 `Kiss Me More` 保留有效播放 47。证据 `/tmp/spotify-agent-v6-round5-20260927/postfix-probe-final-v3.json`，SHA-256 `0a968eb04e82a7b186713eb9baed5e28069913e3a1c9c47c3508061d7ceed2aa`。
- 最终固定 11 题真实模型批次与默认完整 fullstack 均已重新执行并通过；结果见第 5.3、6 节。

### 1.5 第六轮 L3 计数一致性收口（2026-09-27，已完成）

- 事件级复核确认 `track:1493` 当前规范事件为 379 次，L3 组附加成员 `track:48498` 有 1 次有效逻辑事件（`play_id=2392703`），所以 L3 合计应为 380；旧 v11 活动快照保留了 381 的派生值，且多出的次数没有对应时长增量。
- 搜索统计快照 builder 提升为 `music_search_snapshot_v12_logical_event_count`，旧 v11 活动快照不再作为 LKG 服务；新快照仍按规范加权事件逐成员求和，不采用会把动态 L3 榜单播放从 298 错减为 297 的全局 distinct-ID 改法。
- 完整 Billboard 的单成员版本组也统一从规范加权成员集求和，避免 `vampire` L2 从陈旧 aggregate fallback 读成 380；快照榜单构建在普通口径有效时复用周曲目/来源聚合，保持动态 L3 榜单播放 298、峰值 1、在榜 37 周、Power 4431 / rank 7。
- v12 四变体重建 gate 全部 ready、迁移 82/82、精确集合与幂等门禁通过；12 个代表性组合快路径与完整 builder 12/12 零差异。全部有播放的多成员 L3 组在动态和固定阈值下分别 493/493 匹配、0 差异，`vampire` 均为 380。
- 原始证据及 SHA-256：`rebuild-v12.json` 为 `3247e7bf5b4c8605da6a21051e52828ae6d8da21fd6159ae1f58d3b570e555fa`；`twelve-combo-reconciliation.json` 为 `426d7cad6034ca211cfd2c1807f117d2aed48527c1a1808f6c13f0f5282831b5`；`l3-all-groups-reconciliation.json` 为 `47ae1687dfa9c052199f717ba38afd407b43b55eabf7f918e392815d558d67a9`。三者均位于 `/tmp/spotify-agent-v6-round6-fixed-20260927.wNoU8J/`。
- 正式数据库在本轮前后 SHA-256 均为 `8f9b7ac11c7058f2e6a231bfd31c70dc65e801cbe2c001b9ea8d0e54fe175f95`；正式封面目录 4,358 个文件的最新 mtime 为 2026-09-21 13:10:21，早于本轮，后台日志中的封面任务均以 stale 跳过。所有重建、模型任务与 fullstack 写入只发生在隔离副本。

本轮没有提交、推送或部署。真实数据验收只读取正式 SQLite 后创建 Online Backup，并将任务、年度报告 sidecar 和派生产物放在隔离目录；正式数据库、原始数据、正式缓存和原主检出未写入。API Key 只由已有本地配置读取，未写入报告或日志。

## 2. S0—S6 交付

| 阶段 | 已交付能力 | 验证摘要 |
|---|---|---|
| S0 | 冻结自由问法、稳定性集、历史集、年度报告样本、预算和性能门槛 | 24 题 fixture、12 题三轮稳定集、历史 runner 与报告测量格式可重跑 |
| S1 | migration 80/81/82、版本化 runtime event、请求上下文投影、execution identity、lease generation fence、dispatch attempt | PASS（定向）：模型请求与逐次外部派发已分离持久化；失租 Worker 和取消后续派发被拒绝；unknown attempt 保守占预算 |
| S2 | Chat、报告研究和章节 writer 共用模型步骤执行器与事件存储 | PASS（定向）：三条实际调用链已接入逐次派发门禁和不可变 descriptor |
| S3 | 固定报告上下文、逐章检查点、恢复复用、最终总审与发布门禁 | PASS：上下文、图表与计划按任务代次冻结；源数据漂移不混入在途报告；已审核章节不重写 |
| S4 | `awaiting_input` 真状态、SSE cursor v2、渐进章节快照、重连去重和前端展示 | PASS（定向与浏览器）：轮询接管终态，权威快照撤回旧章节；hook 回归覆盖断流、resync、乱序和 task 切换 |
| S5 | 自由问法路由、实体/时间/排名约束和答案审查修正；报告性能收口 | PASS：第五轮冻结 11 题 V6 为 11/11；Tool P95 14.813s，P0-06 全部工具 219ms；年度报告历史有效证据保持通过 |
| S6 | 当前规则、验收报告、兼容与回退证据 | PASS：定向恢复/预算、旧索引缺失封面三浏览器验收与当前默认完整 fullstack 均通过 |

当前运行规则见 [`../reference/ai-agent-runtime-v6.md`](../reference/ai-agent-runtime-v6.md)。V5/V6 的切换只影响新任务；V6 在途任务不会交给不理解新事件和章节协议的旧 Worker。

## 3. 真实模型问答验收

| 集合 | 结果 | 关键耗时 | 原始证据 |
|---|---:|---:|---|
| 新自由问法 | 24/24；21 `done`、3 个必要澄清 `awaiting_input` | 有效执行 P50 6.813s、P95 14.860s、最大 19.239s | `/tmp/spotify-agent-v6-freeform-24-final.json` |
| 当前历史 full runner | 42/42；多轮展开后实际 45 turns | Turn P50 6.313s、P95 12.325s、最大 23.011s；Model P95 8.846s；Tool P95 4.439s | `/tmp/spotify-agent-v6-historical-42-final-pass.json` |
| 固定稳定性集第 1 轮 | 12/12 | 最大 18.368s | `/tmp/spotify-agent-v6-stability-locked3-r1.json` |
| 固定稳定性集第 2 轮 | 12/12 | 最大 10.251s | `/tmp/spotify-agent-v6-stability-locked3-r2.json` |
| 固定稳定性集第 3 轮 | 12/12 | 最大 9.990s | `/tmp/spotify-agent-v6-stability-locked3-r3.json` |
| P0 | 12/12 | P95 12.138s | `/tmp/spotify-agent-v6-p0-run4.json` |
| 安全边界 | 8/8 | P95 6.569s | `/tmp/spotify-agent-v6-safety-final2.json` |
| 多轮 | 3/3，实际 6 turns | P95 7.768s | `/tmp/spotify-agent-v6-multiturn-pass.json` |

S0 文档最初沿用历史报告中的 33 个 live 场景。最终执行前核对当前 runner 后，发现现行集合已经扩展为 39 个单轮场景和 3 个多轮场景，即 42 cases、45 个实际 turns；这里按当前 runner 全量执行，没有删题、降低断言或在结果出来后放宽阈值。

相较 2026-08-31 记录的 Turn P95 42.087s，当前历史集 P95 为 12.325s，下降约 70.7%。两版均满足各自质量门禁；不同日期的 Provider 波动和当前扩展题集意味着该比例只作本地参考，不等同生产 SLA。

所有未通过的中间样本均保留，例如 `/tmp/spotify-agent-v6-stability-locked2-r1.json` 的 11/12；最终结果不是通过删除失败样本得到。

模型用量按 Provider 返回值原样记录，不推算金额：新自由问法 24 个样本共 480,586 input / 25,833 output token、70 次模型调用、50 次工具调用；当前历史集 42 cases 共 573,308 input / 33,988 output token、99 次模型调用、63 次工具调用；三组 cold/hot 年报共 68,730 input / 12,571 output token、36 次 Provider 调用。历史 V5 验收没有保存同口径 token 样本，Provider 也没有价格合同，因此这里不声称货币成本或“相对 V5 token 下降”；本轮只确认全部样本在固定步骤、调用和时间预算内完成，原始用量可审计。

## 4. 真实模型年度报告验收

完整年度 2025 独立执行三组冷/热配对，每次均为 6/6 模型章节、0 确定性补齐，并通过章节检查点、事实校验、critic 和最终 artifact 质量门禁。

| 样本 | Cold | Hot | 证据 |
|---|---:|---:|---|
| Pair 1 | 54.774s | 28.990s | `/tmp/spotify-agent-v6-report-pair1.json` |
| Pair 2 | 50.182s | 33.634s | `/tmp/spotify-agent-v6-report-pair2.json` |
| Pair 3 | 54.363s | 30.482s | `/tmp/spotify-agent-v6-report-pair3.json` |
| 三样本汇总 | 中位数 54.363s；最大 54.774s | 中位数 30.482s；最大 33.634s | 三组原始文件 |

样本数仅为 3，因此不把插值或最大值写成稳定 P95。与 S0 参考冷 123.825s、热 81.472s 相比，中位数分别下降约 56.1% 和 62.6%；全部低于 240s/180s 门槛。运行中曾直接观察到任务仍为 `running` 时已有 2 个 `validated` 章节，证明首个审核章节早于最终发布。

边界年份：

- 2026 部分年度：46.052s，6/6 模型章节、0 回退，部分年度措辞与全部质量门禁通过；证据 `/tmp/spotify-agent-v6-report-partial-2026-final.json`。
- 2010 无数据年度：明确返回 `data_status=empty`，report/artifact 为 `null`，0 provider 调用、0 章节尝试、0 章节记录；证据 `/tmp/spotify-agent-v6-report-no-data-2010-final2.json`。
- 两次无数据修复前产生虚假叙事的失败样本仍保留为 `/tmp/spotify-agent-v6-report-no-data-2010.json` 和 `/tmp/spotify-agent-v6-report-no-data-2010-final.json`；最终实现改为确定性 fail-closed 空态，而非用提示词掩盖。

## 5. 补修后的同源、恢复与浏览器证据

### 5.1 2026-09-27 固定配对批次

第二轮在运行前固定 `P0-01` 与 `P0-03…12` 共 11 题，明确排除已知 V5 质量失败的 `P0-02`；两版各运行一次，不重抽样。两份数据库均由同一个 94,760 条播放事实的 Online Backup 建立，模型配置、题目、问题时间和预算一致。原始证据为 `/tmp/spotify-agent-v6-round2/run-20260927/v5-paired-p0.json` 与 `/tmp/spotify-agent-v6-round2/run-20260927/v6-paired-p0.json`。

| 路径 | 质量 | Turn P50 / P95 | Model P50 / P95 | Tool P50 / P95 |
|---|---:|---:|---:|---:|
| V5 | 10/11；`P0-01` 失败 | 13.964s / 46.510s | 5.540s / 8.146s | 7.115s / 44.996s |
| V6 | 11/11 | 17.453s / 49.758s | 5.234s / 8.104s | 11.157s / 48.410s |

在预定批次中两版都通过的 10 题上，V6/V5 的 Turn 中位数比为 1.070，总 token 中位数比为 1.024，模型调用与工具调用中位数比均为 1.000；这些相对值没有超过 115%。但整批 V5 未全过质量，V6 Tool P95 又超过 45s 绝对门槛；两边启动期间都观测到派生快照构建和相邻 governance revision 竞争，因此本批次只能保留为 `PARTIAL`，不能宣称性能门禁通过，也不追加抽样替换失败值。

第三轮直接核对两份原始 JSON、任务事件和工具 observation 后，P95 均由 `P0-06` 的 cache miss `billboard_entity_detail(track_id=1493)` 主导：V5 实际工具执行 44.773s，V6 为 48.036s，均返回 7,940 bytes 且此前都先经历同样的无 ID 失败与实体解析。该路径是完整 Billboard 冷构建，不是 V6 事件恢复或预算重放代码；V6 比 V5 多 3.263s 不能形成稳定的 V6 因果归因。`P0-01` 和 `P0-04` 也显示同批次派生构建竞争。因此第三轮当时保持 `PARTIAL`，且没有用追加样本替换既定失败值；第 5.2 节记录第四轮针对已确认默认参数错位和可复用发布 ledger 的收口结果。现有三组年度 cold/hot 及 Provider token/call 用量仍按第 3、4 节原始证据报告，不把历史不同合同拼成新的通过结论。

### 5.2 2026-09-27 第四轮冻结 V6 批次

不覆盖第二/三轮原始失败文件，使用同一 11 题清单和固定问题时间仅运行一次当前 V6。证据 `/tmp/spotify-agent-v6-round4-20260927/v6-fixed-p0.json`，SHA-256 `f73de1f4b17b612f8721b342107be9917f17ce25258dccd3646663248ee736db`。

| 质量 | Turn P50 / P95 | Model P50 / P95 | Tool P50 / P95 | 模型 / 工具调用 |
|---:|---:|---:|---:|---:|
| 11/11 | 10.000s / 13.434s | 5.703s / 8.110s | 3.452s / 7.740s | 31 / 19 |

P0-06 任务 `0e9f73383e9d` 总耗时 4.205s、模型 3.967s、全部工具 175ms、目标详情工具 39ms，结果大小 7,528 bytes。该批次累计 191,988 input / 11,291 output token；没有价格合同，因此仍不推算金额。修复前配对数据保留为问题发现与因果分析证据，不再代表当前代码的性能状态。

### 5.3 2026-09-27 第五轮冻结 V6 批次

第五轮使用同一 11 题清单和固定问题时间，在事实一致性修复后的候选上仅运行一次。证据 `/tmp/spotify-agent-v6-round5-20260927/v6-fixed-p0.json`，SHA-256 `aa5568f972ca9b0dad219e81cc0de37118cde7ddf14c6fefc360323c49c2c3aa`。

| 质量 | Turn P50 / P95 | Model P50 / P95 | Tool P50 / P95 | 模型 / 工具调用 |
|---:|---:|---:|---:|---:|
| 11/11 | 9.646s / 20.966s | 5.948s / 7.802s | 2.957s / 14.813s | 31 / 19 |

P0-06 任务 `346704edeb7a` 总耗时 4.836s、模型 4.492s、全部工具 219ms，返回有效播放 380、峰值 1、在榜 37 周、冠军 3 周和 Power 4531。该批次累计 190,639 input / 10,630 output token，工具结果共 369,744 bytes；没有价格合同，因此仍不推算金额。全部 11 题在 45s Tool P95 门槛内通过，没有重抽样或删除失败题。

### 5.4 2026-09-27 第六轮冻结 V6 批次

第六轮在 v12 快照与 L3 全量对账完成后，继续使用同一 11 题清单和固定问题时间，仅运行一次当前 V6。证据 `/tmp/spotify-agent-v6-round6-fixed-20260927.wNoU8J/v6-fixed-p0.json`，SHA-256 `e59fdc13e5a31b033c4db7d8d2c9f3a4889e870eecc43f1d5fa7677d08e3fd4d`。

| 质量 | Turn P50 / P95 | Model P50 / P95 | Tool P50 / P95 |
|---:|---:|---:|---:|
| 11/11 | 7.930s / 11.348s | 6.139s / 8.210s | 2.060s / 4.719s |

P0-06 任务 `92e38d3d1c59` 返回 L2 有效播放 379、峰值 1、在榜 37 周、冠军 3 周和 Power 4531；没有重抽样、删除失败题或放宽事实门禁。L3 的 380 次另由第 1.5 节的成员级与全组对账证明，不把 L2/L3 不同 composition 结果混写为同一数值。

### 5.5 2026-09-23 历史同源样本

同一个 Online Backup（94,760 条播放事实）和同一组 12 个 P0 问题分别运行 V5 与 V6，没有把不同日期、不同数据或不同题集拼成“升级收益”：

| 路径 | 质量 | 总耗时 | Model | Tool |
|---|---:|---:|---:|---:|
| V5 | 11/12，P0-02 失败 | P50 8.544s；P95 27.209s | P50 5.827s；P95 8.659s | P50 2.091s；P95 24.019s |
| V6 | 12/12 | P50 10.829s；P95 30.534s | P50 6.941s；P95 9.233s | P50 3.569s；P95 26.171s |

原始证据为 `/tmp/spotify-agent-v6-repair-20260923/v5-p0.json` 与 `/tmp/spotify-agent-v6-repair-20260923/v6-p0-final.json`。V6 达到质量门禁且每题低于 60 秒；V5 有一题失败，因此这里不宣称 V6 性能优于 V5，也不把两条性能分布当作等质量比较。

真实硬中止恢复使用隔离数据库 `/tmp/spotify-agent-v6-repair-20260923/v6-recovery-kill.db`：任务 `9e701c903b41` 在 `writing_sections`、已有 1/6 审核章节时对服务进程发送 `SIGKILL`。重启后任务恢复为 `done`、6/6 章节审核通过；已完成 opening 保持 version 1，工具 observation 仍为 16 条且无重复 ID，模型调用从 5 增至 10，说明只执行剩余五章；累计预算从中止前的 model/tool 5/10、input/output 14538/5928 延续为 10/10、24981/7664，没有重置。

真实浏览器在独立副本上验证了：已有年度任务找回、刷新后 6/6 章节恢复、错误态保留 3/6 已审核章节与重试入口、后端断开期间保留 3/6、服务恢复后重新连接，以及取消后显示终态并保留已审核章节。2026-09-27 又强制让 SSE 连续四次 `ERR_CONNECTION_REFUSED`：HTTP 仍显示 6/6；`closing` 以更高 version/sequence 失效后页面在轮询周期内变为 5/6；陈旧 `running/state_version=100` 不会覆盖 HTTP `done/state_version=102`。浏览器临时库中的注入状态只用于前端恢复/错误/取消流，不进入正式数据库；本轮截图为 `output/playwright/v6-sse-http-reconciliation.png`。

## 6. 故障、兼容和自动化测试

第二轮定向后端相关集合 137 项通过，覆盖逐次 provider 派发、runtime 投影/恢复、Chat/报告真实调用链、章节协议、API 和任务服务；前端相关集合 32 项通过，其中权威 HTTP/SSE 调和用例 8 项覆盖 `done/error/cancelled`、`resync`、撤回、乱序和 task 切换。

第六轮收口后的当前代码门禁结果：

| 门禁 | 结果 |
|---|---:|
| V6 恢复/预算/报告定向集合 | 81 passed；恢复/预算广集 156 passed；第六轮相关统计集合 135 passed |
| Backend seed（默认完整 fullstack） | 3044 passed，2 skipped |
| Backend real integration | 186 passed，1 skipped |
| Frontend test | 684 passed，4 skipped；88 files passed、1 skipped |
| Frontend production build | PASS；仅保留既有大 chunk warning |
| Pre-commit | PASS；ruff、ruff format、mypy、detect-secrets 全部通过 |
| 旧索引缺失封面浏览器专项 | PASS；Chromium、Firefox、Playwright WebKit 的桌面/手机与核心交互全部通过 |
| L3 真实副本对账 | PASS；12/12 代表组合，动态/固定阈值各 493/493 多成员组，0 mismatch |
| 固定 11 题真实模型 | PASS；11/11，Turn P95 11.348s，Tool P95 4.719s |
| 默认完整 fullstack | PASS；run `20260927T123442.686018Z-e24f493b421d` 八阶段同轮通过 |

默认完整全栈使用未带 `--only` / `--from` 的 full 模式，在 94,760 条播放事实的隔离 Online Backup、报告 sidecar 和治理 sidecar 上执行。机器汇总记录如下：

| 阶段 | 结果 | 耗时 |
|---|---:|---:|
| preflight | PASS | 8.684s |
| quality | PASS | 61.721s |
| backend | PASS | 751.042s |
| api | PASS | 227.340s |
| browser-routes | PASS | 413.805s |
| browser-interactions | PASS | 83.319s |
| browser-inventory | PASS | 47.316s |
| browser-compat | PASS | 287.591s |

其中 API smoke 154/154、边界 113/113，51 组 API 性能端点各取 22 个 warm 样本且无 hot P95 超过 500ms；首页 P95 100.897ms，完整 `/api/billboard/all-time` P95 377.984ms，`/api/billboard/data` P95 400.669ms。双视口主/详情路由和五档关键视口通过，0 console error/warning、0 横向溢出；桌面/手机交互、40 组控件盘点（1,979 个控件、307 个主要触控目标、0 违规）、7 个长列表及 Chromium/Firefox/WebKit 兼容均通过。完整 run 汇总 SHA-256 为 `2a0ffc1bb4a36ea0270768aae98be5d16daffe6bc80a52fb97cf0dd5cdacb4fb`。

第六轮最终 run 前两次默认完整尝试也保留：run `20260927T121853.951834Z-c3f85c7db4b3` 在 quality 阶段因 `ruff-format` 自动改写一个新增测试文件而停止；格式化后 pre-commit 全通过。run `20260927T122122.763972Z-e75c36643861` 的功能探针均通过，但 `/api/billboard/data` 在持续主机负载下 hot P95 为 573.822ms，超过固定 500ms 门槛，浏览器阶段未运行。同进程 22 次定向复测 P95 为 363.941ms，随后最终默认完整 run 在未放宽门槛下得到 400.669ms 并八阶段同轮通过。

第五轮最终 run 前的三次默认完整尝试均保留：第一次在治理 sidecar 尚未完成发布时使两个健康端点返回 503；其后两次分别只有 `/api/billboard/data` 或完整 `/api/billboard/all-time` 的 P95 在持续主机负载下略超 500ms。没有放宽阈值；同一 51 端点独立复测全部通过后，最终默认完整 run 在相同 500ms 门槛下取得八阶段同轮 PASS。

第三轮失败 run `20260927T042711.583960Z-8de97844b79c` 与尾段 `20260927T045611.365300Z-ad30086e66b5` 继续保留为修复前证据。第四轮另用旧候选 generation 构造候选可服务、统计不可用的隔离副本：artist 8428/8141 的持久旧 URL 经读取清洗为 `null`，artist 7652 的真实封面保持加载成功。专项 JSON 位于 `/tmp/spotify-agent-v6-round4-20260927/browser-chromium-stale.json` 与 `browser-firefox-webkit-stale.json`。

第四轮正式 full run 前还保留了两次 preflight 环境失败：run `20260927T042546.827978Z-ce3f9c91189f` 与 `20260927T042605.328521Z-e31e363349de` 均因当前 worktree 缺少本地 `.venv`，使 OpenAPI 审计从错误解释器加载依赖而失败。随后用项目既有虚拟环境建立忽略的 worktree 链接后，第四轮 full run 的 preflight 和后续代码门禁正常执行；没有降低测试范围或阈值。该轮存储守卫峰值 806,982,054 bytes、最低可用空间 43,049,226,240 bytes，未触发停止并在失败后完成清理。

故障验证包含：工具结果与恢复事实原子提交、模型结果落盘窗口、lease 接管后旧 Worker 拒写、累计预算不重置、版本不兼容拒绝复用、已审核章节恢复零重写、取消与完成竞争、SSE v1 兼容读取/v2 重连去重、空数据禁止生成叙事，以及最终审核失败不发布成功缓存。

## 7. 已知背景噪声与未扩范围事项

隔离真实报告运行期间，日志偶发 `Governance source/config changed during build`。只读核对表明 governance 动态 health revision 当前包含 `ai_agent_turn_events`、`ai_runtime_events`、`ai_task_runs` 等波动表；AI 自己写运行事件会触发相邻治理构建重试。这不是播放源数据漂移，未破坏报告质量或本次绝对性能门槛，但属于现有治理 revision 的相邻设计问题。本轮没有借 V6 扩修；后续若优化，应单独定义 governance 输入域和验收。

未执行且不能从本报告推断：Git commit、push、PR、任何环境部署、生产凭据配置、生产在线 AI 验收、物理手机验收。V6-S6 仅标记为本地完成；生产启用与在线验收仍是独立工作。
