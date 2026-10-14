# 维护完成原生回收候选：当前源码默认完整门禁

2026-10-14（Asia/Shanghai）；SS-2026-10-08-001，关联SS-2026-10-09-001。

## 结论

**当前未提交三文件候选的本地默认全栈门禁PASS，8/8必需阶段同轮通过，实际退出0。** run `20261014T005816.915594Z-9d1a29cefca3`，总耗时1811.010秒。不是复用旧6c的CI/full8，也不是--from/--only局部结果。

唯一研发树仍基于6c74b9b416dbba47b354b850bdfe678f26ece63a、dirty=true；变更为 `backend/core/job_queue.py`、`backend/tests/unit/test_job_queue.py`、未跟踪的 `backend/tests/unit/test_job_queue_native_memory.py`。实际源码SHA与10-13冻结记录及运行前后均一致，新7用例在完整seed XML中实际执行并通过。产品代码未整合到main；本轮未commit/push/CI/deploy，也无生产API、重启、预暖或配置修改。

发布仍HOLD，资源问题OPEN / Partial。此门禁使用macOS，原生回收helper为no-op；保留[10-13 warmup=0 Linux仿真](2026-10-13-native-trim-maintenance-candidate.md)的原范围：11次实际回收保持缓存，9对完整响应/两strict通过，ready/final低343/333MiB，但采样峰高约40MiB、读取增长略大。完整门禁不能把这些资源边界改判为通过。

## 当前完整结果

| 阶段 | 实际状态 | 秒 |
| --- | --- | ---: |
| preflight | PASS | 8.260 |
| quality | PASS | 70.626 |
| backend | PASS | 755.983 |
| api | PASS | 227.708 |
| browser-routes | PASS | 412.950 |
| browser-interactions | PASS | 81.759 |
| browser-inventory | PASS | 46.146 |
| browser-compat | PASS | 207.443 |
| optional | NOT_RUN | 0.000 |

- 质量：pre-commit hooks、文档审计、CI parity、Ruff、frontend test/build通过；前端803 passed/4 skipped。Phase5由父门禁执行，unit/contract的独立marker重复明确跳过，backend阶段负责整个seed和真实集成，符合现有规则。
- 后端：seed 3955 passed/2 skipped；真实数据integration 186 passed/1 skipped，XML无失败。seed约364.52秒，integration约378.41秒；警告原文保留。
- API：smoke157/157、boundary113/113；51端点×22次，共1122样本，500ms阈值未改，slow_count=0，hot P95无null、最高267.241ms。外部进程首次请求不冒充cold，后续warm不推断cache hit。
- 浏览器：路由、重点五视口、桌面/移动交互及图表、控件/长列表、Chromium/Firefox/WebKit全部通过。WebKit是测试引擎，不代表真机Safari；手机初始加载时弹层重挂载问题仍按原独立台账OPEN。
- optional未运行；production preview、真实LLM/OAuth/物理手机、原生amd64资源和生产首次窗口不由本轮推定。

## 数据与运行隔离

复制前确认旧本地fullgate fixture无开放消费者，文件逐一SHA核对，包括已有WAL/SHM。旧fixture已包含年度成品；新运行副本复用其事实，不因生产关闭预热而额外生成年度缓存。排名规范validate/install/verify实际0，安装器在新副本生成自己的file-local lineage。当前服务全程warmup=0，外部封面使用门禁规定default1，端口仅loopback8138/5188。

默认门禁只指向新自有runtime；integration插件另建一份session可写副本。旧fixture与原关闭七文件备份最终字节不变，不打开正式本地数据库。运行结束后后台、Vite与门禁自有进程均关闭，lsof确认runtime无开放消费者；现有WAL/SHM按原字节保存，不为归档额外checkpoint。

存储守卫实际0，peak临时文件1.033GiB、最低可用空间13.137GiB；未触发stop，owned test临时目录已自动清理。独立归档不混入待清理测试目录。

## 首轮失败保留

首轮run `20261014T005719.998507Z-719af7c2b7d7` 为默认模式，preflight实际失败、gate退出1，后续质量/测试未开始。研发树旧 `output/native-trim-fullgate-20261013/fullgate-report.md` 含两个已失效归档链接，被全Markdown审计当作新文档扫描。

按原始证据的存放约定改名为 `.md.snapshot`，原字节/SHA不变，old→new映射、原报告、失败日志/summary均保存；未改产品或 authored docs、未调整门禁与阈值。随后启动新自有服务，复用本轮已完成准备的自有副本，运行第二轮默认全部阶段；没有--from热续跑，也没有重跑Linux性能对照。

## 恢复与下一步

归档ID `native-trim-maintenance-fullgate-20261014-20261014T013012Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。私密 `evidence.zip` 包括精确源码及tracked/new-test补丁、两个默认run原记录、XML/benchmark/浏览器证据、完整关闭runtime和WAL/SHM、规范排名输入、原报告字节与路径变更映射、协调文档快照；逐条内容/SHA独立复核，恢复时解压到新的私密目录。数据库和payload不进入Git、镜像或CI artifact。

当前可进入精确提交与整合审阅；本轮授权只继续验证，未执行提交。之后的新研发CI与发布仍需针对新提交，不能复用6c的旧CI；发布前另核成品fence、目标镜像及维护触发条件。原生峰值、逐请求64MiB、平台期、整体OOM保持OPEN，不为触发回收调整生产warmup配置。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-submission-review.md)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。
