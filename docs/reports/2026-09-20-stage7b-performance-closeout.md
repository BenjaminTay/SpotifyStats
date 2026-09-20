# 阶段 7B：验收阻塞修复与本地收口（Partial）

## 结论与边界

本轮结论为 **Partial**。Records 最终三个独立进程的 cold builder 为 10.110869、9.652281、12.245321 秒，中位数 **10.110869 秒**，没有达到 ≤10 秒门槛。三次完整 payload 与优化前一致，仅排除 `meta.generated_at`。不能将 10.111 秒取整为 10 秒并判 Pass。Analysis LKG、艺人冷读取和未发布配置的返回耗时也尚未全部达标，故障 UI 与实际并发矩阵仍有缺口。

定向门禁尚未全通过，因此没有启动本轮标准全量测试序列、最终默认完整 fullstack 或 Git 提交。阶段 7 的完整后端失败不能凭本轮定向测试改写为“完整后端 0 failed”。未 push、未部署、未同步正式数据。

按本轮追加指示，Docker full/showcase/dual 运行态验收移至独立的发布前任务，**不属于 7B Pass 门禁，也不作为本轮 Blocked 或产品缺陷**。撤出之前执行过 `open -a Docker`、`docker info` 和只读镜像列表；没有启动 SpotifyStats 容器。收到指示后没有继续 Docker 构建、拉取、Compose、创建或删除操作，也没有关闭 Docker Desktop 或改动既有对象。

起点 HEAD：`faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`。起点工作区与阶段 7 结束状态逐文件一致，已暂存区为空。既有约 270 个阶段文件继续保留；本轮只在该基础上修复已确认阻塞。

## 证据位置

本轮证据根目录：

`/Users/benjaminlei/.codex/visualizations/2026/09/20/01a0bdd8-b911-7b33-b062-c94e7b068598/spotifystats-stage7b`

隔离数据库和运行脚本位于 `/tmp/spotifystats-stage7b`。正式数据库经 SQLite Online Backup 生成副本；性能样本使用新的 Python 进程及独立空目标 sidecar。性能任务使用同一个主机文件锁，但其他项目没有共同使用该锁，因此进程证据是判定样本有效性的必要部分。

复用 [阶段 7 报告](2026-09-20-stage7-local-performance-acceptance.md) 的有效 396 次路由访问及既有合同证据，没有重跑该整套矩阵。阶段 7 的 fullstack 结果仍为历史结果。

## 已实现的修复

- Archive tracking marker 改为自身合同版本与触发器定义指纹，migration 77 负责升级。无关 DDL 不再让 Archive 失效；缺失 marker/trigger 的私有修复更新 epoch，事务回滚保留原数据。正常 lifespan 在迁移后检查 tracking。
- tracked seed 通过正式 migration 从 74 升至 77；源事实表逐表对账不变，完整 migration 序列及 integrity check 保存在 `seed-upgrade.json`。Search 测试移除 schema 74 硬编码。
- Analysis lifetime 集成测试通过真实私有 fixture 发布快照。未发布 custom GET 保持 503，并单独调用私有 builder 验证真实空范围的零值结构。
- Home exact key 使用 Billboard `full_data` 持久发布的 cache-key 与内容摘要，移除进程内 preview 计数依赖。
- Records 优化小时区间切片、longevity 连续区间计算、重复 feat 名称判断、skip 分组聚合，以及只添加列时的数据表复制；保留事件/时长双轨、原排序和 L2/L3 归属。
- 年度 artifact 私有发布保存 preparation-key 元数据；generation-status 优先只读查 key，避免重复收集每年的完整 scoped digest。旧 sidecar 的元数据补齐仍属于私有维护。
- 艺人 rank context 复用既有 Analysis store 的私有发布；全局竞赛排名、Top 250 和最近 50 个逻辑事件只维护一次。实体详情和榜单按目标艺人装载事实，保留完整字段；缺失/漂移返回 unavailable，GET 不补建。
- Phone Community 头像与主要操作扩大到 44px 点击区；年度总结五个筛选按钮从 40px 调整为 44px。

曾尝试缩小 Records 封面解析集合，完整对账发现一条每日纪录的封面发生变化，因此已撤掉该项优化。失败样本和差异证据保留，最终三次对账均为完整相等。

## 定向测试

