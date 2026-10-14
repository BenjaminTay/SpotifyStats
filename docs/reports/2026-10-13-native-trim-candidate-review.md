# 完整预热原生内存回收候选：归因、验证与整合审阅

2026-10-13；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。

后续状态：6c74b9b4仅研发分支已推送，main未推送/部署；发布前只读核对发现生产warmup=0，当前full预热回收不会触发，发布HOLD。原完整预热实验及本地整合证据保留原范围；最新CI与准备见[发布准备报告](2026-10-13-native-trim-release-preparation.md)。

**结论：INTEGRATED（本地），未推送或部署。** 最小补丁已实现并审阅，默认 Phase5 与默认完整本地八阶段门禁通过；Linux 仿真对照证明维护完成后的驻留收益及样本响应等价。用户授权后，业务提交 `e01a44550ee0082a71788bd37f2cd939e53542a2` 已原样快进进入 main，整体资源合同与 OOM 保持 Partial/OPEN。

## 基线与精确范围

唯一研发分支为 `codex/album-rank-cost`，工作树为 `/Users/benjaminlei/.codex/worktrees/album-rank-cost/202605-SpotifyStats`。验收基线为 `13ec3ec110886abf91e9da420ca046846c311c4a`，其backend/scripts/frontend与已发布c0d的Git内容相同；当前业务提交为e01a4455，四文件与该基线上的完整门禁候选逐字节一致。

本轮补丁仅含以下四文件；两个新文件原为 untracked，完整恢复补丁已经包含它们。下列 SHA256 是源文件内容指纹，不是提交 SHA。

```text
backend/core/native_memory.py
2513ea7033c72717125a313787db651417569d4c2861b91e2b3823c2eb76aeec
backend/core/warmup.py
9bee03f7a9db5b0e0a9ee7155f4e26e3759dbdc492f6c9fa2c6704dbb6febd4b
backend/tests/unit/test_native_memory.py
4854d95edc024acedd1dd13d083cc7185c3ef366ee12475cf5b9743a3e4f262f
backend/tests/unit/test_warmup.py
aaf23e84afa104cb534ea77d870fa0ff5e137e46a532a161621de10dc72c676d
```

提交映射：研发 `e01a44550ee0082a71788bd37f2cd939e53542a2` → main 同一完整SHA，采用fast-forward，未复制或重写产品补丁。main原有六份未提交文档在快进前独立保存，快进后逐字节保持，再由协调方统一更新为本地整合状态。

提交前精确暂存四文件，cached内容与冻结SHA一致；native/warmup的13项回归通过，ruff、ruff-format、mypy、detect-secrets提交钩子全部通过。业务提交只包含四文件。README、AGENTS/CLAUDE已检查，规则无需变更，AGENTS与CLAUDE一致。

## 归因与最小修复

正常预热及三轮有界请求后的帧缓存仍有合法持有；缓存条目稳定不等于进程 RSS 稳定。初次 Linux 归因在缓存保留时单独调用 trim，RSS 约下降 966MiB，帧预算、被观察帧身份及 Python arena 容量不变。这支持 glibc 空闲页保留是本次窗口驻留的主要可回收部分，不证明全部剩余 RSS 的唯一来源。

最小候选在完整后台预热正常返回、builder 已退出且源连接已关闭后调用一次 `malloc_trim(0)`。只在 Linux 且 glibc/trim 符号可用时执行；非 Linux、缺少符号为 no-op，OSError 记录后返回 False。minimal 预热或提前失败不调用。

复核未发现阻塞项：ctypes 参数/返回类型明确；调用点复用既有后台任务和 CPU gate；不清 LRU、不运行 GC、不新增调度器、环境变量、缓存或逐 GET hook，不恢复旧投影/生命周期混合补丁。false/no-op 不改变维护成功状态。测试覆盖平台与符号兼容、异常、zero-pad、注册 ready 缓存保留、调用次数及 builder/连接完成顺序。

此修改针对**已完成完整预热后的驻留**，未覆盖每次后台维护或 minimal 启动，也没有证据证明它能降低构建期间峰值。

## 本地正确性与默认门禁

四文件内容在定向测试、仿真配对、审阅、默认 Phase5 和本地全栈之间一致。

| 验证 | 结果 | 范围 |
| --- | --- | --- |
| 定向正确性 | 64 passed | warmup/native/年度/队列49项、公开读取与快照边界15项；Ruff、format、diff检查通过 |
| 默认 Phase5 | 实际0，PASS | unit2735/2skip、contract571、前端803/4skip、构建、文档与CI规则检查；不代替 fullstack |
| 默认本地 fullstack | 实际0，八阶段PASS | run `20261013T093055.808116Z-598e44fa152c`，1705.908s；未使用 --only、--from、--skip-cross-browser 或放宽阈值 |
| 后端及真实副本集成 | 3948/2skip；186/1skip | seed 全套与真实数据副本分别报告 |
| API | smoke157/157；boundary113/113 | 延迟51端点×22轮=1122样本，500ms阈值，最高hot P95 228.785ms；无slow端点或空hot P95 |
| 浏览器 | Chromium/Firefox/WebKit PASS | 详情路由、五视口、桌面/手机交互与图表、控件/触控目标、长列表；WebKit引擎不等于真实Safari设备 |

fullstack 八个必需阶段为 preflight、quality、backend、api、browser-routes、browser-interactions、browser-inventory、browser-compat，全部同轮通过。未请求的 optional 行为 NOT_RUN。存储保护峰值1108513392 bytes、最低空闲20097699840 bytes，未触发停止，临时目录已清理。已有 bundle/LibreSSL/弃用警告仍保留。

