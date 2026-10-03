# 专辑目录与艺人证据：生产交付

> 事项：SS-2026-09-24-001 / SS-2026-09-24-002；2026-10-03。
> 固定发布版本：`daf098ca035b5c587bb544a0ef0fb6c572514a98`；业务代码等于本地完整验收的 `8464ffa635745ccb57e08c82002be7d484e10d63`。
> 状态：已提交并推送业务、CI及正式发布成功、生产迁移/限定维护/HTTPS专项完成；全栈范围Partial。
> 本报告登记独立的生产备份、限定维护和线上验收；不改写此前本地报告的历史边界。

## 调查与数据合同

Album 缓存的 Earth, Wind & Fire、Tyler, The Creator 是真实含逗号样本；旧验证拆分名称会误拒绝。JOLIN provider 身份由已有人工治理解析至 canonical Jolin Tsai。发行周期原失败放行路径也已修正。Album 同名不同 Spotify ID 的实际误关联、同一 ID 历史改名未得到真实样本证明，相关边界由合成测试覆盖，不能把 Track 同名样本当成 Album 对账结果。

独立保存 `spotify_album_credit_sets`、`spotify_album_artist_credits` 和追加的 `spotify_album_credit_events`：Album 主体、Spotify artist ID、来源名称、从零开始的署名顺序、来源与观察信息、内容指纹及审计。解析复用现有外部身份与 canonical 人工治理；名称用于展示，顺序不表示 primary/featured。无法唯一解析保留 unresolved/ambiguous，不创建或按名称合并艺人。缺字段、请求失败及身份集合冲突保留上一可靠结果。严格验证要求稳定身份，旧名称兼容明确为 legacy。

主刷新、补取、发行周期与封面脚本共用写入合同；发行周期、Billboard/Album Project 元数据筛选、自动归并与 Records 可信原版判断使用对应证据。Album 不替代 Track 有效署名，不改变播放贡献，不恢复隐藏前端入口。完整目录与发行位置使用独立证据，未知位置不借另一发行推断。最终规则见[元数据参考](../reference/music-metadata-management.md)，代码及完整本地门禁见[最终集成报告](2026-10-03-album-metadata-final-integration.md)。

## 生产源与有界维护

生产原版本 `814ea7cb8cdeec4f8ae7d80f58373e00ecb0a97e`，dual，schema 85。Online Backup 为 `/opt/spotify-stats/backups/spotify-stats-pre-album-daf098ca-20261003-production.db`，444,588,032 字节，SHA-256 `529fb30f8082cf44cf2e1f9384975c8b7bcab74a31beec045275897471d58869`，integrity ok。最终停服保护点 `spotify-stats-pre-album-quiescent-daf098ca-retry2.db` 与其完整哈希相同，证明正式切换前源未漂移。

实际生产选样：47 个目录缺口（12 partial / 35 missing）、3 个 50 首完整边界及5个位置样本，去重后维护54个发行；Album 艺人选择当前消费者所需发行与上述样本的并集154个。Taylor 发行周期来源链为94个发行。没有全库采集或填满无关旧位置。

使用两份现有维护 CLI 在新副本完成：目录54 complete，艺人两个批次分别100/54，最终154份证据集、177条有序艺人、154条审计与54份目录/位置证据；请求失败与拒绝均0。5个发行重复读取 unchanged=5、observed/changed/rejected/failed=0。迁移86 `album_metadata_semantic_revisions`、87 `spotify_album_tracklist_evidence`、88 `spotify_album_artist_credit_evidence` 连续升级85→88并重复执行，旧记录保持可读。

审核增量只更新54份既有 Album 元数据并写入上述4张证据表，安装前核对154个来源元数据及35类保护事实。增量文件 SHA-256 `07d7d46d6c316b12ae555ef61904ab229b144a1c8f04f8513dbb1eb10f688632`。正式维护从新的停服 Online Backup 构造目标、验证后原子安装；没有用早期副本覆盖可能的新播放。旧镜像先证明可读增量 schema，再恢复健康，随后由既有流水线发布固定新版本。

生产原始与治理事实前后逐行指纹相同：plays 94,760、tracks 10,026、raw track_artists 10,496、自动署名8,970、人工覆盖34、有效署名11,789；项目/成员、人工关系、Track provider 身份与周榜等共35类均保持。这里使用生产实测值，不复用本地旧署名数量。主目录本机数据库仍schema81，未写入。

