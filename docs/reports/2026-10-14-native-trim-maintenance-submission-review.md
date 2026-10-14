# 维护完成回收候选：提交与整合范围审阅

2026-10-14；SS-2026-10-08-001，关联SS-2026-10-09-001。

当前交付：业务`8f46b3cb`已按授权提交并进入本地main，同SHA映射；十份文档独立提交及三树同步见本文末节。未推送或部署，资源/OOM仍OPEN。

## 提交前审阅结论

**审阅通过，可交精确提交；未提交、未整合、未推送或部署。** 唯一研发树仍为 `codex/album-rank-cost`，基线 `6c74b9b416dbba47b354b850bdfe678f26ece63a`。三文件原字节与10-13冻结值、10-14完整门禁独立归档中的源码一致，审阅没有修改业务或测试。

代码未发现阻塞项：回收位于成功handler返回后、done前且持已有CPU gate；无额外启动预热、GET回收点、缓存失效或新配置。未列入既有CPU重型job_type集合的任务、未知handler及失败任务跳过，不以resource_class扩展或收缩集合；full预热不重复调用。已有helper的非Linux/非glibc/缺符号/OSError返回False不会改变任务完成，失败重试与后续排队路径保留。七个新增用例覆盖顺序、缓存对象、False返回、类型选择、失败重试及串行边界；原helper/warmup兼容与失败测试、54专项、当前默认全栈8/8实际0均是同一候选证据。

main与现有 `codex/versus-detail-integration` 均在同一6c基线，目标两旧文件字节与基线相同，新测试路径不存在。两处 `git apply --check` 实际0；仅干净可应用性检查，没有改目标源码。三棵树索引均未暂存任何内容。main已有九份未提交协调文档均属于同一问题链，逐份保护后审阅，不将它们复制到研发树。

发现并修正一个文档问题：docs地图/报告索引仍称“新完整门禁未运行”，与同一冻结候选10-14默认full8 Pass冲突。索引改为当前完整门禁已通过、新提交CI尚未运行；旧报告中的10-13检查点和raw receipt保持原范围。新增本报告后文档提交范围为十份文件。

## 两次精确提交草案

第一份仅在研发分支提交以下三个路径，标题 `perf(memory): 在重型维护完成后回收闲置原生页`；中文正文写明完成边界、跳过类型、保留缓存及已有验证，资源仍Partial。

- `backend/core/job_queue.py`
- `backend/tests/unit/test_job_queue.py`
- `backend/tests/unit/test_job_queue_native_memory.py`

第二份为main协调文档提交，标题 `docs: 固定维护回收验证与发布边界`。包含此前仍未提交的同链CI准备、专项/完整门禁报告、当前审阅和状态同步；不包含数据库、清单payload、原始日志、ZIP、covers或任何output。

- `docs/CHANGELOG.md`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/README.md`
- `docs/issues/2026-08-27-issue-register.md`
- `docs/reports/2026-10-13-native-trim-candidate-review.md`
- `docs/reports/2026-10-13-native-trim-maintenance-candidate.md`
- `docs/reports/2026-10-13-native-trim-release-preparation.md`
- `docs/reports/2026-10-14-native-trim-maintenance-fullgate.md`
- `docs/reports/README.md`
- `docs/reports/2026-10-14-native-trim-maintenance-submission-review.md`

完整提交信息与分路径补丁已保存为私有准备材料，尚无staged diff或commit。授权后先精确提交研发三文件并执行项目hooks；再将同一业务commit按当前可快进关系进入本地main，记录实际source SHA→main SHA；main文档统一补上提交/整合事实后独立提交。现有main的dirty文档保留，不做整树reset/clean。整合树同步只在状态与未提交文件保护后进行。

不提前填写尚不存在的提交SHA，也不预先把状态改为INTEGRATED。提交后的新CI及任何远端推送/发布另按明确授权推进，不由本次审阅或过去6c的CI推定。

## 验证与资源边界

[当前默认完整门禁](2026-10-14-native-trim-maintenance-fullgate.md) run `20261014T005816.915594Z-9d1a29cefca3`，8/8/actual0；seed3955、真实集成186、前端803、API157/113、三浏览器通过。此次审阅源码未变，不重复测试、完整门禁或Linux性能窗口；只对变更后的协调文档运行审计与diff检查。

[Linux专项](2026-10-13-native-trim-maintenance-candidate.md)支持维护后驻留下降343/333MiB，但采样峰高约40MiB、读取增长略大；原生amd64环境缺失，峰值/64MiB/平台期/OOM仍OPEN，发布HOLD。既有生产c0d首次窗口不追加请求、预暖或重启。

## 审阅时证据与停止边界

本轮独立审阅归档 `native-trim-maintenance-submission-review-20261014-20261014T014433Z`，父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`；包含三文件精确补丁及源码、两处无写入apply-check收据、协调文档保护/最终快照、精确路径提交草案、提交信息与审计结果。完整门禁950文件归档仍是 `native-trim-maintenance-fullgate-20261014-20261014T013012Z`，不改写原材料，不重复复制数据库。

用户本轮“继续”对应审阅与整合范围准备。AGENTS.md明文“未经明确要求不执行 git commit 或 git push”，因此提交仍待明确指令；当前准备工作已完成。

## 2026-10-14 授权后的本地提交与整合

用户已明确授权三文件业务提交、本地main整合及十份协调文档提交，不含推送或部署。业务提交 `8f46b3cb9af8ebc2c546727df089d4d97e7f5309`（`perf(memory): 在重型维护完成后回收闲置原生页`）精确包含三文件，提交前54回归通过，提交时ruff/format/mypy/detect-secrets四项hooks通过。

研发 `codex/album-rank-cost` 源SHA `8f46b3cb9af8ebc2c546727df089d4d97e7f5309` → main业务SHA `8f46b3cb9af8ebc2c546727df089d4d97e7f5309`，采用同一commit快进，没有重写代码。main原有十份dirty文档在快进前后逐份字节保持；本报告与其余九份协调文档由随后独立docs提交保存，实际docs SHA见Git历史和下述归档收据，不预先填写未知SHA。源码仍等于当前默认full8已验版本，没有重新运行完整门禁或Linux对照。

main、研发、统一整合树将在本轮文档提交后安全同步同一最终HEAD；不做reset/clean、不删除问题链工作树。当前保留同一研发/整合树服务后续资源问题与交付，OOM、原生峰值/64MiB/平台期继续OPEN，发布HOLD；未push/新CI/deploy，无生产请求或配置变更。

本轮独立恢复入口：`native-trim-maintenance-local-integration-20261014-20261014T015116Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。包含业务/docs两提交补丁、原文档保护及最终快照、实际commit/hooks与fast-forward记录、source→main映射、三树关闭检查点、文档审计和54回归。数据库与完整旧性能材料不重复打包，继续使用已验证的既有独立归档。原始收据保持原样，执行后的最终HEAD与同步结果由最终收据记录。
