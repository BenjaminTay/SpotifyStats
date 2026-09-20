# Home / Billboard 公开快照读取合同

> 最近修订：2026-09-20
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

## 前端与验证口径

前端将 snapshot_unavailable 解析为独立错误，展示“当前筛选的数据尚未发布”，不自动重试该错误；用户可以手动刷新。其他错误原有重试次数不变。有观察者的 Home/Billboard Query 命中 LKG 时展示上次发布提示并保留事实，不转为空态。

零写入验证包括 builder/writer/排队 sentinel、主数据库及 Billboard DB/WAL 字节、Home JSON 内容/mtime、相关表和队列对比。SQLite WAL 的 `-shm` read-mark 可能由只读连接更新，这是锁协调，**不宣称操作系统层完全没有共享内存写入**。保留正常只读 WAL 可见性；不能用 immutable 连接忽略已提交 WAL 来伪造零变化。

所有验证在 seed 或 Online Backup 副本进行；生产状态需独立验证。本合同不扩展为全应用所有 GET 的无计算保证，也不改变 L2/L3、播放次数与双轨时长规则。
