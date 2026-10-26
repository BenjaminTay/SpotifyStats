# 音乐查找方向与性能修复规划

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。同日方向重定、性能与体验规划、验收缺口修复规划集中保存。它们记录方案演进，不取代当前候选与统计分离、四套发布集合和GET只读合同。

当前规则与状态见[文档地图](../../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [音乐查找方向重新指引：轻量候选索引与统计快照解耦](#音乐查找方向重新指引轻量候选索引与统计快照解耦)
- [SpotifyStats 音乐查找性能与体验完整优化规划](#spotifystats-音乐查找性能与体验完整优化规划)
- [音乐查找验收缺口完整修复规划](#音乐查找验收缺口完整修复规划)

## 音乐查找方向重新指引：轻量候选索引与统计快照解耦

原记录：`2026-08-16-music-search-direction-realignment.md`。

> 创建日期：2026-08-16
> 状态：`SUPERSEDED`；阶段 A–E 的历史验收保留，当前实现与维护边界由 2026-08-28 零停机方案、对应交付报告和 reference 文档接管，本文已归档
> 适用范围：Masthead Quick Open、`/music/search`、候选索引、搜索统计、模糊匹配、简繁体匹配与生产发布
> 关联文档：`2026-08-16-music-search-performance-and-experience-optimization-plan.md`、`2026-08-16-music-search-remediation-plan.md`、`2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md`、`../../reports/2026-08-16-music-search-optimization-delivery.md`

> 2026-08-28 补充：候选/统计解耦的方向不变；“统计 snapshot 未 ready 时阻断候选”、candidate
> serving/building 状态混用、曲目署名 revision 竞态和无差别全局重建已完成修复。当前实现与验收以
> `2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md` 及对应交付报告为准。

### 0. 结论

现有搜索 V2 把昂贵的 lifetime 播放统计和 Billboard 计算移出用户输入请求，解决了搜索热路径
延迟和统计一致性问题，这个基本方向继续保留。但当前实现把“名称候选索引”和“六套统计快照”
绑定在同一个语义基线上，导致搜索索引 generation 或任意发布 SHA 变化时，也可能从头计算
L1/L2/L3 × 动态阈值开/关六个统计变体。

这不是实现模糊搜索、简繁体匹配或快速候选所必需的成本。后续方向调整为：

1. **候选搜索只解决找到谁**：名称、别名、简繁体、标点差异、前缀、子串和有限拼写容错。
2. **统计上下文只解决这个实体的数据是什么**：播放次数、`PK #`、在榜周数和走势排名。
3. 两层只通过稳定 `entity_key` 关联，分别版本化、失效、重建和验收。
4. 发布是否重建由数据 revision 与 builder version 决定，不由 Git commit SHA 或随机 generation ID
   决定。
5. 只有播放数据或统计语义真正变化时才重建六套统计；只改前端、部署脚本或查询匹配规则时，
   不得连带重算六套统计。

六变体快照和公开只读边界继续保留；新的生产实现只改变两层的版本、失效和发布复用边界，
不把统计计算重新放回查询请求。

#### 0.1 当前实施进度（更新于 2026-08-17）

- migration 35/36 已把候选 revision、确定性 `candidate_index_version`、统计 fingerprint 与 CJK
  n-gram 物理索引拆开；随机 generation ID 不再进入统计身份。
- 发布前维护默认自适应复用，持久 resume artifact 可在 source marker 一致时续建；每个统计变体按
  精确 fingerprint 独立复用，Online Backup、漂移拒绝、原子替换与联合回滚保持不变。
- OpenCC 0.1.7 提供确定性简繁双向查询扩展；单/双字 CJK 使用有界 n-gram，只有原始/简繁主路径
  零命中且查询长度至少 4 时才进入最多 50 条 trigram 候选池和有界编辑距离。
- 真实主库 Online Backup 副本首次升级只重建候选索引，耗时 4.62 秒、峰值 RSS 318.984MiB、
  45,269 个文档与 188,673 条 n-gram；六个统计变体全部复用且各为 0ms。第二次运行 0.41 秒，
  候选与六变体均复用。40 个简繁/CJK/拼写/高命中混合样本 P95 为 26.467ms。
- 部署回归由两个独立成本叠加：旧耦合路径每次 SHA 可能冷建六套统计，本地约 16 分 23 秒；GitHub
  托管 runner 直推 TCR 又会在少数大层长期停滞。前者解释搜索改造后新增的固定计算成本，后者解释
  总时长进一步放大到 30–40 分钟甚至超时；单纯延长任何一侧 timeout 都不是修复。
- 镜像链路已改为 GitHub 构建 `linux/amd64`、上传一天保留的私有 CAS Artifact、仅将服务器缺失 blob
  用可续传 rsync 传到现有生产机、校验后 `docker load`，再由服务器本地网络推送 TCR 并按 digest
  拉回核验。全部镜像传输完成后才允许 Online Backup、搜索预检、停服和数据库原子替换。
- 一次性生产统计引导 workflow `31972521511` 成功建立 migration 36 与六个 exact-ready 变体，耗时
  约 24 分钟，其中六变体 1,391,706ms；这是旧生产库首次升级成本，不属于正常发布预算。
- 首个正常发布 workflow `31977767545` 以 SHA `898c3d60` 成功切换，端到端约 10 分钟；搜索预检
  `reused=true`，六套统计精确复用，候选维护与统计校验仅 2 秒。三模式、Online Backup、漂移拒绝、
  runtime exact gate、public 只读和联合回滚边界均保留。
- 正常发布容量门禁与一次性统计冷建分开：严格统计复用路径使用 640MiB 候选预算，统计不匹配会在
  任何重建前失败；独立引导仍保持 1280MiB 冷建预算。两者分别基于 318.984/876.758MiB 实测峰值，
  不通过降低冷建安全余量换取发布速度。
- 最终 production workflow `31979057642` 以 SHA `cf2270f1` 在 9 分 57 秒完成，deploy job 为
  2 分 46 秒；58 个镜像 blob 命中 52 个，只续传 6 个/29,801 B。生产只读语义 smoke 验证精确、
  模糊、简繁和短 CJK 全部命中，耗时 574.827ms；CAS 同时保留当前版与上一版 archive/image IDs。

### 1. 为什么曾经需要提前计算

用户看到的搜索结果不只有名称，还包含播放次数和个人 Billboard 摘要。如果在每次输入后临时加载
全部播放记录、重建逻辑播放时间线并计算 Billboard，真实数据库上可能耗时数秒至十几秒。因此现有
V2 在后台提前生成统计快照，让用户输入时只执行轻量索引查询和精确快照读取。

提前计算达成了以下效果：

- 候选请求不再同步运行 lifetime Pandas/Billboard 重计算；
- 候选先出现，统计随后渐进补齐；
- 搜索 badge 与相同过滤口径的详情页一致；
- public GET 纯读取，不写库、不排队、不触发冷构建；
- 新快照未验证通过前不会污染当前 ready 数据。

这些收益应继续保留。需要改变的是重建边界，不是重新把昂贵计算塞回搜索请求。

### 2. 当前方向的问题

#### 2.1 两类不同数据被过度耦合

候选索引主要依赖：

- 实体名称、类型、别名和详情深链；
- 名称标准化与 tokenizer 版本；
- album project、canonical artist 和稳定 `entity_key`。

统计快照主要依赖：

- 播放数据 revision；
- 统计设置、merge level、动态阈值和最大间隔；
- Billboard 周边界、Top N、精选集设置和 chart builder；
- 有效艺人署名、身份归并及统计 builder。

两者变化频率和成本不同，不应共享一个包含随机 index generation ID 的重建开关。

#### 2.2 每个新 SHA 都可能付出完整冷构建成本

旧生产流程对新 SHA 在 Online Backup 副本执行完整索引与六变体 one-shot。即使只修改前端、部署
脚本或查询匹配逻辑，也可能生成新的索引 generation 和 semantic base，从而重新计算全部统计。

当前真实规模的本地 `linux/amd64` 实测：

- 完整六变体约 16 分 23 秒；
- 峰值 RSS 约 876.758MiB；
- SQLite 净增加约 31.43MiB；
- 低配生产服务器第一次 60 分钟窗口内仍未完成。

这证明当前发布成本主要来自六套统计计算，不是名称检索本身。

#### 2.3 超时后缺少可复用进度

旧路径的六个变体虽逐个发布到工作副本，但工作副本属于单次临时发布目录。workflow 超时或被取消后，
下次发布仍可能从头开始，已经完成的变体不能安全复用。

#### 2.4 镜像跨境上传是另一条独立慢路径

搜索重建之外，旧 workflow 还要求 GitHub 托管 runner 直接向 TCR 上传全部镜像层。搜索加入 OpenCC
和新后端代码后首次出现新层，暴露了这条链路对少数大层的长期停滞；即使拆层和串行上传，固定剩余
层仍会超时。因此部署变慢与搜索改动有时间相关性，但不是“搜索查询本身拖慢 Docker push”。最终
方案将 GitHub 到生产机的传输与生产机到 TCR 的发布分开，并以内容寻址 blob 复用消除重复整包传输。

### 3. 新的目标架构

```text
用户输入
   │
   ▼
查询标准化与变体扩展
   │  原文 / 简体 / 繁体 / 别名 / 有限模糊
   ▼
轻量候选索引
   │  返回稳定 entity_key、名称、类型、封面、深链、match type
   ▼
候选立即可点击
   │
   └──────────────► 精确统计上下文
                      按 statistics fingerprint + entity_key
                      返回播放次数与 Billboard 摘要
```

#### 3.1 候选层

候选层只负责：

- 搜索歌曲、album project 和 canonical artist；
- 名称、别名、简繁体、常见标点与空白差异；
- 前缀、子串和有界拼写容错；
- 稳定排序、准确总数、分页和详情深链；
- 返回可供排序、高亮、测试和诊断使用的 `match_field` / `match_type`；消费界面默认不展示这些工程标签。

候选层不得：

- 加载完整 lifetime 播放帧；
- 计算完整 Billboard；
- 因用户 GET 写库或启动维护任务；
- 把易变播放量固化为必须重建整个名称索引的主体身份。

#### 3.2 统计上下文层

统计层只负责：

- 当前精确过滤口径下的播放次数和总时长；
- 个人 Billboard 的 `PK #`、在榜周数和走势排名；
- L1/L2/L3 × 动态阈值开/关六个产品支持变体；
- ready/warming/stale/failed 状态和 builder version；
- 按稳定 `entity_key` 与候选合并。

统计未就绪时，候选仍可显示和打开详情；界面不得把“尚未加载”伪装成 0。

#### 3.3 两套独立版本与指纹

建议建立两个明确契约：

`candidate_index_version` 只包含：

- 名称/别名来源 revision；
- album project 与 canonical identity revision；
- normalization/tokenizer/search builder version；
- 索引内容的确定性 source digest。

`statistics_fingerprint` 只包含：

- playback、settings、Billboard aggregation、identity 和 credit revisions；
- 完整统计过滤参数；
- snapshot/chart builder version。

随机生成的 index generation ID 只用于索引原子切换和诊断，不进入统计语义指纹。候选索引与统计
快照都必须生成稳定 `entity_key`，并由该键连接。

### 4. 模糊搜索方向

模糊匹配必须分层排序，不能让低可信结果压过正确结果。推荐顺序：

1. 原文完全匹配；
2. 标准化后完全匹配；
3. 前缀匹配；
4. 子串匹配；
5. 别名匹配；
6. 简繁体转换匹配；
7. 有限拼写容错。

#### 4.1 标准化

继续使用统一且可版本化的最小标准化：

- Unicode NFKC；
- casefold；
- 弯引号、破折号、中日韩全角标点归一；
- trim 与连续空白折叠；
- 保留原文用于展示和高亮映射。

标准化必须前后端共享测试向量。高亮仍使用 React nodes，并在 `Intl.Segmenter` 缺失或不可构造时
安全降级。

候选实体名称、艺人/专辑副标题和最近查看列表必须跟随全局简繁体偏好；转换只发生在展示层，不能改写
稳定 `entity_key`、详情深链、索引内容或本地保存的原始名称。

#### 4.2 有限拼写容错

不对全部实体逐条计算编辑距离。推荐流程为：

1. 用 FTS5 trigram 召回一个有界候选池，例如前 30–50 条；
2. 只对候选池计算字符级相似度或有界 Levenshtein distance；
3. 查询长度不足时关闭强容错，避免单字母或单汉字产生大量误匹配；
4. 对完全匹配、前缀和别名设置不可被模糊分覆盖的排序上限；
5. 返回 `match_type=fuzzy`，用于测试、排序和内部诊断，不在普通搜索结果中直接展示。

拼音、同音字和语义联想不进入第一阶段。它们误匹配率更高，应在真实查询样本证明必要后作为独立
能力评估。

### 5. 简繁体中文匹配方向

优先采用确定性查询扩展，而不是复制所有实体或用模型猜测：

```text
用户输入：周杰伦
查询变体：周杰伦 / 周杰倫
```

实现要求：

- 使用固定版本的 OpenCC 词典或同等确定性转换器；
- 同时保留原始 query，原文匹配排序高于转换匹配；
- 简转繁、繁转简变体去重，并设定最大变体数；
- 转换只影响候选召回，不改变实体名称、身份或统计归属；
- 一对多词汇转换产生歧义时以低权重召回，不自动改写显示名称；
- 汉字、假名、韩文单字符可以搜索，Latin/数字单字符默认不发请求。

查询时扩展几乎不增加持久存储，也不要求重建六套统计。如果未来证明查询扩展召回不足，再评估为
索引增加简体/繁体辅助字段；其空间成本只随可搜索文本增长，必须单独 probe，不能用六快照成本代替。

FTS5 trigram 对一至两个字符的查询能力有限，短 CJK 查询应使用专用的单字/双字 n-gram 辅助表，
或在有界实体集合上执行经过性能门禁的 fallback；不得让短查询退回全量播放数据扫描。

### 6. 重建与发布决策矩阵

| 变化 | 候选索引 | 六套统计 | 说明 |
|---|---|---|---|
| 仅前端 UI、部署脚本或文档 | 复用并校验 | 复用并校验 | 不得冷重建 |
| 仅查询时简繁扩展/排序策略 | 通常复用 | 复用 | 没有持久索引格式变化时零重建 |
| normalization/tokenizer/索引 schema 变化 | 重建 | 复用 | entity key 契约不变时不影响统计 |
| 名称、别名、封面或详情深链变化 | 增量更新或重建 | 通常复用 | 身份归属未变时不重算统计 |
| 播放数据或统计设置变化 | 通常复用 | 失效并重建 | 候选名称不应跟随播放数据全量重建 |
| Billboard 统计语义变化 | 复用 | 重建 | 提升 chart/snapshot builder version |
| album project、艺人身份或有效署名变化 | 重建相关文档 | 重建受影响统计 | 两层 revision 都必须明确 bump |
| `entity_key` 规则变化 | 重建 | 重建 | 属于高风险联合迁移 |

生产部署流程调整为：

1. 对 Online Backup 读取当前两套 revision/builder 状态；
2. 内容兼容且 exact-ready 时只执行只读 revalidation；
3. 仅重建发生变化的层；
4. 六统计变体按稳定 semantic base 保留已完成进度，可在中断后续建；
5. 全部必要门禁通过后，再执行停服、第二份备份、漂移比较和原子切换；
6. 发布决策和报告记录“为什么复用/为什么重建”，不能只记录 commit SHA。

### 7. 性能、空间与体验预算

继续保留现有交互预算：

- 候选 warm P95 ≤80ms；
- context P95 ≤20ms；
- 单个响应 ≤8KiB；
- GET 不扫描完整 `plays`、不计算 Billboard、不写库。

新增发布预算：

- 仅 UI/部署代码变化时，搜索派生数据只校验、不重建；
- 候选索引单独重建必须有服务器实测时间、RSS 和磁盘增量报告；
- 六变体首次或统计语义变化时允许长构建，但不得成为每个 SHA 的固定发布成本；
- 中断后必须能识别已完成的 semantic base/variant，避免重复计算；
- 工作副本、Online Backup 和报告必须有明确保留与清理策略。

当前约 31.43MiB 的数据库净增量是完整索引与统计快照的联合实测，不应被解读为简繁体查询扩展的
必然成本。简繁体查询扩展本身几乎没有持久空间成本；新增索引字段、短 CJK n-gram 或模糊辅助表
必须分别测量。

### 8. 分阶段实施顺序

#### 阶段 A：先解耦重建语义

状态：已完成并通过生产复用验收。

- 从 `statistics_fingerprint` 移除随机 index generation ID；
- 引入独立、确定性的 `candidate_index_version`；
- 保持现有 `entity_key` 和 candidate/context API 响应兼容；
- 补充“只改前端/部署脚本不重建”“只改索引不重建统计”的契约测试。

退出条件：同一数据与 builder 下的新 SHA 只校验 ready 数据，不产生新六变体。

#### 阶段 B：发布复用与断点续建

状态：已完成。一次性引导成功续建六变体；正常发布精确复用并在 2 秒内完成搜索预检。

- 让工作副本或可恢复派生 artifact 按 semantic base 保存进度；
- 每个变体独立校验、发布和复用；
- workflow 取消后清理运行容器，但保留经过验证的可续建数据；
- 加入每变体耗时、峰值资源和复用原因报告。

退出条件：中断后只计算未完成或已失效的变体。

#### 阶段 C：简繁体匹配

状态：已完成并纳入生产只读语义门禁。

- 后端统一查询扩展；
- 原文、简体、繁体去重和排序；
- 单字/双字 CJK fallback；
- 前后端标准化、高亮和 IME 回归测试。

退出条件：代表性简繁查询双向可找、无名称改写、无六快照重建。

#### 阶段 D：有限模糊搜索

状态：已完成并纳入生产只读语义门禁。

- trigram 有界召回；
- 候选池内编辑距离重排；
- 长度阈值、误匹配上限和 match type；
- 用真实但非敏感查询集合评估召回率、准确率和 P95。

退出条件：拼写轻微错误可找回目标，完全/前缀结果不被模糊结果压制，性能仍在预算内。

#### 阶段 E：生产门禁与文档收口

状态：**Pass**。私有 Artifact、内容寻址增量传输、服务器侧 TCR 发布和正常 production workflow
均已通过；生产运行 migration 36、当前精确六变体和 builder v2，搜索 context orphan 为 0。

- schema/索引/统计三类变更分别演练；
- Online Backup、漂移拒绝、原子切换和联合回滚继续通过；
- 更新现有优化计划、remediation、交付报告、CHANGELOG 与项目提示词中的重建边界；
- 只有真实服务器证据通过后才把本文件状态改为“已实施”。

生产证据：

1. 非生产 transport smoke 已验证 archive → Artifact → CAS missing blobs → `docker load` → 服务器侧
   TCR push/pull → manifest/revision；smoke 不调用 deploy、backup 或搜索预检。
2. 一次性引导只用于 schema 33 旧库建立 migration 36 和首套六变体，之后正常发布不得重复承担。
3. workflow `31977767545` 和最终 `31979057642` 证明镜像和数据库联合发布成功、搜索统计 0 重建、
   旧 Backend 在切换前持续在线；后者另验证四类真实搜索语义和 CAS `current/previous`。失败演练均
   在门禁处保持或恢复旧服务，没有以不完整副本覆盖生产库。

### 9. 必须保留的现有成果

本次方向调整不得回退以下能力：

- Masthead Quick Open 与 `/music/search` 的现有信息架构；
- candidates/context 两阶段响应；
- 稳定 `entity_key`、准确总数、分页和详情深链；
- IME composition、220ms 防抖、AbortSignal、`retry: 0` 与 keep-previous-data；
- Quick Open 默认不选首条、键盘导航、焦点恢复和 Phone presentation；
- 当前过滤口径下统计与详情/Billboard 的一致性；
- public 只读白名单、`eligibility=current` 和 GET 零副作用；
- snapshot ready/builder/fingerprint fail-closed；
- migration、Online Backup、数据漂移拒绝和联合回滚门禁。

### 10. 非目标

- 当前数据规模不引入 Elasticsearch、Meilisearch、Redis 或外部搜索 SaaS；
- 不使用 LLM 推断实体、简繁体、拼音或别名；
- 不为了缩短部署而恢复搜索请求内的 lifetime/Billboard 同步计算；
- 不用不受控的 `%LIKE%` 扫描替代索引并宣称完成模糊搜索；
- 不因统计 warming 隐藏所有候选或把未知统计展示为 0；
- 不以降低完整性、orphan、公开只读或回滚门禁换取发布速度。

### 11. 最终判断标准

新方向是否成功，不以“增加了模糊搜索开关”判断，而以以下结果判断：

1. 用户能快速找到名称、别名、简繁体和轻微拼写错误对应的本地实体；
2. 候选可立即点击，统计按精确口径渐进补齐；
3. 名称匹配规则变化不会无故重算六套播放/Billboard 统计；
4. 只有数据或统计语义变化才承担六变体成本；
5. 普通前端和部署脚本发布恢复为轻量校验路径；
6. 所有复用、重建和失败决定都有版本、revision、报告和回滚证据。

## SpotifyStats 音乐查找性能与体验完整优化规划

原记录：`2026-08-16-music-search-performance-and-experience-optimization-plan.md`。

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

> 创建日期：2026-08-16
> 状态：已完成（首轮 M0–M5 与 remediation 全部门禁通过）
> 适用范围：Masthead Quick Open、`/music/search`、`/api/music/search`、搜索派生数据与公开只读运行面
> 关联文档：`../../reference/playback-stats-rules.md`、`../../reference/music-metadata-management.md`、`2026-08-05-mobile-web-design-and-implementation-plan.md`、`2026-08-13-dual-deployment-profile-plan.md`
> 历史设计：`docs/archive/05-yearly-report-genre/music-search/`
> 取代边界：保留旧方案的入口归属、详情深链、统计一致性和“不在播放排行重复放搜索框”等产品决策；取代“每次搜索同步计算过滤后播放统计与完整 Billboard payload”的性能实现
> 交付证据：`../../reports/2026-08-16-music-search-optimization-delivery.md`
> 修复计划：`2026-08-16-music-search-remediation-plan.md`
> 后续方向：`2026-08-16-music-search-direction-realignment.md`（候选/统计身份解耦、发布续建、简繁与有限模糊匹配）

2026-08-16 后续实现已将随机索引 generation 从统计 fingerprint 移除，并以确定性
`candidate_index_version` 单独治理候选索引。真实副本首次只重建候选索引 4.62 秒，六个统计变体
全部 0ms 复用；重复维护 0.41 秒。本文 M0–M5 的两阶段结构与统计一致性结论继续有效，但“普通新
SHA 也必须冷建六变体”的发布假设已由后续方向文档取代。

首轮交付后发现的 L1/L3、动态阈值关闭、非默认 Billboard 参数和高命中查询缺口已经按 remediation
plan 全部修复。真实维护链路现有六个精确 ready 变体；七类查询各 60 次的 HTTP 候选 P50/P95 为
15.780/40.741ms，HTTP context 为 6.034/6.921ms。Chromium、Firefox、WebKit、360–1280px、
200% reflow、公开只读、生产 FTS5/trigram、full/showcase/dual 和迁移恢复门禁均通过。

### 0. 执行摘要

当前音乐查找的信息架构是正确的：Desktop 通过 Masthead 打开全局 Quick Open，Phone
进入独立 `/music/search` 推入页，歌曲、专辑、艺人结果打开现有详情路由。当前主要问题不是
入口不足，而是一个交互式搜索请求同时承担了四类工作：

1. 在本地实体表中查找候选；
2. 加载并切分完整 lifetime 逻辑播放时间线；
3. 按歌曲、album project 和有效艺人署名重新过滤候选统计；
4. 计算完整 Billboard payload，再从中提取少量搜索 badge。

在 2026-08-16 的真实主数据库上，91,286 条播放记录、12,362 首歌曲、5,316 张专辑、
1,189 位艺人的只读基准为：

| 场景 | 实测耗时 |
|---|---:|
| 只搜索候选，不计算过滤后次数和榜单 | 约 213ms |
| 过滤后搜索统计帧 | 冷 6.55s / 热 4.00s |
| 搜索 Billboard lookup | 冷 12.03s / 热 0.63s |
| 完整搜索，不含榜单 | 约 8.31s |
| 完整搜索，包含榜单 | 约 19.81s |
| 同一后端进程内搜索相邻关键词 | 约 5.80s |

这说明仅增加名称索引不能解决主要延迟。最终架构必须将搜索拆为两个独立层次：

- **候选层**：只负责名称、别名、类型、封面和详情深链，持久化索引，快速返回；
- **上下文层**：从精确、版本化、可失效的派生快照读取播放次数和个人 Billboard 摘要，
  不在用户输入请求中重算 lifetime 时间线或完整 Billboard。

前端先显示候选，再渐进补齐统计。用户仍能看到播放次数、`PK #`、在榜周数和走势排名，
但不再被这些次级信息阻塞。Quick Open 和完整页共享查询、实体键、统计语义与缓存，
Desktop、Compact、Phone 保持独立 presentation。

### 1. 目标、非目标与完成定义

#### 1.1 目标

1. Quick Open 在本地或个人云的正常网络条件下快速出现首批可点击结果。
2. 搜索热路径不再调用 `load_period_plays()`、完整时间切片或
   `compute_billboard_data()`。
3. 搜索显示的播放次数与详情统计 API 一致，榜单摘要与三类 Billboard 详情一致。
4. 歌曲、专辑、艺人支持名称、相关艺人/专辑、有效别名和常见标点差异匹配。
5. “查看全部结果”进入真正可分页、可分享、可恢复的完整查找页。
6. 快速输入不会造成过时请求堆积、结果闪烁或中文输入法组合阶段误搜索。
7. 搜索在 `private-admin` 与 `public-readonly` 中遵循相同数据事实和不同副作用边界。
8. 导入、统计设置、版本归并、艺人身份与曲目署名变化后，搜索派生数据可诊断、可重建、
   可回滚。

#### 1.2 非目标

- 不新增顶级导航项，不在“播放排行”页增加重复搜索框。
- 不建立全站设置、社区帖子、AI 消息或任意文本搜索。
- 不搜索 Spotify 云端未出现在本地数据中的音乐。
- 不调用 LLM、Spotify Web API、Wikipedia、歌词服务或任意外部 URL。
- 不改歌曲、专辑、艺人的既有详情路由。
- 不改播放统计、逻辑时间线、album project、有效署名或 Billboard 口径。
- 不通过拼音库、外部分词服务或模型猜测实体名称；拼写纠错留作独立后续能力。
- 不把导入的 Spotify `search_queries` 当作应用内最近搜索直接公开展示。

#### 1.3 完成定义

只有同时满足以下条件才可将本计划标记为完成：

- 候选接口与上下文接口均达到本计划性能预算；
- 候选热路径没有全量 `plays` 聚合和完整 Billboard 计算；
- 三类实体在代表性过滤指纹下通过搜索与详情的一致性契约测试；
- Quick Open、完整页、Phone 页均完成正常、加载、空、错误、过期快照状态；
- 全部结果页具备真实总数和分页，不再把每类 5 条称作“全部”；
- 公开请求不会写库、排队、触发外部补全或构建搜索快照；
- 导入和所有相关治理 mutation 均进入明确的派生数据失效矩阵；
- 360/390/430/768/1280 路由矩阵、键盘、IME、焦点恢复和跨浏览器门禁通过；
- 发布前后性能证据、数据一致性、公共只读和回滚演练写入交付报告。

### 2. 事实基线与根因

#### 2.1 当前产品与数据链路

当前入口：

- Desktop/Compact：Masthead 右侧搜索图标打开 `MusicSearchDialog`；
- Phone：Mobile Top Bar 搜索图标进入 `/music/search`；
- 完整页：URL 使用 `q` 与 `kind`，支持歌曲、专辑、艺人切换；
- 详情深链：
  - 歌曲：`/music/tracks/:trackId`
  - 专辑：`/music/albums/:albumName?artist=...`
  - 艺人：`/music/artists/:artistName`
- Quick Open 与完整页当前均请求 `include_chart=true`；
- Quick Open 默认不高亮第一条结果，只有 hover、focus 或方向键后才高亮。

当前后端调用链：

```text
输入关键词
  -> /api/music/search
  -> search_music_entities()
  -> load_period_plays() x track/album 与 artist fan-out
  -> resolve_entities() x track / album / artist
  -> 对每个候选重新过滤 DataFrame
  -> compute_billboard_data()
  -> 将完整 JSON payload 重新转换为 DataFrame 和 lookup
  -> 返回候选 + 播放次数 + chart
```

#### 2.2 已确认的主要根因

| 根因 | 当前行为 | 影响 |
|---|---|---|
| 搜索与完整统计耦合 | 每个关键词加载 lifetime 逻辑播放帧 | 热缓存后仍需约 4s |
| 搜索与完整 Billboard 耦合 | 为少量 badge 计算完整榜单、纪录、Power Score 和封面 payload | 冷请求增加约 12s |
| 候选查询复用 AI resolver | 搜索同时承担 schema 探测、艺人 canonicalization 和全量署名播放聚合 | 交互热路径职责过重 |
| 名称查询不可 seek | `lower(name) LIKE '%query%'` | 普通名称索引主要被扫描，仍需临时排序 |
| 专辑候选查询聚合多来源 | 每个关键词组合 track album、junction 与 source album 播放来源 | 每次候选查询重复扫描播放数据 |
| 请求不能随输入取消 | TanStack `queryFn` 未把 `signal` 传给 API | 旧请求继续占用连接和后端线程 |
| 搜索继承全局重试 | 失败可自动重试两次 | 昂贵查询可能被放大三倍 |
| 前端替换整个结果区 | 新 query key 加载时显示 loading panel | 输入时产生明显闪烁和布局变化 |
| 完整页每类仍为 5 条 | API 上限 10，页面固定请求 5 | “查看全部结果”与实际能力不一致 |
| 缓存键未统一搜索文本 | 只 trim，不统一 Unicode、大小写和标点 | 相同意图形成多份缓存 |

#### 2.3 为什么不能只调整防抖或加普通索引

- 250ms 防抖只能减少请求数量，不能缩短单个请求的 4–20s 执行时间。
- 普通 B-tree 对前导 `%` 的子串查询不能高效定位。
- 即使候选检索降到几十毫秒，完整播放统计和 Billboard 仍是主要耗时。
- HTTP 取消只能停止前端等待；FastAPI 同步线程中的 pandas/SQLite 计算不一定随断开终止。
- 因此必须先让每个搜索请求本身变轻，再把防抖、取消和索引作为配套能力。

### 3. 冻结的产品决策

#### 3.1 信息架构不变

- 搜索继续是全局 utility，不增加第六个顶级导航。
- `/music/search` 继续是唯一完整查找页。
- 播放分析二级导航顺序不因本计划改变。
- 音乐详情页继续负责深入浏览，搜索结果不复制详情能力。

#### 3.2 搜索范围

搜索文档只包含本地可访问的歌曲、专辑项目和艺人：

- 当前有效统计下存在播放，或已有可解析详情/榜单事实的实体；
- 歌曲以稳定 `track_id` 和当前合并语义为基础；
- 专辑以 album project identity + canonical artist 为主，缺少 project 时使用本地 album fallback；
- 艺人以 canonical artist identity 为主，别名只参与检索，不生成重复结果；
- 有效曲目署名参与歌曲的艺人检索文本与艺人归属，但不得重写原始表。

#### 3.3 结果信息层级

第一阶段候选立即显示：

- 封面；
- 实体类型；
- 名称；
- 艺人/专辑等区分信息；
- 详情深链。

`match_field` / `match_type` 只用于内部排序、高亮、测试和诊断，不在消费界面展示“匹配艺人名称”、
“匹配别名”、“简繁匹配”或“近似匹配”等工程标签。名称、艺人和专辑文字必须跟随全局简繁体偏好，
但详情深链和本地保存值继续使用原始实体数据。

第二阶段渐进显示：

- 播放次数；
- `PK #`；
- 在榜周数；
- 走势排名。

继续不显示冠军周数、工程口径、缓存状态、过滤指纹或治理术语。没有榜单事实时只保留播放
次数，不增加噪声较高的“未入榜”标签。

#### 3.4 Quick Open 与完整页职责

| 能力 | Quick Open | `/music/search` 全部 | 单类型页签 |
|---|---|---|---|
| 每类首批结果 | 最多 3 条 | 最多 5 条预览 | 每页 20 条 |
| 总数 | 显示分组数量或总数 | 显示每类准确总数 | 显示总数与页码 |
| 统计上下文 | 渐进补齐可见结果 | 渐进补齐可见结果 | 渐进补齐当前页 |
| 键盘导航 | 完整支持 | 标准 Tab/链接导航 | 标准 Tab/链接导航 |
| 分享 URL | “查看全部”进入页面 | `q` + `kind` | `q` + `kind` + `page` |
| 最近查看 | private 可显示 | private 可显示 | 不占用结果区 |

“全部”视图不一次挂载 60 条结果。它负责展示每类前 5 条和准确总数，每个分组提供
“查看全部 X 个”进入对应类型页签。

### 4. 目标架构

#### 4.1 总体数据流

```text
用户输入
  -> 标准化 + IME 门禁 + 防抖
  -> GET /api/music/search?response_mode=candidates
       -> active music_search index generation
       -> exact semantic snapshot eligibility join
       -> 返回候选、total_by_kind、分页信息、entity_key、snapshot_status
  -> UI 立即渲染可点击结果
  -> GET /api/music/search/context?entity_key=...
       -> exact active semantic snapshot
       -> 返回播放次数与 chart 摘要，或 warming/unavailable
  -> UI 在预留区域渐进补齐上下文
```

后台派生链路：

```text
导入 / 设置 / 版本归并 / 艺人身份 / 曲目署名变化
  -> 标记 search documents 或 semantic snapshot dirty
  -> private maintenance / job queue 去重重建
  -> 新 generation/snapshot 完整验证
  -> 单事务切换 active pointer
  -> 清理旧 generation（保留一个可回滚版本）
```

#### 4.2 分层职责

| 层 | 职责 | 禁止事项 |
|---|---|---|
| Search normalizer | Unicode、空白、标点、简繁体搜索变体 | 修改展示名称 |
| Search document builder | 从规范实体和别名生成派生文档 | 重写 `tracks`、`albums`、`artists` |
| Candidate repository | FTS/回退检索、精确资格 join、排序、分页、总数 | 加载 `plays` DataFrame |
| Context snapshot builder | 复用统计/榜单规范函数批量生成上下文 | 为每个候选逐行重新计算 |
| Context repository | 精确快照 lookup | 在 GET 请求中冷构建 |
| API facade | 参数校验、运行面策略、response model | 拼接任意 SQL |
| Frontend query layer | 候选/context 查询、取消、缓存与渐进状态 | 在组件内手写 fetch 状态机 |
| Presentation | Desktop/Phone 视觉、键盘与触控交互 | 改写统计事实 |

### 5. 搜索索引设计

#### 5.1 派生表

通过 additive migration 创建以下派生结构，具体 migration 编号在实施时取当前下一个编号，
不得在规划阶段硬编码：

##### `music_search_index_state`

- `state_id = 1`
- `active_generation_id`
- `document_revision`
- `build_status`: `ready | pending | running | failed`
- `last_error`
- `updated_at`

##### `music_search_documents`

- `document_id`
- `generation_id`
- `entity_key`
- `kind`: `track | album | artist`
- `label`
- `secondary_text`
- `normalized_label`
- `normalized_secondary`
- `aliases_text`
- `track_id`
- `album_id`
- `album_project_id`
- `artist_id`
- `cover_type`
- `cover_entity_id`
- `href`
- `popularity_tiebreaker`
- generation 内唯一 `(entity_key)`

##### `music_search_fts`

- FTS5 虚拟表；
- 索引标准化名称、secondary text 和 aliases；
- `generation_id`、`kind`、`entity_key` 作为非检索过滤/关联字段；
- 当前本机 SQLite 3.51 已验证支持 FTS5 trigram；生产镜像必须通过运行时 doctor，
  不得只依据开发机能力下结论。

#### 5.2 稳定实体键

| 类型 | 首选 entity key | fallback |
|---|---|---|
| 歌曲 | `track:{canonical_track_id}` | `track:{track_id}` |
| 专辑 | `album_project:{project_id}` | `album:{album_id}` |
| 艺人 | `artist:{canonical_artist_id}` | `artist:{artist_id}` |

`entity_key` 是搜索候选与上下文快照之间的唯一关联键。前端不得用 label、href 或数组位置
匹配上下文；专辑不得只用 `album_name` 匹配。

#### 5.3 标准化规则

标准化只作用于检索文本，不改变消费界面的展示名称：

1. Unicode NFKC；
2. trim 并折叠连续空白；
3. Unicode-aware casefold；
4. 统一弯引号、直引号、连字符和全角标点的搜索变体；
5. 保留原文，同时生成简体、繁体搜索变体；
6. 将歌曲名称、有效艺人署名和专辑名称分字段索引；
7. 艺人 canonical name 与已批准 alias 同时索引；
8. 不从 genre、语言、歌词或外部常识生成搜索词。

前端只做最小且与后端共享测试向量的规范化，后端标准化是最终事实源。API response 返回
`normalized_query`，前端 TanStack key 使用同一结果或等价纯函数。

#### 5.4 检索与排序

排序分层固定为：

1. 主名称完全匹配；
2. 主名称前缀匹配；
3. 主名称全部 token 匹配；
4. secondary/alias 完全或前缀匹配；
5. trigram 子串匹配；
6. 同层内使用 `popularity_tiebreaker`、规范名称和稳定实体键确定顺序。

个人播放热度只能作为同层 tie-breaker，不能让高播放但弱匹配结果压过准确名称。搜索排序不使用
Billboard peak 或 Power Score，以免过滤设置改变候选顺序和缓存键。

多字段示例：

- `cardigan taylor` 可匹配歌曲名 + 艺人名；
- `folklore taylor swift` 可匹配专辑名 + 艺人名；
- 艺人旧名或有效 alias 返回 canonical 艺人一条结果；
- 同名专辑通过 canonical artist 和封面区分。

#### 5.5 短查询与 FTS fallback

- 拉丁/数字等单字符不请求远端候选，只展示初始状态；
- 两字符使用精确/前缀规范索引，不依赖 trigram；
- 中日韩文字允许单字符，但限制返回数量并优先主名称前缀；
- 三字符及以上使用 FTS5 trigram；
- 若生产 SQLite 缺少 FTS5/trigram，doctor 将状态标为 degraded，候选 repository 使用
  `normalized_label` 前缀索引 + 有界 substring fallback；
- fallback 不得重新聚合 `plays`，性能退化只能发生在候选匹配阶段。

#### 5.6 构建与发布

- 在非 active `generation_id` 中完整构建文档与 FTS 行；
- 验证实体数、重复 entity key、空 label、无效 href 和随机抽样深链；
- 单事务更新 `active_generation_id`；
- 发布后保留上一代，下一次成功构建后再回收更早 generation；
- 构建失败保持上一 active generation，不暴露半成品；
- 文档索引是可重建数据，不进入原始数据备份的唯一事实层，但随 SQLite Online Backup 一并备份。

### 6. 精确上下文快照设计

#### 6.1 快照内容

##### `music_search_snapshot_meta`

- `snapshot_key`
- 完整播放/Billboard 过滤指纹；
- 数据库播放 revision；
- track group revision；
- album project revision；
- artist identity revision；
- track credit revision；
- Billboard aggregation revision；
- `status`: `pending | running | ready | failed`；
- `created_at`、`activated_at`、`last_error`。

##### `music_search_entity_context`

- `snapshot_key`
- `entity_key`
- `play_events`
- `total_ms`
- `peak_position`
- `peak_weeks`
- `weeks_on_chart`
- `weeks_at_no1`
- `power_score`
- `power_rank`
- `first_week`
- `latest_week`
- `first_peak_week`
- 唯一 `(snapshot_key, entity_key)`。

UI 继续只消费允许展示的字段。保留 `weeks_at_no1` 等字段是为了与详情契约完整对照，不代表搜索
UI 恢复冠军周数展示。

#### 6.2 过滤指纹

搜索上下文指纹至少包含：

- `min_ms`
- `music_only`
- `merge_enabled`
- `dynamic_threshold`
- `max_merge_gap_minutes`
- `merge_level`
- `bb_top_n`
- `bb_album_top_n`
- `bb_artist_top_n`
- `bb_week_start_dow`
- `bb_week_start_hour`
- `year_start`
- `year_end`
- 所有相关数据与元数据 revision

指纹生成复用现有统计上下文规范，不在搜索 service 内维护第二套默认值。

#### 6.3 构建规则

- 一次构建批量生成全部可搜索实体的统计映射；
- 播放次数复用逻辑播放事件和详情统计的规范归属，不使用搜索候选 SQL 的原始 `COUNT(*)`；
- 歌曲使用规范 track identity；
- 专辑使用 album project membership + canonical artist；
- 艺人使用有效曲目署名 fan-out，再经 canonical artist 去重；
- chart 摘要优先复用 staged weekly、summary 和 power cache/预聚合，不调用完整 records payload；
- 构建完成后抽样与三类详情 API 对照，失败不得激活；
- 构建过程允许秒级，但不能运行在用户关键词 GET 请求内。

普通消费搜索的候选资格也来自该精确快照：Candidate repository 先完成名称匹配，再按当前
`snapshot_key` join context，只保留 `play_events > 0` 或存在可解析 chart 事实的实体，并按当前
merge level 折叠规范歌曲/专辑身份。这样候选层虽然不做实时统计，仍不会把当前详情资格之外的
随机实体当成可访问结果。搜索文档本身保持可重建；资格、规范 entity key 和准确总数由精确快照
决定。

当精确快照处于 `pending/running` 时，普通消费搜索必须返回明确 `warming` 状态，不得用 raw
candidate 或旧 snapshot 冒充当前事实。Settings 治理选择器可以使用私有的 `eligibility=any_local`
模式查找本地原始实体，但该模式不属于普通消费搜索，也不得在 `public-readonly` 开放。

#### 6.4 重建协调

- 使用单一 job type，例如 `music_search_snapshot_rebuild`；
- exact snapshot key 去重，同一 key 只允许一个 queued/running 任务；
- 当前设置指纹优先；旧设置快照可按 LRU/数量上限清理；
- 导入维护在 Billboard 预聚合和 album project 完成后构建搜索快照；
- 设置 mutation 先保存设置并标记新指纹 pending，再异步构建；
- 私人运行面若请求精确快照但状态 pending，只返回 `warming`，不得同步等待；
- 公共运行面只读取 `ready` 精确快照，不能排队、构建或降级到昂贵实时统计。

#### 6.5 失效矩阵

| 变化来源 | 候选文档 | 播放上下文 | Billboard 上下文 |
|---|---:|---:|---:|
| Streaming History 导入 | 重建 | 重建 | 重建 |
| Spotify 元数据补全 | 可能重建 | 不一定 | 封面/identity 变化时重建 |
| `min_ms` / dynamic threshold / gap | 不变 | 重建 | 重建 |
| Billboard 周边界 / Top N | 不变 | 不变 | 重建 |
| L1/L2/L3 版本归并 | 可能重建 | 重建 | 重建 |
| album project 重建 | 专辑文档重建 | 专辑重建 | 专辑重建 |
| 艺人身份 mutation | 艺人/相关歌曲重建 | 艺人重建 | 艺人重建 |
| 曲目署名 mutation | 歌曲 secondary 与艺人文档重建 | 艺人重建 | 艺人重建 |
| 简繁体显示偏好 | 不变 | 不变 | 不变 |
| 主题偏好 | 不变 | 不变 | 不变 |

每个 mutation 只能调用一个集中式 `mark_music_search_derived_data_dirty()` 或等价编排入口，
不能由各 API 自行拼失效逻辑。

### 7. API 契约

#### 7.1 候选接口

保留：

```http
GET /api/music/search
```

新增参数：

- `response_mode=candidates|legacy`
- `eligibility=current|any_local`，默认 `current`；`any_local` 仅 private 管理消费者可用
- `q`
- `kind=track|album|artist`
- `limit_per_type`
- `page`
- `page_size`

过渡规则：

- 实施期默认 `legacy`，确保旧前端和 Settings 消费者不被后端先行部署破坏；
- 新 UI 显式请求 `response_mode=candidates`；
- `eligibility=current` 使用 PlayFilters、BillboardFilters、MergeConfig 解析出的精确快照资格；
- `eligibility=any_local` 不返回消费统计，只供获得 private capability 的 Settings 治理选择器使用；
- `include_chart` 仅在 legacy 模式兼容，记录弃用但本计划同一交付不删除；
- 所有内部消费者迁移后，是否变更默认值必须单独提升 API contract version，不在本计划暗改。

候选响应示意：

```json
{
  "response_version": "music_search_v2",
  "query": "taylor",
  "normalized_query": "taylor",
  "snapshot_status": "ready",
  "filter_fingerprint": "...",
  "kind": null,
  "page": 1,
  "page_size": 5,
  "total": 24,
  "total_by_kind": {
    "track": 12,
    "album": 4,
    "artist": 8
  },
  "tracks": [],
  "albums": [],
  "artists": []
}
```

候选行新增：

- `entity_key`
- `match_field`: `label | artist | album | alias`
- `match_quality`: `exact | prefix | token | substring`

`match_quality` 只用于稳定渲染/调试，不向普通消费 UI显示工程术语。

#### 7.2 上下文接口

新增显式只读 GET：

```http
GET /api/music/search/context?entity_key=track:123&entity_key=artist:45
```

规则：

- 最多 30 个 entity key；
- 去重并保持响应按 key 映射；
- 使用完整 PlayFilters、BillboardFilters、MergeConfig；
- 只读取精确 `ready` snapshot；
- 返回 `ready | warming | unavailable | stale`；
- `stale` 数据不冒充当前事实；若 candidate 与 context 指纹不一致，UI 使当前候选进入更新态并
  重新请求候选，不能把旧 context 附着到新实体；
- 不接受任意 SQL、名称匹配或 href；只接受合法稳定 key。

响应示意：

```json
{
  "response_version": "music_search_context_v1",
  "snapshot_status": "ready",
  "filter_fingerprint": "...",
  "items": {
    "track:123": {
      "play_events": 280,
      "total_ms": 50200123,
      "chart": {
        "peak_position": 1,
        "weeks_on_chart": 12,
        "power_rank": 8
      }
    }
  }
}
```

#### 7.3 错误与降级

| 场景 | 候选接口 | 上下文接口 | UI |
|---|---|---|---|
| 空 query | 200 空集合 | 不调用 | 初始建议状态 |
| 索引 missing | 有界 resolver fallback | 不受影响 | 正常候选，记录 degraded |
| 索引 failed | 上一 active generation | 不受影响 | 无工程错误文案 |
| snapshot warming | 200 `warming`，不返回未经证明的消费候选 | 200 `warming` | 显示“音乐资料正在更新”，不伪装为空结果 |
| snapshot failed/unavailable | 200 `unavailable`，不返回未经证明的消费候选 | 200 `unavailable` | 显示暂不可用状态和轻量重试 |
| 非法 entity key | 不适用 | 422 | 不重试 |
| 网络失败 | 保留已有结果 | 保留已有候选 | 行内错误，不清空输入 |

#### 7.4 公开只读运行面

- `/api/music/search` 已在公开 GET 白名单中；新 `/api/music/search/context` 必须经过显式安全评审后
  加入白名单，不能依赖路径前缀自动开放；
- 两个接口都只能返回本地结构化音乐实体和统计；
- public 只允许 `eligibility=current`，拒绝 private `any_local` 管理模式；
- 公共请求使用 `mode=ro` + `PRAGMA query_only=ON`；
- 公共搜索不得写 `background_jobs`、snapshot state、search history 或封面 metadata；
- 公共搜索不得触发外部封面补全。结果封面只使用已存在本地/数据库 URL，缺失时前端占位；
- snapshot 不精确时只返回 `unavailable`，不触发后台构建；
- 不把 imported Spotify 搜索历史或 private 最近查看下发到公共运行面。

### 8. 前端查询与状态架构

#### 8.1 Query hooks

将搜索数据逻辑从通用 `useAnalysis.ts` 收口到搜索 feature：

- `useMusicSearchCandidates()`
- `useMusicSearchContext()`
- `musicSearchApi.searchCandidates()`
- `musicSearchApi.getContext()`

为了兼容 Settings 现有引用，`useAnalysis.ts` 可暂时 re-export，所有新代码直接使用 feature hook。

Query key：

```text
['music', 'search', 'candidates', semanticFilterKey, normalizedQuery, kind, page, pageSize]
['music', 'search', 'context', filterFingerprint, sortedEntityKeys]
```

搜索文档索引不因普通关键词查询重建，但普通消费候选必须按当前完整语义资格筛选，因此 candidate
query key 包含由当前播放/Billboard 设置生成的 `semanticFilterKey`。服务端仍以包含数据 revision
的完整 `filter_fingerprint` 为最终事实；导入和治理 mutation 必须集中失效 `queryKeys.music.all`。
上下文 key 包含服务端返回的完整过滤指纹与排序后的 entity keys。

#### 8.2 请求行为

- `queryFn` 接收 TanStack `signal` 并传给 `api.get()`；
- 搜索候选 `retry: 0`；仅明确的瞬时网络错误允许用户手动重试；
- 初次候选显示轻量 skeleton；后续关键词变化用 `placeholderData/keepPreviousData` 保留布局，
  同时显示低干扰“正在更新”；
- 上下文加载不覆盖候选 loading 状态；
- 新候选集合返回时，只保留 entity key 仍存在的旧上下文；
- 关闭 Quick Open 后取消未使用 query observer，不主动清空可复用缓存；
- 搜索候选建议使用较短 `gcTime`，上下文快照使用与数据 revision 一致的较长 `staleTime`；
- 导入、设置、版本归并和 metadata mutation 继续按 `queryKeys.music.all` 集中失效。

#### 8.3 输入状态

- Quick Open 与完整页共用 search input controller；
- Desktop 防抖目标 180–250ms，实际值在 M0 交互测试后冻结；
- `compositionstart` 到 `compositionend` 之间不请求、不改 URL；
- URL 只写 trim 后原始显示 query，查询 key 使用 normalized query；
- 完整页继续使用 `replace` 更新输入产生的 URL，避免每个字符污染浏览器历史；
- 点击类型和分页更新 URL；返回详情后恢复 query、kind、page 与滚动位置；
- 从 Phone Top Bar 明确点击搜索进入时聚焦并打开键盘；从详情返回时恢复焦点位置但不自动重开键盘。

#### 8.4 过时请求与竞态

必须有自动化测试覆盖：

1. 输入 `tay` 发出请求 A；
2. 输入 `taylor` 取消 A 并发出 B；
3. 即使 A 最后返回，UI 也不能覆盖 B；
4. A 的取消不展示网络错误；
5. context A 不能附着到 candidates B 的同数组位置，只能按 entity key 匹配。

### 9. 体验设计

#### 9.1 Desktop/Compact Quick Open

- 搜索图标保留原位置；
- 增加 `⌘K` / `Ctrl+K` 全局快捷键，输入框或可编辑区域获得焦点时不劫持普通按键；
- 打开后聚焦输入；关闭后恢复到触发按钮；
- 默认不选中第一条结果；
- `ArrowDown/ArrowUp` 首次使用后才激活结果；
- `Enter` 只在存在 active result 时打开详情；否则保持输入；
- `Escape` 关闭；Tab 遵循 dialog focus trap；
- 最多 9 条候选（每类 3 条），空分组不显示；
- 底部“查看全部结果”保留当前 query；
- 候选出现后上下文渐进填入，不显示全屏“匹配榜单信息”的阻塞 loading。

#### 9.2 完整查找页

全部视图：

- 每类前 5 条；
- 分组标题显示准确总数；
- 每组底部“查看全部 X 个”；
- 不显示三组空容器；
- 全部为空时提供更具体的改写建议。

单类型视图：

- 每页 20 条；
- URL 为 `?q=...&kind=track&page=2`；
- 搜索词或类型变化时 page 回到 1；
- 显示结果范围，例如“21–40 / 128”；
- 上一页、下一页和页码控件满足 44×44px；
- 页面切换保留旧页直到新页就绪，避免整页闪烁。

#### 9.3 Phone presentation

- 继续使用独立 Phone presentation 和 Push Top Bar，不挂载 Desktop dialog；
- 无 query 时保留紧凑页面标题；有 query 时首屏优先吸附搜索和类型切换；
- 类型切换为 44px 触控目标，允许有意的 chip 横向滚动但不得产生页面级溢出；
- 结果继续使用 `MobileEntityRow`，上下文使用固定高度 facts/badges 区域；
- 完整页分页不得使用宽表或密集页码，使用“上一页 / 第 N 页 / 下一页”；
- 360/390/430px 下名称、secondary 和 badge 不造成横向滚动；
- 键盘出现时使用 `100dvh`/visual viewport，底部内容不被系统键盘遮挡。

#### 9.4 初始状态与最近查看

`private-admin` 可以显示应用内最近打开的音乐实体：

- 最多 6 条；
- 只存稳定 entity key、label、kind、href 和本地时间；
- 优先使用前端本地存储，不写入服务端搜索历史；
- 导入/身份变化后无法解析的实体静默移除；
- 提供清除操作。

`public-readonly` 不展示 private 最近查看，也不读取 imported Spotify 搜索历史；初始状态只显示
搜索范围说明或公开安全的固定引导。

#### 9.5 匹配解释与高亮

- 名称中安全高亮匹配片段，不使用 `dangerouslySetInnerHTML`；
- 如果歌曲因艺人或专辑字段命中，secondary text 显示自然语言区分信息；
- 不向普通用户显示 `exact/prefix/token/trigram` 等工程标签；
- 同名实体必须依靠 canonical artist、专辑或封面区分，不能只显示重复 label。

#### 9.6 可访问性

- Quick Open 使用可访问 dialog + combobox/listbox 关系或等价 APG 模式；
- 输入框提供 `aria-controls`、结果数量 live region 和 active descendant；
- loading live region 只在状态变化时播报一次；
- 上下文渐进补齐不重复朗读整行；
- 所有封面保留实体化 alt，装饰 icon 隐藏；
- focus ring、暗色对比度、reduced motion 和 200% zoom 通过验收；
- 关闭 dialog、打开详情再返回时焦点恢复可预测。

### 10. 性能预算与可观察性

#### 10.1 服务端预算

以下预算以当前真实数据库量级和个人云单用户部署为基线：

| 指标 | 目标 |
|---|---:|
| 候选 repository 热查询 P50 | ≤50ms |
| 候选 API 热查询 P95 | ≤150ms |
| 候选 API 冷连接 P95 | ≤400ms |
| 30 个 entity context 精确快照 lookup P95 | ≤100ms |
| Quick Open 首批可点击结果 P95 | ≤400ms |
| 已缓存 query 重新打开可见结果 | ≤100ms |

预算门禁还包括：

- 候选 query plan 不扫描/聚合 `plays`；
- context query plan 只访问 snapshot meta/context 索引；
- 任何搜索 GET 不触发 snapshot build；
- 单次候选响应建议控制在 50KB 以内；
- Quick Open 最多请求 9 张可见封面，继续 lazy decoding；
- 搜索交互区域新增 CLS 目标 ≤0.02。

预算若因 CI 硬件差异无法使用绝对值，应在本地真实数据 probe 使用绝对预算，CI 使用“不得访问
plays/不得调用重计算函数”和相对基线双门禁，避免脆弱的毫秒测试。

#### 10.2 Server-Timing

候选响应至少记录：

- `normalize`
- `candidate_query`
- `serialize`
- `total`

上下文响应至少记录：

- `fingerprint`
- `snapshot_lookup`
- `serialize`
- `total`

日志只记录 request id、query 长度、kind、结果数、索引 generation、snapshot 状态和耗时。默认不记录
原始搜索词，避免把个人搜索意图复制到服务端日志。

#### 10.3 性能探针

新增 `scripts/music_search_performance_probe.py`：

- 默认以 `mode=ro` 打开数据库；
- 支持 candidate/context/end-to-end；
- 支持 cold process 与 warm repeat；
- 使用固定非敏感 query 集合或调用者显式传入 query；
- 输出 JSON 和人类可读表格；
- 记录数据库大小、plays/tracks/albums/artists 数量、SQLite 版本和 FTS 能力；
- 支持预算参数，超预算退出非零；
- 不打印真实完整结果或用户原始历史。

### 11. 实施阶段

#### M0：契约冻结与基准固化

目标：在改代码前固定“快什么、准什么、不能做什么”。

任务：

- 建立只读性能 probe，复现本计划基线；
- 增加当前搜索调用链的分段计时；
- 冻结 `entity_key`、candidate response、context response 和状态枚举；
- 建立 query 标准化测试向量；
- 建立三类详情一致性 golden cases；
- 确认生产 Docker SQLite FTS5/trigram 能力；
- 记录公开运行面安全评审结论。

门禁：

- probe 可在真实 DB 和 seed DB 重复运行；
- 基准结果附机器、数据量和冷/热条件；
- API schema 评审通过后才进入 M1。

粗略工作量：0.5–1.5 个开发日。

#### M1：候选与上下文解耦

目标：在还未建立 FTS 和持久快照前，先消除首屏 8–20s 阻塞。

任务：

- 为 `/api/music/search` 增加显式 candidate 模式；
- candidate 模式禁止加载过滤后 lifetime frames 和完整 Billboard；
- 增加 `/api/music/search/context` schema，但初期可以返回缓存已有/`warming`；
- 前端拆为 candidates/context 两个 hook；
- 传递 AbortSignal，关闭搜索请求的自动重试；
- 初次 skeleton、后续 keep-previous-data；
- Quick Open 与完整页改为候选先显示、上下文渐进补齐；
- Settings 中复用搜索的消费者显式选择 candidate + private `any_local` 模式；
- M1 可以完成内部链路与体感验证，但普通消费搜索不得在缺少 M3 精确资格快照时作为生产默认切换。

门禁：

- candidate service 测试通过 monkeypatch 保证不会调用 `load_period_plays()` 和
  `compute_billboard_data()`；
- 当前真实 DB candidate end-to-end P95 ≤400ms；
- 旧 legacy 合同继续通过；
- 搜索结果先出现时已经可点击，不等待 context。

粗略工作量：1.5–3 个开发日。

#### M2：持久搜索索引与相关性

目标：将候选查询从通用 AI resolver 收口为专用、稳定、可分页的搜索 repository。

任务：

- additive migration 创建 generation state、documents 与 FTS；
- 实现 normalizer、document builder、FTS doctor 与 fallback；
- 接入 canonical artist、album project 和有效署名；
- 实现 exact/prefix/token/secondary/trigram 排序；
- 实现 `total_by_kind`、全部视图预览和单类型分页；
- 增加重建 CLI 与导入维护接入；
- 增加 active generation 原子发布与上一代回滚。

门禁：

- 实际候选 API 热 P95 ≤150ms；
- query plan 不访问 `plays`；
- 同名专辑、艺人 alias、合作署名和 album project 用例通过；
- FTS unavailable fallback 合同通过；
- 构建失败仍可查询上一代。

粗略工作量：2–4 个开发日。

#### M3：精确统计与 Billboard 快照

目标：让上下文重新具备完整详情一致性，同时保持 lookup 级延迟。

任务：

- 创建 snapshot meta/context 派生表；
- 实现完整过滤指纹和 revision；
- 批量构建三类播放统计；
- 从 staged/preaggregated Billboard 结果生成轻量 chart context；
- 接入 job queue exact-key 去重；
- 接入 import maintenance、settings、version merge、artist identity 和 track credits 失效；
- public GET 实现 exact-ready-only；
- 增加快照健康状态与管理探针，不新增普通消费 UI 治理术语。

门禁：

- 30 个实体 lookup P95 ≤100ms；
- 三类搜索 context 与详情 API 在 L1/L2/L3、动态阈值、gap、榜单周边界代表矩阵中一致；
- 搜索 GET 期间 job queue 无新增任务；
- pending/failed snapshot 不阻塞候选；
- public-readonly 的数据库 total changes、job 数量和外部 provider 调用均不变化。

粗略工作量：3–5 个开发日。

#### M4：完整页、键盘、Phone 与体验收口

目标：解决“有搜索但不够像完整查找工具”的体验缺口。

任务：

- Quick Open 每类 3 条和 `⌘K/Ctrl+K`；
- 完整页准确总数、每类 5 条预览和单类型 20 条分页；
- IME、焦点 trap/restore、live region、active descendant；
- 匹配片段安全高亮和 secondary match 解释；
- private 最近查看与 public capability 隔离；
- Phone sticky controls、分页、键盘视口和返回状态恢复；
- 保留默认不预选第一条结果。

门禁：

- 键盘、鼠标、触控均可完成查询和打开详情；
- 旧请求晚返回不覆盖新 query；
- “查看全部”与真实总数一致；
- 360/390/430/768/1280 0px 页面级横向溢出；
- Chromium/Firefox/WebKit 交互 smoke 通过。

粗略工作量：2–3 个开发日。

#### M5：生产发布、回滚与文档收口

目标：将搜索优化作为可回滚的生产变更交付，而不是只通过本地测试。

任务：

- 部署前 Online Backup；
- 在 private/full 中构建并验证 active search generation/snapshot；
- showcase/dual 发布前检查 exact snapshot ready；
- 执行 full/showcase/dual 三模式门禁；
- 对比发布前后冷/热基准、HTTP timing、数据库完整性和公共副作用；
- 演练回滚旧 commit SHA：旧代码忽略 additive 派生表，旧 `/api/music/search` legacy 仍工作；
- 更新 README、AGENTS、CLAUDE、docs/CHANGELOG 与交付报告；
- 只有用户明确要求时才提交 Git。

门禁：

- 同一 commit SHA 的两个 Web 运行面搜索结果一致；
- public 无写入、无外部请求、无后台构建；
- 真实浏览器 Quick Open 与 Phone 页面达到预算；
- 回滚后旧搜索仍可用，数据库无需 destructive downgrade。

粗略工作量：1–2 个开发日。

总工作量预估：单人约 10–18 个开发日。该估算不包含发现统计口径缺陷后的额外修复，实施时应按
M0–M5 独立验收，不把总工期当作跳过阶段门禁的理由。

### 12. 文件与模块地图

#### 12.1 后端预计新增

- `backend/domains/music_search/__init__.py`
- `backend/domains/music_search/normalization.py`
- `backend/domains/music_search/documents.py`
- `backend/domains/music_search/repository.py`
- `backend/domains/music_search/context_snapshot.py`
- `backend/domains/music_search/rebuild.py`
- `scripts/rebuild_music_search_derived_data.py`
- `scripts/music_search_performance_probe.py`
- 对应 unit/contract/integration tests

#### 12.2 后端预计修改

- `backend/api/music.py`
- `backend/models/music_search.py`
- `backend/services/music_search_service.py`：最终成为兼容 facade，不继续堆积查询实现
- `backend/core/migrations.py`
- `backend/core/access_surface.py`
- `backend/core/cache_manager.py`
- `backend/services/import_maintenance_service.py`
- Settings、version merge、artist identity、track credits 的集中失效调用点
- `scripts/api_smoke_probe.py`
- `scripts/phase5_check.sh`

#### 12.3 前端预计新增/收口

- `frontend/src/features/music/search/api.ts`
- `frontend/src/features/music/search/useMusicSearch.ts`
- `frontend/src/features/music/search/searchInputController.ts`
- 搜索 response/context 类型与状态组件

#### 12.4 前端预计修改

- `frontend/src/features/music/search/MusicSearchDialog.tsx`
- `frontend/src/features/music/search/MusicSearchPage.tsx`
- `frontend/src/features/music/search/MusicSearchResults.tsx`
- `frontend/src/features/music/search/musicSearchUtils.ts`
- `frontend/src/hooks/useAnalysis.ts`：兼容 re-export
- `frontend/src/api/query-keys.ts`
- `frontend/src/components/layout/Masthead.tsx`
- `frontend/src/components/layout/MobileTopBar.tsx`
- 搜索、移动 Shell、route context、query hook 和 public surface tests

模块拆分应遵守 Phase 5 route container 和 feature 边界，不因为搜索优化将所有逻辑继续集中到一个
service 或一个 React 组件。

### 13. 验证矩阵

#### 13.1 后端 unit

- 标准化：Unicode、大小写、空白、弯引号、连字符、简繁体；
- 排序：exact、prefix、token、secondary、alias、稳定 tie-break；
- entity key：track group、album project、canonical artist、fallback；
- FTS doctor 与 fallback；
- generation 原子发布和失败保留旧代；
- snapshot fingerprint、dedupe、pending/ready/failed；
- GET 请求不调用 rebuild；
- context 最多 30 key、非法 key 和去重。

#### 13.2 后端 contract

- legacy `/api/music/search` 兼容；
- candidate V2 response model、total_by_kind、分页；
- context ready/warming/unavailable；
- 搜索播放次数与三类 stats detail 一致；
- 搜索 chart 与三类 Billboard detail 一致；
- `dynamic_threshold`、gap、L1/L2/L3、Top N、周边界；
- public allowlist、query-only、零写入、零 provider；
- OpenAPI 与生成类型更新。

#### 13.3 数据与迁移

- 空 DB、seed DB、真实旧 DB migration；
- migration 幂等；
- FTS 重建后文档数与规范实体数对账；
- 重复 entity key、空 label、无效 deep link 为 0；
- import maintenance success/partial/error 报告包含搜索派生状态；
- snapshot build 中断后旧 active 仍可读；
- Online Backup 和 restore 后 FTS/context 可用。

#### 13.4 前端 unit/integration

- candidates/context 独立状态；
- context 渐进补齐和固定布局；
- AbortSignal、取消错误不展示、竞态不串线；
- IME composition；
- Quick Open 默认无 active result；
- Arrow/Enter/Escape/Tab；
- `⌘K/Ctrl+K` 与 editable target 排除；
- 准确总数、类型页、分页 URL；
- 最近查看 private-only；
- context unavailable 时候选仍可用。

#### 13.5 浏览器与可视验收

- 360/390/430/768/1024/1280；
- 日间/夜间；
- Chromium/Firefox/WebKit；
- 中文输入法、英文快速输入、复制粘贴、清空；
- 长名称、同名专辑、缺封面、无 chart、大数字；
- 慢速网络、offline、context warming；
- 200% zoom、reduced motion、键盘-only；
- Quick Open 关闭焦点恢复、详情返回状态恢复；
- public/full/dual 三运行面。

#### 13.6 性能验收命令目标

实施时将最终命令固化到 probe 和文档，至少包含：

```bash
.venv/bin/python scripts/music_search_performance_probe.py --mode candidate --cold --json-output /tmp/music-search-candidate.json
.venv/bin/python scripts/music_search_performance_probe.py --mode context --warm-repeat 10 --json-output /tmp/music-search-context.json
.venv/bin/pytest backend/tests/unit/test_music_search_*.py -q
.venv/bin/pytest backend/tests/contract/test_music_search_*.py -q
cd frontend && npm test -- --run src/tests/music-search-components.test.tsx src/tests/music-search-flow.test.tsx src/tests/query-hooks.test.tsx
cd frontend && npm run build
```

最终实际文件名以实施为准；规划中的命令不得在对应脚本尚未落地时写成“已通过”。

### 14. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 搜索快照与详情口径漂移 | 构建器复用规范函数；三类详情 contract 对照；指纹纳入所有 revision |
| album 同名/版本归属错误 | entity key 使用 album project + canonical artist，不按名称关联 context |
| 艺人 alias 重复 | 文档生成阶段 canonicalize，alias 只进检索字段 |
| FTS 在生产不可用 | 发布前 doctor；前缀索引 + 有界 substring fallback |
| rebuild 与在线读冲突 | generation/snapshot 非 active 构建，单事务切换 pointer |
| public 搜索触发副作用 | exact-ready-only、query-only、job/provider spy contract |
| HTTP 取消未终止后端线程 | 不把取消当性能核心；先保证请求本身轻量 |
| 快照状态长期 pending | maintenance health、last_error、显式 rebuild CLI、上一 active 保底 |
| 搜索 query 泄漏日志 | 默认只记长度、hash/类别和耗时，不记录原始文本 |
| 前端旧 context 串到新结果 | 只按 entity key 合并，不按 index/label/href |
| 派生表增加数据库体积 | 记录 generation 数量上限，仅保留 active + 上一代 |
| 回滚旧 SHA 不识别新表 | additive migration；旧代码忽略派生表；保留 legacy API |

### 15. 发布与回滚

#### 15.1 发布顺序

1. 备份主 SQLite 并记录 commit SHA、部署模式和现有搜索基准；
2. 应用 additive migration；
3. private maintenance 构建 search documents 与当前精确 context snapshot；
4. 验证数据对账、性能和三类详情一致性；
5. 启动目标 full/showcase/dual 模式；
6. 执行公共白名单、query-only、封面无外部补全和浏览器门禁；
7. 记录发布后冷/热结果与 active generation/snapshot key。

#### 15.2 回滚

- 代码回滚使用上一 commit SHA 和原部署模式作为一个单元；
- SQLite 不做 destructive downgrade，新派生表由旧代码忽略；
- legacy `/api/music/search` 在弃用期保留，旧前端仍可工作；
- 新 generation 出错时只切换 active pointer 到上一代，不删除当前原始数据；
- 若上下文快照异常，前端可以只显示候选，不能把错误快照冒充当前事实；
- 回滚后重新执行旧搜索 smoke、数据库 integrity check 与公共只读门禁。

### 16. 后续可选能力

以下首项已由后续方向实现，其余能力仍不属于本计划完成门禁：

- [x] 有界拼写纠错、确定性简繁体扩展与短 CJK fallback；
- 拼音/罗马字检索；
- 搜索结果快捷预览面板；
- 系统级 Spotlight/快捷指令集成；
- 本地最近搜索跨设备同步；
- 统一搜索歌曲、专辑、艺人之外的播放记录或社区内容。

任何扩展都不得让音乐实体搜索重新依赖 LLM、外部服务或同步全量统计计算。

### 17. 规划验收清单

- [x] M0 基准、契约和 FTS runtime 能力已冻结
- [x] M1 候选与 context 解耦，首批结果不再等待统计
- [x] M2 持久搜索索引、相关性、总数与分页完成
- [x] M3 精确统计/Billboard 快照、六变体覆盖、失效矩阵和 public cache-only 完成
- [x] M4 Desktop/Compact/Phone、键盘、IME、焦点与最近查看完成
- [x] M5 三模式本地生产门禁、真实浏览器、全部性能向量、回滚和文档收口完成
- [x] 旧入口归属、详情深链、默认不预选和搜索 badge 展示规则未回归
- [x] remediation plan 的阻断项已修复并由新证据证明，不再提前声明 Pass

后续方向已按
[`2026-08-16-music-search-direction-realignment.md`](#音乐查找方向重新指引轻量候选索引与统计快照解耦)
完成：候选版本与统计 fingerprint 解耦，简繁、短 CJK 和有限模糊匹配已上线；镜像改经私有 CAS
Artifact 将缺失 blob 续传到现有服务器，再由服务器推送 TCR。一次性旧库统计引导后，正常 production
workflow `31977767545` 首次成功；最终 workflow `31979057642` 在 9 分 57 秒内完成，搜索预检精确
复用六变体且仅耗时 2 秒，生产精确/模糊/简繁/短 CJK 语义门禁全绿，远程状态不再 Blocked。

## 音乐查找验收缺口完整修复规划

原记录：`2026-08-16-music-search-remediation-plan.md`。

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

> 创建日期：2026-08-16
> 状态：已完成（实现、真实主库维护、生产副本预建、联合回滚与远程生产均通过）
> 前置结论：实施前仅默认 L2 + 动态阈值开启场景可用；该 Partial 基线已被本轮修复取代
> 适用范围：搜索快照覆盖、统计语义、候选热路径、Quick Open、`/music/search`、公开只读与生产门禁
> 关联文档：`2026-08-16-music-search-performance-and-experience-optimization-plan.md`、`../../reports/2026-08-16-music-search-optimization-delivery.md`

> 2026-08-16 后续调整：本文的六变体统计语义与历史验收证据继续有效，但“每个新 SHA 都在一次性
> 工作副本中冷建候选索引和六变体”的发布策略已被
> `2026-08-16-music-search-direction-realignment.md` 取代。新实现按确定性候选版本与统计 fingerprint
> 分别复用，随机 generation ID 不再触发统计重建；阶段 A–E 已完成。镜像经私有 CAS Artifact
> 增量传输到现有服务器，再由服务器推送 TCR；正常 production workflow `31977767545` 已成功切换，
> 最终 workflow `31979057642` 以 SHA `cf2270f1` 在 9 分 57 秒完成，六套统计精确复用，搜索预检
> 仅 2 秒，生产精确/模糊/简繁/短 CJK 语义门禁通过。

### 0. 执行摘要

最终结果为 **Pass**。migration 34、持久 revision state、六变体 snapshot-set、Billboard 非默认
参数贯穿、候选 SQL 分页与前端状态机均已落地。真实主库六个变体全部为
`ready + music_search_snapshot_v2`，搜索 GET 不再扫描 `plays` 推断 revision，也不把完整资格集合或
全部 FTS 命中加载到 Python。七类查询各 60 次、共 420 个 HTTP 候选样本 P95 为 40.741ms，HTTP
context P95 为 6.921ms，响应均小于 8KiB。Chromium、Firefox、WebKit、七档视口、200% reflow、
full/showcase/dual、本地生产镜像、schema 33→34、Online Backup 与恢复演练全部通过。

验收中另外发现并修复了三项计划外但同范围的问题：SQLite `foreign_keys=OFF` 时旧快照 context
不会随 meta 裁剪、Firefox 缺少可构造 `Intl.Segmenter` 会空白页、Docker 构建上下文会带入嵌套
`seed.db`。真实库 15,175 条搜索 context 孤儿已在 165MiB 在线备份保护下定点清理为 0；其余
7,831 条历史外键问题不属于本轮，未修改。生产发布由 GitHub Actions 在每个目标 SHA 上执行
自适应副本预检与 runtime exact gate；远程是否已运行该 SHA，仍只以 production deployment 记录
为准。

本轮修复不推翻已经完成的两阶段搜索架构。候选索引、context 快照、IME、请求取消、分页、
Quick Open、Phone presentation 和公开只读边界继续保留。需要修复的是三个尚未闭合的基础契约：

1. **快照覆盖契约**：前端实际支持 L1/L2/L3 与动态阈值开/关，但维护链路目前只预建
   L2 + 动态阈值开启；其他模式会永久返回 `unavailable / 0`。
2. **统计一致性契约**：过滤指纹包含 `merge_enabled` 与 `include_compilations`，但 Billboard
   lookup 没有完整消费这两个值，非默认设置下可能把不同口径的播放次数和榜单 badge 合并展示。
3. **轻量热路径契约**：候选请求仍通过 `COUNT / MAX / SUM / COUNT DISTINCT` 扫描整张 `plays`
   计算 revision，并在 Python 中加载、排序所有 FTS 命中；当前规模基本达标，但延迟仍随数据量和
   高命中查询线性增长。

目标状态是：六种消费搜索变体都有明确生命周期；搜索 GET 只做 O(1) revision 读取和有界索引查询；
context 中的播放次数、PK、在榜周数和走势排名与相同完整口径的详情接口一致；公开请求始终纯读取。

### 1. 当前验收事实

#### 1.1 最终已通过并继续保留

- `response_mode=candidates` 与 `/api/music/search/context` 已从旧 lifetime pandas/Billboard 同步路径解耦。
- FTS5 trigram、fallback、准确总数、单类型分页、稳定 `entity_key` 和安全详情深链已经建立。
- 当前真实主库六个支持变体全部为 `ready + music_search_snapshot_v2`，`love` 在默认变体返回
  276 个候选。
- 七类查询共 420 个最终 HTTP 样本：候选 P50/P95 15.780/40.741ms，context
  P50/P95 6.034/6.921ms。
- Quick Open 的 Cmd/Ctrl+K、默认不预选、键盘导航、焦点归还、IME 门禁和 Phone 返回恢复已通过。
- public-readonly 显式允许两个搜索 GET、拒绝 `any_local`，并有零写入测试。
- migration 32/33/34、生产 FTS5/trigram、旧 HEAD 读取 additive schema、33→34 与本地恢复已经验证。

#### 1.2 实施前必须修复的失败证据

真实接口同一查询：

| 过滤变体 | `snapshot_status` | `total` |
|---|---|---:|
| L2 + 动态阈值开启 | `ready` | 276 |
| L1 + 动态阈值开启 | `unavailable` | 0 |
| L3 + 动态阈值开启 | `unavailable` | 0 |
| L2 + 动态阈值关闭 | `unavailable` | 0 |

原因是 `music_search_maintenance_service._current_filter_values()` 将 `dynamic_threshold=True`、
`merge_level=2` 写死，而前端 `useAnalysisFilters()` 从 localStorage 读取这两个值。现有 L1/L2/L3
一致性契约测试在测试内部手工构建三份 snapshot，没有验证真实维护链路能否产生它们。

#### 1.3 实施前性能复核

以下数据是确定修复范围时冻结的失败基线，不代表最终状态：

- `playback_source_revision()` 的查询计划包含 `SCAN plays` 和临时 B-tree；真实主库 P50 约 16.3ms。
- 完整 filter context 构建 P50 约 19.3ms、P95 约 20.9ms。
- 高命中三字符查询 `the` 的 60 次热 HTTP 请求为 P50 77.992ms、P95 81.359ms、最大 268.581ms，
  已略超候选 P95 80ms 预算。
- 当前 `get_ready_music_search_entity_keys()` 每次请求加载约 7,581 个 key；当前约 2.1ms，但仍随实体数增长。

### 2. 目标与非目标

#### 2.1 修复目标

1. 前端实际支持的 L1/L2/L3 × 动态阈值开/关六种组合都能获得精确 snapshot。
2. source/settings 变化后，六种 snapshot 有可诊断的 `pending / running / ready / failed / stale` 生命周期。
3. 默认 L2 + 动态阈值开启优先恢复，其他变体随后后台完成；任何变体不得冒充另一个变体。
4. `merge_enabled`、`include_compilations`、merge level、动态阈值、最大间隔、Top N、周边界和年份
   在 snapshot 构建、详情对照、filter fingerprint 和缓存 key 中一致。
5. 候选和 context GET 不扫描 `plays`、Billboard aggregate 或 metadata 全表来计算 revision。
6. 候选 repository 不把完整 eligible key set 和所有高命中结果加载到 Python 后再分页。
7. warming/stale 状态会自动观察就绪，但网络失败仍保持 `retry: 0`，避免昂贵错误重试。
8. 当前规划、交付报告和变更日志只在新门禁实际通过后恢复 `Pass / 已完成`。

#### 2.2 非目标

- 不恢复旧同步 `include_chart=true` 搜索作为消费 UI 热路径。
- 不改变 Masthead utility、`/music/search` 和既有详情路由的信息架构。
- 不引入 Elasticsearch、Meilisearch、Redis、LLM、拼音猜测或外部搜索服务。
- 不让 public GET 排队、写 snapshot、写 background job 或触发外部补全。
- 不在本轮重构全部 Billboard；只扩展搜索 snapshot 所需的完整过滤参数，并用共享契约防回归。
- 不把任意 API 查询参数组合都预建为 snapshot。候选 V2 的消费范围限定为当前服务端基础设置和六个
  明确支持的客户端变体；旧 legacy 接口继续承担兼容用途。

### 3. 冻结的修复决策

#### 3.1 支持六个、且只支持六个消费变体

`merge_level` 与 `dynamic_threshold` 是当前搜索消费界面可独立变化的参数，因此每一套服务端基础设置
必须覆盖：

```text
(L1, dynamic=true)   (L1, dynamic=false)
(L2, dynamic=true)   (L2, dynamic=false)
(L3, dynamic=true)   (L3, dynamic=false)
```

`min_ms`、`music_only`、`merge_enabled`、`max_merge_gap_minutes`、`include_compilations`、三类 Top N 和
Billboard 周边界继续以服务端 Settings 为基础事实。服务端基础设置发生变化时生成一个新的
`semantic_base_key`，旧 base 下的 snapshot 全部转为 stale。

候选 V2 若收到与当前服务端基础设置冲突的自定义参数，必须返回 422 和稳定错误码
`unsupported_candidate_filter`，不再以 `unavailable` 掩盖“该组合从未被维护链路支持”。
`year_start / year_end` 仅保留给 legacy 或其他明确支持年份窗口的接口，候选 V2 当前不接受自定义年份窗口。

#### 3.2 搜索 GET 永远纯读取

- candidates/context GET 只读取 revision state、active index 和 snapshot。
- missing/warming/stale/failed 都不能在 GET 中创建 meta、enqueue job 或更新 `last_accessed_at`。
- private 和 public 使用相同读取代码；差别仅为 public 禁止 `any_local` 和维护写入口。
- 重建只允许由启动维护、导入维护、Settings mutation、版本归并、艺人身份、曲目署名和显式的
  private-admin 维护操作触发。

#### 3.3 一个 snapshot-set job 顺序构建六个变体

不得向 3-worker 通用 JobQueue 同时投放六个会争用 pandas/SQLite/Billboard cache 的重任务。每个
`semantic_base_key` 只允许一个 `music_search_snapshot_set_rebuild` job，job 内顺序为：

1. L2 + dynamic=true（public 与默认 private 基线）；
2. L1 + dynamic=true；
3. L3 + dynamic=true；
4. L2 + dynamic=false；
5. L1 + dynamic=false；
6. L3 + dynamic=false。

入队事务先为六个 fingerprint 创建或更新 `pending` meta。每个变体独立事务发布，先完成的立即
`ready`，单个失败不得回滚已经 ready 的其他变体。job 最终报告 `ready_count / failed_count / timings`。

#### 3.4 revision 必须持久化，不在 GET 中推断

新增 O(1) revision state，由已知 mutation 在同一业务事务或成功维护收口点显式递增。候选 GET 不再
通过表 cardinality、`SUM(ms_played)` 或文件 mtime 猜测数据是否变化。

### 4. 目标数据模型与指纹

#### 4.1 migration 34

新增 `music_search_revision_state`：

| 字段 | 含义 |
|---|---|
| `state_id=1` | 单例 |
| `playback_revision` | 成功导入/播放事实变化后递增 |
| `billboard_revision` | aggregate 成功发布或榜单语义变化后递增 |
| `metadata_revision` | 影响搜索文档的名称、项目、身份、署名变化后递增 |
| `settings_revision` | 影响搜索基础语义的服务端 Settings 成功保存后递增 |
| `updated_at` | 诊断时间 |

为 `music_search_snapshot_meta` 增加：

- `semantic_base_key TEXT`；
- `merge_level INTEGER`；
- `dynamic_threshold INTEGER`；
- `builder_version TEXT`；
- 索引 `(semantic_base_key, status, merge_level, dynamic_threshold)`。

旧 snapshot 在 migration 后标记 stale。migration 不重写原始音乐事实；新 snapshot 完成前默认变体
显示 warming/unavailable，不回退到未经证明的 any-local 消费结果。

#### 4.2 指纹 V2

`semantic_base_key` 包含：

- 服务端基础过滤设置；
- `playback_revision / billboard_revision / metadata_revision / settings_revision`；
- active search index revision；
- artist identity revision、track credit revision；
- normalization/index/snapshot/chart builder 版本。

最终 `filter_fingerprint` 为：

```text
sha256(semantic_base_key + merge_level + dynamic_threshold)
```

任何影响播放次数、资格、entity key 或 chart badge 的实现变化都必须提升对应 builder/version 常量。

#### 4.3 失效矩阵

| 事件 | revision | documents | 六变体 snapshot | 触发时机 |
|---|---|---|---|---|
| Streaming import + maintenance 成功 | playback + billboard | rebuild | rebuild | 成功发布后 |
| min/music/merge/gap/Top N/周边界/精选集设置 | settings | 视字段决定 | rebuild | Settings 提交后 |
| aggregate shadow table 发布 | billboard | 不变 | rebuild | 单事务发布后 |
| track group / album project 变化 | metadata | rebuild | rebuild | 版本归并成功后 |
| artist identity revision | metadata | rebuild | rebuild | identity aggregate ready 后 |
| track credit revision | metadata | rebuild | rebuild | credit aggregate ready 后 |
| 名称/主体元数据修订 | metadata | rebuild | rebuild | metadata mutation 后 |
| 仅封面文件下载完成 | 不变 | 不变 | 不变 | cover URL 由稳定 ID 决定 |
| 搜索 normalization/index schema 改变 | metadata + version | rebuild | rebuild | deploy maintenance |

失败或回滚的业务 mutation 不得递增 revision；导入回滚后 revision 与 snapshot 状态必须恢复到备份事实。

### 5. 统计一致性修复

#### 5.1 Billboard 参数贯穿

扩展 `_build_chart_lookup()` 及 Billboard staged/cache 链，使其显式消费：

- `merge_enabled`；
- `include_compilations`；
- 已有的 merge level、动态阈值、最大间隔、三类 Top N、周边界和年份。

`compute_billboard_data()`、`_compute_billboard_data_cached()`、`_load_and_rank*()` 及其 cache key 必须
同时增加 `merge_enabled`，不能只修改函数入口而继续命中旧缓存。`include_compilations` 已存在于 Billboard
计算签名，本轮必须从 search context 传到底。

`merge_enabled=false` 不得读取只代表 merge-enabled 口径的预聚合结果；若当前 aggregate schema 没有
对应维度，就显式走 raw exact 路径。`backend/api/billboard/data.py::_billboard_params()` 也必须传递该值，
避免搜索 snapshot 修正后与 Billboard weekly/data 页面继续分叉。

#### 5.2 播放次数与榜单分别对照权威详情

每个 snapshot item 的验收规则：

- `play_events / total_ms` 对照同口径实体 Stats/Plays；
- `peak_position / weeks_on_chart / power_rank` 对照同口径 Billboard detail；
- 专辑按 album project + canonical artist；
- 艺人按有效署名 fan-out + canonical identity；
- L2/L3 track 使用规范 group 主体和详情真路由；
- 无上下文仍为 `context: null`，不得序列化 0 冒充未加载。

新增精选集 fixture，必须证明 `include_compilations=false/true` 会产生预期差异，且搜索与详情差异完全一致。

#### 5.3 snapshot 发布安全

- 构建前写 `pending/running`，旧 exact-ready snapshot 不得被不同 fingerprint 复用。
- 数据行先写入新 fingerprint，数量、重复 entity key、负数指标、链接主体和 chart 范围验证通过后再 ready。
- 构建失败保存异常类型和阶段，不保存原始查询、实体名称或播放行。
- 每个 base 最多保留当前六变体和上一 base 的六变体；清理不得删除正在被读的 current rows。

### 6. 候选热路径修复

#### 6.1 移除请求内全表 revision 计算

`build_music_search_filter_context()` 改为只读取：

- `music_search_revision_state` 单行；
- `music_search_index_state` 单行；
- identity/credit state 单行；
- Settings 的已解析快照。

`playback_source_revision()` 与 `billboard_aggregation_revision()` 可保留为离线 doctor/审计工具，但不得由
candidates/context GET 调用。目标为 fingerprint phase P95 ≤2ms，查询计划不得出现 `SCAN plays` 或扫描
任一 aggregate 全表。

#### 6.2 eligibility 改为 SQL join

repository 接收 `snapshot_key`，在 FTS/document 查询中 join `music_search_entity_context`，不再先读取
全部 7,581+ eligible entity keys 为 Python set。不存在 exact-ready snapshot 时仍 fail closed。

#### 6.3 相关性、总数和分页下推 SQLite

把稳定排序规则写成 SQL `CASE`：

1. label exact；
2. label prefix；
3. label token；
4. secondary/alias exact 或 prefix；
5. trigram substring；
6. popularity、normalized label、entity key tie-break。

同一 bounded match CTE 分别产生：

- `GROUP BY kind` 的准确总数；
- 当前 kind 的 `ORDER BY ... LIMIT/OFFSET`；
- all 视图每类前 5 条，可使用 window function 或三次有界查询。

不得先把所有命中行构造成 Pydantic 对象后再切片。fallback 继续允许 bounded LIKE，但两字符查询只做
exact/prefix；fallback 必须返回准确状态，不把前 10 条数量冒充 total。

#### 6.4 性能探针升级

固定探针至少覆盖：

- exact；
- prefix；
- 多 token 跨字段；
- 高命中三字符；
- Unicode/NFKC；
- 单字符 CJK；
- 单类型第 2 页。

报告继续只记录 query id、长度、类型和命中数量，不写 raw query 或实体内容。每种 query class 至少
60 个 warm 样本，分别报告 fingerprint、snapshot join、candidate SQL、serialize 和 HTTP total。

### 7. 前端状态与体验修复

#### 7.1 snapshot 状态观察

- 网络错误仍使用 `retry: 0`。
- 当成功响应为 `warming` 或 `stale` 时，候选 hook 使用显式状态轮询：2s 起步，退避至 10s；ready、
  unavailable、组件卸载或页面隐藏后停止。
- Quick Open 关闭后由 TanStack observer 自动取消无观察者请求，不做前缀级 `cancelQueries`。
- `unavailable` 显示“暂不可用”和手动重新检查；private 可提供前往 Settings 维护区的入口，public 只展示
  cache-only 文案。
- 状态刷新期间保留当前可证明的同 fingerprint 候选；不得显示其他变体的 placeholder 数据。

#### 7.2 filter key 与服务端能力对齐

- query key 继续包含 `semantic_base_key + normalized query + kind + page + page size + eligibility`。
- context key 继续包含服务端返回的完整 fingerprint 和排序去重后的 entity key。
- 前端不再发送服务端不接受/忽略的伪参数；`include_compilations` 由服务端 Settings base 决定。
- 切换 merge level 或动态阈值必须形成新 key，并正确显示该变体的 warming/ready，而不是旧结果冒充。

#### 7.3 标准化高亮

`HighlightedSearchText` 使用与 query key 相同的 NFKC、标点和稳定 lowercase 规则，并维护规范化字符到
原始 grapheme 范围的映射；继续输出 React text/`<mark>`，禁止 `innerHTML`。根据 `match_field` 在 label
或 subtitle 中高亮；alias 命中仍可参与排序和诊断，但消费界面不展示“匹配别名”等内部标签。结果名称
与副标题必须跟随全局简繁体偏好，深链和最近查看的持久化值继续保留原始实体数据。

覆盖弯引号、全角 Latin、Unicode 空白、`ß -> ss` 和 CJK 标点；浏览器 locale 不得改变 query key 或高亮。

### 8. 实施阶段

#### R0：先把失败写进门禁（小）

1. 将现有交付报告和原规划状态暂改为 `Partial / remediation pending`。
2. 新增真实维护链路测试：只调用 `rebuild_current...`/snapshot-set builder，不允许测试手工补齐 L1/L3。
3. 固定六变体失败向量、精选集/merge disabled 语义向量和高命中性能向量。
4. 给测试数据库加硬门禁：任何会写派生表/job 的测试若连接真实 `data/spotify_stats.db` 立即失败。

退出条件：新测试在旧实现上稳定暴露本报告的三个根因，且测试本身不改真实主库。

#### R1：revision state 与六变体生命周期（大）

1. migration 34 与 revision helpers。
2. 统一 mutation/maintenance revision bump 和失效矩阵。
3. snapshot meta 增加可诊断维度。
4. 单 job、顺序构建六变体；默认 L2/true 优先。
5. doctor/rebuild script 输出六变体状态、实体数和阶段耗时。

退出条件：新基础设置下六个 fingerprint 都能从 pending/running 进入 ready；任一失败不污染其他变体。

#### R2：统计语义贯穿（大）

1. Billboard 计算与缓存 key 增加 `merge_enabled`。
2. search chart lookup 传递 `merge_enabled/include_compilations`。
3. 六变体 × 三实体对照详情；精选集 true/false、merge true/false 独立覆盖。
4. 提升 search snapshot/chart builder version，禁止旧 snapshot 继续 ready。

退出条件：所有非默认配置一致性 contract 通过，且同一 fingerprint 内没有混合口径。

#### R3：候选热路径收口（中到大）

1. candidates/context 改读持久 revision。
2. eligibility 下推 SQL join。
3. rank、total、pagination 下推 SQLite。
4. 升级性能 probe 和 Server-Timing 门禁。

退出条件：GET 查询计划无 plays/aggregate scan；全部固定 query class 的 warm HTTP P95 ≤80ms，context
P95 ≤20ms，响应 ≤8KiB。

#### R4：前端状态与高亮（中）

1. warming/stale 状态轮询与停止条件。
2. variant key/placeholder 隔离。
3. 标准化高亮和 match field 展示。
4. Quick Open、完整页、Phone、Settings 两个治理消费者回归。

退出条件：切换 L1/L2/L3、动态阈值和输入法时没有空白假结果、旧指标串线或请求风暴。

#### R5：生产与文档收口（中）

1. 全量 unit/contract/frontend/build/pre-commit/OpenAPI。
2. 真实主库只读性能、六变体离线构建时间和磁盘增量。
3. Chromium/Firefox/WebKit 与 360/390/430/768/1024/1280、200% reflow。
4. production backend 镜像 FTS5/trigram、full/showcase/dual、public zero-write。
5. Online Backup、migration 34 升级、旧镜像读取、失败回滚演练。
6. 只有全部门禁通过后，将原规划和交付报告恢复为 `Pass / 已完成`。

### 9. 文件级实施地图

#### 9.1 后端新增

- `backend/domains/music_search/revisions.py`：持久 revision 读取、递增和 base key。
- `backend/domains/music_search/variants.py`：六变体枚举、优先级和 fingerprint 构造。
- `backend/tests/unit/test_music_search_revisions.py`。
- `backend/tests/contract/test_music_search_snapshot_variants.py`。
- `backend/tests/contract/test_music_search_nondefault_consistency.py`。

#### 9.2 后端修改

- `backend/core/migrations.py`：migration 34。
- `backend/domains/music_search/context.py`：移除 GET 内扫描，升级 fingerprint v2。
- `backend/domains/music_search/snapshot.py`：snapshot-set 构建、参数贯穿、逐变体发布。
- `backend/domains/music_search/repository.py`：snapshot join、SQL 排序/总数/分页。
- `backend/services/music_search_candidate_service.py`：传 snapshot key，不再传完整 eligible set。
- `backend/services/music_search_maintenance_service.py`：单 set job、六变体生命周期。
- `backend/services/music_search_service.py`：完整 chart 参数。
- `backend/domains/billboard/chart_compute.py`、`chart_load_rank.py` 及必要 data loader：`merge_enabled`
  贯穿、raw/aggregate 分流与 cache key。
- `backend/api/billboard/data.py`：所有 staged Billboard facade 传递 `merge_enabled`，与详情和搜索共享口径。
- `backend/api/music.py`：支持范围校验、稳定状态响应和日志。
- 导入、Settings、version merge、artist identity、track credits：统一 revision bump/失效 helper。
- `backend/tests/conftest.py`：真实数据库写入硬阻断，而不是只 patch 个别 client fixture。

#### 9.3 前端修改

- `frontend/src/features/music/search/useMusicSearch.ts`：状态轮询、variant placeholder 隔离。
- `frontend/src/features/music/search/api.ts`：只发送受支持参数。
- `frontend/src/api/query-keys.ts`：base/variant key。
- `frontend/src/features/music/search/HighlightedSearchText.tsx`：规范化范围映射。
- `MusicSearchDialog.tsx`、`MusicSearchPage.tsx`、`MusicSearchResults.tsx`：warming/failed/manual check 文案。
- 搜索 hooks/components/flow 测试：六变体、轮询停止、过时响应和高亮向量。

#### 9.4 运维与文档

- `scripts/rebuild_music_search_derived_data.py`：六变体报告与 `--require-all-ready`。
- `scripts/music_search_performance_probe.py`：query class 和 phase budgets。
- `scripts/api_smoke_probe.py`、boundary/parameter audit：unsupported base filters 与状态协议。
- 原规划、交付报告、CHANGELOG、AGENTS/CLAUDE：仅同步成为长期约束的最终事实。

### 10. 验证矩阵

#### 10.1 后端功能与一致性

| 维度 | 必测值 |
|---|---|
| merge level | L1 / L2 / L3 |
| dynamic threshold | true / false |
| merge enabled | true / false |
| include compilations | true / false |
| entity | track / album / artist |
| snapshot | missing / pending / running / ready / stale / failed |
| index runtime | FTS5 trigram / degraded fallback |
| surface | private-admin / public-readonly |

不做 3×2×2×2×3 的盲目笛卡尔积；使用 pairwise 覆盖全部参数交互，同时保留六变体 × 三实体的核心
18 个端到端事实对照。

#### 10.2 前端交互

- composition 期间 0 请求，结束并防抖后 1 请求；
- A 请求晚于 B 返回，UI 仍只显示 B；
- variant 切换不得保留旧 context；
- warming 自动观察 ready，network error 不自动重试；
- URL q/kind/page、Back、Phone autofocus 和滚动恢复；
- Quick Open 无默认选择、方向键、Enter、Escape、Tab trap、focus restore；
- public 不读写 recent localStorage；
- NFKC/弯引号/全角/ß/CJK 高亮仍为安全 React nodes。

#### 10.3 性能与容量预算

| 指标 | 门禁 |
|---|---:|
| fingerprint warm P95 | ≤2ms |
| candidate HTTP warm P50 | ≤50ms |
| candidate HTTP warm P95 | ≤80ms |
| context HTTP warm P95 | ≤20ms |
| candidate/context response | 各 ≤8KiB |
| candidate GET plays/aggregate scan | 0 |
| GET database writes/background jobs | 0 |
| 单 base 同时运行的 snapshot-set job | ≤1 |

初版生产 `linux/amd64` 镜像在真实 Online Backup 副本上的完整构建峰值为 1,569.547MiB，真实服务器
仅有 1,349MiB 可用时被门禁正确拦截。完成变体间 cache/GC 与主播放帧、艺人 fan-out 顺序计算后，
最终同规模六变体为 983,317.824ms（约 16 分 23.3 秒）、峰值 RSS 876.758MiB、数据库增量约
31.43MiB、WAL 0；同一 ready 副本重复校验为 313.549ms 且 DB/WAL 增量为 0。生产门禁据此冻结为
一次性统计冷建为 MemAvailable ≥1,280MiB（峰值之上约 403MiB/46% 余量）；普通发布固定严格复用
统计，使用 ≥640MiB 的候选预算（候选峰值 318.984MiB 的 2 倍以上）。可用磁盘均要求
≥`max(1GiB, DB × 4)`；目标服务器只有在候选版本或统计 fingerprint 实际变化时才执行对应独立维护，
普通新 SHA 只做精确复用校验。

#### 10.4 发布门禁

- `pytest -m unit`、`pytest -m contract`、搜索聚焦和 mutation 失效测试；
- 前端全量 Vitest、production build、目标 ESLint；
- Ruff、format、mypy、detect-secrets、OpenAPI generate/diff/audit；
- production Docker SQLite FTS5/trigram doctor；
- full/showcase/dual config validation；
- public GET 前后逐表/`total_changes`/job count 零变化；
- migration 33→34、Online Backup、旧镜像只读兼容和回滚演练；
- 新 SHA 在明确数据库副本上关闭 startup rebuild，执行自适应 `--require-all-ready`；
- 精确六 fingerprint、migration 36、builder v2、搜索 context orphan=0 与容量门禁；
- 停服后的第二份 Online Backup 必须与预检源一致，否则拒绝替换；
- 失败时 SQLite、镜像 SHA 与 deployment mode 联合回滚；远程结果按 production workflow 判定。

### 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 六变体构建耗时或内存过高 | 只在统计 fingerprint 真实变化时构建；精确 ready 逐变体复用，持久 resume artifact 续建未完成部分；1,280MiB/4× 磁盘门禁继续 fail closed |
| Billboard 增加 merge flag 引发缓存串线 | 所有 facade/staged/LRU key 同步增加参数并加 key-separation test |
| revision 漏接 mutation | 集中 helper、失效矩阵 contract、禁止业务代码直接手写 stale SQL |
| 旧 snapshot 被新代码误读 | fingerprint/builder version v2，migration 后旧 snapshot 统一 stale |
| SQL 排序与 Python 旧排序不一致 | 固定 golden vectors、稳定 tie-break、分页重放测试 |
| 测试再次污染真实主库 | 测试启动时检查 `PRAGMA database_list`，命中真实路径立即 fail |
| public 打开隐式维护能力 | rebuild/prewarm API 不进 public allowlist，公开 GET 逐表零写入 |
| warming 轮询形成请求风暴 | 仅状态响应轮询、2–10s 退避、页面隐藏/卸载停止 |

### 12. 完成定义

只有同时满足以下条件，修复计划才可标记完成：

- [x] 真实维护链路产生六个支持变体，不依赖测试手工补 snapshot；
- [x] L1/L2/L3 和动态阈值开/关的消费搜索均能 ready；
- [x] merge enabled/disabled、精选集 included/excluded 的搜索 badge 与详情一致；
- [x] candidates/context GET 查询计划没有 `SCAN plays` 或 aggregate 全表扫描；
- [x] 高命中、Unicode、分页等全部性能向量满足预算；
- [x] warming/stale/failed、variant 切换和高亮完成浏览器验收；
- [x] public-readonly 保持零写入、零排队、零外部补全；
- [x] 真实主库、生产镜像、三浏览器、三模式和回滚门禁通过；
- [x] 全量测试在隔离数据库运行，没有新增主库 job/generation；
- [x] 原规划和交付报告根据新证据更新，不再提前声明 Pass；
- [x] 生产新 SHA 的副本预建、容量、精确六变体和联合回滚门禁已落地；
- [x] 远程运行状态只按对应 SHA 的 production deployment 记录表述，不以本地镜像代替。
