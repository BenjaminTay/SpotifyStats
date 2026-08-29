# 音乐查找方向重新指引：轻量候选索引与统计快照解耦

> 创建日期：2026-08-16
> 状态：`SUPERSEDED`；阶段 A–E 的历史验收保留，当前实现与维护边界由 2026-08-28 零停机方案、对应交付报告和 reference 文档接管，本文已归档
> 适用范围：Masthead Quick Open、`/music/search`、候选索引、搜索统计、模糊匹配、简繁体匹配与生产发布
> 关联文档：`2026-08-16-music-search-performance-and-experience-optimization-plan.md`、`2026-08-16-music-search-remediation-plan.md`、`2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md`、`../../reports/2026-08-16-music-search-optimization-delivery.md`

> 2026-08-28 补充：候选/统计解耦的方向不变；“统计 snapshot 未 ready 时阻断候选”、candidate
> serving/building 状态混用、曲目署名 revision 竞态和无差别全局重建已完成修复。当前实现与验收以
> `2026-08-28-music-search-zero-downtime-and-metadata-delta-plan.md` 及对应交付报告为准。

## 0. 结论

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

### 0.1 当前实施进度（更新于 2026-08-17）

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

## 1. 为什么曾经需要提前计算

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

## 2. 当前方向的问题

### 2.1 两类不同数据被过度耦合

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

### 2.2 每个新 SHA 都可能付出完整冷构建成本

旧生产流程对新 SHA 在 Online Backup 副本执行完整索引与六变体 one-shot。即使只修改前端、部署
脚本或查询匹配逻辑，也可能生成新的索引 generation 和 semantic base，从而重新计算全部统计。

当前真实规模的本地 `linux/amd64` 实测：

- 完整六变体约 16 分 23 秒；
- 峰值 RSS 约 876.758MiB；
- SQLite 净增加约 31.43MiB；
- 低配生产服务器第一次 60 分钟窗口内仍未完成。

这证明当前发布成本主要来自六套统计计算，不是名称检索本身。

### 2.3 超时后缺少可复用进度

旧路径的六个变体虽逐个发布到工作副本，但工作副本属于单次临时发布目录。workflow 超时或被取消后，
下次发布仍可能从头开始，已经完成的变体不能安全复用。

### 2.4 镜像跨境上传是另一条独立慢路径

搜索重建之外，旧 workflow 还要求 GitHub 托管 runner 直接向 TCR 上传全部镜像层。搜索加入 OpenCC
和新后端代码后首次出现新层，暴露了这条链路对少数大层的长期停滞；即使拆层和串行上传，固定剩余
层仍会超时。因此部署变慢与搜索改动有时间相关性，但不是“搜索查询本身拖慢 Docker push”。最终
方案将 GitHub 到生产机的传输与生产机到 TCR 的发布分开，并以内容寻址 blob 复用消除重复整包传输。

## 3. 新的目标架构

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

### 3.1 候选层

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

### 3.2 统计上下文层

统计层只负责：

- 当前精确过滤口径下的播放次数和总时长；
- 个人 Billboard 的 `PK #`、在榜周数和走势排名；
- L1/L2/L3 × 动态阈值开/关六个产品支持变体；
- ready/warming/stale/failed 状态和 builder version；
- 按稳定 `entity_key` 与候选合并。

统计未就绪时，候选仍可显示和打开详情；界面不得把“尚未加载”伪装成 0。

### 3.3 两套独立版本与指纹

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

## 4. 模糊搜索方向

模糊匹配必须分层排序，不能让低可信结果压过正确结果。推荐顺序：

1. 原文完全匹配；
2. 标准化后完全匹配；
3. 前缀匹配；
4. 子串匹配；
5. 别名匹配；
6. 简繁体转换匹配；
7. 有限拼写容错。

### 4.1 标准化

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

### 4.2 有限拼写容错

不对全部实体逐条计算编辑距离。推荐流程为：

1. 用 FTS5 trigram 召回一个有界候选池，例如前 30–50 条；
2. 只对候选池计算字符级相似度或有界 Levenshtein distance；
3. 查询长度不足时关闭强容错，避免单字母或单汉字产生大量误匹配；
4. 对完全匹配、前缀和别名设置不可被模糊分覆盖的排序上限；
5. 返回 `match_type=fuzzy`，用于测试、排序和内部诊断，不在普通搜索结果中直接展示。

拼音、同音字和语义联想不进入第一阶段。它们误匹配率更高，应在真实查询样本证明必要后作为独立
能力评估。

## 5. 简繁体中文匹配方向

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

## 6. 重建与发布决策矩阵

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

## 7. 性能、空间与体验预算

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

## 8. 分阶段实施顺序

### 阶段 A：先解耦重建语义

状态：已完成并通过生产复用验收。

- 从 `statistics_fingerprint` 移除随机 index generation ID；
- 引入独立、确定性的 `candidate_index_version`；
- 保持现有 `entity_key` 和 candidate/context API 响应兼容；
- 补充“只改前端/部署脚本不重建”“只改索引不重建统计”的契约测试。

退出条件：同一数据与 builder 下的新 SHA 只校验 ready 数据，不产生新六变体。

### 阶段 B：发布复用与断点续建

状态：已完成。一次性引导成功续建六变体；正常发布精确复用并在 2 秒内完成搜索预检。

- 让工作副本或可恢复派生 artifact 按 semantic base 保存进度；
- 每个变体独立校验、发布和复用；
- workflow 取消后清理运行容器，但保留经过验证的可续建数据；
- 加入每变体耗时、峰值资源和复用原因报告。

退出条件：中断后只计算未完成或已失效的变体。

### 阶段 C：简繁体匹配

状态：已完成并纳入生产只读语义门禁。

- 后端统一查询扩展；
- 原文、简体、繁体去重和排序；
- 单字/双字 CJK fallback；
- 前后端标准化、高亮和 IME 回归测试。

退出条件：代表性简繁查询双向可找、无名称改写、无六快照重建。

### 阶段 D：有限模糊搜索

状态：已完成并纳入生产只读语义门禁。

- trigram 有界召回；
- 候选池内编辑距离重排；
- 长度阈值、误匹配上限和 match type；
- 用真实但非敏感查询集合评估召回率、准确率和 P95。

退出条件：拼写轻微错误可找回目标，完全/前缀结果不被模糊结果压制，性能仍在预算内。

### 阶段 E：生产门禁与文档收口

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

## 9. 必须保留的现有成果

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

## 10. 非目标

- 当前数据规模不引入 Elasticsearch、Meilisearch、Redis 或外部搜索 SaaS；
- 不使用 LLM 推断实体、简繁体、拼音或别名；
- 不为了缩短部署而恢复搜索请求内的 lifetime/Billboard 同步计算；
- 不用不受控的 `%LIKE%` 扫描替代索引并宣称完成模糊搜索；
- 不因统计 warming 隐藏所有候选或把未知统计展示为 0；
- 不以降低完整性、orphan、公开只读或回滚门禁换取发布速度。

## 11. 最终判断标准

新方向是否成功，不以“增加了模糊搜索开关”判断，而以以下结果判断：

1. 用户能快速找到名称、别名、简繁体和轻微拼写错误对应的本地实体；
2. 候选可立即点击，统计按精确口径渐进补齐；
3. 名称匹配规则变化不会无故重算六套播放/Billboard 统计；
4. 只有数据或统计语义变化才承担六变体成本；
5. 普通前端和部署脚本发布恢复为轻量校验路径；
6. 所有复用、重建和失败决定都有版本、revision、报告和回滚证据。