源库已有60,294条搜索派生 FK orphan：weekly chart context 60,270、year-end meta 20、year-end projection state 4。排序后的 FK 集合哈希 `d02726a739ee47501e34b8042ce5939ea795fc5344cbf6eabc2befd322a29fdd` 在源、维护副本和线上保持；没有新增 Album FK 错误，也没有清理该遗留问题。当前精确快照读取门禁另行检查，不能将本轮生产 FK 说成0。

## 消费者与发布证据

副本 Records 事实及1,413个原版 membership 结果相同；自动归并候选仍0，strong evidence 1,311→1,310，incomplete 跳过1→0、身份 unresolved 跳过新增2，属于保守证据判断，未批准归并。Lana 181：A&W Disc1/Track4，标题曲 Disc1/Track2；Mimi 147/243：14共享、6独占，发行位置来自各自完整列表。Taylor94个来源经现有发行组去重，消费结果71个发行。选样并集中的96个发行可稳定验证为Taylor，这与94个消费来源、71个去重结果是不同口径。

13个 Album 的证据集共24条艺人行，其中17条未解析；包括 Various Artists、古典/剧组身份与 Cats。JOLIN 映射为canonical532，未批准新身份或关系，不将 Cats 内Taylor歌曲署名当作其Album艺人。

四个当前受支持精确搜索变体以 `--statistics-reuse-only --require-all-ready` 在副本重复确认 ready/repeat-safe；旧镜像亦验证兼容，没有全局统计冷重建。年度内容版本为 `yearly_review_v2_19_album_evidence`。旧镜像启动会按旧合同重置 Analysis revision epoch，因此早期副本年度键与线上不一致，安装保护已拒绝旧结果；最终年度结果须在新代码启动后按实测修订准备，不手改缓存键。

固定版本交付分支质量[37111786346](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37111786346)及生产合同[37111786326](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37111786326)成功。主线发布[37126148736](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37126148736)，独立质量[37126148783](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37126148783)，主线发布 attempt2 与独立质量均 success；质量、full/showcase/dual、linux/amd64镜像、私有CAS传输、TCR digest-pull、健康及CAS保留均完成。线上三容器为固定daf098ca、healthy，dual/public，Backend不暴露宿主端口，Web仅127.0.0.1:3001/3002。

生产digest：API `sha256:fd443fd2432d38d6b7f86403e3a53beec7c533ec430383fe9d88a481cb8887e0`，Web `sha256:01ad917c18f8b7d3aafe672f029ef186d60ab89d661f1bd74907158e0b681314`。发布preflight可用内存2,132MiB、要求640MiB，未降低门槛；统计复用，当前entity context orphan0，未混同全库遗留FK。

### 线上消费者发现的增量遗漏与补齐

初次线上Mimi比较为空，缺口为此前目录维护新增的简化曲目名称未纳入首次受控增量；不是原始歌曲或署名缺失。对缓存副本重新清点：54个已选发行中43个发行涉及1,175条新增 `spotify_track_meta`，全部没有本地 tracks/播放；另17条既有名称变化未安装，保留原有行。

新 Online Backup 副本只插入这1,175条缺失 provider 元数据，验证35类事实、FK集合、Lana/Mimi、71个Taylor消费发行、1,413个membership及四变体reuse-only通过。正式事务再次确认所有ID仍缺失、仍属于已选完整目录且没有本地歌曲，再原子插入；不更新既有行，不新增Track艺人证据或署名。补充保护点 `album-stage-daf098ca/supplement-pre-live.db` SHA-256 `207427c0588dcc8d0ec33b64db5aaea14c6f77befdeb2e800836291135f08fad`。

重启Backend清除进程缓存，正式verify通过（schema88、4/4 ready、当前entity context orphan0、exact/fuzzy/CJK/short-CJK语义门禁通过）；线上服务函数再次证明Mimi14共享/6独占、Lana位置和Taylor结果，membership与审核副本逐项完全相同。原始及治理事实仍一致。

### 年度缓存

按新代码最终源在副本生成2026确定性V2，106.375秒，内容版本 `yearly_review_v2_19_album_evidence`，未调用LLM。补充元数据后再次按线上源准备并确认精确键 `5e38e39efc07eee4b1d6cddd2f347063113f9ad1e509e48b2a0fe0f8973e6faf`、filter `89a0533217853760298beda8c86b2d4a50c52efccdf67d9b1d4a480bb2a18997` 和来源修订 `ef33805afcfe92bab904fc8ae92bb49f9f340458edf3b519da3521ed70ff852b:album:f3fe65cb874322bab9cd` 完全匹配后安装。只写年度派生sidecar的2026新键及实际namespace的prepared-key，保留其他年份/旧键。

