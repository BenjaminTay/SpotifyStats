# 发行周期剩余24项调查结果

事项：`SS-2026-10-24-001`。最后核验：2026-10-24。状态：**INVESTIGATED / PLAN READY，建议未实施**。

用户要求对24项全部给出建议，不确定项继续调查。本轮正式库以SQLite `mode=ro`及main写入拒绝authorizer读取；未改正式数据、项目成员、歌曲归属、艺人署名、Spotify原始声明、来源绑定、UI或业务代码，未提交、推送或部署。The Moment继续暂缓。上批4项本地应用及验收结论保持，生产仍未应用该4项。

24项现状均与上批正式验收一致，原系统首个阻塞分类仍为粗日期7、来源12、艺人身份5。本轮按实际处理路径改分为：日期补证/冲突审核5、逐曲及版本审核4、发行参照/身份判断9、继续暂缓6。这是建议分组，不是新恢复数量；正式待审仍为24。

## 关键调查结论与前次概括纠正

### 1. 多人发行并不等于不能作为来源

当前Spotify完整Album署名与逐曲署名显示：

- Olivia的17曲原声带明确列Olivia、Rachel Zegler和Flatland Cavalry；本地Olivia及Rachel身份已解析，仅Flatland Cavalry未解析。
- 中国好声音第3期明确列苏玮、单依纯、傅欣瑶；单依纯身份已解析，另外两位未解析。
- Turning Red明确列Ludwig Göransson和4*TOWN，两者身份都已解析；三首项目成员在完整目录中直接ID匹配。

`AlbumArtistResolver.match()`目前先要求**所有Album署名都解析完成**，才检查目标艺人是否在集合中。因此前两项会被其他艺人的缺失证据连带阻塞。前一轮将这几项概括成“多人发行不能给个人项目使用”过于笼统，应纠正为目标身份判断与来源关系问题。完整艺人集合的规范化仍应保持严格；不能因此把全局canonical集合解析条件直接放宽。

