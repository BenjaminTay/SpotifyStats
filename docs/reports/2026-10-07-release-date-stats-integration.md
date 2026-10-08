# 发行日期精度与详情空统计联合集成验收

日期：2026-10-07。问题：SS-2026-09-24-003、SS-2026-10-07-001。

状态：LOCAL_INTEGRATED / FULLSTACK_PASS / UNPUSHED / NOT_DEPLOYED。两项代码已本地收口；正式数据库迁移、有界来源补证、CI和生产发布尚未执行。

## 固定交付与集成

用户在验收后授权继续独立提交空值修复、与日期精度集成并运行合并版本完整门禁。空值补丁以10个明确文件独立提交为 `9c360714`，提交钩子通过。日期固定输入为 `98dea609`、`6edbe051`、`c5e3314b`。合并提交 `7f7185cfddb8320fa13090a7f44fdc749098cd6f` 保留两个分支的业务行为，四处冲突仅在变更日志、开发状态和文档地图，已同时保留两项证据。

新版本在独立工作树 `codex/release-date-integration` 验收，随后主目录由干净 `c67d296a` fast-forward 到 `7f7185cf`。后续本报告、状态表与地图收尾仅修改文档，不改变已验收业务。来源工作树保持干净的 `9c360714` 和 `c5e3314b`。

## 新默认完整门禁

成功 run：`20261007T150856.854749Z-290c0b989199`。selection=full；运行HEAD `7f7185cf`、dirty=false；八个必需阶段全部同轮PASS，总耗时 `1,461,832ms`，约24分22秒。optional未启用，不代表preview或额外性能探针通过。

| 阶段 | 状态 | duration_ms |
| --- | --- | ---: |
| preflight | PASS | 7639 |
| quality | PASS | 65946 |
| backend | PASS | 537770 |
| api | PASS | 175420 |
| browser-routes | PASS | 400037 |
| browser-interactions | PASS | 79938 |
| browser-inventory | PASS | 46200 |
| browser-compat | PASS | 148756 |

- 后端seed全量：3424 passed / 2 skipped；独立真实数据integration：186 passed / 1 skipped。两进程按父门禁分工执行，没有再追加marker重跑。
- 前端全量：763 passed / 4 skipped，production build通过；pre-commit、Ruff、mypy、密钥扫描、文档与静态API覆盖通过。既有act、LibreSSL/pandas与大chunk提示保留，没有吞错误或放宽断言。
- API契约157/157、边界113/113通过。51个benchmark组合共1122个样本，失败0；每组合21个有效warm样本，最大warm P95为313.73ms，500ms门槛通过。外部服务首个请求不称cold，warm不推断为cache hit。
- 默认完整路由、360/390/430/768/1280px宽度矩阵、桌面/手机交互、图表、控件和长列表通过；Chromium、Firefox、Playwright WebKit全部通过。WebKit不等同于物理Safari/iPhone验收。
- 存储保护退出0并清理自己的临时目录；峰值890222644 bytes，未触发2GiB预算。使用默认主机阶段排他锁。

规范结果位于 `/tmp/spotify-fullstack-verification/20261007T150856.854749Z-290c0b989199/summary.json`。两轮完整报告、XML和benchmark已另存本任务ignored输出，避免仅依赖latest指针。

## 日期与空统计联合专项

在同一合并版本与运行副本上，Chromium分别检查1440×1000桌面和390×844手机：Afterlife（44155）、Midnights（41553）、收穫（42141）、C,XOXO（42311），共8个场景；另检查手机2026-10-07真实零总量，以及实际操作时间sheet切回全部时间并切换累计图。

Afterlife实际API `found=false`、趋势为null，正常展示“暂无个人播放统计”，不挂载统计KPI。Midnights全部时间保持2567次；单日API `found=true`、总量0、每日和累计数组为空，页面保持真实零统计，切回全部恢复2567次。收穫只展示2001，不混入冲突来源的Rock Records厂牌或发行11首；C,XOXO按确认day展示2024-06-28（桌面日期格式28 Jun 2024）。没有console error/warning、page error、NaN或横向溢出。空态、零总量、年份和day截图已目视检查。

专项CLI会话中途关闭，未将该轮算完整通过；改用独立Playwright进程重新执行。首次独立脚本把日期文字当作时间按钮aria-label，定位超时；按实际“当前按日”标签修正验证脚本后，9场景与零→有效统计交互全部通过。产品代码和断言范围未改，失败日志保留。

## 副本、准备失败与事实守恒

独立环境位于 `/Users/benjaminlei/.codex/worktrees/release-date-integration/202605-SpotifyStats/output/playwright/date-stats-integration/`。主库和六个sidecar以SQLite Online Backup复制先前已准备的schema89日期验收副本，封面和cache使用独立APFS克隆；后端18827、前端5197均为本轮独立进程。原始本地schema81来源另以只读Online Backup保存作对照，未把应用或迁移指向正式库。

首次默认run `20261007T144527.374104Z-8ca56745c84f` 为FAIL：preflight、quality、backend和157/113契约检查通过，但HTTP benchmark多族503 `snapshot_unavailable`，浏览器阶段未执行。原因是准备环境遗漏：Analysis快照绑定device/inode，其他发布键也含数据库路径，复制旧sidecar不能证明新副本可消费。失败不是有效性能样本，也没有算成Pass。

随后仅在本轮副本、共享排他锁内通过正常后台维护重新准备默认快照；等待任务结束后以同一文件身份重启prepared runtime，使用正常应用lifespan，关闭重复预热/搜索/L3启动维护，并按既有隔离方式抑制重复默认队列。主要接口实际恢复200；之后重新执行上述成功的默认完整门禁，没有修改业务或门禁脚本、放宽预算、使用旧完整Pass或改写正式快照。副本仍保留3142条来源精度未知、89条year、1条month和2条day，不把未知变成确认day。

最终19个保护表按来源完整列双向EXCEPT均为0，包含原始播放/歌曲/署名、Album/project原关系、身份与人工覆盖；Album与project日期原文两组也完全保持。plays94760、tracks10026、track_artists10496、albums4030、album_projects2940保持；有效曲目署名投影11770行的规范摘要相同；runtime integrity=ok。正式来源前后Online Backup同样逐项保持，schema仍81。冻结的无writer备份以immutable只读打开，活动runtime使用正常只读连接。

真实数据、来源响应、缓存、封面、截图与日志只留ignored输出，没有进入Git。验收完成已停止本轮后端、前端与浏览器。

## 下一步

代码部分已收口。下一步先从新生产Online Backup做schema88→89演练，仅选择必要Album ID获取来源证据，预览冲突、精度变化与日级消费者降级；按同源证明准备受影响快照，再推进三模式门禁、CI、联合回滚及生产只读/API与桌面手机展示验收。不全库补取，不批准身份/归并，不以本地Pass替代正式迁移、生产模型/OAuth或真机验收。

本轮24分22秒只是该版本单次门禁计时，不能据此关闭三次低干扰稳定验收或安全续跑/分片待办。原两任务历史范围保持：[日期专项](2026-10-07-release-date-precision-acceptance.md)、[空值专项](2026-10-07-entity-stats-empty-acceptance.md)；后续排期见[开发状态](../DEVELOPMENT_STATUS.md)和[日期计划](../archive/06-productization-closeout/2026-10-07-release-date-precision-plan.md)。
