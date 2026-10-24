# 发行周期28项审核与4项日期本地应用

事项：`SS-2026-10-23-002`。最后核验：2026-10-24。当前状态：**4项日期已按确认范围应用到本地正式库，并完成快照、接口及原UI验收；剩余24项暂缓，未提交、推送或部署生产**。

以下至“用户确认后的本地正式应用与验收”之前保留应用前的只读审核记录；当前应用结果见文末。

本轮范围为本地正式库中剩余28个选择器条目。正式库只用 SQLite `mode=ro` 连接，authorizer 拒绝 main 写入；日期登记、审核和归属门禁仅在同一连接的 TEMP 影子表预演，结束回滚。没有修改原始记录、Spotify原始声明、主来源绑定、项目成员、歌曲归属或UI，没有提交、推送、部署。前轮发行周期与Title生产结项保持 CLOSED。

## 结论与数量

- 当前28项全部复核：粗日期11、来源未确认12、艺人身份未确认5。与前轮29项基线相比，仅Title已按前轮确认恢复；旧可解析条目无新增退化。
- 30份当前Spotify完整目录已重新只读获取，缺失0；日期与精度均未漂移。两份目录的曲目ID数组发生变化，数量各自仍为15、13，不能用相同曲数冒充目录一致。
- 下一批可确认的是**4项独立原专辑日期**，沿用现有来源，无新增/更换主来源提案。其余24项暂缓。正式未应用，所以当前剩余仍为28；未来确认并成功应用这4项后才预计降至24。
- TEMP联合预演：4个项目 / 8种选择器 / 32次出现恢复解析，原ready退化0；已发布7015条歌曲owner变化0，归属门禁的其他语义检查通过。28条规划解释随日期变化，不将其描述为全部解释文本不变，也没有发布新全库规划。

## 下一批4项可确认日期

所有日期均为 `original_release`，不宣称具体扩展版、附加曲或后续再版都在该日首次发行。表内Spotify来源仍保留原有year声明，独立证据只补充项目原始日及有效读取。

