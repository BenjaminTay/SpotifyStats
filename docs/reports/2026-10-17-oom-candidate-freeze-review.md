# 累计资源候选冻结、审阅与阶段提交

日期：2026-10-17。事项 `SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。本报告完成R0，R1镜像/验收包继续；资源准入和正式交付仍HOLD。

## 审阅与测试补修

唯一研发树 `codex/album-rank-cost` 以 `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06` 为基线，原22文件独立审阅无阻塞发现。五个Python业务文件、十六个回归测试采用；Docker allocator ENV保留待实际镜像及原生资源准入。没有扩大缓存或改变统计口径。

审阅覆盖track/艺人/合作事实的必要列、署名展开、事件次数与独立时长、membership、canonical身份、去重键、NULL/dtype/索引/attrs、异常fallback、Yearly Review预载调用及合法返回对象保活。Records复用只读逻辑ID输入，以唯一窄键回填日期，并在最后消费点释放临时引用。完整源码审阅清单保存于恢复包。

一项非阻塞收集缺口已补：`test_records_frame_peak_ownership.py` 增加unit标记，两项用例通过；旧默认full8已全量收集这两项，不推翻旧门禁。

AI线程SQLite警告做候选/HEAD各一次自然定向：候选2通过未复现；HEAD2通过并精确复现 `ai_task_service._run_handler_safely -> get_db -> PRAGMA journal_mode=WAL -> disk I/O error`。时间线证明前项visual模式接口测试的daemon仍打开临时SQLite时，fixture已恢复DB_PATH并删除db/wal/shm；候选还观察到线程跨入session数据库。证明HEAD存在同类测试竞态，不倒推原full8的每个调度细节，也不称完整HEAD full8等价。

最小修复只在该模式契约测试mock路由引用的 `start_report_task`，返回合法任务响应，验证六个请求字段实际转发；生产AI、WAL和重试均未改。整个visual模块及相邻years GET共6通过，线程warning提升为error；AI daemon创建、AI worker SQLite连接和外网尝试均0。唯一warning为本机既有LibreSSL提示。

## 阶段验证与提交

- 当前五个业务Python文件及allocator ENV与[10-16默认完整门禁](2026-10-16-oom-date-warning-startup-validation.md)逐字节一致，复用run `20261016T100238.045158Z-7c6286a7191d` 的八阶段PASS/实际0。本轮两处测试补修后未重跑full8；最终整合版仍须执行一次完整门禁。
- 新增2项unit/6项contract通过；Ruff、format、mypy、detect-secrets四hooks通过，提交时staged hooks再次通过；diff check通过。
- 原22文件及补修后23文件patch在main/现有整合树apply-check均0，尚未将业务补丁应用到二者。
- 按大阶段提交授权形成研发提交 `c844b98f260b85b92ae298e9d135fdab6cb05de2`，标题 `perf: 降低实体统计与播放记录构建的临时内存`，共23文件；未推送部署。源SHA→main业务SHA映射待R4。

README产品说明与AGENTS/CLAUDE规则无需改变，两份约定保持一致。协调文档、变更日志和索引由main统一维护。

## 恢复入口及剩余工作

研发证据在 `output/oom-closeout-execution-20261017/`，独立恢复包在 `~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261017/R0-candidate-review.zip`。23份源码、binary patch、选中清单、审阅、警告原始时间线及hooks已CRC与逐字节读回核验；相邻 `R0-commit-receipt.json` 记录提交和包hash。恢复包不含真实七库。

R1预检已确认历史registry镜像源502、PyPI TLS/下载超时；Pillow官方元数据及现有镜像pip check不支持为此升级Python或改变依赖约束。实际Dockerfile新构建、镜像启动及可移植包继续实施，不以旧封存应用镜像替代。非生产原生amd64环境仍缺失；原64MiB、多实体50%/LRU、长期并发、容量及正式发布后72小时观察均未完成。