4*TOWN的独立障碍是来源已绑定44511。建议保留该唯一绑定，另外登记仅用于发行证据、限定现项目曲目的参照；同一发行被引用不等于要转移其内部owner。Disney官方公告同时确认三首歌和2022-03-11数字发行范围。[官方公告](https://press.disneyplus.com/news/disney-plus-turning-red-original-song-nobody-like-u-from-billie-eilish-finneas-oconnell)

其余逐曲参与项目也不能将Cast、Disney、影视原声带等标签合并成某个歌手。Cats的Taylor一首、小美人鱼的Daveed两首/Halle两首、轩辕剑的张婧一首、Frozen的Kristen三首均有对应完整目录和有效逐曲署名；建议限定曲目参照，不将完整原声带其他曲目加入项目，不改变每首现有L3归属。

### 2. 同曲名、相同曲数与ID变化不能替代录音核验

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

### 3. Hands All Over的核心还包括后加曲，而不仅是日期地区

该项目当前唯一成员是Moves Like Jagger。发行方2010公告给原专辑美国计划日2010-09-21，但[A&M/Octone的2011公告](https://www.prnewswire.com/news-releases/amoctone-releases-new-maroon-5-single-124427793.html)将Moves Like Jagger描述为当时新发行曲，当前13曲来源包含它。不能把2010原版日当作这首歌已在专辑收录的证明。13个ID的ISRC对应解决的是录音关联支持，不解决修订版日期问题。[原专辑公告](https://www.prnewswire.com/news-releases/hands-all-over-highly-anticipated-third-maroon-5-album-produced-by-studio-legend-robert-john-mutt-lange-set-for-release-on-september-21st-2010-93323604.html)

### 4. 已增加可用的原始日期证据，但要保留用途与地区

- Nevermind：艺人官方时间线明确1991-09-24。当前来源09-26/day仍原样保留，未来应走显式独立日期冲突审核，而非改原声明或换75曲周年版。[Nirvana](https://www.nirvana.com/timelines/)
- Ultraviolence：环球德国明确2014-06-13；Interscope美国原公告明确06-17并逐一列11原曲与3 bonus，和当前14曲顺序一致。建议原项目以DE06-13为候选、US06-17另存地域事实，不称所有数字UPC同日首发。[环球德国](https://www.universal-music.de/lana-del-rey/musik/ultraviolence-209784)、[美国原公告](https://www.prnewswire.com/news-releases/lana-del-rey-announces-june-17-release-of-new-album-ultraviolence-interscopepolydor-uk-259226061.html)
- E=MC²：本轮直接读取环球日本原单CD UICL-1079，2008-04-16、16曲及两首bonus均明确，避开12-17四碟盒。但它不能直接证明当前数字UPC首次日，项目原版与日本16曲版仍须明确口径。[环球日本](https://www.universal-music.co.jp/mariah-carey/products/uicl-1079/)
- Indigo Girls：新增Folk Alley对成员Emily Saliers的原始访谈，2019-02-28节目介绍明确原专辑1989-02-28，可提升原项目日期证据；不能用它证明含1994现场的Expanded版1989首发。[原始访谈](https://folkalley.com/basic-folk-emily-saliers/)
- Aquarium：Scandipop在2017-03-26发布20周年原创回顾，明确斯堪的纳维亚原版1997-03-26。可形成中等证据候选，仍非厂牌原始档案，也不证明当前17曲Special版日期。[周年原报道](https://scandipop.co.uk/aquas-aquarium-is-now-20-years-old-here-are-20-reasons-to-celebrate-it/)
- Frozen：作曲家Christophe Beck官网明确区分电影11-27与唱片11-25，并列出Kristen相关三首。可审原声带2013-11-25锚点，不能替所有59曲附加轨认定首次日。[作曲家官网](https://christophebeck.com/projects/frozen/)

### 5. 有些“来源不足”需要统计范围决定，继续搜索日期无法代替

Andrew Garfield项目13首中，Come to Your Senses、Green Green Dress、Play Game、Real Life、Come to Your Senses末尾版这5首没有Andrew的有效演唱署名。Sony原17曲发布页也逐曲确认了这些演唱者，数字发行日2021-11-12、CD12-03明确。问题是该13曲项目究竟代表全剧集合还是Andrew个人参与集合；保持当前成员的前提下，不能自动删除这5首或声称它们是Andrew个人演唱。[Sony原公告](https://www.sonymusic.ca/press_release/tick-tick-boom-soundtrack-from-the-netflix-film-directed-by-lin-manuel-miranda-out-today-from-sony-music-masterworks)

ZAYN项目来源是Taylor的46曲官方数字包装，不能只因包含合作曲就当ZAYN个人专辑。Spotify/Apple都写2017-11-09，而Apple版权标2018；2018-11-30是进一步检索得到的发行线索，尚未取得足够直接材料闭合，不能据此自动纠年，也不能按标题含Playlist就自动改类型或隐藏选择器。[对应Apple目录](https://music.apple.com/us/album/reputation-stadium-tour-surprise-song-playlist/1444778002)

### 6. 三项仍缺可靠的具体日

Gorilla官网只确认May1975；孙燕姿演唱会CD06-07仍主要依赖旧论坛转录，本轮LINE目录另显示2005-02-01，不能替代原CD日；执迷不悔的环球日本页是2024复刻，不能证明原香港02-05。前两项不由月推1日、不把VCD/数字再版日当CD日，后一项继续补原新艺宝CP-5-0091同期档案。[James Taylor](https://www.jamestaylor.com/discography/gorilla)、[LINE目录](https://music-tw.line.me/album/1028460)、[环球复刻](https://www.universal-music.co.jp/faye-wong/products/uijy-75257/)

## 证据与完成边界

本地只读材料：`output/versus-release-cycle-20261024-review24/`中的`current-24.json`、`current-inspection.log`、`track-evidence.json`、`catalog-recording-analysis.json`、`participation-analysis.json`与`recommendations-24.json`。完整目录复用上轮未安装观测，181个录音信息为本轮新读；没有把同ISRC支持描述为新身份批准。代码检查确认现有Client Credentials仅向Provider请求token，未读写正式认证记录。

当前24项逐项建议和未实现程序路线见[处理规划](../plans/2026-10-24-release-cycle-remaining24-resolution.md)。没有运行正式应用、迁移、全量归属发布、快照重建或界面改造；原始/成员/归属/UI保护继续有效。本轮只对调查文档运行文档审计与差异检查，不把源码检查或网络读资料描述成程序修复已验收。