| ID / 项目 | 现有来源（保持） | 当前日期 | 建议独立项目日 | 证据与适用范围 |
| --- | --- | --- | --- | --- |
| RC-007 / 42144，孙燕姿《我要的幸福》 | `78cBYsAtN8VqvWmyW4Uu4m`，12曲 | 2000 / year | **2000-12-09** | [艺人官网](https://www.makemusic.sg/2-my-desired-happiness)直接图片标日期；12曲顺序与现来源一致。旧商品12-01、论坛转录12-07保留为异说，以艺人原始目录为本批依据。 |
| RC-038 / 41610，Avril Lavigne《Under My Skin》 | `7851Vsjv3apS52sXUik6iF`，13曲 | 2004 / year | **2004-05-25** | [艺人官网目录](https://store.avrillavigne.com/pages/catalog-2024)该节直接嵌入同一Spotify来源；[Apple US 13曲目录](https://music.apple.com/us/album/under-my-skin/533016327)同日。确认范围为艺人官网所连数字目录的主专辑锚点，不是全球最早发行日。 |
| RC-058 / 42108，孙燕姿《自选集》 | `7cEwS35EbkJmjlnnYUQPb1`，12曲 | 2002 / year | **2002-01-05** | [艺人官网](https://www.makemusic.sg/4-start)直接图片标日期及12曲；目录与现来源一致。旧论坛02-01不采用；本轮已闭合官网入口及图片归属。 |
| RC-069 / 41913，Christina Aguilera同名专辑项目（现名Expanded Edition） | `6fpPZS13ImRVpr7Tqs6yP9`，18曲 | 1999 / year | **1999-08-24** | [Sony / Legacy公告](https://www.sonymusic.ca/press_release/legacy-recordings-celebrates-the-20th-anniversary-of-christina-aguilera-the-artists-self-titled-debut-album-with-special-releases-coming-friday-august-23rd)明确RCA原版日期，并区分2019-08-23周年数字版。本地5首均属原12曲；现18曲来源保持，不认定其额外6曲或整个Expanded版在1999-08-24首次发行。 |

Under My Skin的[Sony现黑胶商品文案](https://shop.sonymusic.ca/products/avril-lavigne-under-my-skin-silver-grey-black-marble-vinyl)另写原始05-19，此异说未被删除，也未被擅自解释为某个日本发行日。本批采用的是艺人官网明确日期与直接所连来源的口径；若要求统一“全球所有地区最早实际发行日”，此项应继续暂缓，不应把05-25当成该口径的已证结论。

孙燕姿官网链为 MAKE / MUSIC 艺人入口 → 中文discography → 具体专辑页面 → Squarespace同站图片。本轮已直接查看图片；不是仅凭搜索摘要或无法归属的PDF批准。图片及原HTML保存在本地审核包。

## 已核实日期但不能在本批应用

| ID / 项目 | 联网核查结论 | 暂缓原因及下一步 |
| --- | --- | --- |
| RC-021《The Moment》 | [艺人官网](https://www.makemusic.sg/7-the-moment)标原专辑2003-08-22；官网22曲（7+15）含当前19曲（5+14），两者不应称为同一版。[原宣传稿](https://ent.sina.com.cn/p/i/2003-09-27/1821207682.html)写8月22日及台北首日活动，但网页日期晚于正文预告，只作交叉支持；Apple19曲08-19保留为数字版异说。 | 实际五项联合TEMP预演被owner门禁拒绝：`l1:2987`《永遠》、`l1:3941`《沒有人的方向》会改变规划归属，当前均归The Moment。其共同候选还有《未完成》42178，现旧year排序参与归属。需单独审阅精选/原生收录事实与保留现归属的明确决定；本轮不实施。 |
| RC-050 Nirvana《Nevermind》 | [艺人官方时间线](https://www.nirvana.com/timelines/)明确原版**1991-09-24**。 | 当前13曲Remastered来源为09-26/day；不能用原版日期证明该重制来源的首次发行日，且成员与目录直接ID匹配0/13。需匹配具体版别及显式日期冲突治理，不能为了日期选择75曲周年版。 |
| RC-088 Lana Del Rey《Ultraviolence》 | [环球德国](https://www.universal-music.de/lana-del-rey/musik/ultraviolence-209784)为**2014-06-13**；[发行方美国新闻](https://www.prnewswire.com/news-releases/lana-del-rey-announces-june-17-release-of-new-album-ultraviolence-interscopepolydor-uk-259226061.html)为**06-17**，两者有地区范围。 | 当前14曲Deluxe为01-01/day，与已核实地区日冲突。需闭合该来源版别/地区并处理原声明冲突，不能仅改项目日期声称已恢复。 |
| RC-060 Pitbull《Global Warming: Meltdown》 | [Sony公告](https://www.sonymusic.com/sonymusic/fifa-and-sony-music-entertainment-select-we-are-one-ole-ola-by-global-music-sensation-pitbull-featuring-international-superstar-jennifer-lopez-and-brazils-own-claudia-lei/)确认**2013-11-25为Meltdown再版日**，新增Timber等5曲；[日本商品](https://www.sonymusic.co.jp/artist/pitbull/discography/buy/SICP-3951)为12-18，[Sony财报](https://www.sony.com/en/SonyInfo/IR/library/presen/er/13q4_supplement.pdf)另列11-22。 | 当前Spotify2012/year与原Global Warming语境相关，不能把2013再版日直接写成原项目日。正式assertion12本来就是edition_release / pending，本轮未改。先分原专辑日、再版日及后5曲收录范围，再做保护预演。 |
| RC-047 Mariah Carey《E=MC²》 | [环球日本商品](https://www.universal-music.co.jp/mariah-carey/products/uicl-9076/)区分原16曲04-16与盒版12-17。 | 当前16曲Deluxe是2008-04-04/day，未闭合到日本16曲原商品；不能采用盒版日期或将其他地区日混为统一日期。 |
| RC-039 Jessie J《Who You Are》 | [环球德国Deluxe](https://www.universal-music.de/jessie-j/musik/who-you-are-deluxe-edt-178587)为2011-11-18，说明新增三曲，含DVD规格。 | 当前16曲Platinum为01-01/day，Apple17曲02-25不是16曲Platinum首发证明。需目录、媒介和原版/扩展版范围闭合。 |

独立日期现有入口会拒绝与来源已声明exact day不兼容的日期。这是当前读取合同，不能用“网页找到了日期”替代来源/版别审核；本轮没有改代码放宽它。

## 其余18项逐项审核

| ID / 项目 | 具体阻塞与所需证据 |
| --- | --- |
| RC-024 Leona Lewis《Spirit》 | [艺人官网](https://www.leonalewismusic.com/music/)原版2007-11-09；当前17曲包含后来附加的Run、Forgive Me、Misses Glass等，本地记录也涉及后加曲。需逐曲收录事实及17曲版日期，不能直接借原版日期。 |
| RC-041 孙燕姿《2000台北万人演唱会》 | 04-10 VCD与06-07庆功CD是不同媒介。当前12曲CD日主要见[旧官站论坛转录](https://www.ptt.cc/bbs/Yanzi/M.1146124984.A.156.html)，需原发行方CD档案或同期原报道。 |
| RC-043 王菲《执迷不悔》 | 原10曲year、另一Remaster01-01/day、[Apple Remastered2019的02-05](https://music.apple.com/hk/album/執迷不悔-remastered-2019/1488204120)并存；[环球日本](https://www.universal-music.co.jp/faye-wong/products/uijy-75257/)只证明原1993年2月与2024再版。需原版日级直接证据并处理来源集合冲突。 |
| RC-059 James Taylor《Gorilla》 | [艺人官网](https://www.jamestaylor.com/discography/gorilla)只写May1975；当前2019Remaster标1975-05-01/day。未取得独立具体日，不能由月份推定1日。 |
| RC-080 Aqua《Aquarium》 | 当前17曲Special为1997-01-01/day；原丹麦03-26/美国09-09的旧资料未闭合该特别版。[环球25周年商品](https://shop.universalmusic.it/products/aqua-aquarium-25th-anniversary-vinile-colorato)不足以证明当前17曲版的原始具体日。 |
| RC-081 Maroon 5《Hands All Over》 | 地区09-15/09-17/09-21仍待具体版别闭合。现13曲来源ID数组发生变化，成员直接ID匹配0/1；先查重新上架/目录替换，不安装新目录或更换成员。 |
| RC-084 Indigo Girls同名Expanded | [艺人官网](https://www.indigogirls.com/studio-albums)只有年，[原创周年报道](https://stereogum.com/2033408/closer-to-fine-at-30-the-legacy-of-indigo-girls-spellbinding-singalong/columns/sounding-board)支持原10曲1989-02-28。现12曲含1994现场，Apple03-01/另源05-17不证明该扩展版首发日；原版日保留为次级候选，待更直接证据和收录范围。 |
| RC-046 Taylor Swift《Cats》 | 多艺人原声带，16曲来源已属44473；不能凭Taylor参与就转给个人项目。需专属发行或合作项目治理。 |
| RC-049 Andrew Garfield《tick,tick...BOOM!》 | 17曲原声带身份未闭合且来源已属44489；保持成员和归属，待专属发行/合作项目治理。 |
| RC-062 ZAYN《reputation Stadium Tour Surprise Song Playlist》 | 46曲Taylor相关拼合集，Album artist与ZAYN项目不匹配；包含一首作品不能证明个人整张来源。 |
| RC-067 Olivia Rodrigo《The Hunger Games》 | 11-17的17曲多人原声带与11-03专属单曲不同；身份通过的单曲不能替代整张原声带。 |
| RC-070 4*TOWN《Turning Red》 | 32曲完整原声带已属44511，不从其他项目抢占。需专属发行证据。 |
| RC-074 ROSÉ《BLACKPINK 2021 THE SHOW LIVE》 | Album artist为BLACKPINK，和ROSÉ个人项目不匹配；15曲ID目录也漂移。本轮不安装新目录。 |
| RC-078 单依纯《中国好声音第3期》 | 整期8曲多人发行与个人项目范围不同。需专属发行或独立合作项目证据。 |
| RC-079 Daveed Diggs《The Little Mermaid》 | 15曲原声带艺人不匹配且已属44480；不改变原声带owner。 |
| RC-083 Halle《The Little Mermaid》 | 同一15曲原声带已属44480；04-26专属单曲不能替代05-19整张原声带。 |
| RC-092 张婧《轩辕剑影视原声碟》 | 10曲多人原声带，Album artist身份未闭合到张婧个人项目；需专属发行或合作项目证据。 |
| RC-096 Kristen Bell《Frozen》 | 59曲Deluxe多人原声带已属44520，身份也未闭合；01-01/day与旧审核11-25仍不能越过来源占用与身份门禁。 |

上述source ID、完整目录、有序艺人证据、已占用项目与直接ID匹配数逐项保存在审核包，不因身份阻塞而伪造日期结论。

## 预演证据、限制与后续

本地证据目录：`output/versus-release-cycle-20261023-review28/`（不提交个人数据库或完整本地资料）。

- `review.json`：当前8种选择器与28项快照；`live-catalogs.json`：30份实时完整目录，只读观察未安装；`catalog-comparison.json`：两份数组漂移。
- `official-image-provenance.json`：三个艺人官网页面、图片真实URL与本地文件；对应HTML和图片已保存并直接查看。
- `audit-28.json`、`checklist.md`：28项完整判断、证据和后续；`next-batch-proposals.json`：最终4项显式日期提案。
- `proposal-preview-first-failure.log`、`proposal-preview-failure.json`：原五项门禁失败原样保留；`held-moment-date-proposal.json`：The Moment未采用日期提案。
- `proposal-preview.json`、`proposal-preview.log`：剔除The Moment后的4项联合保护与解析预演。正式连接main写入尝试0；保护表没有TEMP替身；原始记录96881、成员3328、已发布归属7015均未写。

Spotify和官方图源首次TLS失败后，经仓库既有代理有界重试成功；失败日志保留。浏览器取证超时不计入验收，实际日期取自已成功读取并查看的官网图片和公开来源。没有改代理持久配置、业务HttpClient或UI。

这次仅验收证据与计算资格的TEMP预演，没有构建正式快照、没有在本地应用日期、没有做生产HTTP或原页面上线验收，不能标记为已上线。没有新增业务代码，故不重复运行全量后端/前端或全栈测试。

下一步：用户确认上述4项日期及范围后，才可从正式库自身fresh Online Backup重新生成受控提案，在独立副本完成应用与相关快照、接口及原UI验收，再按授权决定正式本地/生产动作。24项继续保留具体阻塞；The Moment优先单列收录事实与归属保留方案，不能自动沿用Title的人工作品决定。


## 用户确认后的本地正式应用与验收

最后核验：2026-10-24。用户确认采用4项日期及对应适用范围、沿用现有来源，授权继续应用和验收；The Moment继续暂缓。本节覆盖本地正式应用，生产环境未改动。

从本地正式库自身fresh Online Backup生成baseline与独立候选，重新核验schema95、现有来源目录/艺人、项目旧日期及L3依赖。候选仅新增4条独立日期断言和8条登记/批准审计事件，批准后L3发布保留原归属，只推进必要依赖水位。重复批准无第二次修改、事件或revision增加。

| 项目 | 已应用项目日期 | 现有来源 |
| --- | --- | --- |
| 42144《我要的幸福》 | 2000-12-09 / day | 78cBYsAtN8VqvWmyW4Uu4m，保持 |
| 41610《Under My Skin》 | 2004-05-25 / day | 7851Vsjv3apS52sXUik6iF，保持；艺人官网所连数字目录口径 |
| 42108《自选集》 | 2002-01-05 / day | 7cEwS35EbkJmjlnnYUQPb1，保持 |
| 41913《Christina Aguilera》项目 | 1999-08-24 / day | 6fpPZS13ImRVpr7Tqs6yP9，保持；原专辑日，不认定整个Expanded版同日首发 |

未更换或新增主来源绑定，Spotify原year声明保持；来源占用、艺人证据、曲目目录及既有治理事实均未重写。117项保护通过：96881条原始播放、原始歌曲/署名、3328条项目成员、全部Spotify原始声明与7015条已发布目标/原生项目归属保持。全部非目标项目完整行、既有归属override和逐曲证据保持；L3完整发布行仅有已审阅的共享依赖水位推进，不安装全库新规划。唯一运行期额外记录为已完成的minimal启动预热作业。

The Moment完整项目保持2003/year；`l1:2987`《永遠》和`l1:3941`《沒有人的方向》继续归41962，没有应用其已核实但会改变规划归属的日期。全部8种选择器与预演逐项一致，剩余由28降至24（粗日期7、来源12、身份5）；旧ready无退化。Title与Christmas既有方案完整保持。

### 快照维护与本地切换

精确搜索六变体在明确副本离线准备，禁止网络访问和项目成员bootstrap/rebuild，且保留已有发布归属。完成8配置96项Billboard发布、4套详情投影、默认及含精选集个人排名，以及依赖日期revision的分析、社区、音乐档案和治理快照。最终路径下完成2022–2026确定性年度与首页维护，`verify-pre`和`verify-post`全部ready。

停止经PID、父子关系、命令及cwd核实的旧8000/4173服务后，全161表及schema源围栏与fresh基线一致；七库quick_check通过才切换。旧七库原inode及首页缓存整体保留，候选路径相关发布在正式路径重新校验/绑定。现本地监督进程74648，继续使用原前端成品，没有重新构建前端。

联合恢复点：`output/versus-release-cycle-20261023-review28/local-apply/local-activation/old/`与`old-home-overview/`，`journal.json`记录切换过程。需要回滚时须停止已核验的新监督进程，再整体恢复七库和首页；不能仅覆盖运行中的主库或WAL。

### 接口、独立指标与原界面

- 应用前保存32项实际HTTP基线。候选和正式各57项HTTP通过，覆盖8种选择器、4项日期/来源、TTPD/Showgirl、Title/Christmas、The Moment暂缓边界、个人统计/排名、对决及重排。
- 候选和正式各32次受影响专辑比较、192项六指标，从计次/排名基础独立对账通过。原TTPD/Showgirl与Title/Christmas的日期、来源和六指标与基线一致；实体集合保持。4张旧专辑发行时段缺少榜单/基线的指标仍显示“—”，发行周播放为0，半数播放距分别1265、1016、1212、1290周；不把无历史榜单改写为虚构排名或内部状态文字。
- 1280×900桌面和390×844手机实际选择4张专辑，表格仍为原六行；没有“发行日期”、诊断或内部状态行。显示值与经独立对账的接口一致，手机整体横向溢出0。前端源码输入与全部成品文件保持，原TTPD/Showgirl表格outerHTML应用前后完全一致，没有改样式、布局或文案。
- 实际手机验收后控制台观察为0错误/0警告；浏览器会话曾失效，重新打开后完成上述实际验收，收尾close确认会话已不在运行。失效会话及汇总脚本初次row_factory缺失等工具失败日志保留，未将失败步骤记为通过，没有因此重跑已通过的业务矩阵。

本地证据位于审核目录下`local-apply/`：`user-confirmation.json`、`installation-proof.json`、`expected-date-registry.json`、`preparation-receipts.json`、`candidate-api.json`、`formal-api.json`、`candidate-six-metrics.json`、`formal-six-metrics.json`、`formal-coverage.json`、`formal-protection-runtime.json`、`original-pair-dom-proof.json`和`acceptance-summary.json`。实际截图位于`output/playwright/release-four-local-20261023/`。

本批本地应用及验收已收口；业务源码和UI没有修改，不重复跑无关全量测试。本轮文档审计与差异检查通过。未执行Git提交、推送或生产部署；其余24项独立治理另行推进，The Moment仍暂缓。
