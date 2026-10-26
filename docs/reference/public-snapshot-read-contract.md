# Home / Billboard 公开快照读取合同

适用读者：维护者与Agent。本文是共用技术参考；日常操作见[使用指南](../user-guide.md)，实施与验收证据见[报告索引](../reports/README.md)。

> 最近修订：2026-09-21
> 状态：CURRENT；实现及局部验证见 [阶段 1 交付报告](../reports/2026-09-19-public-snapshot-boundary.md)

## 公开专辑项目详情

`public-readonly` 增加的 GET 仅为当前专辑页面的稳定身份入口：

- `/api/billboard/album-project/{project_id}`：summary / project / overview / tracks 等既有专辑只读 view；
- `/api/music/album-projects/{project_id}/stats`、`rankings`、`plays`、`play-dates`。

`project_id` 在访问策略中限制为整数。新增路径不开放 POST、PATCH、DELETE 或任何治理/维护入口；原有 public/private capability flags 不变。名字入口解析到项目后，Desktop 和 Phone 消费相同统计事实。

## Billboard 发布读取

持久快照继续使用既有 family、规范化参数 request-key、来源 revision、builder-version 与 SQLite atomic row publish；不改变统计计算。

| 情形 | public-readonly 行为 |
|---|---|
| exact 存在 | 200，原事实及 `snapshot.status=ready`、`freshness=current` |
| exact 缺失，但相同 request-key / builder 的 LKG 存在 | 200，旧事实及 `status=warming`、`freshness=last_known_good`；source_revision 保留旧来源，target_revision 为当前目标 |
| exact/LKG 都缺失、参数不兼容、持久内容不可读 | 503 `detail.error=snapshot_unavailable`，`status=unavailable`，不返回空榜或虚假 0 |
| key 构造失败 | 同样 503，target_revision=null；不得借用无法证明相容的 LKG |

公开检查在 build lock、force-rebuild 与 builder 之前。未命中发布的公开请求不构建 DataFrame；公开快照读取不发布 sidecar，不排重建任务；内部误传 force-rebuild 也不绕过此限制。这里的“warming”表示有旧发布而目标未发布，不证明当前有后台任务执行。

详情、project 解释和旧 release-cycle GET 可能绕过 staged builder，因此在对应 API dependency 中先验证相同过滤的 full_data 发布，再进入现有只读 view；缺失时也不得先计算。详情响应通过 `X-Snapshot-Freshness` / `X-Snapshot-Target-Revision` 暴露该前置发布状态。存在发布时的原有详情投影计算并未在此批次优化。既有只读 POST 比较接口不由这个 GET 前置检查改变。

private-admin 受控维护保留原有行为。默认维护 readiness 检查 weekly、all_time、full_data、records、power_scores、summaries、latest year_end 及 available_years 中各年的 exact。维护显式确保三个独立 staged family 已发布，避免 all_time exact 短路后遗漏子 family。仍按行原子发布，失败不覆盖此前已发布的旧行；不是整套 family 同事务发布。

当前 Records 页面读取 `/billboard/records?projection=page`；周榜、总榜、榜首分别使用对应 page/entity/number-ones projection。完整 `/billboard/data` 等响应保留兼容验证，不作为当前首屏消费者。

## Home 文件发布读取

public Home 跳过 private 的计算 LRU，只读取当前 exact JSON 或同语义 LKG JSON。它不会创建目录、补写 LKG、替换 JSON、启动 thread、写数据库或排 JobQueue。低层文件 writer 和 thread starter 也检查公开上下文。缺失/不兼容/key 异常使用相同 503 合同；有 LKG 返回原事实、cache_state=warming 和 snapshot 的 freshness/source/target。

Home target_revision 为现有 exact 文件名摘要，覆盖过滤 context、database revision、facts version、Billboard `full_data` 持久发布的 cache-key / 内容摘要和 yearly cache state。不使用进程内 preview 计数；相同来源与配置在重启后仍命中 exact。新发布同时保存这个来源；历史 LKG 没有记录来源时 source_revision=null，不冒充当前来源。语义 LKG key、os.replace 发布与 private warmup/维护路径保留。

## 艺人排名与年度维护状态

默认 lifetime 艺人详情的 `include_rank_context=true` 复用私有维护发布的全局排名，使用既有 Analysis sidecar 的 `artist_rank_context` family。发布包含三个既有时间范围的竞赛排名、Top 250 统计和最近 50 个逻辑事件的艺人计数。实体自己的事实按艺人范围装载；基础 stats 仍由消费者显式传 `include_rank_context=false`。

排名发布缺失或来源 revision 漂移时返回 503，不把旧排名拼到新实体事实中，不在 GET 上重建。应用启动和已提交的相关变更由私有 JobQueue 维护默认发布；过滤参数、数据库身份和 builder version 参与 key。

默认四配置（L2/L3 × 动态/固定阈值）的lifetime歌曲详情完整排名复用既有 `entity_rank_context_v2` 精确发布。三个范围和current_period排名从发布读取，歌曲自身事件、时长、趋势及最近播放按目标范围计算。数据库身份、完整过滤、来源revision及builder校验沿用原对决发布合同；缺失/漂移返回503，不从GET维护。非默认过滤或非lifetime请求保留既有计算路径。

默认四配置的主库 lifetime 专辑完整统计在项目身份和曲目归属齐备时复用同一发布。实体事件、时长、趋势、曲目拆分与最近播放按目标归属读取，并使用发布中的全局时间边界。历史详情的专辑 ranks 和 Top250 字段沿用 L2 口径，因此 L3 请求同时校验请求配置与同来源 L2 发布；读取结束再校验请求发布，缺失或来源漂移返回503，GET 不准备、写入或排队。

