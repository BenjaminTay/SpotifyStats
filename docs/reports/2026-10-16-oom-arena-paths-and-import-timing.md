# 启动 arena 持有路径、迟载导入对照与日期回填警告候选

> 后续补证（2026-10-16）：日期候选A-B-A自然ready低20.719–25.133MiB；默认full8同轮PASS/实际0，三浏览器通过，seed线程SQLite警告保留。启动峰/CPU/读取增长及整体资源仍未收口，详见[自然启动与累计门禁](2026-10-16-oom-date-warning-startup-validation.md)。以下保留本轮原始归因及当时门禁边界。

本轮在唯一研发隔离树 `codex/album-rank-cost`（HEAD `dc1cf9ad`）补充持有路径并完成有界 Linux 对照。发现正常 Records 日期回填的 pandas FutureWarning 会把整份业务源码留在 `linecache.cache`，这是此前遗漏的重要根；保留一个消除该警告、显式保持旧 dtype 推断的最小本地候选。批量提前导入只保留实验，不加入业务代码：ready 驻留下降，但启动峰没有改善。

状态：**局部正确性通过，整体资源仍 Partial / HOLD**。本轮未提交、推送、部署或整合 main 业务代码。累计候选仍为六个 tracked、十六个 untracked，共二十二个文件；本轮仅增改其中 `analysis_records_service.py` 和 `test_records_album_release_lookup.py`。整体问题继续使用 `SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。

## 证据范围与有界条件

- 冻结基线复用上一轮原生采样窗的 arena 原始字节；不重写旧证据。
- 三次完整进程启动：首窗在自然 ready 封存后的根图扫描失败，随后原导入时机和提前导入各一有效窗。首窗的启动数字有效，但无完整 GET/strict 尾段，不能并入完整通过数。
- 相同七库来源、相同二十二文件基线镜像 `37903f982dd3…`、Python 3.9.25 / pandas 2.3.3 / glibc 2.41；amd64 在 ARM Linux 引擎仿真，不能代替原生生产资源验收。
- 容器网络关闭、根文件系统只读、内存及 swap 同为 4GiB、CPU 2、进程数 128，单窗总超时 900 秒，RSS 保护 3GiB。无额外 GC、malloc_trim 或业务缓存失效；正常维护自身释放保留。
- 每 100ms 的样本沿用预分配原生缓冲；导入/任务事件也用固定原生数值槽位。两有效窗均核对全部 32 对目标导入、11 对任务开始/结束，事件时间顺序及容量有效。
- 根图放在自然启动封存后，在 fork 子进程中扫描：180 万节点、90 CPU 秒、110 秒 alarm、路径最多 30 层；实际控制窗 734291 节点，未截断。父进程不保存全堆 Python 引用。

本报告原验证时磁盘不足默认完整全栈的 12GiB 门槛，本轮不降低门槛、不为实验删除正式数据或旧证据，也不重跑默认 full8。旧完整后端的 3634 通过、2 跳过、2 项存储门槛失败在 HEAD 同现，继续保持 Partial。

## 原 288 个 arena 补证及快照缺口

这 288 个指上一轮释放探针列表并 GC 后，604 个高空闲 arena 中，未被“四个业务缓存 + 新模块受限图”触及的部分；不表示 288 个泄漏。

冻结快照内重新解析 dict 键/值、list 内部数组、tuple、function、code、cell、module 与代码 C 缓存的确定指针边，原 288 个共 3483 个活块：

| 冻结快照补证 | 数量 |
| --- | ---: |
| 新找到路径的块 | 387 |
| 至少一个块找到额外路径的 arena | 109 |
| 全部活块均连到 code/function/module 端点的 arena | 73 |
| 仍没有上述新增路径的 arena | 179 |

这些 code/function 端点是明确字段路径，不能自动等同于已连到 `sys.modules` 的完整根。快照缺失 arena 外的 26304 份 dict 键表及 119 份 list 数据数组，旧进程已经退出，无法逐地址恢复这些外部关系。逐 arena、逐块目录保存在 `original-288-paths.json`，**原 288 个没有全部逐地址补齐**。

另有 354 个未解释字符串与当前同字节版本的 Records 源码行完全一致，分布于 107 个 arena。内容相同只能作为线索；后续新进程根图才提供真实引用证据，不能用新进程的 arena 编号替换旧编号。

## 新进程中确认的长期持有路径

新图遍历所有已载模块字典及显式业务缓存，以真实强引用边连接对象，并补 list.ob_item、dict.ma_keys / ma_values、set.table、code.co_zombieframe / co_opcache / co_opcache_map / co_cell2arg。只读已知精确内建对象的槽位，匹配封存快照活块和类型；不沿 weakref 的弱目标建立强持有关系。

| 根图覆盖 | 原导入时机 | 提前导入 |
| --- | ---: | ---: |
| 高空闲 arena | 589 | 497 |
| 至少一个块连根 | 572 | 464 |
| 所有活块均连根 | 433 | 341 |
| 连根块 / 高空闲块 | 37633 / 38984 | 30742 / 33383 |
| 块覆盖率 | 96.53% | 92.09% |
| 完全没有根路径的 arena | 17 | 33 |

新图确认的关键路径：

1. `track_composition_identity._traditional_to_simplified` 的 maxsize=1 LRU → OpenCC → dict_cache → TSCharacters / TSPhrases 字典 → 字符串。控制窗 4805 个块、102 个高空闲 arena 连到这个根。它是有界、必要的转换字典；本轮不删除或关闭转换。
2. `linecache.cache` → `/app/backend/services/analysis_records_service.py` → tuple 中的源码行列表 → 字符串/内部数组。控制窗触及 153 个高空闲 arena、561 个块，其中 77 个 arena 的全部活块在所选路径图中都连到这个根；提前导入窗仍触及 154 个、全块连到该根的有 88 个。
3. 既有模块的运行期缓存、函数闭包、嵌套 code 的 freevars/cellvars，以及 C opcode / zombieframe 缓存，也是原受限图遗漏的边。控制窗新捕获 3897 个 list 内部数组、131 个 dict 键表、30 个 dict values、870 个代码缓存帧、369 个 opcode cache 和 359 个 opcode map 的路径。

这些路径可能共享，触及数不可相加；“全部块选择同一 BFS 根”也不是该根唯一强持有者的证明，77×256KiB 不能直接当作可保证释放的 19.25MiB。控制窗完全未连根的 17 个包含一个全空备用 arena、Pandas 扩展 freelist、raw 块和少量字符串。全部 1351 个未解释块已列入目录，不能依据数值头把它们统称活 PyObject 或泄漏。

## 修正采样器下的真实导入时机

仅改变诊断脚本中的导入时机：把 32 个已知启动期 backend 模块放在 lifespan 开始前导入，不执行 builder、不主动读库或预热缓存。httpx 和探针依赖在两窗均先完成导入。

| 控制窗首次导入 | 距 lifespan 开始 | 当时 RSS MiB | 所在任务 |
| --- | ---: | ---: | --- |
| playback.records_album_facts | 40.383s | 954.805 | analysis_snapshot_rebuild |
| community.feed_generator | 78.569s | 456.824 | community_snapshot_rebuild |
| account_archive.cohorts | 88.280s | 411.227 | account_archive_snapshot_rebuild |

提前导入窗这些模块均在 lifespan 之前导入，RSS 约 200–202MiB。导入确实有在高内存阶段发生的情况，但其总效果需区分 ready 驻留与瞬时峰。

| 自然启动封存指标 | 原导入时机 | 提前导入 |
| --- | ---: | ---: |
| ready RSS MiB | 409.668 | 392.465 |
| arena 数 / 容量 MiB | 1005 / 251.25 | 935 / 233.75 |
| 分配块 MiB | 84.564 | 85.503 |
| 启动采样峰 MiB | 993.719 | 1010.289 |
| ready 累计 CPU 秒 | 122.870 | 121.750 |
| 启动最大采样间隔 秒 | 1.185 | 0.887 |

ready RSS 低 17.203MiB、arena 少 70 个；启动峰反而高 16.570MiB。首次根图失败窗 ready 为 412.098MiB / 1015 arena / 峰 985.789MiB，其自然段作为运行波动旁证保留。每种只有一个完整有效窗，不能把上述差值当稳定因果量。**本轮不将批量提前导入加入业务代码，不宣称启动峰或 OOM 改善。** 根图之后的请求受诊断暂停影响，不用作短峰或 p95 验收。

## 最小候选：保持日期和 dtype，消除正常启动警告

控制窗与提前导入窗均出现日期回填 `object.fillna` 的 downcast FutureWarning。新图证明源码行被 linecache 长期保留，因此修复触发它的具体操作，而非清理 linecache、过滤警告、调整全局 pandas 选项或追加 GC。

`analysis_records_service._build_entity_frames` 在已经 owned 的专辑表上，用 `where(notna, fallback).infer_objects(copy=False)` 明确保留旧 fillna 的值与 dtype 推断；临时 Series 在最后消费点删除。仍仅处理日期 Series，源事件表、时长表和发行日期查询表保持只读，返回表独立。无新增依赖、环境开关或统计口径。

验证：

- 本地相关 139 项通过，包含新增 9 项日期回填回归；把实际冻结旧函数替换回去，新增组中 2 项复现警告、其余 7 项通过。不是只验证实现自身。
- 同版本 Linux 七组日期小对照：空表、全缺失、混合日期、fallback 全空等，值、dtype、name、index 和输入不变，候选均无该警告；旧全缺失例复现警告。
- Linux 独立进程调用真实 builder、确定性 fixture、正常警告显示：旧函数缓存 618 行源码；候选不产生该源码缓存，日期结果均为全缺失 float64。这证明警告→源码缓存链路，不是启动 RSS 收益测试。
- Linux 真实数据 3 层级 × 3 个时间范围共 9 组，27 张完整返回表及 27 张时长表与冻结旧函数逐字段、dtype、索引、顺序一致；源事件和时长表不变，运行副本七库 SHA 不变。这个实际数据组双方都未触发该警告，触发场景由启动日志及 fixture 补充证明。

本轮已证明候选消除一个具体常驻根的触发原因；**尚未对该候选单独跑完整自然启动 A/B，其总 RSS、arena 和启动峰净收益仍未验证**。本次两个有效完整窗使用的是修改前冻结镜像，不能把其 17.203MiB 差值归给这个候选。

## 正确性、失败保留与交接

原导入/提前导入两有效窗各九次 GET，共 18 份完整响应与上一轮最终二十二文件窗逐字节相同；六份 stats/Records 发布事实相同，仅跨构建业务对账省略 meta.generated_at。两窗读取前后来源、保护表、队列/发布和六 sidecar strict 通过，不增加失败或待运行任务。它们验证导入实验；日期候选的验证另见上述本地和 Linux builder 对账。

诊断失败均保留：首完整窗的扩展类型 `__module__` 非字符串；小预检的输出 label 被字典键变量覆盖（控制窗实际根图文件名为 `_router-root-paths.json`，算法与路径有效，下一窗已修正命名）；一次预检重复目录；独立警告验证首次发现镜像不含测试 fixture，改为显式复制本地 fixture 后通过。未覆盖或改写失败。自然启动对照在这些根图操作前已经封存。

正式七库、main 五个无关改动、三个 HEAD、空暂存区及整合树保持；本轮只改两个已有候选文件及 main 协调文档。文档审计另附日志。

下一阶段只需给日期警告候选做独立、修正采样器下的完整自然启动对照，并将剩余小规模 interpreter / extension 路径与长期平台验收分开。旧 288 的缺失外部字节无法事后恢复，不再把全量补齐作为可完成的承诺。原生 Linux、默认基镜像、64MiB 请求门槛、长期平台和生产 OOM 继续 OPEN。

原始证据：研发树 `output/oom-arena-paths-import-timing-20261016`；独立归档：`~/.codex/archives/spotifystats-delivery/oom-arena-paths-import-timing-20261016/evidence.zip`。包含旧 288 清单、新根图、两有效窗及失败首窗、18 响应、六事实、strict、最小候选与测试、Linux 实际 builder 对账。全部含本地数据的材料仅本地保存，不入 Git。核验归档后仅删除本轮三个已停止 owned 容器，保留正式七库、镜像和原始 output。

## 磁盘清理补记（2026-10-16）

连续实验保留了每组完整数据库副本及原始 arena 二进制，同时又保存独立归档；归档后未及时回收展开副本，导致研发树 output 累积约54GiB。本轮按用户授权清理28个阶段的已归档大文件，逐项比对当前文件与恢复副本的长度和CRC，并完整读取压缩条目核验可恢复后，仅unlink对应叶子文件。

删除230个数据库/二进制重复文件，共45.678GiB。可用空间实测约3.012→50.798GiB；这是系统总可用空间变化，不将额外系统回收量归为本轮删除量。无运行进程使用这些文件。正式七库、当前22候选、main五个无关文件、三个HEAD、工作树状态和暂存区全部保持；未改Docker对象。压缩或目录归档、日志、JSON结果、失败记录和代码继续保留。

本报告及其他历史报告中的原始output路径仍保留小型材料；其中大文件已回收到原有独立归档，不再原地展开。逐文件原路径→归档条目及CRC见研发树 `output/oom-evidence-space-cleanup-20261016/deleted-files.jsonl`，清理收据另存 `~/.codex/archives/spotifystats-delivery/space-cleanup-20261016/`。如需旧数据库或arena字节，只恢复所需条目；不要直接重跑假定runtime齐全的旧脚本。后续每轮实验完成并核验归档后及时回收展开的大文件。
