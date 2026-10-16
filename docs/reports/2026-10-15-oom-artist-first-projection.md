# 艺人统计首次读取内存峰值：载入与署名展开投影

核验日期：2026-10-15。问题：SS-2026-10-08-001，关联 SS-2026-10-09-001。

## 结论与范围

**本地最小候选保留；整体资源仍 Partial。** 冻结既有 mmap、Records 启动重排及冷专辑投影，只在已发布排名上下文的艺人详情分支新增 SQL 字段投影。130 项相关测试通过；同源两镜像各 9 次读取，完整响应逐字节一致，六份启动业务事实与 strict read window 通过。艺人首次请求采样峰增量 126.879→101.590 MiB，本轮读取窗口峰值低 27.465 MiB，末尾驻留低 8.230 MiB。启动峰值未改善，不关闭 OOM。

代码仅在 `codex/album-rank-cost` 研发工作树；共四个 tracked 修改和三个新测试文件，未暂存、提交、推送、整合或部署。main 仅更新协调文档，整合树保持原样。

## 分段归因

同一首次 Taylor Swift lifetime/dynamic 请求：

1. SQL 返回 27,534 行；原始投影 33 列。范围仍包含目标曲目前一条合格播放，不能删去这段上下文，否则会错误合并被其他曲目打断的播放。
2. 事件重建、有效署名展开与 canonical artist 处理完成后，原路径 RSS 约 623 MiB；署名后事件 21,432 行×48 列，未阈值化时长 30,113 行×41 列。
3. 随后筛选目标艺人与拥有的专辑、展开时长、构建专辑加权表。原路径最高浅栈证据位于 `compute_album_project_plays` 的 membership 关联后：37,387 行×57 列 weighted/events 与 37,387 行×78 列 merged 同时存活；上层还保留 all/current、目标事件、目标时长和 owned album 副本。采样 RSS 724.988 MiB。

因此，SQL/署名展开并非这次最高点；它们携带的多余列被后续多份宽表反复复制，放大了峰值。候选最高 RSS 样本未取得 backend 局部栈；此前样本位于同一专辑聚合段，不能把候选的最高样本精确归到某一内部语句。

## 最小修复

`entity_stats_service::_ARTIST_STATS_PLAY_COLUMNS` 明确已发布艺人详情所需字段，并以 `partial(load_plays_for_artists, columns=...)` 传给现有 scoped loader。复用 SQL 投影与缓存键，载入时就省去国家、播放原因、导入批次等未消费字段；并非展开完后再删除。

保留播放编号、时间及日历字段、platform、时长、track/source album、provider token、source fingerprint、曲目/专辑展示字段和 duration_ms；loader 仍添加 resolved L1/source/representative 身份。最近播放、专辑归属、动态阈值、合并边界与次数/时长轨道保持原消费合同。

| 阶段 | 原路径 | 候选 | 行数 |
| --- | ---: | ---: | ---: |
| SQL 输入列 | 33 | 22 | 27,534 |
| 署名及身份归并后事件列 | 48 | 37 | 21,432 |
| 署名及身份归并后时长列 | 41 | 30 | 30,113 |
| owned album 加权表列 | 57 | 46 | 37,387 |

未更改前序上下文 SQL、排序、逻辑事件编号先于署名展开、canonical identity 去重、有效署名解析、统计过滤或发布版本。未减少缓存预算、清缓存、强制 GC、增加 trim 或向公开 GET 加入写入。无发布上下文及轻量分支仍使用原路径。

## 正确性与镜像验证

- 56 项专项：新增 8 组 merge/dynamic/music 组合，将投影后每列事件与时长逐行对账全宽 loader；4 组完整 published artist payload 对账全宽 scoped loader并核对源/发布文件未写入；既有署名、身份、排名与缓存策略测试通过。
- 74 项相关消费者：既有 track/Top250 投影、Records 生命周期、专辑 published rank、所有收听时长、逻辑次数及艺人 chart loader 通过。共 130 个唯一测试；格式化后重复新增 12 项通过，不重复计数。
- 测试进程恢复全宽 `columns="*"` 后，8 个前置宽度断言均按预期失败；不把它计为业务结果差异。Ruff、格式检查、mypy hook、diff 检查通过。
- 同一封存缓存 runtime，Dockerfile backend 阶段离线构建；无 backend 源码覆盖挂载。两镜像各 518 个 backend/scripts 源文件与冻结上下文逐一一致，Python/依赖相同，mmap ENV 在 Python 启动前存在，代理未进入 runtime ENV。