Top250 先选取三个发布范围各前250行涉及的曲目 ID（去重前至多750个），展开 L2 成员后只装载这些候选的播放，再按原排序和展示行边界计数。一个 ID 的多种艺人展示不能合并为单行；合并所需的前置上下文事件不计入候选。旧曲目未建立 L1 关联时保留原始 ID；有项目身份但尚无曲目归属、非默认过滤、非 lifetime 或非主库仍沿用兼容路径，不能把空归属当作没有播放。

专辑摘要、榜单概览及项目视图中的 `unique_canonical_songs` 在既有发布读取事务内按校验后的项目 membership 和有效来源计数。计数专用路径将目标 L1 完整来源事实及对应 source-check 以有界 JSON 批量读取，仍逐目标验证行数、plays、total_ms 和 digest，包括无事实的成员；任何缺失、损坏或不相容发布返回503。校验之后保留原 representative track/artist inner join 过滤，再按 membership 的 canonical song key 去重，不以原始曲目、来源专辑数量或 play_count>0 替代。该路径不组装来源 DataFrame或补展示元数据；完整项目解释仍使用原来源读取。没有新缓存、迁移、发布版本或公开GET维护，外层身份、source/filter、ledger/context和source fence合同不变。

`plays / plays_for_artists / billboard_raw / billboard_raw_for_artists`共享384MiB保守缓存字节预算和各自条目上限；包含附加时长frame及区间，超大单条不驻留，按共享LRU淘汰。失效同时推进generation，在途旧构建不能重新存回缓存。此预算不是进程RSS上限，年度和其他缓存/瞬时材料化仍单独验收。

预算loader保留`cache_clear/cache_info/cache_budget_info`接口，外层`singleflight`显式透传，注册缓存的`get_stats()`返回预算字段。集成测试需由私有fixture先发布精确歌曲rank，再验证GET；缺失发布仍503，不能为测试恢复GET冷建。

年度 generation-status 优先只读查询已发布 artifact 的 preparation-key / cache-key 元数据，不读取完整 artifact。私有年度构建同步保存 preparation-key，来源、语言或配置变化后不能借用旧 key；旧 sidecar 的元数据只能由私有维护补齐。

## 前端与验证口径

前端将 snapshot_unavailable 解析为独立错误，但普通页面统一使用“数据正在准备 / 暂时不可用”等业务语言，不显示后端返回的“尚未发布、构建失败、重建任务”等维护详情。只要 LKG 或保留内容仍可正常使用，Home、播放分析、Billboard 与音乐搜索都不渲染可见维护横幅；稳定容器仅用 `aria-busy` 或屏幕阅读器状态表达后台刷新，旧事实保留且页面布局不改变。完全没有可用事实、真实请求错误和可操作的设置治理状态继续明确显示。

播放分析的 GET 继续严格只读。private-admin 可通过独立 POST 显式排队缺失范围并轮询 GET；public-readonly 不开放该 POST，只能读取已维护的 lifetime / last_4_weeks / last_6_months 等结果。任何 surface 的 GET 都不得同步构建或写入。

零写入验证包括 builder/writer/排队 sentinel、主数据库及 Billboard DB/WAL 字节、Home JSON 内容/mtime、相关表和队列对比。SQLite WAL 的 `-shm` read-mark 可能由只读连接更新，这是锁协调，**不宣称操作系统层完全没有共享内存写入**。保留正常只读 WAL 可见性；不能用 immutable 连接忽略已提交 WAL 来伪造零变化。

所有验证在 seed 或 Online Backup 副本进行；生产状态需独立验证。本合同不扩展为全应用所有 GET 的无计算保证，也不改变 L2/L3、播放次数与双轨时长规则。

## Community

Community 三个 GET 的只读发布、LKG、unavailable、分页及私有维护规则见 [Community 持久读模型](community-snapshots.md)。公开请求不构建、不发布、不排队。


来源revision采集使用短只读SQLite事务，把tracking合同与持久epoch/revision向量固定为一个已提交快照，结束后rollback。封面缓存或任务簿记提交不能仅凭`PRAGMA data_version`变化使有效来源读取503；无效tracking、未提交调用事务和真实发布前后漂移仍失败，不引入GET修复或事实扫描。

## 详情年榜附属投影

年榜摘要与历史由维护期从精确周账本发布，复用公共Year-End评分、覆盖与排序函数。核心搜索快照和附属投影分别记录状态；附属投影失败不把可用搜索摘要改成失败，也不能把旧投影拼到新来源。

`summary`不读取年榜历史，`year_end_history`保持空数组；`overview/full`返回按年份降序的完整行，展示组件在副本中调整顺序。`year_end_summary`只在有入榜事实时返回对象，无入榜事实时为null。`ready + summary=null + history=[]`表示已完成且未入过年榜，不显示假名次。

`warming`表示精确投影已排队或正在维护；失败、版本不兼容、无精确快照使用unavailable，不在详情GET触发Year-End builder。启动维护必须同时检查核心快照和当前投影；旧库有核心ready但缺投影时幂等补齐，完成后重启不重复排队；终止失败不能永久维持warming。

同fingerprint重发和旧快照pruning必须清理过期投影，不能依赖调用方恰好启用了SQLite外键。验收逐字段核对公共Year-End名次、积分、峰值、在榜/冠军/前五/前十周与播放数；时延按当前受影响体验合同判断，不重新启动历史组合资源门槛。UI规则见[详情年榜展示](../../frontend/UI_STYLE_GUIDE.md#详情年榜展示)。
