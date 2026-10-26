# 发行周期剩余项调查与五项交付

原记录日期以文件名及正文为准；2026-10-25至26日按同日同题合并。调查与共用能力交付合为一份记录。原24项建议不是批准清单，最终确认5项生产交付；生产余23、本地余19及Nevermind、The Moment边界继续保留。

当前规则与状态见[文档地图](../README.md)。以下保留分阶段事实；后续补记仍使用原事件日期，失败、局部通过和部署范围分别判断。

## 阅读顺序

- [发行周期剩余24项调查结果](#发行周期剩余24项调查结果)
- [发行周期共用能力、六项目副本验收与五项生产交付](#发行周期共用能力六项目副本验收与五项生产交付)

## 发行周期剩余24项调查结果

原记录：`2026-10-24-release-cycle-remaining24-investigation.md`。

事项：`SS-2026-10-24-001`。最后核验：2026-10-24。状态：**INVESTIGATED / PLAN READY，建议未实施**。

用户要求对24项全部给出建议，不确定项继续调查。本轮正式库以SQLite `mode=ro`及main写入拒绝authorizer读取；未改正式数据、项目成员、歌曲归属、艺人署名、Spotify原始声明、来源绑定、UI或业务代码，未提交、推送或部署。The Moment继续暂缓。上批4项本地应用及验收结论保持，生产仍未应用该4项。

24项现状均与上批正式验收一致，原系统首个阻塞分类仍为粗日期7、来源12、艺人身份5。本轮按实际处理路径改分为：日期补证/冲突审核5、逐曲及版本审核4、发行参照/身份判断9、继续暂缓6。这是建议分组，不是新恢复数量；正式待审仍为24。

### 关键调查结论与前次概括纠正

#### 1. 多人发行并不等于不能作为来源

当前Spotify完整Album署名与逐曲署名显示：

- Olivia的17曲原声带明确列Olivia、Rachel Zegler和Flatland Cavalry；本地Olivia及Rachel身份已解析，仅Flatland Cavalry未解析。
- 中国好声音第3期明确列苏玮、单依纯、傅欣瑶；单依纯身份已解析，另外两位未解析。
- Turning Red明确列Ludwig Göransson和4*TOWN，两者身份都已解析；三首项目成员在完整目录中直接ID匹配。

`AlbumArtistResolver.match()`目前先要求**所有Album署名都解析完成**，才检查目标艺人是否在集合中。因此前两项会被其他艺人的缺失证据连带阻塞。前一轮将这几项概括成“多人发行不能给个人项目使用”过于笼统，应纠正为目标身份判断与来源关系问题。完整艺人集合的规范化仍应保持严格；不能因此把全局canonical集合解析条件直接放宽。

4*TOWN的独立障碍是来源已绑定44511。建议保留该唯一绑定，另外登记仅用于发行证据、限定现项目曲目的参照；同一发行被引用不等于要转移其内部owner。Disney官方公告同时确认三首歌和2022-03-11数字发行范围。[官方公告](https://press.disneyplus.com/news/disney-plus-turning-red-original-song-nobody-like-u-from-billie-eilish-finneas-oconnell)

其余逐曲参与项目也不能将Cast、Disney、影视原声带等标签合并成某个歌手。Cats的Taylor一首、小美人鱼的Daveed两首/Halle两首、轩辕剑的张婧一首、Frozen的Kristen三首均有对应完整目录和有效逐曲署名；建议限定曲目参照，不将完整原声带其他曲目加入项目，不改变每首现有L3归属。

#### 2. 同曲名、相同曲数与ID变化不能替代录音核验

在原30份完整目录基础上，本轮通过现有SpotifyProvider只读查询**181个曲目ID，返回181、缺失0**，保留请求ID、返回ID、ISRC、时长、艺人及所属专辑；没有安装到数据库，未输出凭据。

| 对象 | 实测结果 | 判断 |
| --- | --- | --- |
| Hands All Over | 13个位置的ID全部变化，13组位置ISRC相同 | 可以形成受控版本等价审核候选；不自动合并曲目或重写ID。 |
| THE SHOW | 2个位置的ID变化；其中新旧ISRC不同，分别涉及How You Like That、Lovesick Girls | Track端点读到不同录音身份，尚不能证明等价；不能批准整15曲刷新，也不能直接断言实际音频已被替换。 |
| Spirit | 当前本地13首中11首有来源ISRC对应；Better in Time / Run的Single Mix同名但ISRC及约2.12秒/4.59秒时长均不同 | 不能仅凭同名或相近时长判作同录音。 |
| Who You Are | 5首中4首有ISRC对应；同名Who You Are的ISRC不同，时长相差40ms | 接近时长也不构成等价证明。 |
| Nevermind | 本地13首与当前13曲来源全部有ISRC对应支持 | 原“直接ID匹配0/13”不足以否定关系；可作为录音关联审核依据，不自动改ISRC、L1/L3身份。 |
| Ultraviolence | 本地9首与14曲来源均有ISRC对应支持 | 主要剩独立日期与源day声明冲突，并非没有曲目关系。 |

THE SHOW当前项目仅涉及Gone：原记录、目录候选有相同ISRC，原记录的Track端点所属专辑仍指向现有THE SHOW来源，可单独审阅该曲关系；不能顺带批准其他两处录音变化。[YGEX](https://ygex.jp/blackpink/news/detail.php?id=1091870)确认2021-06-01数字Live音源发行，应与1月演唱会及DVD分开。

#### 3. Hands All Over的核心还包括后加曲，而不仅是日期地区

该项目当前唯一成员是Moves Like Jagger。发行方2010公告给原专辑美国计划日2010-09-21，但[A&M/Octone的2011公告](https://www.prnewswire.com/news-releases/amoctone-releases-new-maroon-5-single-124427793.html)将Moves Like Jagger描述为当时新发行曲，当前13曲来源包含它。不能把2010原版日当作这首歌已在专辑收录的证明。13个ID的ISRC对应解决的是录音关联支持，不解决修订版日期问题。[原专辑公告](https://www.prnewswire.com/news-releases/hands-all-over-highly-anticipated-third-maroon-5-album-produced-by-studio-legend-robert-john-mutt-lange-set-for-release-on-september-21st-2010-93323604.html)

#### 4. 已增加可用的原始日期证据，但要保留用途与地区

- Nevermind：艺人官方时间线明确1991-09-24。当前来源09-26/day仍原样保留，未来应走显式独立日期冲突审核，而非改原声明或换75曲周年版。[Nirvana](https://www.nirvana.com/timelines/)
- Ultraviolence：环球德国明确2014-06-13；Interscope美国原公告明确06-17并逐一列11原曲与3 bonus，和当前14曲顺序一致。建议原项目以DE06-13为候选、US06-17另存地域事实，不称所有数字UPC同日首发。[环球德国](https://www.universal-music.de/lana-del-rey/musik/ultraviolence-209784)、[美国原公告](https://www.prnewswire.com/news-releases/lana-del-rey-announces-june-17-release-of-new-album-ultraviolence-interscopepolydor-uk-259226061.html)
- E=MC²：本轮直接读取环球日本原单CD UICL-1079，2008-04-16、16曲及两首bonus均明确，避开12-17四碟盒。但它不能直接证明当前数字UPC首次日，项目原版与日本16曲版仍须明确口径。[环球日本](https://www.universal-music.co.jp/mariah-carey/products/uicl-1079/)
- Indigo Girls：新增Folk Alley对成员Emily Saliers的原始访谈，2019-02-28节目介绍明确原专辑1989-02-28，可提升原项目日期证据；不能用它证明含1994现场的Expanded版1989首发。[原始访谈](https://folkalley.com/basic-folk-emily-saliers/)
- Aquarium：Scandipop在2017-03-26发布20周年原创回顾，明确斯堪的纳维亚原版1997-03-26。可形成中等证据候选，仍非厂牌原始档案，也不证明当前17曲Special版日期。[周年原报道](https://scandipop.co.uk/aquas-aquarium-is-now-20-years-old-here-are-20-reasons-to-celebrate-it/)
- Frozen：作曲家Christophe Beck官网明确区分电影11-27与唱片11-25，并列出Kristen相关三首。可审原声带2013-11-25锚点，不能替所有59曲附加轨认定首次日。[作曲家官网](https://christophebeck.com/projects/frozen/)

#### 5. 有些“来源不足”需要统计范围决定，继续搜索日期无法代替

Andrew Garfield项目13首中，Come to Your Senses、Green Green Dress、Play Game、Real Life、Come to Your Senses末尾版这5首没有Andrew的有效演唱署名。Sony原17曲发布页也逐曲确认了这些演唱者，数字发行日2021-11-12、CD12-03明确。问题是该13曲项目究竟代表全剧集合还是Andrew个人参与集合；保持当前成员的前提下，不能自动删除这5首或声称它们是Andrew个人演唱。[Sony原公告](https://www.sonymusic.ca/press_release/tick-tick-boom-soundtrack-from-the-netflix-film-directed-by-lin-manuel-miranda-out-today-from-sony-music-masterworks)

ZAYN项目来源是Taylor的46曲官方数字包装，不能只因包含合作曲就当ZAYN个人专辑。Spotify/Apple都写2017-11-09，而Apple版权标2018；2018-11-30是进一步检索得到的发行线索，尚未取得足够直接材料闭合，不能据此自动纠年，也不能按标题含Playlist就自动改类型或隐藏选择器。[对应Apple目录](https://music.apple.com/us/album/reputation-stadium-tour-surprise-song-playlist/1444778002)

#### 6. 三项仍缺可靠的具体日

Gorilla官网只确认May1975；孙燕姿演唱会CD06-07仍主要依赖旧论坛转录，本轮LINE目录另显示2005-02-01，不能替代原CD日；执迷不悔的环球日本页是2024复刻，不能证明原香港02-05。前两项不由月推1日、不把VCD/数字再版日当CD日，后一项继续补原新艺宝CP-5-0091同期档案。[James Taylor](https://www.jamestaylor.com/discography/gorilla)、[LINE目录](https://music-tw.line.me/album/1028460)、[环球复刻](https://www.universal-music.co.jp/faye-wong/products/uijy-75257/)

### 证据与完成边界

本地只读材料：`output/versus-release-cycle-20261024-review24/`中的`current-24.json`、`current-inspection.log`、`track-evidence.json`、`catalog-recording-analysis.json`、`participation-analysis.json`与`recommendations-24.json`。完整目录复用上轮未安装观测，181个录音信息为本轮新读；没有把同ISRC支持描述为新身份批准。代码检查确认现有Client Credentials仅向Provider请求token，未读写正式认证记录。

当前24项逐项建议和未实现程序路线见[处理规划](../plans/release-cycle-data-governance.md)。没有运行正式应用、迁移、全量归属发布、快照重建或界面改造；原始/成员/归属/UI保护继续有效。本轮只对调查文档运行文档审计与差异检查，不把源码检查或网络读资料描述成程序修复已验收。

## 发行周期共用能力、六项目副本验收与五项生产交付

原记录：`2026-10-24-release-cycle-shared-capabilities-acceptance.md`。

事项：SS-2026-10-24-001。日期：2026-10-24。状态：**CLOSED / RELEASED（本批5项）：代码已提交推送并部署，生产自身fresh副本应用4参照/2日期，快照维护、120保护、81HTTP、216指标及原六行双视口通过。生产剩23项、本地剩19项，Nevermind与The Moment继续暂缓。** 下方候选和本地记录均为历史检查点，最新结果见文末生产交付。

用户授权：先修三项共用能力，再在数据库副本验证Nevermind、Ultraviolence、Indigo Girls、Olivia／Hunger Games、单依纯／好声音第3期、4*TOWN／Turning Red；验收后整理正式应用清单。原始记录、项目成员、歌曲归属和UI保持，The Moment继续暂缓。不包含正式数据批准、提交、推送或部署。

### 实现与源码位置

基线 `f65ac8e53f445d0f9e98fc795b3fd10fb811c382`。唯一研发分支 `codex/release-reference-review`，工作树 `/Users/benjaminlei/.codex/worktrees/release-reference-review/202605-SpotifyStats`。主目录继续服务原8000/4173，业务代码没有复制过去；其上批4日期文档及本轮调查文档保留。当前候选没有提交。

1. **目标艺人列名验证**：`AlbumArtistResolver.target_presence()`只以可唯一解析的稳定艺人ID验证目标。无关联合署名未解析不再连带否认已列名目标；目标自身歧义、未列名或无证据仍拒绝。完整 `match()`、`canonical_key()` 和全局艺人归并规则保持严格。发行解析、独立日期审核、逐曲来源审核使用同一目标资格合同。
2. **非占有发行参照**：schema96新增 `album_release_references` 及事件。明确登记项目、完整既有曲目范围、录音ID、Album artist或Track artist关系、日期用途、地区/媒介、证据、目录观测及成员/身份/已发布归属守卫。只接受现有明确Track owner对应，不能凭同名或同ISRC自动关联；既有来源唯一绑定保持，不新增项目成员，也不向L3注入全来源目录。待审记录不参与读取；批准、撤销推进revision，漂移使有效参照失效。显式版别请求不能借用项目参照。
3. **显式日期冲突审核**：普通 `review_assertion()`继续拒绝冲突；独立 `prepare_date_conflict()`／`approve_date_conflict()`记录选定用途、原提供方声明、完整来源集合、成员和归属基线及审核原因。读取仅覆盖审核用途，保留Spotify原声明；原项目和版别日分离。`project_release_correction`拒绝创建读取端仍会拒绝的日期，已有有效独立审核可按同一合同读取。

`review_release_evidence()`使用事务保存点和完整L3前后规划，限定受影响歌曲范围；拒绝未批准目标、原生项目、代表曲目、艺人键或归属类型变化，并保留范围外旧发布。没有自动添加force_target，也没有发布全库新规划。`scripts/preview_release_evidence.py`始终对输入源做Online Backup，只在临时副本迁移和演练，无正式写入开关；已从本地正式库只读输入实际验证。

### 六项目结果与可确认正式清单

下列5项只在副本获批并验收，**仍需用户确认后才能应用正式库**。Spotify原声明全部保持。

| 项目 / ID | 建议发行锚点及用途 | 正式应用的具体动作 |
| --- | --- | --- |
| Olivia／Hunger Games / 42016 | 2023-11-17，当前17曲数字原声带 | 新增现有1首的Album artist参照；不采用11-03单曲来源，不添加其他16首。项目日期不改。 |
| 单依纯／好声音第3期 / 41800 | 2020-09-04，当前8曲数字发行 | 新增现有2首的Album artist参照；不添加其他6首，永不失联的爱现owner44180保持。项目日期不改。 |
| 4*TOWN／Turning Red / 42280 | 2022-03-11，数字原声带 | 新增现有3首的Album artist参照，完整来源仍绑定44511。项目日期不改。 |
| Ultraviolence / 41722 | 2014-06-13，德国原专辑项目日 | 新增现有9首的来源参照，沿用14曲Deluxe来源；独立日期由2014-01-01／未知精度改为该日／day。Spotify的01-01/day不改；不宣称各地区Deluxe数字版都在06-13首发。美国06-17证据不混入此口径。 |
| Indigo Girls Expanded / 41835 | 1989-02-28，原专辑项目日 | 沿用当前12曲来源；独立日期由1989/year补为该日/day。不宣称含1994现场的Expanded版1989首发，不改原曲当前成员或归属类型。 |

具体来源ID、证据链接、曲目ID及守卫保存在私有目录的 `six-candidate-manifest.json`、`guarded-proposals.json`；清单共5个项目、4条参照、2条日期，不能把6次操作误写成6项目通过。

**Nevermind / 42362不进入本批。** 当前13首原始Track ID与安装的Remastered目录13个Track ID均不同，后者在 `spotify_track_owners` 中尚无对应；完整艺人ID及13组ISRC支持不能替代录音关联审核。来源名称也不同于原项目名，原程序未建立可用来源。因此本轮来源参照和日期审核均正确拒绝，保留 `release_source_unconfirmed`。原专辑1991-09-24证据仍保留，未登记成已批准项目日。

后续若处理Nevermind，需要单列13组录音关系的明确审核层，保存真实观测、原/目标ID、ISRC及其他录音证据和完整守卫，仅供该发行参照使用；不写回原Track ID、不自动合并Track owner、不放宽全局同ISRC匹配。完成这一录音关系能力后，再走本轮已有参照及日期审核并重复该项副本门禁。本轮未以特殊白名单或直接重绑填补缺口。

### 验收证据

私有归档：`output/versus-release-cycle-20261024-shared-capabilities/`。真实浏览器材料：`output/playwright/release-shared-20261024/`。代码补丁及新增文件保存于前一目录，长期证据不依赖运行中的候选服务。

- 136项定向回归通过，覆盖目标已列名/歧义、共享绑定、完整曲目范围、Album/Track两类参与、普通日期冲突拒绝、显式批准/撤销、漂移失效、版别分离、批量回滚、幂等及来源纠正读写合同。Ruff与差异检查通过。
- 本地正式源只读Online Backup；117类保护检查通过。96,881条原始播放、3,328项专辑成员、8,383项曲目成员、7,015条已发布歌曲目标/原生归属，以及原始/有效署名、Spotify元数据和声明、唯一来源绑定保持。副本只改变上述2个项目日期和独立审核层；没有修饰原始记录。
- 正式旧版44次HTTP与候选81次HTTP通过，覆盖8配置选择器、发行周期、个人统计/排名、对决结果和逆序请求。TTPD、Showgirl、Title、Christmas及上批4项日期的源、日期和指标保持。The Moment与Nevermind仍分别因粗日期、来源未确认而不可用。
- 单依纯项目原本在L3选择器中不出现；本轮维持原选择器/归属，L2四配置适用。其余4项各8配置适用，共36次比较，独立复算216个指标全部一致，不把不可选范围计为恢复。
- 桌面及390×844手机实际完成5项两批比较，原六行名称、数字、空值及横向页面边界通过。原表仍显示“首发排名／最高排名／发行周播放／艺人影响力／大盘影响力／半数播放距 (周)”，没有新增发行日期行、诊断状态或样式。前端源码与成品未修改。
- 候选运行期间仅在副本完成派生缓存与5个封面任务；原有任务记录保全。原始事实和正式库保护另行复核，不将这些副本运行记录冒充原库完全逐字相同。
- 预演CLI再次从正式源只读备份，6项操作通过，输入库写入为0。审批幂等通过；日期会导致歌曲迁移的合成用例整批回滚。
- Playwright专用session及18824/4184候选服务已关闭；原8000/4173服务未停止。候选工作树保留READY，消费者为下一阶段代码整合和用户确认的正式应用；待整合保存后按项目规则归档。

这只是本任务的候选程序、真实副本和原界面验收，不等于正式库已应用或生产已部署。本地正式剩余仍24项；若本批5项获批并应用，预计余19项，须以应用后的实际审核计数为准。The Moment继续暂缓，上批4日期本地结项保持。

### 用户确认后的本地正式应用与验收

2026-10-24，用户确认采用清单中的5项发行参照、日期及对应适用范围，并授权代码整合、本地正式应用、快照维护及接口/原界面验收。未授权新的录音映射、额外数据治理、Git提交/推送或生产发布。

#### 实际应用

- 12个已验收文件按保存补丁和新增文件白名单整合到主目录，与候选逐字一致；136项定向回归、Ruff和差异检查通过。其余既有文档工作保持，没有前端源码或成品修改。
- 从本地正式库重新做SQLite Online Backup，不复用旧试验库；副本中逐项复验已确认来源、目录、成员、有效身份及已发布归属守卫，与上轮验收方案一致后应用4条参照、2条日期。幂等验证无额外变更。
- Olivia现有1首、单依纯现有2首、4*TOWN现有3首、Ultraviolence现有9首的4条参照已批准；不转移完整来源绑定、不引入其他曲目。Ultraviolence采用德国原项目日2014-06-13，Indigo Girls补原专辑项目日1989-02-28，Spotify原声明保持；其余3项目日期行不改。
- 六套搜索统计、八配置96项榜单发布、音乐详情、默认/包含合辑排名及相关Analysis/Archive/Community/Governance/艺人排名快照维护完成。七库在同文件系统联合切换，路径相关发布重新绑定，2022–2026确定性年度及首页消费者就绪；没有LLM/网络补证或项目成员重建。
- 停服后正式源的全部表与schema再次和fresh基线核对，一致才执行切换。原七库文件inode及首页缓存保留在本轮恢复目录；失败可联合恢复数据与本轮代码，旧失败日志保留。

#### 正式验收

- 117类保护检查通过：96,881条原始播放、3,328项专辑成员、8,383项曲目成员、7,015条已发布歌曲目标/原生归属，原始/有效署名、Spotify原始元数据和声明及唯一来源绑定保持。仅审核登记层及上述2个项目日期在白名单内；外键异常0。
- 新副本和正式环境各81次HTTP通过，旧正式基线44次HTTP保留；各36次适用比较、216个指标独立复算一致。原有TTPD、Showgirl、Title、Christmas及上批4项源/日期/指标保持；原TTPD/Showgirl表格outerHTML与本轮修改前完全一致。
- 八配置全选择器复核只恢复5个获批项目，其他原ready无退化。单依纯仍按原L2四配置范围；未为L3选择器增加成员或改变归属。正式剩余19项：粗日期6、来源未确认8、艺人身份未确认5。Nevermind未批准录音映射，The Moment日期仍2003/year且两首歌曲仍归41962。
- 正式4173桌面和390×844手机两批完成5项实际比较，显示数字与已验证API一致。前端源码及原dist逐字保持，仍为原六行表格，没有发行日期行、内部状态文案、控件或样式修改。
- 专用Playwright会话和18813候选进程已关闭；8000/4173正式本地服务正常。程序已整合并实际运行，尚未提交、推送或部署到生产。

本轮私有证据：`output/versus-release-cycle-20261024-shared-capabilities/local-apply/`，以 `acceptance-summary.json`、`formal-protection.json`、`formal-coverage.json`、`formal-api.json`、`formal-six-metrics.json` 及 `original-pair-dom-proof.json` 为入口。恢复目录为其下 `local-activation/`，保存原七库、原首页缓存、切换journal、停止时全源fence、重新绑定日志及后续消费者保护。浏览器证据在 `output/playwright/release-five-local-20261024/`。源工作树处置另见本轮归档收据，不依赖源目录保存长期证据。

源码收尾：源工作树已通过Codex归档，归档身份为 `/Users/benjaminlei/.codex/worktrees/release-reference-review/202605-SpotifyStats`；源码与主目录逐字一致、补丁及新增文件已另存后移除。源分支仍指向已在main中的基线f65ac8e5，核验祖先关系后删除；当前仅主工作树。此为恢复归档，不是主线Git提交或生产发布。处置收据为本轮 `source-worktree-closeout.json`。

### 用户授权后的提交、生产发布与上线验收

2026-10-24按用户授权完成本轮独立提交、推送、生产应用及定向上线验收。生产运行 `dacdb8629aad889752e899798ad3468860cd9918`，三个容器同SHA且healthy，deployment mode仍为dual。原始记录、项目成员、歌曲归属、Spotify声明和UI保持。

#### 提交和发布范围

- 业务提交 `dacdb862` 采用23文件白名单；相对原生产f153dc9f仅本轮通用能力与Title收口文档，没有其他任务代码。数据库、私有验收材料和前端文件未纳入提交，前端目录相对生产原SHA逐文件无差异。
- 提交前补齐 `LATEST_SCHEMA_VERSION=96` 及合成seed迁移，46项迁移/新能力回归、文档审计和全部hooks通过；合成seed原始事实、成员和归属行保持。原136定向与本地验收证据复用。
- [质量CI 40059332341](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40059332341)、[部署契约40059332349](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40059332349)和[正式Release 40059332342](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40059332342)成功。正式检查为3276单元、578合同、819前端及28部署契约通过，full/showcase/dual三模式通过；既有跳过保留，不能据此声称全站全栈验收。
- Release第1/2次分别因可用磁盘4094/5098MiB低于5347MiB被拒绝，生产未切换。对已关闭副本和备份无损压缩并验证解压字节一致，去除一份与保留归档字节相同的未启用镜像重复件；current/previous原文件恢复点保留。第3次完整门禁成功，未降低容量阈值。失败日志和恢复收据保留。

#### 生产自身受控应用

生产初始为f153dc9f/schema95、28项待审。本批仅应用用户确认的5项目：4条非占有发行参照，41722与41835两条独立原项目日期。地区、媒介与适用范围沿用上方已确认清单；Ultraviolence为德国原项目2014-06-13，Indigo为原专辑1989-02-28，均不冒充各Expanded/Deluxe版别首发日。Spotify原始声明、来源唯一绑定、全部既有成员及歌曲归属保持。

生产新备份的来源/目录/署名/成员/归属守卫与已确认方案一致。4参照、2日期审核的成员变化和归属变化均0，重复应用changed=0。首次切换前全源fence拒绝旧副本：唯一漂移为既有治理快照任务由running到done。取得最新Online Backup后，证明全部其他源表逐字段摘要一致，向候选保留该任务的最新status/updated_at并重新封存完整源基线；没有忽略漂移或丢弃新任务状态。

前批4日期（42144、41610、42108、41913）仍仅本地应用，本次不顺带改生产。Nevermind未建立未经批准的录音映射；The Moment的2003/year及两首歌曲归属保持。

#### 维护、上线事实与原界面验收

- 在生产自身隔离副本准备六套搜索统计、8配置96榜单发布项、四套详情、默认及含精选集的8套排名、6套播放分析，以及社区/档案/治理/艺人排名、2022–2026年度和首页精确快照。七库完整性和外键检查通过，全部默认消费者cache-only读取ready。
- 七库及首页缓存联合切换，保留原文件与切换前后Online Backup。实际运行门禁通过：schema96、搜索4/4、exact/fuzzy/简繁/短CJK、96榜单、详情和默认消费者ready；网关、运行面与端口边界保持。
- 候选及实际接口/浏览器操作后的120类保护事实均通过：96,881条plays、3328条album成员、8383条track成员、7015条发布归属不变；来源绑定、Spotify完整元数据/署名/日期证据、全部其他项目及既有任务保持，新增运行任务0。只允许确认的4参照/2日期登记、审计及必要派生事实变化。
- 81次实际生产HTTP通过，覆盖8配置的适用比较、个人统计/排名/榜单；36次比较的216指标从计数及排名原语独立复算一致。全选择器只恢复41722、41800、41835、42016、42280，其他发行锚点保持，L3不增加单依纯项目。TTPD、Showgirl、Title/Christmas与前批4项的既有生产结果保持。
- 桌面及390×844手机实际完成5项比较，仍为原六行，真实0和空值按原格式显示；没有发行日期行、内部状态文字、控件或样式修改。原TTPD/Showgirl表格outerHTML与上线前逐字相同。手机补核末行可滚动读出，已保存独立截图；专用浏览器会话已关闭。
- 按最终生产事实重新导出、验证并安装同SHA的Billboard、详情及默认排名标准manifest，旧清单另存恢复目录。一次维护端读取未命中年度行的失败保留；生产内48个年度精确键全部可读，生产容器内只读导出96项的digest与候选一致，未重建正式榜单或修改正式事实。

外部入口补验：HTTPS展示入口health 200、public-readonly能力与dacdb862一致；额外81次展示入口HTTP及8配置结果与私有网关逐项一致。私有网关实际页面通过SSH隧道验收，但配置中的Tailscale私有域名在本机及服务器均未解析，直连HTTPS检查未通过，不能标成全部外部入口通过。未修改域名、Tailscale或其他网络配置；该外部条件独立核查，不混入本批代码和数据修复。

生产剩23项：粗日期10、来源未确认8、艺人身份未确认5；本地剩19项。差异为前批4日期尚未包含于本次生产应用。本批共用能力及5项交付收口，剩余证据治理独立处理，不重开本功能或UI范围。

私有生产证据：`output/versus-release-cycle-20261024-shared-capabilities/production/`，以 `release-result.json`、`formal-api.json`、`formal-six-metrics.json`、`formal-coverage.json`、`formal-protection.json`、`original-pair-dom-proof.json` 和最终收口收据为入口。浏览器截图位于 `output/playwright/release-five-production-20261024/`。服务器操作目录为 `/opt/spotify-stats/backups/versus-release-cycle-five-20261024/`；原七库及首页在 `originals-*`，Online Backup和旧清单在 `recovery/`。无损压缩以逐份往返校验收据为准；恢复时先解压到独立目录，七库/首页/旧清单按同一恢复点联合处理，不能只回退一个数据库。可再生成材料留于tmp，完成后按已有48小时规则清理；原文件恢复点沿current/previous轮转。