基线：`sha256:36fd0f4ff920b8bac75455be8123dce7c10b4734a8d3b3ddb4accb379a3d5e56`。
候选：`sha256:c4005c2c108f345ca4f0cec9ac2fea5e8fd6ab47f8009aaf61556a6a3ebefb05`。

## 有界 Linux 对照

每侧新建七库副本，正常启动维护结束后，Midnights 两种 rank 请求各三轮，再 Taylor Swift artist 三轮；共 9 次串行 GET。相同 sampler/浅栈与阶段观察器，不做额外释放。每侧仅运行一次；不与上轮 33 读窗口直接比较。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1144.031 | 1160.723 | +16.691 |
| startup ready | 542.625 | 542.492 | -0.133 |
| 首次 artist 前 | 598.109 | 595.934 | -2.176 |
| 首次 artist 采样峰增量 | 126.879 | 101.590 | -25.289 |
| 本轮读取采样峰 | 724.988 | 697.523 | -27.465 |
| 最终 idle | 618.402 | 610.172 | -8.230 |
| ready 至最终增长 | 75.777 | 67.680 | -8.098 |
| 合法帧预算占用 | 202.910 | 181.076 | -21.834 |

候选三次 artist idle：610.500 / 610.172 / 610.172 MiB。缓存未饱和，有限重复不证明长期平台期或无泄漏。首次 artist 样本数 78/67，最大间隔 0.129/0.118 秒；整个窗口最大间隔 1.226/0.563 秒，记录的是采样峰而非连续真实高水位。

9 份完整响应逐字节一致。latest 三范围 stats/Records 六份业务事实一致，跨构建仅移除 `meta.generated_at`；各自 strict 比较未豁免时钟。37 原始表、保护事实、队列、发布与六 sidecar 读取前后保持；原七文件 SHA 未变。每侧均 8103 done/38 historical failed，failed 任务行相同；容器 exit0/OOMKilled=false。11 次 trim 均为原有真实维护调用，前后 cache roots/LRU 状态一致，没有额外释放。

## 证据、恢复与剩余边界

原始证据：研发树 `output/oom-artist-first-20261015/`。包括 frozen-existing-candidate、selected-candidate、artist-only.patch、两套镜像上下文/清单、130 项日志、原全宽断言失败、完整 body、stage/peak 栈、native 资源、strict 收据及 six-facts 对账。

独立恢复入口：`~/.codex/archives/spotifystats-delivery/oom-artist-first-20261015/`。压缩包 CRC、源码/文档快照、两侧完整 body 和业务事实校验后，按精确容器 ID 清理本轮两个已退出容器；保留镜像、原始输出及正式数据。最终归档/清理结果以该目录的收据为准。

基线 runner 在候选单独调用时覆盖了其汇总 list；没有重跑窗口，基线 live receipt 已核对 exit0，随后从独立 inspect、process-exit、strict 结果恢复保存为 baseline-window-receipt.json。两侧完整原始证据仍在。

当前 ARM Linux 引擎运行 amd64 仿真，使用封存缓存 runtime 替代命名 Python 基底；不构成默认 Python 基镜像、原生 CPU/时延或生产验收。沿用上一轮默认镜像构建 Partial，未重试网络。默认 overview 的 64 MiB 门槛、长期/更广并发、原生 Linux 与生产 OOM 仍 OPEN；本轮统计冷请求不套用 overview 门槛。

剩余峰值仍涉及目标/owned album 时长投影与多个全范围副本的共存。下一项应基于本轮栈证据收窄这些中间表并检查生命周期；不恢复旧混合 OOM 补丁，不因本次局部下降宣布整体收口。
