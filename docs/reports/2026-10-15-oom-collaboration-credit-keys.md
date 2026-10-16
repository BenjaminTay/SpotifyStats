# 合作纪录署名键收集的最小投影候选

核验日期：2026-10-15。SS-2026-10-08-001，关联 SS-2026-10-09-001。

## 处置与改动

**保留本地最小候选，结构改善已验证，整体资源仍 Partial，整合/发布 HOLD。** 收集署名键不再复制六张完整源表；同源配对观察到启动采样峰 1081.211→1046.914 MiB，低 34.297 MiB。但采样间隔与仿真 CPU 存在差异，不能把这部分全部归因为改动收益。读取增长约 65 MiB，仍未改善。

仅在 `codex/album-rank-cost` 增改两个文件：`backend/domains/playback/records_collaboration.py` 和新测试 `backend/tests/unit/test_collaboration_credit_key_projection.py`。此前九文件逐字节保留，当前共十一文件未提交。main 仅更新协调文档，未整合业务、暂存、提交、推送、部署或请求生产。

实现抽出 `_credit_track_ids`，共用 representative_track_id 优先、缺失不猜测、仅 legacy raw 库允许 track_id 回退及 pd.to_numeric(errors=coerce) 的原规则。requested-ID 收集直接读取键 Series 并去重，不再调用返回完整副本的 `_credit_key`；后续合作版本筛选、有效署名、完整事实表和聚合仍沿用原逻辑。没有裁剪 Records/Yearly 返回列，也没有缓存/分配器/回收配置变更。

## 正确性

169 个唯一相关测试通过，含 19 个新增测试；38 项署名键/合作纪录专项已包含在其中。新增测试覆盖现代与 legacy 边界、代表 ID 优先、空代表 ID 不回退、非法字符串/nullable ID/小数/空输入、重复索引、source 与 attrs 不变，以及仅出现在时长侧的曲目仍进入有效署名查询。

源表复制检查在 provider 查询时验证：仅建立逻辑身份所需的原事件复制存在，键收集不复制事件/歌曲/专辑及三张时长源表；恢复旧实现后按预期失败。冻结旧实现另完成 22 次完整 CollaborationFacts 比较：总事件数与七张完整事实表相同，共 154 张表比较；三个榜共 66 次聚合结果相同，覆盖手工 add/remove、Spotify 自动署名、canonical 艺人别名、L3 实际合作版本、重复项目/逻辑事件、时长切片和预载无连接路径。

Ruff、format、项目 mypy hook 与 diff check 通过。新增测试首轮 import 排序提示已修正；对账运行器初版摘要字段把八个 dataclass 字段误称八张表，已更正为七张表加总事件数，原日志末尾注明，比较循环本身未变。未运行新 full8、CI 或浏览器/生产验收。

## 两个隔离窗口

基线为上一轮已验证的九文件镜像 `sha256:7cf508099a18510d7c9762950967c00ff86836e96aea942b64c1adadcab36900`，候选为 `sha256:06a9d9de5a67fb0cf8c57f1a5b8e56be56d7368da9bd8cca0db654c8700d0445`。均从同一关闭历史七库来源（94,760 原始 plays）复制，全新运行并正常完成启动维护后，执行完全相同两条链三轮、每侧 9 次 GET：Midnights L3 fixed light/rank 六次与 Taylor Swift L2 dynamic rank 三次。

| MiB | 基线 | 候选 | 候选减基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1081.211 | 1046.914 | -34.297 |
| startup ready | 532.801 | 547.887 | +15.086 |
| 读取采样峰 | 654.035 | 664.477 | +10.441 |
| 第9次读取后 idle3s | 598.188 | 613.105 | +14.918 |
| 最终 idle | 598.188 | 613.105 | +14.918 |
| ready 至末尾增长 | 65.387 | 65.219 | -0.168 |
| 最终帧预算 | 181.076 | 181.076 | +0.000 |

末尾高 14.918 MiB，ready 已高 15.086 MiB；本窗读取增长 65.387→65.219 MiB，仅差 -0.168 MiB，不称改善。双方第9次读取后及末尾观测前后 RSS 都没有额外跳升，原值完整保留在 residence-checkpoints.json。

基线/候选 ready pymalloc arena 数 1481/1541，末尾仍为同一数量，候选多 60 个 arena（15 MiB）；ready 空闲 pool 256.918/270.773 MiB，末尾 160.035/174.207 MiB。这解释了末尾差异为何在读取前已存在，但不证明下一批读取不会继续增长。分配器统计与缓存估算不与 RSS 相加。

启动维护等待 140.427→165.210 秒，ready 进程 CPU 139.60→166.04 秒。候选 CPU 更高；未经过本次键收集路径的首个 Billboard 维护阶段也由 18.50→24.84 CPU 秒，不能把全部差异归因到本次代码，但也没有获得加速证据。进程 CPU 差值不是单 worker 线程 CPU，细分保存在 maintenance-timing-attribution.json。

基线最高采样同点浅栈在更早的 `_build_records_track_frame` 歌曲时长 merge；候选最高浅栈见证 1017.828 MiB 在艺人载入，未取得其实际最高样本1046.914 MiB的同点栈。基线/候选最大采样间隔 0.737/1.745 秒，存在漏过短峰的可能。因而结构性去复制证据与整个进程峰值观察分列，不能将 34.297 MiB 当作已证明的因果收益，也不能直接与上轮相减拼接累计收益。本轮只有两窗，不追加挑选有利结果。

## 守恒与封装

双方9份完整响应逐字节相同；三范围 stats/Records 六份业务事实相同，跨构建仅排除 meta.generated_at，strict 读取守恒不放宽时钟。37 原始表、保护事实、队列、发布及六 sidecar 前后不变；均 8103 done / 38 historical failed，failed 明细相同，无 pending/running、新失败或 OOM，实际 exit0。原七库文件 SHA 未变。

两镜像各 518 个 Python 源文件与冻结上下文相同，Python/glibc/依赖一致，未覆盖源码、未带 runtime proxy。保持 warmup=0 和既有 11 次维护回收，cache roots/LRU 与帧预算合同相同，无额外 GC/trim/cache clear。构建沿用封存缓存 runtime，并非默认基镜像构建已获得通过。

这是 ARM Linux 引擎的 amd64 仿真、每变体单窗；默认镜像、原生 amd64 资源、overview 64MiB、长期/更广并发和生产 OOM 均 OPEN。

## 下一步与恢复

优先围绕本窗基线同点最高栈的歌曲时长 canonical merge 继续缩小临时工作集；先验证能否仅计算聚合键再回填，保持重复键、索引、代表署名和所有输出列一致。读取增长另沿现有缓存 owner、生命周期与空闲 pool 证据继续归因，不能用降低预算或强制清理替代修复。当前十一文件仅作本地候选，资源准入前不整合发布。

原始输出 `output/oom-collaboration-keys-20261015/`，独立恢复入口 `~/.codex/archives/spotifystats-delivery/oom-collaboration-keys-20261015/`。保存原九文件、目标原实现、十一文件候选、局部补丁、fixture/旧函数比较、两套 runtime、完整 body/事实/strict、allocator 与时序。归档验证 CRC、源码/文档、双方响应与六事实后，仅删除本轮两个已退出容器，镜像、输出和正式源保留；收据记录最终状态。