sidecar Online Backup `spotify-stats-pre-album-yearly-cache-daf098ca.db` SHA-256 `0815392045ab066fbd37dab128416da9f30d45e806231768bd0acda2a72c91f9`；安装后缓存读取ready。旧代码阶段生成的不同修订缓存没有发布。

### 实际 HTTPS 专项

`/api/runtime/capabilities`、Glee project43076摘要、Records及2026年度V2均200；公开设置写入和年度prewarm均403，隐藏版本比较仍404。Glee旧摘要已声明106首，问题是目录只存前50，不能称为声明总数50→106。新详情同时显示发行106/已听1。

Records前后只有4项变化：`meta.generated_at` 和 `snapshot.request_key/source_revision/target_revision`；逐项排除这些必要修订字段后其余响应完全相同，没有把整个snapshot删掉再比较。第一次重启后的Glee摘要59.080秒，已记录为冷态，不计热请求通过；随后热态Glee0.484、Records0.528、年度1.400秒。不是生产默认完整全栈或全部API性能门禁。

### 实际浏览器

实际HTTPS Chromium 1440×1000 / 390×844：Glee发行106/已听1、Records探索页Midnights86次完整回放，两端同一统计事实。合作曲排行Taylor/Sabrina为独立链接，中点与完整署名保留，两个视口分别实际点击Sabrina进入其艺人详情后返回；没有嵌套链接或横向溢出。最终浏览器console0错误/0警告。

合作曲区域抽样可见封面14个Desktop、6个Phone均加载成功，使用160px `thumb.webp`；Glee Desktop命中320px、Phone命中640px，Sabrina Phone命中320px WebP，无上述可见样本坏图，保留尺寸/DPR策略。Records手机首次resize后的全DOM测量有4张待加载图片，不能登记为4张坏图或全部离屏图片已经验收；随后以可见区域完成解码核验并保存截图。合作曲两端截图已实际检查，Glee/Records/Sabrina截图另保存；本轮实际消费覆盖160/320/640px，完整三档补建数量仍见封面报告。

浏览器属于生产专项通过，默认完整全栈范围标为Partial；未模拟登录、调用LLM、验证OAuth或物理手机。页面隐藏发行档案与艺人生涯的边界保持。

## 失败记录与回退

首次维护辅助脚本中 compose oneoff 消费了 SSH 脚本 stdin，Backend 停止后脚本提前结束，未切数据库，已恢复旧服务。第二次副本文件权限不足，保护流程拒绝安装并恢复旧服务，正式库仍未切换。修正仅限本任务新副本权限和 oneoff stdin；第三次完整运行成功。维护存在服务暂停，失败日志保留，不能登记为零停机。

旧版本镜像及schema85保护点保留；既有发布流程负责固定SHA、CAS缺块传输、三模式门禁、快照复用、健康检查与数据库/镜像/模式联合回滚。HTTPS/Tailscale、公网端口及入口身份边界保持。自动发布前备份另为 `spotify-stats-pre-release-daf098ca035b-20261003T135058Z.db`（schema88）；如需回到维护前schema85，使用前文独立停服保护点与814ea7cb镜像联合恢复，不把发布后备份当作维护前备份。

## 证据范围与后续

本轮是生产专项验收；完整本地八阶段PASS来自同业务代码的 `20261003T070853.211207Z-f917b9718886`，不是在生产重跑的默认全栈。真实手机、生产LLM和OAuth未由本任务验收。

发布 attempt 1 在容器集合恒定检查处失败：本任务并行年度缓存 oneoff 在传输期间结束，before/after 差异仅该临时容器，正式三容器与其他应用保持。未进入 deploy，旧服务健康。保留失败记录，停止 oneoff 并重跑同SHA失败发布任务，不修改或跳过门禁。

原始数据库、选择清单、增量、消费者响应、保护指纹、维护日志和Actions记录保存在ignored `output/album-production/`；线上浏览器证据保存在ignored `output/playwright/album-production/`，不提交真实数据、密钥或截图。服务器备份及回退镜像保留。