| 范围 | 结果 | 日志 |
|---|---:|---|
| 阶段 7 原十个失败 ID，真实数据副本 | 10 passed | `original-ten.log` |
| Archive / Governance revision | 54 passed | `revision-tests.log` |
| migration / startup / Home | 56 passed | `migration-home-tests.log` |
| Records / yearly 首轮定向 | 59 passed | `records-yearly-tests.log` |
| rank / yearly / startup 后续回归 | 66 passed | `rank-yearly-tests.log` |
| Search 合同与受影响边界 | 94 passed | `changed-contracts.log` |
| 最终 Records 等定向与 Analysis 集成组合 | 86 passed、3 failed | `records-analysis-final-tests.log` |
| 上述 Analysis 集成改用真实 Online Backup 副本 | 10 passed | `analysis-integration-real-copy.log` |
| 最终 rank revision / CLI / Home / yearly / Records 定向 | 60 passed | `final-directed.log` |

组合测试中的三项失败源于误用小型 seed：数据规模断言要求超过 50,000 次播放，seed 只有 118 个有效事件。未降低断言；随后指定 `SPOTIFY_STATS_TEST_SOURCE_DB` 为隔离真实副本，整个 Analysis 集成文件通过。原失败日志保留。

一次早期组合定向进程在 59 个进度点后退出 139（Python segmentation fault），保存在 `directed-backend.log`；后续拆分定向组通过。另一次 snapshot 队列测试发现 rank job 被耦合进两类 Analysis 的 enqueue，已改为 main 启动/已提交变更处独立排队，后续 66 项通过。以上都没有被记为最终完整后端通过。

## 性能证据

| 项目 | 本轮有效结论 |
|---|---|
| Home restart exact | 三个新进程均为相同 exact generation：96.867 / 91.574 / 92.356ms；见 `cold-http.json` |
| Records cold builder | before median 13.348972 秒；最终 median 10.110869 秒，**不通过**；见 `records-final-acceptance.json` |
| 年度 generation-status | 最终三个新进程冷读取 299.637 / 346.752 / 336.041ms，热读取 287.315 / 274.045 / 274.615ms，全部 ≤500ms；见 `final-http.json` |
| 艺人 stats + rank context / rankings | 完整字段相等；不带观测器的 stats 冷读取 696.993 / 609.539 / 742.297ms；rankings 480.590 / 533.825 / 555.466ms，未全部 ≤500ms |
| Analysis LKG / 真实故障读取 | 不带观测器的 LKG 首读 579.676 / 445.240 / 450.916ms，未全部 ≤500ms；未发布参数 Stats / Records 冷读 439.988 / 440.579ms，超过 300ms |

观测器本身会影响时延，最终另以不带 SQL/row 计数器的真实 HTTP 进程交叉验证，数据保存在 `plain-http.json`，没有把纯 service 时长替代 HTTP。上述未达标项在不带观测器时仍存在；公开只读行为使用带观测器及 sentinel 的独立证据验证。Stats LKG profile 的 491.450ms 中，source revision 收集占 486ms，sidecar 读取约 3ms；Pydantic 验证 2.216ms、序列化 1.339ms，主要成本仍是 28 张依赖表的完整指纹读取。见 `stats-lkg-final-profile.json` / `.txt`。

`records-final-acceptance.json` 与 `records-isolated-{1,2,3}-processes-{before,after}.txt` 保存最终 Records 原始样本和进程环境；`records-*-profile-profile.txt` 保存 profile。空目标 sidecar 不等于 SQLite 页缓存或操作系统磁盘缓存为空，本轮没有清理全机缓存。

外部资源竞争已直接观测到另一项目 pytest、Vitest、vue-tsc 和后续 Playwright workers。`records-quiet` 只是运行标签，其开始/结束仍有该项目 worker，不能当作独占证据。`performance-exclusion.json` 列出排除范围，失败数据未删除。外部 Playwright 总进程结束后才采集最终 `records-isolated` 三次样本。

## 真实浏览器与状态

Firefox 的历史断点来自本机 Playwright/Firefox 的协议 reload：`page.reload()` 新增同 URL 历史项且丢失 `history.state`，没有观察到应用额外 push。使用浏览器原生 `location.reload()` 后保留历史；三种引擎统一采用相同原生刷新流程。

Chromium / Firefox / WebKit × Desktop / Compact / Phone 的 9 组交互均完成：从首页真实实体链接进入详情、非默认页签 replace、深链刷新、后退回首页、前进恢复页签与内容，以及未发布 custom 范围错误消费。没有通过跳过引擎或只断言 URL 取得通过。原协议失败、诊断和最终完整流程分别保存在 `browser-interactions-protocol.json`、`firefox-history-diagnostic.json`、`browser-interactions.json`。