本地门禁使用原已封存 Online Backup 的七文件独立副本和规范排名清单安装。一次正常完整预热结束后启动标准门禁服务，warmup=off、外部封面开关为文档默认1。默认封面下载与维护可写自有副本，故整个门禁窗口不声明严格GET事实守恒。原始七文件备份 SHA 不变；本轮服务均已关闭，runtime 无 open owners，残留 WAL/SHM 与原始记录一并归档。

本轮 macOS helper 是 no-op；上述门禁证明功能集成，不增加原生 Linux 时延、CPU 或绝对 RSS 证据。API first 样本没有新鲜进程状态证明，本轮不等于生产首次验收。

## 有界 Linux 配对

发布 amd64 镜像运行于 Docker Desktop aarch64 Linux，属于仿真。原版与候选各使用独立关闭备份，同一规范四套排名安装、2CPU/4GiB、禁网、无端口及只读根文件系统；各一次正常 lifespan，两条请求链各三轮。候选仅覆盖固定 helper/warmup 源码。

两边均9个HTTP200、实际exit0/OOMKilled=false。保存的9对完整响应逐字节相等，每侧同类三次响应SHA相同；两侧startup settled后的扩展读取守恒通过，包含源事实、原始37表、队列、主库/六sidecar发布、schema、epoch、fence和文件身份。

实际产品hook调用一次并返回True；缓存信息、帧预算和被观察roots不变，调用期间RSS下降约890.63MiB。观察工具没有额外清缓存、GC或trim。

| 定点 | 原版RSS MiB | 候选RSS MiB | 差值MiB |
| --- | ---: | ---: | ---: |
| startup ready | 1773.89 | 898.73 | -875.16 |
| 最终idle | 1832.81 | 1043.58 | -789.23 |
| 采样峰值 | 1867.72 | 1843.62 | -24.10 |

候选专辑idle1→3仍+1.75MiB，年度+0.016MiB，跨链及最终idle另有数MiB变化；不宣称全进程多轮平台期已证明。采样最大实际gap779.69/926.03ms，不能把采样最大值称精确峰值；单对约24MiB峰值差不证明构建峰值改善。仿真时间只作探索上下文，不用于原生准入。

## 保留的失败和证据缺口

- Linux初次工具collector缺少PYTHONPATH：两边已完成startup，但均在第一个GET前失败，各0GET/实际exit1。失败窗口保存；仅修正工具环境，成功配对从原始备份新建冷副本。
- fullstack初次PERFORMANCE_DATASET误用描述性字符串，在任何检查阶段之前实际退出2；保留原记录。修正为CLI支持的online_backup后，以新服务从头跑默认完整模式并通过，未将后缀重跑称完整通过。
- 旧macOS基本统计SHA与Linux不同，旧响应原文缺失，有界离线检查未得到唯一解释；没有追加请求补成结论。本轮两版Linux完整响应相等。

## 独立证据与恢复

以下均为本地私密归档目录，不包含于Git或镜像。历史收据路径保留原样，用各自archive-receipt解释复制位置。

| 归档ID | 内容 |
| --- | --- |
| resource-ownership-20261013-20261013T051529Z | macOS缓存/帧所有权与有界自然请求诊断 |
| linux-resource-ownership-20261013-20261013T054034Z | glibc/arena/smaps归因与单独trim干预 |
| native-trim-candidate-20261013-20261013T064040Z | 候选固定源文件、64项验证、失败与成功Linux配对、18个完整响应及strict |
| native-trim-review-20261013-20261013T082323Z | 静态审阅、默认Phase5、实际退出与存储保护 |
| native-trim-fullgate-20261013-20261013T100340Z | 默认完整fullstack、首轮配置失败、关闭后的runtime/WAL、四文件补丁、handoff和机器可读结果；779文件逐字节复制校验 |
| native-trim-local-integration-20261013-20261013T135607Z | 本次13项回归、精确暂存/提交钩子、原样快进、六份原文档保护与同步收据；文档快照后缀导致的首次审计失败及路径映射保留 |

共同父目录为 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。fullgate归档的 `current/candidate-complete.patch` 和 `current/candidate-source/` 可恢复四文件候选，`current/attempt2/summary.json` 是成功门禁入口；本地整合归档包含 `current/main-evidence/` 和 `current/source-evidence/`。raw运行记录不依赖活跃工作树。

## 当前决定与下一步

用户明确授权四文件候选及六份文档提交和本地整合，原“暂不提交”限制仅在此范围解除。业务提交已进入main；六份协调文档作为独立状态提交保存，随后安全同步原研发和统一整合工作树。未推送、未部署，不访问或重启生产，不重复生产90或额外仿真轮次。

用户已说明没有非生产原生amd64环境。原生时延/CPU/绝对RSS、逐请求64MiB、多轮进程平台期、构建峰值和整体OOM仍未关闭。下一步是明确固定版本的后续交付与资源验证条件；推送、CI和部署尚未执行。资源门槛若仍不达标，短生命周期builder应作为新的有界阶段单独评估，不扩入当前补丁。现有两工作树保留用于同一资源问题链和统一交付，不新建并行候选。

README、AGENTS/CLAUDE无需改变产品或协作规则；本轮同步开发总表、问题台账、变更日志及文档索引。历史[生产交付](2026-10-13-album-rank-cancellation-production-delivery.md)和[前一整合检查点](2026-10-13-album-rank-cancellation-integration-review.md)继续保留原版本与范围。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-submission-review.md)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。