Phone 390×844 的 Community、Analysis stats、Archive、Search、Yearly Review、Home 可见主要按钮/页签/导航几何检查均无小于 44px 的目标，无横向溢出。真实点击包括头像入口、社区时间筛选、年度章节选择和完整榜单翻页。证据为 `phone-controls.json`、`phone-actions.json` 与 screenshots；正文内联链接未机械放大。

追加状态证据见 `state-http-additional.json`、`state-http-remainder.json` 及对应 browser/payload 文件。Home、Stats、Records、Billboard、Search、Community、Archive、Governance、Yearly 使用各自真实读取路径。Yearly 未发布返回原合同的 404，Search 可返回 200 + unavailable/failed statistics metadata；这些均不算 ready。

矩阵的初次 Search config 探针错误传入 candidates 不支持的 `min_ms`，422 只证明参数拒绝，不算 config drift。初次 Search source drift 没同步 import-owned Search counter，ready 也不算漂移证明；纠正记录见 `search-source-fault-correction.json`。初次 fault UI 采用全站 networkidle，被年度维护状态轮询阻塞；该轮不算完整 UI 通过。追加探针显式区分 public/private surface，保留这些失败，不覆盖为通过。

正常 lifespan 已运行并重启两次，启用 L3 启动检查，关闭外部 warmup / Search 自动重建；隔离副本中继承的 pending/running/failed 外部任务及失败封面重试标记先移出本轮运行，详情见 `lifespan-private-copy-preparation.json`。两次 health、Home、Stats、Archive 均返回 200，Home 为同一 exact generation。第一次因测试恢复数据库引起 Governance 全局 schema cookie 变化，启动修复后后台维护 Governance；第二次没有待运行任务。第一次 Stats 读取与后台维护重叠为 1544.683ms，不算独占性能通过。见 `lifespan.json`。

追加故障 HTTP 20 项全部完成，观测的 builder/write/enqueue 均为零。故障 UI 证据仍不完整：首轮 networkidle 被轮询阻塞；后续通用文本长度等待既捕获过未完成的 Search/Yearly 加载画面，又在短错误文案页面超时。这些截图只作诊断，不证明对应消费者通过。Phone 重试点击、治理面板实际展开、Search 真正 config drift 和未污染的实际四并发样本仍需补齐。

## 正式数据、Git 与剩余门禁

正式数据最终对账：**4172 个 application 文件大小与 SHA-256 全部不变，元数据也不变**；9 个 SQLite 瞬态文件内容不变，仅 `data/spotify_stats.db-shm` 的 mtime 变化；2 个 OS 元数据文件内容与元数据均不变。汇总见 `formal-summary.json`。

正式文件按照 application、sqlite_transient、os_metadata 三类建立 `formal-before.json` / `formal-after.json`。主库、sidecar、备份、封面、缓存和清单按大小与 SHA-256 对账；WAL/SHM/journal 与 `.DS_Store` 单列。没有主动改写、删除或恢复 `.DS_Store`。

最终 Git：仍在 `main`，HEAD 保持 `faa5e4e45e83f9c478e62a51f4b7d25b17eab1a0`；相对本地缓存的 `origin/main` 为 ahead 0 / behind 0（本轮未联网 fetch）。staged 为空，工作区 274 项状态；相对 7B 起点变化 40 个文件，逐文件与 patch 见 `stage7b-changes.json` / `stage7b.patch`。本轮启动的 8000 后端与 5173 前端已停止；Docker Desktop 保持用户要求的现状。

文档审计 PASS（117 个当前 Markdown），受影响代码 Ruff 检查、`git diff --check` 与空 staged 的 `git diff --cached --check` 通过。这些局部质量检查不替代标准完整门禁。

本轮没有 commit，阶段归属提交表尚未进入执行；未达到 Pass 时不得为凑齐 4–7 个提交而暂存或提交。最终 HEAD、staged 状态、完整剩余文件和 origin ahead/behind 见 `git-final.json`、`status-final.txt`。README 无产品入口变化；AGENTS 与 CLAUDE 保持一致；本轮更新规则、变更日志与文档地图。

最终仍需先关闭 Records ≤10 秒与其他未通过的定向性能/状态门槛，再按用户指定顺序执行标准 unit、contract、完整后端、默认 npm test、build、docs audit、phase5、diff check 和一次默认完整 fullstack。只有全部通过后才整理大阶段本地提交及 all-files hooks。Docker 三模式验收独立留给未来发布前任务。
