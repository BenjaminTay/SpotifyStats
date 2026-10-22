# 发行周期剩余98项来源审核

日期：2026-10-21。关联：`SS-2026-10-21-004`（原功能恢复已交付）、`SS-2026-10-21-006`（本轮新发现的来源类型与身份传递缺口）。状态：**SS-2026-10-21-006 本地研发与验收已收口，本节及代码随本地收口提交保存；尚未推送或生产发布。下文逐批“未提交”均为当时检查点，当前结果见文末收口记录**。

## 范围与方法

复用原八上下文选择器清单，对当前正式本地 SQLite 的98个剩余条目、728次出现重新解析，原因与原清单一致。统计粒度是选择器条目，Positions/positions是同一名称歧义组的两个标签，不应当作两次独立的合并决定。来源为同一事务读取的当前项目、成员、Spotify日期/类型/完整目录、署名和现有来源所有权；复用已安装官方响应，没有联网补证。

主库使用 SQLite URI `mode=ro`。112个候选绑定及13组专辑类型排除实验仅修改内存TEMP影子表，每个候选回滚；没有写正式数据库、改成员或批准关系。TEMP结果证明解析器采用该输入后的后果，不能证明被选来源就是应批准的主版。原始成员Spotify ID与目录交集也不等于不同发行版本完全相同。

## 对上一轮剩余项判断的修正

上一轮将剩余98项统称为数据审核边界过于笼统。本轮证据确认其中还有两个程序合同缺口，不能全部通过人工选择日期或合并身份解决。TTPD/Showgirl的原始故障恢复及既有实际验收仍成立；新增缺口按006跟踪，不把模拟描述成已部署修复。

### 同名单曲进入专辑日期来源

36项日期冲突中，有13项同时包含Spotify `single`和`album`来源。隔离排除单曲来源并按现有合同同步后，11项可解析出专辑发行日，另外2项仍有专辑之间的日期冲突。11项包括两个Jolin/JOLIN标签的同一音乐作品，数量仍按原选择器粒度计算。

例如《Deeper Well》的单曲来源是2024-02-08、1首，专辑来源是2024-03-15、14首；《Chemtrails Over The Country Club》也有同名single与album。当前来源集合未区分目标发行种类，先行单曲因而成为整张专辑的冲突锚点。13项混合类型之外，还有14项相差一天的来源冲突、9项其他专辑目录/日期冲突；应分别核对，不能用“取最早日”统一解决。

后续代码补修必须在目标项目、明确版本及来源类型合同内筛选，保留真正单曲项目的能力、明确成员版本的锚点，以及所有既有ready样本。不能全局删除single缓存、改原始链接，或仅为了通过而指定一个primary来源。

### 名称入参丢失稳定项目身份

3个歧义条目对应两组独立发行：

- Ariana Grande：project41567为`Positions`专辑（14首来源、2020-10-30）；project44793为`positions`单曲（1首来源、2020-10-23）。不应因大小写相同而合并。
- Various Artists：project44547为1994来源的《The Lion King》，project44517为2019来源的电影原声带。二者已有不同Spotify来源绑定，不能仅凭短名称代选。

当前选择器仅给出显示名称/艺人名，compare请求模型也只有名称，批量resolver未消费project_id；名称规范化后无法区分上述项目。后续应让选择器、队列、query key、请求和返回列贯通稳定项目ID，并验证艺人、合并层级及项目范围，旧名称调用保持唯一时兼容。显示标签同时提供版本/年份；不能通过合并这两个不同发行来消除错误。

## 33项关联缺口及首批具体建议

33项进一步分为：21项有单一可计算的album版别候选；4项有多个可计算候选；2项需核对single/compilation类型；6项涉及署名或既有来源所有权。技术上可计算不等于版别选择正确，例如`Title`的候选还混有圣诞专辑和单曲，不能按任意候选能通过就安装。

首批以下6项均有唯一候选、完整缓存目录、已验证同艺人ID、全部已知原始成员ID命中，且没有其他项目占用来源。TEMP绑定后只改变对应项目精度NULL→day，日期文字保持原值，未变更任何成员。**建议确认所列版本作为本地项目主来源，而非声称标准版和Deluxe等版本完全等同。**

| 审核编号 | 本地对象 | 建议主来源版本 | 保留日期 | 已有成员ID命中 |
| --- | --- | --- | --- | --- |
| RC-002 | 光良《光良「回憶裡的瘋狂」巡迴演唱會》 | 同名(Live) | 2016-06-13 | 29/29 |
| RC-013 | 陶喆《Soul Power》 | Soul Power (Live Concert) | 2003-09-09 | 28/28 |
| RC-030 | Niall Horan《Flicker Featuring The RTÉ Concert Orchestra》 | 同名(Live) | 2019-02-01 | 9/9 |
| RC-008 | Niall Horan《Flicker》 | Flicker (Deluxe) | 2017-10-20 | 13/13 |
| RC-029 | Rihanna《ANTI》 | ANTI (Deluxe) | 2016-01-28 | 16/16 |
| RC-035 | Katy Perry《Witness》 | Witness (Deluxe) | 2017-06-09 | 13/13 |

具体project_id、Spotify Album ID、预期旧日期/精度、来源所有者、成员及艺人ID保存在私有`first-batch-proposals.json`。其`apply_ready=false`，不是可直接执行的授权清单。确认后还需按正式代码、来源漂移门禁、Online Backup及副本演练准备对应派生成品，才能安装；不得用TEMP结果替代正式页面复验。

## 身份与粗日期

5个艺人身份待审项目都有来源艺人ID，均非简单补空ID：Cats来源署名为作曲家/演员阵容，tick,tick...BOOM!为演员阵容，另有Taylor Swift来源挂在ZAYN对象、BLACKPINK来源挂在ROSÉ对象，以及影视原声带来源挂在張婧对象。应审核专辑项目的署名范围与成员归属，不能把不同艺人全局合并或抢占已有来源。其余33项中的部分原声带来源已经属于独立项目，同样保持所有权。

21个粗日期条目的当前来源均为year。保留已确认年份和日级不可计算说明；本轮没有新日级证据，不升级precision或补成01-01。

## 审核阶段的后续顺序与验证边界（历史）

1. 优先修复006中的来源类型筛选及稳定ID传递。先固定上述真实失败样本，再做受影响回归；对所有既有ready来源核对是否有回退，对13项混合类型和两组歧义核对恢复与独立版本保护。
2. 对首批6项给出具体版别确认。批准后按逐项预期状态检查安装，保留来源与治理审计，准备受影响快照并验证实际页面；当前未应用。
3. 继续审核其余版别、日期和项目署名问题。单一候选中的疑似特殊版、目录ID未命中及01-01等来源另行核实，不由标题或日期外观推断；真实粗年份保持。

本轮没有改业务代码、原始事实或正式元数据，没有提交、推送、发布或重启服务。没有重新运行全站/全栈/资源测试；已执行审核脚本、TEMP模拟及复用结果的两段Notebook检查。

## 私有证据

目录：`output/versus-release-cycle-20261021/remaining-review/`，独立于已归档交付工作树。

- `review_remaining.py`：完整只读SQL、解析及TEMP模拟代码。
- `current-reasons.json`：728次出现的当前实际原因。
- `review-package.json`：98条目及112候选的类型、日期、署名、所有权、目录交集和模拟结果。
- `review-checklist.md`：全部98条目逐项建议与首批6项。
- `first-batch-proposals.json`：待确认的具体关系及预期旧值。
- `remaining-review.ipynb`：复用已执行结果的可检查Notebook，两段检查已运行。

这些文件包含本地音乐库对应关系，留在ignored私有目录，不提交Git。上述日期均表示当前安装来源的观测值，本轮未独立核对外部艺人/厂牌对全球首发日的表述。

## 用户确认后的修复与本地应用

用户明确确认上述六个版本作为对应项目主发行来源，并要求保持原始记录和项目成员。原 `first-batch-proposals.json` 保留审核时的 `apply_ready=false`，不改写历史授权状态；本轮使用独立治理运行、六条追加来源关系和六条审计事件记录新决定。

两处通用修复：默认日期来源集合区分同名专辑与先行单曲，保留单曲项目、未知旧类型及明确 primary/成员版本；选择器、队列、普通榜单、个人统计/排名、发行周期、缓存键、返回列和详情深链贯通项目ID。同名不同发行不合并，错误ID、艺人或层级不回退名称。Positions 的两个来源分别保留2020-10-30和2020-10-23；1994与2019两版Lion King保持独立，2019版本未进入当前榜单时不加入选择器。

先在当前本地库的 SQLite Online Backup 副本应用六项来源，逐项校验主专辑、成员、艺人、来源日期、完整目录和既有所有权。只将这六个项目日期精度 NULL→day，日期字符串均保持。重复应用新增来源/事件均为0。其余108项保护投影、原始播放/歌曲/署名、项目成员和人工覆盖逐列保持；治理运行/事件/来源三表仅有本次批准的追加，旧行完整保留。

项目revision推进后，既有7015条L3归属按原发布结果保留，只更新上游revision及发布摘要。前后完整规划决定一致；规划器相对既有发布存在一条此前的Positions归属差异，本轮没有采用该差异或重分配歌曲。搜索四变体在隔离副本显式准备后通过严格复用检查，96项Billboard、四套详情和个人排名以及默认消费者配套准备。正式路径切换有源漂移检查、七库原inode及旧前端/首页联合恢复点。

定向验证：后端211项通过；最后热度元数据的L3范围补齐另复验9项通过；前端5文件29项、TypeScript/Vite构建、受影响7文件mypy及ruff通过。八上下文所有既有ready项目均无日期/项目身份退化；隔离HTTP27请求核对TTPD/Showgirl六指标、六项主来源、Positions独立榜单/个人统计/排名、重排、两版Lion King以及错误ID/艺人和旧名称歧义保护。

正式本地8000/4173已加载补丁与六项来源，27个HTTP验收请求全部通过，与副本结果一致。八上下文的现有ready项目无退化；实际带ID选择器共恢复20个原不可用条目（11项混合来源、3项名称歧义、6项批准主来源），剩余78个选择器标签：日期冲突25、来源关系未确认27、仅年级日期21、艺人署名范围5。各上下文名称歧义均为0。本轮不提交、推送或生产发布；原004生产版本的验收不代替006新补丁的生产证据。

私有应用证据：`output/versus-release-cycle-20261021/confirmed-six-apply/`，包含 `baseline.db`、`installation-proof.json`、`prepared-protection.json`、`coverage.json`、`candidate-api.json`、发布manifest、准备回执和 `local-activation/` 恢复档案。源快照、代码补丁和正式应用证据分别保存，不把当前HEAD描述成包含尚未提交的补丁。

### 正式本地最终验收

| 上下文 | 可计算条目 | 剩余原因 |
| --- | ---: | --- |
| L2，动态阈值开/关，不含精选 | 446 | 日期冲突25、粗日期21、来源24、署名5 |
| L2，动态阈值开/关，含精选 | 452 | 日期冲突25、粗日期20、来源27、署名4 |
| L3，动态阈值开/关，不含精选 | 427 | 日期冲突22、粗日期21、来源23、署名3 |
| L3，动态阈值开/关，含精选 | 430 | 日期冲突22、粗日期21、来源26、署名3 |

1440×1000桌面与390×844真实浏览器验收通过：TTPD/Showgirl发行周播放276/297、半数播放距20/7周；四对象实际请求中的普通榜单、个人统计、个人排名、发行周期均含正确project_id。Positions单曲/专辑可同时添加，移动端重排后日期2020-10-23/2020-10-30和半数播放距204/214周仍各自对应。四个详情链接均使用稳定项目路由，实际点击单曲进入44793。

手机页面宽度390无页面横向溢出，周期表格仅挂载一份，表格独立横向滚动507px；12个队列操作目标均44×44px。初次截图发现旧半透明固定列透字、底部操作按钮遮住末行；本轮仅补齐该页底部留白和周期表固定列的不透明背景/层级。2项受影响页面回归及最终TypeScript/Vite构建通过，最终截图和几何复验确认末行底部537.7px、操作按钮顶部602.2px，无覆盖。新前端构建已配套替换，保留替换前构建，不改数据库或再次重启后端。

正式切换前155张表和schema漂移检查完全一致。六项安装后、正式路径消费者准备后，108项其余保护投影完全一致；启动后的严格检查只发现追加1条正常完成的 `startup_cache_warmup` 运行账目，原3592条任务逐列保持。该差异原始检查保留在 `formal-protection.json`；另以精确追加条件核验生成 `formal-protection-runtime.json`，107项其余投影仍一致，原始三表、项目成员、L3归属及人工覆盖保持。没有把正常运行账目变化描述成原始音乐数据变化。

最终证据增加：`formal-api.json`（27请求）、`selector-id-coverage.json`（八上下文全选择器）、`formal-protection-runtime.json`、`browser-request-proof.txt`、`browser-mobile.log`、`browser-final.log`、`browser-stable-link.log`、`mobile-polish-activation.json`。最终截图为 `desktop-final-cycle.png`、`mobile-final-left.png`、`mobile-final-right.png`，初次手机截图保留，不改写为通过。隔离18811/5188及本轮浏览器已关闭，日常8000/4173保持运行。

006至此按本地范围关闭。下一批仅继续审核剩余78项的版本、日期和署名证据；现有年级来源不补造发行日，不自动合并不同发行或艺人。生产仍为004的既有发布版本，本轮新补丁与六项关系尚未生产发布。

## 第二批来源审核（只读完成，待具体版本选择）

> 本节保留用户选择前的只读审核状态。用户随后明确确认8个版本，正式本地应用与2026-10-22最终验收见文末；原pending提案文件保持历史原样。

在006应用后的当前正式本地库继续复核78个剩余选择器标签、584次出现，八种配置下原因/日期无漂移。114个既有候选重新读取目录、日期、署名、来源所有权及已知曲目；82个满足模拟前提的候选仅在TEMP影子表预演。主库URI为 `mode=ro`，另有main写入拒绝authorizer，写入尝试0。没有改程序、正式来源/日期或成员，没有提交、推送、生产发布或重启；006已完成的修复保持关闭。

### 下一批建议：明确采用以下8个版本

| 编号 | 本地项目 | 建议主来源版本 | 保留来源日期 | 已知原始成员ID命中 |
| --- | --- | --- | --- | --- |
| RC-009 | Ariana Grande / thank u, next | thank u, next | 2019-02-08 | 12/12 |
| RC-019 | A-Mei Chang / 我要快樂 | 我要快樂 (Deluxe Version) | 2006-02-17 | 3/3 |
| RC-065 | One Direction / Made In The A.M. | Made In The A.M. (Deluxe Edition) | 2015-11-13 | 2/2 |
| RC-066 | One Direction / FOUR | FOUR (Deluxe) | 2014-11-17 | 5/5 |
| RC-072 | Elton John / Goodbye Yellow Brick Road | Goodbye Yellow Brick Road (Remastered) | 1973-10-05 | 2/2 |
| RC-077 | Ed Sheeran / ÷ | ÷ (Deluxe) | 2017-03-03 | 2/2 |
| RC-086 | flor / come out. you're hiding | come out. you're hiding (deluxe) | 2018-02-02 | 1/1 |
| RC-093 | A-Lin / 幸福了 然後呢 | 幸福了 然後呢 (影音慶功版) | 2013-02-08 | 2/2 |

八项均为完整目录、已验证艺人ID、没有其他项目来源所有者，已知原始成员ID全部命中。联合TEMP预演64次上下文解析均ready，只让这8个项目精度NULL→day，全部日期文字保持，不改原始记录或成员。`next-eight-proposals.json`保存精确Spotify Album ID、预期项目/主专辑/成员/日期及所有权，`apply_ready=false`、`approval_status=pending_user_version_choice`。

这是具体版别选择，尤其flor的Deluxe与A-Lin影音庆功版；该来源日期不能解释为其他版本或全球首发日。歌曲ID交集不等于播放次数，也不批准不同版本完全等价。若采用这8项，预计剩余标签78→70；这是预演结果，当前正式数量仍为78。

Elton官方周年记录列出1973-10-05，[官方说明](https://www.eltonjohn.com/stories/goodbye-yellow-brick-road-45)与该候选声明一致；[Ed Sheeran官方发行资料](https://www.edsheeran.com/album/divide)列出2017-03-03；[Sony的Made in the A.M.发行公告](https://www.sonymusic.co.uk/one-direction-release-made-in-the-a-m/)列出2015-11-13。A-Lin的Avex官方发行目录搜索结果列出影音庆功版2013-02-08及11首CD，正式版另为2012-12-30；目录/电子报直接读取超时或502，网页证据限于已取得搜索索引，不声称已直接抓取成功。其余项目的精确日采用本轮复核的已安装Spotify来源声明，没有把所有项目表述成已获独立外部日期佐证。

### Thank You：两版同时成立，不能把年份差异直接判错

[Sony Music UK于2016-05-13的公告](https://www.sonymusic.co.uk/meghan-trainor-releases-new-album-thank-you/)直接链接Spotify `5nkgosKhWt1yXRzmjXNV2d`。该ID原先不在本地缓存。本轮通过现有Provider只读抓取这两版的日期、署名及完整目录，并核对其曲目ISRC，响应仅保存私有证据，没有安装新缓存或改项目日期。

| 版本 | Spotify Album ID | 官方声明日期 | 完整目录 | 已知原始曲目ID / ISRC命中 |
| --- | --- | --- | ---: | --- |
| Thank You (Deluxe) | `5nkgosKhWt1yXRzmjXNV2d` | 2016-05-13 | 15首 | 3/3、3/3 |
| Thank You (Deluxe Version) | `08eweM0IZoZPCCxODbrMoL` | 2017-05-12 | 17首 | 3/3、3/3 |

两者都包含本地已知3首，因此曲目交集不能替用户决定选原始Deluxe还是2017年17首版。当前项目文字为2017-05-12且精度NULL；如果改用2016版，还会涉及主来源与项目日期跨年纠正，应形成独立明确决定。本轮不把2017来源称为伪造或错误，也不为消除缺证而自动改年。

### 全部78项的动作分组

| 动作 | 条目数 | 下一步 |
| --- | ---: | --- |
| 本次8项具体主来源 | 8 | 确认具体版本后准备正式应用、备份与页面验收 |
| 单一可计算候选仍需佐证 | 8 | Who You Are、E=MC2、Nevermind、Thank You、Gorilla、Aquarium、Ultraviolence、Let's Get It On；核对版别与日期 |
| 其他版本/类型/所有权 | 12 | 多候选4、single/compilation范围2、署名/既有来源所有权6；不抢占、不合并艺人 |
| 其余来源日期冲突 | 24 | 按发行版、地区和目录核对主来源；部分已确认项目锚点还需明确日期纠正决定 |
| 仅年级日期 | 21 | 保持已确认年份，获得版本级日证据后才进入日级计算 |
| 来源艺人范围 | 5 | 审核原声带、演员阵容、团体和项目署名；保持当前成员与艺人身份 |

Who You Are、Nevermind、Let's Get It On的直接曲目ID分别0/5、0/13、0/1；缓存ISRC分别4/5、13/13、1/1，说明录音相关程度不同，不能把ISRC相同自动提升为版别相同。Gorilla的[艺人官网](https://www.jamestaylor.com/discography/gorilla)只给1975年5月，不足以独立确认01日。01-01/每月首日的外观仅是核查线索，不能据此判错或改来源精度；这些来源原有day声明均保持，尚未选择主来源。

完整78项动作、候选细节和82次TEMP结果见私有 `output/versus-release-cycle-20261021/remaining-review-78/`：`review.py`、`review-with-actions.json`、`propose.py`、`next-eight-proposals.json`、`checklist.md`、`remaining-review-78.ipynb`、`thank-you-editions.json`及其抓取脚本。Notebook三段复用结果检查已实际执行。当前业务代码和数据库没有变更，仅更新审核证据与对应文档；本轮只做结果一致性和文档检查，不重复已通过的全栈/浏览器或资源实验。

## 第二批8项正式本地应用与验收

最后核验：2026-10-22。用户明确确认上表8个具体版本作为相应项目主发行来源，并要求原始记录和项目成员保持。以当时已含首批6项的正式本地库制作fresh Online Backup，在独立副本核对项目、成员、日期、艺人、完整目录及来源所有权后应用。新增8条primary关系、8条审计事件和1个治理运行，只将对应8个项目精度NULL→day；所有日期文字保持。重复应用新增写入0。原提案pending状态不改写，新决定由独立治理运行记录。

首次安装后的全库外键检查拒绝提交，事务完整回滚。基线与回滚后副本都存在1,048,384条历史孤立详情派生行，分布在 `music_search_detail_entity_projection`（481,432）、`music_search_detail_source_facts`（566,944）、`music_search_detail_projection_state`（8），引用8个已被淘汰的父快照。根因是既有淘汰逻辑显式清理搜索/周榜/年榜子表，却漏了三个详情子表；上轮私有准备连接未启用外键，也缺少准备后全库外键检查。原始记录及成员保护结论仍成立，不能将此前准备描述成派生外键完整性已通过。

通用淘汰路径现沿用同一父快照资格，显式先删详情子表，保留当前、前代、活动指针及构建中快照。旧代码在外键关闭的回归中失败、开启时通过；修复后搜索快照与详情相关113项通过，ruff通过。副本仅清理无父快照的历史派生行，有效父快照的全部详情行、活动指针及111类保护投影保持；随后启用外键重新准备。首次失败、清理明细和修前/修后回归均留存，没有直接清理正式旧库或删除恢复证据。

治理消费者曾因副本schema版本与保留标记不一致而拒绝，`sqlite_master`定义比基线无差异。通过现有tracking维护入口恢复合同，再完成消费者准备与verify，原失败回执保留。搜索四变体严格复用、八上下文96项Billboard、四套详情和个人排名、默认统计/记录/档案/治理及2022–2026年度与首页均完成准备或正式路径校验。切换前155张表及schema与fresh源围栏完全一致，七库原inode及旧首页缓存保留联合恢复点；本轮复用既有前端构建。日常8000/4173已运行新后端与本批来源。

隔离与正式本地各59个HTTP请求通过：本批8项×8配置的64次日期与来源ID核对、原TTPD/Showgirl六指标、首批6项、Positions单曲/专辑独立日期及重排、两版Lion King和错误ID/艺人/旧名称歧义保护均通过。八配置全部实际选择器ID重新核对，既有ready的原因、日期与来源ID无退化；本批恢复8个条目，累计从98项恢复28项，剩余70项为日期冲突24、来源未确认20、粗日期21、署名5，无名称歧义。

| 上下文（动态阈值开/关一致） | 可计算条目 | 剩余原因 |
| --- | ---: | --- |
| L2，不含精选 | 454 | 冲突24、粗日期21、来源17、署名5 |
| L2，含精选 | 460 | 冲突24、粗日期20、来源20、署名4 |
| L3，不含精选 | 435 | 冲突21、粗日期21、来源16、署名3 |
| L3，含精选 | 438 | 冲突21、粗日期21、来源19、署名3 |

真实浏览器在1440×1000桌面选择前4项、390×844手机选择后4项，全部显示对应批准日期和数值半数播放距；后4项重排后列与日期仍对应。四类真实请求均保留正确项目ID集合，手机只挂载一张周期表、页面宽度390无横向溢出，表格独立滚动，截图逐张查看。初次浏览器脚本错误要求规范排序的请求体与显示队列同序，已按实际合同改为核对请求ID集合并独立核对显示顺序；初次脚本失败记录保留，不属于产品故障。

最终原始播放96,881条、歌曲10,480条、署名10,964条，项目专辑成员3,328条、曲目成员8,383条及L3归属7,015条均逐列/语义保持，人工覆盖不变。正式外键检查异常0。启动前其余108项保护投影完全一致，启动后仅追加1条本次正常完成的 `startup_cache_warmup` 账目，旧任务逐列保留，其余107项仍一致；严格差异与精确运行账目追加证明分别保留。

本次新增代码定向验证为113项与ruff；前轮211项后端、29项前端和正式构建证据复用，除新增淘汰及其测试两个文件外，原业务补丁摘要完全一致。对 `snapshot.py` 执行mypy仍有443/668行两个既有pandas scalar `arg-type`错误，在HEAD原文件独立复现；新增淘汰行没有mypy诊断，不宣称该文件mypy全绿。本次未扩大到全量后端、全栈或OOM实验。

私有最终证据位于 `output/versus-release-cycle-20261021/confirmed-eight-apply/`：`acceptance-summary.json`、`snapshot-proof.json`、`installation-proof.json`、`derived-orphan-repair.json`、`prune-before.log`、`prune-after.log`、`schema-cookie-proof.json`、`consumers-pre-resume.log`、`candidate-api.json`、`formal-api.json`、`formal-coverage.json`、`formal-data-proof.json`、`formal-protection-runtime.json`、`browser-proof.json`、`code-repair-receipt.json`及 `local-activation/`。截图位于 `output/playwright/release-eight-20261021/`：`desktop-eight-first-four-final.png`、`phone-eight-last-four-left.png`、`phone-eight-last-four-right.png`。本轮隔离18812与自有浏览器会话已关闭，日常8000/4173保持。没有Git提交、推送或生产发布；生产仍是004既有版本。本批按本地范围完成，剩余70项继续保留版本、精度及署名边界，Thank You两版仍未选择。

## 第三批来源审核与6项建议

> 本节保留选择前的只读审核。用户随后回复“继续”，已按列明的6个版本完成本地应用；当前结果见下方第三批应用验收，原pending提案文件不改写。

日期：2026-10-22。状态：**只读审核完成，6个新主版本待选择，正式剩余仍为70项**。复用上批最终全选择器清单，在同一只读事务重新解析70标签、520次出现，原因和日期无漂移；105个既有候选的完整目录、署名、成员ID与来源所有权重新读取，73个符合前提的候选仅在TEMP影子表绑定、同步和回滚。主库使用URI `mode=ro`，另有main写入拒绝authorizer，写入尝试0；没有改程序、正式来源、日期、项目成员或服务配置，也没有重启或发布。

本批建议如下，精确Spotify Album ID及主专辑/成员/旧日期守卫保存在私有 `next-six-proposals.json`。目录完整、艺人ID验证、来源无其他所有者；下列命中分母为已知原始曲目ID数量，不能解释为播放次数或不同发行完全等价。

| 编号 | 项目 / 建议主来源 | 保留日期 | 完整目录 | 原始ID命中 / 已知ID | 官方日期资料 |
| --- | --- | --- | ---: | --- | --- |
| RC-005 | Chappell Roan / The Rise and Fall of a Midwest Princess | 2023-09-22 | 14首 | 14/15 | [UMG发行公告](https://www.universalmusic.ca/2023/08/02/chappell-roan-announces-highly-anticipated-debut-album-the-rise-and-fall-of-a-midwest-princess-out-september-22/) |
| RC-015 | Gracie Abrams / The Secret of Us（13首版） | 2024-06-21 | 13首 | 13/18 | [UMG发行安排](https://www.universalmusic.ca/2024/06/07/gracie-abrams-releases-highly-anticipated-new-song-close-to-you/) |
| RC-017 | Beyoncé / COWBOY CARTER（27首版） | 2024-03-29 | 27首 | 25/28 | [Sony发行公告](https://www.sonymusic.ca/press_release/beyonce-releases-cowboy-carter) |
| RC-033 | Camila Cabello / Familia | 2022-04-08 | 12首 | 10/12 | [Sony当日发行公告](https://www.sonymusic.ca/press_release/global-icon-camila-cabellos-new-album-familia-out-now) |
| RC-048 | Halsey / The Great Impersonator（18首版） | 2024-10-25 | 18首 | 15/17 | [Sony当日发行公告](https://www.sonymusic.ca/press_release/halsey-releases-new-album) |
| RC-054 | Kendrick Lamar / GNX | 2024-11-22 | 12首 | 3/4 | [UMG发行条目](https://www.universalmusic.ca/2024/11/22/kendrick-lamar-releases-new-album-gnx/)及[官方新闻日期](https://www.universalmusic.ca/media/page/104/) |

COWBOY CARTER公告网页刊登日期为04-02，正文发行日期为03-29；本轮使用正文日期。GNX文章正文只有标题和试听入口，11-22由官方新闻列表明确给出，没有声称正文包含完整日期。Familia的Sony公告→[官方智能链接](https://camilacabello.lnk.to/Familia)→Spotify落到 `5Nn3fX7CuJo7tbibtqASmf`，与建议源完全一致。其余公告佐证发行日期及版本语境，没有把它们表述成直接绑定全部建议Spotify ID。

这些项目包含其他版本曲目或重复ID，所以不要求用选定目录覆盖、删除其他成员。缓存ISRC对应的原始成员命中依次为15/15、13/18、28/28、12/12、17/17、4/4，仅作录音关联证据，不批准版本等价。The Secret of Us现有18条成员中，建议13首版之外的5条为 `That’s So True`、`I Told You Things`、`Cool` 及两条Live From Vevo（`I Love You, I'm Sorry`、`I Knew It, I Know You`），均保持原成员位置。Halsey另一个候选为19首、10-31；本批选择18首、10-25，不把额外曲目或另一日期删掉或判为伪造。

六项联合TEMP预演通过，全部日期文字保持；只有5项精度NULL→day，GNX已为day、无需再改。八种配置全部实际选择器同时核对，既有ready的原因、日期与来源ID无退化；本批共44次现有适用场景成功，预计剩余70→64。Familia目前仅在四个L2选择器场景出现，未强行加入L3，因此不是机械计算6×8=48。初次私有脚本错误预期48次，保留该失败与诊断后，改为按现有选择器资格断言44次；它没有暴露程序故障，也没有正式写入。

| 剩余70项下一步 | 条目数 | 本轮结论 |
| --- | ---: | --- |
| 本批具体主版本选择 | 6 | 待确认上述版本，已完成联合预演 |
| 其他来源日期冲突 | 18 | 保留版本、地区和项目锚点，部分候选会改变现有日期，需单独形成纠正决定 |
| 仅确认年份 | 21 | 保持年份，版本级日证据齐备后再进入日级计算 |
| 单一候选仍缺版别佐证 | 8 | Who You Are、E=MC2、Nevermind、Thank You、Gorilla、Aquarium、Ultraviolence、Let's Get It On继续保留边界 |
| 类型、多个版本或既有所有权 | 12 | 不抢占来源、不合并原声带/演唱艺人、不以ISRC代替版别选择 |
| 艺人署名范围 | 5 | 原声带、团体及演员范围保持，不能靠全局合并艺人消除缺证 |

本轮额外读取的[evermore英国官方CD页面](https://storeuk.taylorswift.com/products/evermore-album-deluxe-edition-cd)给出2020-12-18，指向实体Deluxe CD，不能用它直接否定数字版本12-11或自动纠正Spotify日期；因此未把evermore加入本批。Thank You的2016/15首与2017/17首证据复用上一轮，不伪称本轮重新抓取，也不自动改年。

完整复核和精确建议位于私有 `output/versus-release-cycle-20261021/remaining-review-70/`：`review.py`、`review-with-actions.json`、`propose_six.py`、`next-six-proposals.json`、`member-coverage-details.json`、`external-evidence.json`、`checklist.md`、`summary.json`及 `remaining-review-70.ipynb`。Notebook三段检查已执行；本轮业务补丁与上轮验收摘要完全一致。没有重复运行已经通过的全栈、浏览器或资源实验。下一步是确认这6个新主来源后，再以fresh Online Backup准备、应用和验收；当前正式数量保持70，原先14项已批准来源和本地修复保持。

## 第三批6项正式本地应用与验收

最后核验：2026-10-22。用户在列明六个版本、日期及成员保留说明并询问是否确认之后回复“继续”，本批按该六项执行。原 `remaining-review-70/next-six-proposals.json` 保留选择前pending状态，新的确认语境与决定写入独立治理运行和审计事件。没有批准其余64项，也没有选择Thank You的另一版本。

从当时含前两批14项的正式本地库制作fresh Online Backup，在独立副本重新核对6项主专辑、日期、目录、艺人ID、成员和来源所有权。新增6条primary关系、6条审计事件、1个治理运行；只有5项精度NULL→day，GNX原有day保持，全部日期文字不变。重复应用新增来源/事件/写入均为0。其余108项保护投影、原始三表、项目成员、人工覆盖保持，7015条L3归属只维护上游revision与摘要，规划前后决定一致，没有采用既有Positions规划差异或重分配歌曲。

副本搜索四变体、八上下文96项Billboard、四套详情与个人排名及默认消费者准备通过。本批沿用包含三个详情子表淘汰补漏的既有补丁，开启外键准备，应用后外键检查异常0；没有新增程序改动，也没有重跑已通过的代码回归。正式切换前155张表及schema与fresh源围栏完全一致，七库逐库quick_check通过，旧库inode和首页缓存保存联合恢复点。正式路径的榜单导入、详情manifest与投影、个人排名、2022–2026年度和首页均准备/校验成功，复用原前端构建，日常8000/4173已运行新来源。

隔离与正式本地各43个HTTP请求通过，包含本批44次实际选择器适用场景，均核对精确project_id、来源ID和批准日期；Familia仍只计四个L2选择器场景，不扩大L3资格。原TTPD/Showgirl八配置六指标、首批6项、Positions两个独立发行与重排、两版Lion King以及错误ID/艺人/旧名称歧义保护均通过。全部选择器ID重新解析，所有前轮ready的日期和来源无退化，本批恢复6个条目，当前剩余64项：日期冲突18、来源未确认20、粗日期21、署名5。累计20项主来源确认，原98项共恢复34个条目。

| 上下文（动态阈值开/关一致） | 可计算条目 | 剩余原因 |
| --- | ---: | --- |
| L2，不含精选 | 460 | 冲突18、粗日期21、来源17、署名5 |
| L2，含精选 | 466 | 冲突18、粗日期20、来源20、署名4 |
| L3，不含精选 | 440 | 冲突16、粗日期21、来源16、署名3 |
| L3，含精选 | 443 | 冲突16、粗日期21、来源19、署名3 |

1440×1000桌面实际选择Chappell Roan、Gracie Abrams、Beyoncé三个项目，390×844手机实际选择Familia、Halsey、GNX三个项目，批准日期与数值半数播放距均显示正确。普通榜单、个人统计、个人排名和周期四类最终请求均携带正确项目ID集合并返回200；手机重排后GNX/Halsey的日期仍各自对应，只有一张周期表、页面宽度390无横向溢出，表格独立滚动。三张截图已实际查看；TTPD/Showgirl的六指标复用本批正式HTTP核对，没有无依据扩大页面验收范围。

正式原始播放96,881条、歌曲10,480条、署名10,964条，专辑成员3,328条、曲目成员8,383条以及L3归属7,015条逐列/语义保持，人工覆盖不变。The Secret of Us另外逐项核对5条附加/现场曲目的原始成员链接，前后完全一致，全部18条已知成员仍在。启动后严格检查仅发现追加1条本次正常完成的 `startup_cache_warmup` 账目，旧任务全部保持，其余107项保护投影一致；严格差异与运行账目追加证明分别保留。正式全库外键异常0。

最终私有证据位于 `output/versus-release-cycle-20261021/confirmed-third-six-apply/`：`snapshot-proof.json`、`installation-proof.json`、`idempotence.log`、`preparation-receipts.json`、`candidate-api.json`、`formal-api.json`、`formal-coverage.json`、`formal-data-proof.json`、`formal-protection-runtime.json`、`secret-of-us-members-proof.json`、`browser-proof.json`、`acceptance-summary.json`及 `local-activation/`。截图位于 `output/playwright/release-third-six-20261022/`：`desktop-three.png`、`phone-three-left.png`、`phone-three-right.png`。本批隔离18813与自有浏览器会话已关闭，日常8000/4173保持运行。

本批按本地范围完成。业务补丁与前批验收版本完全一致，前轮113项等代码回归及已记录的mypy基线边界保持，不把本次数据验收称为新增代码测试、全栈或生产验证。未提交、推送或生产发布；生产仍是004既有版本。余64项继续按版本、精度和署名证据审核，不因本批完成自动批准。

## 第四批来源审核与13项建议

最后核验：2026-10-22。本轮承接“继续”审核剩余64项，仅执行正式库只读读取和TEMP预演回滚；未安装本批来源。第三批已应用20项的结论保持，正式剩余仍是64。以下13项为新的具体版本建议，且6项需要项目日期变化，待用户明确选择后才可应用。

64个条目在八配置中共476次出现；93个已有缓存候选完成审核，61次单候选TEMP预演，当前原因/日期/来源ID与第三批正式基线无漂移。联合选择13项可恢复96次现有适用场景，预计64→51，已有ready的原因、日期与来源无退化。剩余预测为粗日期21、来源未确认20、日期冲突5、艺人署名5。没有把预演称为真实应用或浏览器验收。

### 七项保留日期

| 项目 | 建议版本 | 保留日期 | 来源ID |
| --- | --- | --- | --- |
| Taylor Swift / [evermore](https://music.apple.com/us/album/evermore/1544268281) | 15首 | 2020-12-11 | `2Xoteh7uEpea4TohMxjtaq` |
| Katy Perry / [Teenage Dream](https://music.apple.com/us/album/teenage-dream/716192216) | 12首 | 2010-08-24 | `32Uy0GLddTw4559CWja1f1` |
| Olivia Rodrigo / [you seem pretty sad for a girl so in love](https://store.oliviarodrigo.com/products/you-seem-pretty-sad-for-a-girl-so-in-love-digital-album) | 13首 | 2026-06-12 | `3WZZF72ihlKPZBS4zSsNHl` |
| Kacey Musgraves / [Middle of Nowhere](https://www.universalmusic.ca/2026/03/11/eight-time-grammy-winning-superstar-kacey-musgraves-announces-sixth-studio-album-middle-of-nowhere-set-for-release-may-1-2026/) | 13首 | 2026-05-01 | `1quFS6EneVBW7PTbipPlNg` |
| Lizzo / [Special](https://music.apple.com/us/album/special/1634655863) | 12首 | 2022-07-15 | `1NgFBv1PxMG1zhFDW1OrRr` |
| Selena Gomez / [I Said I Love You First](https://storeuk.selenagomez.com/products/i-said-i-love-you-first-digital-album) | 14首 | 2025-03-21 | `5v7xYJyke25Nmt3l2R7YkR` |
| BLACKPINK / [BORN PINK](https://ygfamily.com/jp/artists/blackpink/discography/1281) | 8首 | 2022-09-16 | `7jaSNQUBJbvfbZHLNFrV7P` |

这七项中evermore和Middle of Nowhere已有day精度保持，其余5项仅精度NULL→day。数字平台Apple Music的evermore、Teenage Dream、Special页面是对应数字版本的第一方声明，其余资料为艺人或厂牌；均用于日期与版别语境佐证，不宣称外部页面直接链接全部建议Spotify ID。

### 六项需要明确项目日期变化

| 项目 | 建议版本 | 当前日期 → 建议日期 | 来源ID |
| --- | --- | --- | --- |
| SZA / [SOS](https://www.sonymusic.ca/press_release/szas-sos-out-now) | 23首 | 2022-12-08 → 2022-12-09 | `07w0rG5TETcyihsEIZR3qG` |
| Conan Gray / [Wishbone](https://www.universalmusic.ca/2025/08/15/conan-gray-releases-highly-anticipated-album-wishbone/) | 12首 | 2025-08-14 → 2025-08-15 | `1Q0kTJx8DrQd8RJW9L7eIN` |
| Mariah Carey / [Caution](https://www.sonymusic.ca/press_release/global-superstar-mariah-carey-releases-mega-anticipated-new-album-caution-today) | 10首 | 2018-11-17 → 2018-11-16 | `64zK6tmksJw9gNZR0L4DVx` |
| LISA / [Alter Ego](https://www.sonymusic.ca/press_release/lisa-announces-highly-anticipated-debut-solo-album-alter-ego-out-february-28-2025) | 15首 | 2025-02-26 → 2025-02-28 | `5eoWRkeplmcCL97afSMJVm` |
| Miley Cyrus / [Endless Summer Vacation](https://www.sonymusic.ca/press_release/miley-cyrus-reveals-tracklist-for-forthcoming-eighth-studio-album-endless-summer) | 13首 | 2023-08-18 → 2023-03-10 | `0HiZ8fNXwJOQcrf5iflrdz` |
| The Weeknd / [Starboy](https://www.universalmusic.ca/2016/09/28/weeknd-makes-biggest-opening-weekend-streaming-history-new-single-starboy/) | 18首 | 2016-11-24 → 2016-11-25 | `2ODvWsOgouMbaA5xf0RkJe` |

六项当前精度均为NULL；采用具体主来源后，现有 `sync_project_release_precisions` 可在同年、来源精确一致的条件下同步派生项目日期和day精度，不重写原始声明。本批没有新增程序缺口。Miley明确选择13首原专辑版，08-18→03-10属于版别选择带来的日期变化，不能描述成一天时区修正；14首后续版本、Used To Be Young及现有成员均保留。日期变化会影响发行周及距发行日指标，后续批准后应在fresh副本重建并独立对账，不能要求所有旧指标数值保持。

### 成员与归属预演边界

13项目录均完整、艺人ID已核实、来源未被其他项目占用；这些条件足够提出主来源建议，不等于批准所有版本完全等价。Teenage Dream原始ID直接命中0/15，缓存目录ISRC仅1条、命中1/15；Special原始ID0/2、缓存ISRC1/2；Miley原始ID0/10、ISRC9/10。稀疏缓存和未直接命中均明确保留，不能据此删除其余录音或替换项目成员。

按缓存ISRC检查，evermore的两条bonus、SOS的19条其他版本成员、Wishbone的5条、Miley的Used To Be Young，以及Starboy中未命中的3条原始记录均保留。Starboy未命中包括Die For You、其Ariana Grande混音与Stargirl Interlude；未命中并不证明歌曲属于其他专辑。成员逐条明细在私有证据，不把ISRC覆盖当成成员修改授权。

对联合预演前后执行只读L3规划：目标项目变化0；75条决定仅 `winning_rank` 中的日期证据变化，除此之外决定字段完全一致。问题、排除、未归属、冲突、排除歌曲集合及扫描数量六项相同。正式源写入/主库写入尝试均0。已发布归属未改；这是预演，后续真正维护仍需验证原始记录、成员、人工覆盖和已发布归属保全。

### 其余五项日期冲突

143当前09-19、An Evening With Silk Sonic当前11-11、Scarlet当前09-20以及I AM...SASHA FIERCE当前11-14均已是day，新的不同日期来源不能覆盖已确认锚点。143的[厂牌公告](https://www.universalmusic.ca/2024/09/20/katy-perrys-new-studio-album-143-is-out-today/)给出09-20，仍应另形成日期纠正决定，不能TEMP强改绕过门禁；另外三项还需地区/版别佐证。慢慢懂的06-01与11-19尚未厘清，保留冲突。这五项未列入本批。

| 64项下一步 | 数量 |
| --- | ---: |
| 本批具体主版本/日期选择 | 13 |
| 仅年份证据，继续保留粗日期 | 21 |
| 单候选仍待版别佐证 | 8 |
| 其他日期冲突 | 5 |
| 类型、多个版本或既有所有权 | 12 |
| 艺人署名范围 | 5 |

完整证据：私有 `output/versus-release-cycle-20261021/remaining-review-64/` 下 `review.py`、`review-with-actions.json`、`propose_thirteen.py`、`next-thirteen-proposals.json`、`preview_with_planner.py`、`joint-l3-planner-proof.json`、`member-coverage-details.json`、`external-evidence.json`、`checklist.md`、`summary.json`及 `remaining-review-64.ipynb`。Notebook三段核查实际执行通过；首次planner脚本导入路径错误在打开源库前发生，保留失败记录并在修正路径后成功完成。业务补丁SHA与第三批验收完全一致，本轮未新增业务代码、数据写入或服务重启，未重复全栈、浏览器与资源测试。文档审计和差异检查另行执行。

下一步：请用户确认这13个具体版本，并明确同意表中6项项目日期变化；获批后按fresh Online Backup、严格源围栏、副本准备、受控本地应用及受影响HTTP/桌面手机验收推进。原始记录、项目成员、人工决定及歌曲目标归属保持；生产发布与Git提交不在本轮授权内。

## 第四批13项正式本地应用与验收

最后核验：2026-10-22。用户明确确认13个版本及6项日期变化，并要求原始记录、项目成员和歌曲归属不变；精确原文保存为独立 `user-confirmation.json`，不改写前一节选择前提案。第四批按上方13个来源ID执行，没有批准余51项或Thank You另一版本。

从含前三批20项来源的当前正式库制作fresh Online Backup，重新核对13项主专辑、日期、目录、艺人ID、成员、来源所有权及业务补丁。副本追加13条primary关系、13条审计事件、1个治理运行；6项日期文字按确认变化，5项仅精度NULL→day，evermore和Middle of Nowhere原day保持。全部11个项目日期pair变化与白名单一致，无其他项目日期变化。重复应用新增记录/事件/写入均0。

原始三表、成员、人工覆盖及7015条已发布L3归属保持；规划前后目标归属变化0，75条规划决定仅日期排名证据变化，不采用既有Positions等无关规划差异。只维护已发布L3投影上游revision与摘要，已发布归属语义逐行一致。副本108项其他保护投影相等。

副本搜索四变体、八上下文96个Billboard发布项、四套详情投影、个人排名及默认消费者准备/验证通过。正式切换前155张表及schema与fresh基线完全一致，七库quick_check通过，旧库原inode及首页缓存保留为联合恢复点。正式路径周榜导入、详情manifest与投影、排名、2022–2026年度及首页准备/验证完成，复用既有前端成品，日常8000/4173运行新来源。

隔离与正式各70个HTTP请求通过：本批96次实际选择器场景的项目ID、来源ID及批准日期精确对应；原TTPD/Showgirl八配置六指标保持，前20项来源逐项复核，Positions两独立发行与重排、两版Lion King、无效ID/错误艺人及旧名歧义保护均保持。全部实际选择器ID重新解析，既有ready原因、日期和来源无退化。本批恢复13项，当前剩余51：粗日期21、来源未确认20、日期冲突5、署名5；累计33项主来源、原98项恢复47项。

| 上下文（动态阈值开/关一致） | 可计算条目 | 剩余原因 |
| --- | ---: | --- |
| L2，不含精选 | 473 | 粗日期21、来源17、冲突5、署名5 |
| L2，含精选 | 479 | 粗日期20、来源20、冲突5、署名4 |
| L3，不含精选 | 451 | 粗日期21、来源16、冲突5、署名3 |
| L3，含精选 | 454 | 粗日期21、来源19、冲突5、署名3 |

新增独立算术对账从所选项目逻辑事件、艺人/大盘逐日次数及已发布周榜名次复算六指标，不调用 `compute_release_metrics`。四个L2配置各13项、四个L3配置各11项，共96次比较/576个指标全部一致，正式接口与同一独立期望再比对通过。日期变化后的值按新锚点验证，不要求沿用旧指标；没有为缺少原始版本ID重写记录或成员。初次私有验收分组三项导致13项末组仅1项，触发2至4项对象约束；修复分组及一次脚本替换语法错误后成功，失败记录保留，没有业务补丁或正式数据纠正。

1440×1000桌面实际选择7个保留日期项目，390×844手机实际选择6个改期项目，四组共13项目全部显示批准日期和正确数值。普通榜单、个人统计、个人排名、周期四类最终请求携带正确ID集合、返回200；请求按既有canonical顺序排序，页面仍按队列重排。手机Miley/Starboy互换后日期仍对应，表格单独横滚，页面宽度390、仅挂载一张周期表。6张截图均实际查看；第一次浏览器脚本错误要求请求顺序等于UI队列，改为核对ID集合；第一次完整断言未返回机器记录，补显式return后重跑收集，均为私有验收脚本问题，业务代码不变。

正式原始播放96,881、歌曲10,480、署名10,964，专辑成员3,328、曲目成员8,383及歌曲归属7,015逐列/语义保持，人工覆盖保全。evermore两首bonus、SOS扩展成员、Miley的Used To Be Young及Starboy其他录音均随完整原始/成员/归属证明保留。启动账目仅追加1条done的startup_cache_warmup，旧任务完全保持，107项其他保护投影相等；严格差异与运行账目追加证明分别保留。正式全库外键异常0。

私有证据：`output/versus-release-cycle-20261021/confirmed-fourth-thirteen-apply/` 下 `snapshot-proof.json`、`user-confirmation.json`、`installation-proof.json`、`idempotence.log`、`preparation-receipts.json`、`candidate-api.json`、`formal-api.json`、`formal-coverage.json`、`six-metric-reconciliation.json`、`metrics-verification.json`、`formal-data-proof.json`、`formal-protection-runtime.json`、`browser-proof.json`、`acceptance-summary.json`及 `local-activation/`。截图在 `output/playwright/release-fourth13-20261022/`。隔离18813与本次浏览器会话已关闭，日常服务保持。

本批已完成本地应用与验收，无新增业务改动，业务补丁SHA仍为19c1a80d59779541796818998d3155490554b1e49e359f080f6e6b351cb54270；复用前轮代码回归与构建，不重复全栈或资源实验，原mypy基线边界保持。未提交、推送或生产发布，生产仍为004既有版本。下一步按原精度/版别/署名证据清单处理余51项，不由本批确认自动扩大批准范围。

## 第五批来源审核与9项建议

最后核验：2026-10-22。本轮“继续”用于审核第四批之后余51项，没有安装新的主来源或改写日期。当前正式仍为33项来源已确认、原98项恢复47、余51项；下列9个版本和4项日期变化需要新的明确决定，其中3项涉及已确认day锚点纠正。

### 现状与候选覆盖

按第四批正式八配置基线重新解析，51个条目共380次出现，原因、日期与来源ID无漂移；来源20、粗日期21、冲突5、署名5。原来源链有64个候选，本轮扩展现有缓存的标题包含及已核实艺人ID候选发现，得到69个候选、36次单候选TEMP预演。标题匹配只用于发现，不能证明版别等价。新增5个候选中，只有Jack Harlow的完整15首专辑进入本批；1432是后续15首版、Olivia/Halle两项是电影单曲，Faye Wong的Remastered缓存01-01与外部对应版02-05不一致，均不自动采用。51项完成现状复核不等于51项均取得新的外部日级证据。

Jack Harlow项目原候选仅First Class单曲，缓存实际已有完整专辑2eE8BVirX9VF8Di9hD90iw。这是私有审核候选清单覆盖遗漏，已扩展本轮审核；不是需要修改自动消费者或放宽单曲/专辑门禁的新程序缺口。主发行关系仍须明确批准。

### 五项保留日期的主来源建议

| 项目 | 建议版本 | 保留日期 | Spotify来源ID |
| --- | --- | --- | --- |
| Sam Smith / [The Thrill Of It All](https://music.apple.com/us/album/the-thrill-of-it-all-special-edition/1440904103) | 14首 | 2017-11-03 | `3TJz2UBNYJtlEly0sPeNrQ` |
| Jack Harlow / [Come Home The Kids Miss You](https://music.apple.com/us/album/come-home-the-kids-miss-you/1622624421) | 15首 | 2022-05-06 | `2eE8BVirX9VF8Di9hD90iw` |
| Beyoncé / [I AM...SASHA FIERCE](https://open.spotify.com/album/23Y5wdyP5byMFktZf8AcWU) | 16首 | 2008-11-14 | `23Y5wdyP5byMFktZf8AcWU` |
| David Tao / [Live Again 陶喆小人物狂想曲現場專輯](https://music.apple.com/us/album/live-again-%E9%99%B6%E5%96%86-%E5%B0%8F%E4%BA%BA%E7%89%A9%E7%8B%82%E6%83%B3%E6%9B%B2-%E7%8F%BE%E5%A0%B4%E5%B0%88%E8%BC%AF/1246658516) | 31首 | 2017-06-08 | `5FezUaPxYnK9LkAjYDDFEv` |
| The Beatles / [The Beatles 1967 - 1970](https://www.thebeatles.com/beatles-1967-1970) | 28首 | 1973-04-02 | `1cTeNkeINtXiaMLlashAKs` |

Sam Smith明确选14首Special Edition的3TJz版本，另一同日/同首数来源保留，不批准所有版本等价。Beyoncé采用Spotify公开同ID页标注的16首/11-14，保留已有day，不以Apple另12首/20首版的11-12或另一11首来源11-17替代。Beatles官网直接嵌入建议Spotify ID，并给出1973-04-02；对应28首Remastered，不选2023年37首版。Beatles继续保持compilation类型。

### 四项日期变化与明确纠正范围

| 项目 | 建议版本 | 当前日期 → 建议日期 | 当前精度 | Spotify来源ID |
| --- | --- | --- | --- | --- |
| Madonna / [Celebration](https://music.apple.com/us/album/celebration-deluxe-version/1874757108) | 37首 | 2009-09-18 → 2009-09-29 | NULL | `28Ts8e6rqdmSPH6itDV4KP` |
| Katy Perry / [143](https://www.universalmusic.ca/2024/09/20/katy-perrys-new-studio-album-143-is-out-today/) | 11首 | 2024-09-19 → 2024-09-20 | day | `3jxt1S4JtW4uFalBwlfehS` |
| Bruno Mars / [An Evening With Silk Sonic](https://music.apple.com/us/album/an-evening-with-silk-sonic/1612867237) | 10首 | 2021-11-11 → 2021-11-12 | day | `4VZ7jhV0wHpoNPCB7Vmiml` |
| Doja Cat / [Scarlet](https://www.sonymusic.ca/press_release/doja-cat-releases-fourth-studio-album-scarlet) | 17首 | 2023-09-20 → 2023-09-22 | day | `6DmPNcfpkXBVRJsEIJY9tl` |

Madonna选择37首Deluxe数字版，09-18→09-29；不能用36首实体、38首加视频版或68项视频版本替这37首版背书，另一37首双碟来源保留，compilation类型不变。Bruno采用10首数字版（含Love’s Train），平台专辑日期11-12，不主张额外歌曲全部在该日首次发行，也不改变现有合作艺人/项目范围。Scarlet选择17首版，厂牌公告正文明确09-22及17曲；网页更新日期与另一15首版声明均不覆盖或删除。

143、Silk Sonic、Scarlet的旧日期均已是day。联合TEMP先只绑定来源并调用原同步函数，三项仍返回release_date_conflict，验证保护门禁保持。然后仅在只读主库的TEMP影子表中，模拟用户另行明确批准的3条项目日期纠正，旧pair精确匹配后更新派生项目锚点，再解析才可计算。正式应用若获批，必须把这3项作为独立明确日期纠正决定/审计事件，保留旧值和证据，再维护revision；不能降为NULL、修改Spotify原始日期、改变通用自动同步规则或把普通主来源确认当成改期授权。

### 联合预演、成员与归属边界

9项联合预演64次实际适用场景通过：7项各八配置，Beatles/Madonna仅四个含精选配置；未扩大现有L3或精选资格。预计51→42，余粗日期21、来源15、署名5、日期冲突1（慢慢懂）。共有8个项目date pair变化：4项仅精度NULL→day、Madonna的NULL旧pair改期到day、3项已day明确纠正；Beyoncé既有day保持。既有ready的原因、日期、来源ID无退化，项目成员未变化，正式源写入及主库写入尝试均0。正式仍51，42是条件预测。

联合预演前后只读L3规划目标归属变化0，29条决定仅winning_rank日期证据变化；其余决定字段、问题、排除、未归属、冲突、排除集合与扫描数量保持。没有把这些规划结果直接写为已发布归属，也不采用既有Positions等无关差异。获批应用仍须以fresh副本和正式读接口验证。

Jack原始ID0/1、缓存ISRC1/1；Beyoncé原始ID0/6、ISRC6/6；Tao原始ID/ISRC均2/4，目录之外的寂寞的季節与Susan說保留原成员和目标归属。143既有15条中，I WOKE UP、HAS A HEART、NO TEARS FOR NEW YEAR’S、OK不在所选11首目录对应缓存ISRC中，全部保留。Madonna原始20条中19条命中缓存ISRC，未命中Material Girl不代表不属于该项目；缓存覆盖不能批准删除或版本完全等价。

### 本批以外的边界

八项曾列单候选待补证者仍未批准：Who You Are、E=MC2、Nevermind、Thank You、Gorilla、Aquarium、Ultraviolence、Let’s Get It On。其余标题发现没有形成可直接安装的日级来源，王菲Remastered的[Apple对应页](https://music.apple.com/hk/album/%E5%9F%B7%E8%BF%B7%E4%B8%8D%E6%82%94-remastered-2019/1488204120)给出02-05而缓存为01-01，两者分别保存；原版来源year保持，不改成看似合理的日。署名/原声带来源已有所有权也不抢占，Thank You跨年版本尚未选择，慢慢懂06-01/11-19仍需厘清版别和日期。

本轮证据位于私有 `output/versus-release-cycle-20261021/remaining-review-51/`：`review.py`、`initial-linked-candidate-review.json`、`review-with-actions.json`、`cached-title-discovery.json`、`propose_nine.py`、`next-nine-proposals.json`、`joint-l3-planner-proof.json`、`member-coverage-details.json`、`external-evidence.json`、`checklist.md`、`summary.json`、`remaining-review-51.ipynb`。Notebook三段校验实际执行通过。业务补丁与第四批正式本地验收完全一致；无代码、正式数据库或服务修改，不重复已通过的代码回归、浏览器、全栈或资源实验。

下一步请用户明确确认上述9个主来源与4处日期变化，特别是3个已确认day锚点的纠正。获批后按fresh Online Backup、精确旧pair/成员/来源围栏、独立副本准备、歌曲归属保全、受控本地应用及受影响接口/真实页面验收推进；不因本轮“继续”自动执行新增选择。

## 第五批修正后8项正式本地应用与验收

最后核验：2026-10-22。原9项建议之后，用户要求联网核查4项变化的标准发行时间；新查证明确143=2024-09-20、An Evening With Silk Sonic=2021-11-12、Scarlet=2023-09-22。Celebration存在09-18地区发行与美国09-29差异，撤回把项目日期改09-29及本批主版本选择，继续保留待定。用户在该修正结论后回复“ok”，本次按8项主来源/3项明确日期纠正执行；完整确认语境保存于user-confirmation.json，原九项提案和预演保留为选择前历史，不改写其数字。

| 已应用项目 | Spotify主来源ID | 日期决定 |
| --- | --- | --- |
| Sam Smith / The Thrill Of It All，14首Special Edition | 3TJz2UBNYJtlEly0sPeNrQ | 保留2017-11-03，仅确认精度day |
| Jack Harlow / Come Home The Kids Miss You，15首专辑 | 2eE8BVirX9VF8Di9hD90iw | 保留2022-05-06，仅确认精度day |
| Beyoncé / I AM...SASHA FIERCE，16首版 | 23Y5wdyP5byMFktZf8AcWU | 保留2008-11-14及原day |
| 陶喆 / Live Again 小人物狂想曲现场专辑，31首 | 5FezUaPxYnK9LkAjYDDFEv | 保留2017-06-08，仅确认精度day |
| The Beatles / The Beatles 1967 - 1970，28首Remastered | 1cTeNkeINtXiaMLlashAKs | 保留1973-04-02，仅确认精度day；compilation类型保持 |
| Katy Perry / 143，11首原版 | 3jxt1S4JtW4uFalBwlfehS | 2024-09-19 day → 2024-09-20 day |
| Bruno Mars / An Evening With Silk Sonic，10首数字版 | 4VZ7jhV0wHpoNPCB7Vmiml | 2021-11-11 day → 2021-11-12 day |
| Doja Cat / Scarlet，17首版 | 6DmPNcfpkXBVRJsEIJY9tl | 2023-09-20 day → 2023-09-22 day |

三项日期纠正有单独标准日期联网证据：143的[厂牌预告](https://www.universalmusic.ca/2024/07/10/global-pop-superstar-katy-perrys-new-album-143-confirmed-for-september-20-release-via-capitol-records/)及[当日发行公告](https://www.universalmusic.ca/2024/09/20/katy-perrys-new-studio-album-143-is-out-today/)，Silk Sonic的[对应平台版本](https://music.apple.com/us/album/an-evening-with-silk-sonic/1612867237)与[当日九首版发行报道](https://digital.abcaudio.com/news/new-music-friday-silk-sonic-lil-wayne-john-legend-and-rick-ross)，Scarlet的[厂牌公告正文及17曲目录](https://www.sonymusic.ca/press_release/doja-cat-releases-fourth-studio-album-scarlet)。保留首发9首与现10首版本区别，不把追加曲目的日期当专辑首发。Celebration的[地区发行记录](https://musicbrainz.org/release-group/bd252c17-ff32-4369-8e73-4d0a65a316bd)与[官网美国发行公告](https://www.madonna.com/blogs/news/a-celebration-of-madonna-music-the-ultimate-greatest-hits-collection-september-28th-release)支持地区差异，不能据09-29否定项目09-18。

从当前含前四批33项来源的正式本地库制作fresh Online Backup，再核对8项主专辑、旧日期pair、目录、艺人ID、成员与来源所有权。副本新增8条primary关系、1个治理运行，以及8条set_primary_release_source和3条correct_confirmed_release_anchor审计事件。普通来源绑定/同步仅改4项精度，三个已day项目仍返回冲突；只有执行明确批准、精确旧pair守卫的三个日期纠正后才可计算。未降低旧日期精度、未改通用同步函数或Spotify原始日期。重复安装新增记录/事件/写入均0。

初次副本安装沿用原9项规划的29条日期证据变化断言，排除Celebration后被守卫拒绝，事务完整回滚、治理事件0、原pair保持，正式源未动。按修正后8项重新进行只读TEMP预演，确认60次适用场景、21条规划日期证据变化；再安装成功。每条变化仅允许批准项目的精确旧/新日期，目标归属、其他决定字段、问题/排除及未归属/冲突集合保持；已发布7015条L3归属逐行保全，仅维护上游revision及摘要，不采用Positions等无关规划差异。原29条预演及失败证据保留，不把私有范围断言错误描述为新增程序缺口。

副本搜索四变体、八上下文96个Billboard发布项、四套详情投影、个人排名及默认消费者准备/验证通过。正式切换前155张表及schema与fresh源围栏完全一致，七库quick_check通过，旧库原inode及首页缓存保留为联合恢复点。正式路径周榜导入、详情manifest与投影、排名、2022–2026年度及首页均准备/验证完成，复用既有前端成品，日常8000/4173运行新来源。

隔离与正式各66个HTTP请求通过。本批60次实际选择器资格（7项各八配置，Beatles仅四个含精选配置）的项目ID、来源ID和日期精确对应；独立从逻辑事件、艺人/大盘逐日次数及周榜名次复算360个指标，隔离与正式均一致，不调用compute_release_metrics。前33项来源逐项再核对，原TTPD/Showgirl八配置六指标、Positions两独立发行和重排、两版Lion King、无效ID/艺人及旧名歧义保护保持。全部实际选择器重新解析，既有ready的原因、日期、来源无退化。本批恢复8项，当前剩余43：粗日期21、来源16、署名5、日期冲突1；累计本问题链确认41项主来源、原98项恢复55项。

桌面1440×1000实际选择Sam Smith、Jack Harlow、Beyoncé、陶喆四个项目；手机390×844实际选择143、Silk Sonic、Scarlet并重排，批准日期与半数播放距数值正确。四类最终请求携带正确ID集合并返回200，手机只有一张周期表、页面宽度390无横向溢出，表格独立横滚，重排后三项日期正确对应。3张截图实际查看。Beatles使用四个含精选配置的真实API与独立指标对账，未改用户精选设置；没有把它描述成默认页面或此次真实浏览器已选项目。

正式原始播放96,881、歌曲10,480、署名10,964，专辑成员3,328、曲目成员8,383、歌曲归属7,015逐列/语义保持，人工覆盖保全。Tao原成员中寂寞的季節/Susan說以及143的4条后续版本成员均保留。Celebration另做副本及正式精确保留证明：完整项目行、成员关系、项目外部来源及两份原始Spotify缓存均相等，仍2009-09-18/NULL，没有新增主来源。启动账目仅追加1条done的startup_cache_warmup，旧任务不变，107项其他保护投影相等；严格差异和运行账目追加证明分别保留。正式全库外键异常0。

私有证据：output/versus-release-cycle-20261021/confirmed-fifth-eight-apply/下user-confirmation.json、approved-eight-sources.json、standard-release-evidence.json、snapshot-proof.json、approved-eight-preview.json、joint-l3-planner-proof.json、installation-first-attempt.json、installation-proof.json、idempotence.log、preparation-receipts.json、candidate-api.json、formal-api.json、formal-coverage.json、six-metric-reconciliation.json、metrics-verification.json、formal-data-proof.json、formal-protection-runtime.json、formal-celebration-held-proof.json、browser-proof.json、acceptance-summary.json及local-activation/。截图位于output/playwright/release-fifth8-20261022/。隔离18813和本次浏览器会话已关闭，日常服务保留。

本批已完成本地应用与验收。没有新增业务代码，业务补丁SHA仍为19c1a80d59779541796818998d3155490554b1e49e359f080f6e6b351cb54270；复用前轮代码回归与前端构建，不重复全栈或资源实验，原mypy基线边界保持。未提交、推送或生产发布。剩余43项含Celebration、慢慢懂及粗日期/版别/署名边界继续待审，不因本次ok自动批准。

## 第六批43项复核与3项待确认来源

2026-10-22，按用户要求继续审核全部43项，日期冲突先联网核实，再整理下一批可确认来源。本轮只读审核和TEMP预演，**未应用新来源或日期；正式剩余仍43项**。原始记录、项目成员、歌曲归属及业务代码保持；不提交、推送、部署或重启服务。

### 当前证据与下一批建议

八上下文320次出现重新解析，原因与第五批正式清单一致：粗日期21、来源未确认16、艺人署名5、日期冲突1。52个候选行对应51个唯一现有Spotify来源；本轮通过正式SpotifyProvider读取51个现有来源及2个新候选，共53份完整目录，仅保存私有审核文件。现有来源的日期/精度、标题、类型、曲数和专辑艺人ID均无变化；ROSÉ现场专辑和Maroon 5的Hands All Over两个来源的曲目ID目录有变化，未覆盖旧缓存。对25个条目另整理44条公开网页证据，包括厂牌/艺人资料、同期报道和平台具体版本声明；未声称全部43项的标准日期均已查实。

以下三项具备可审查的具体主来源建议；选择的是对应版本及项目采用日，不宣称所有收录曲都在该日首次发行，也不批准其他版本完全等价。

| 编号 | 项目与建议主来源 | 当前项目日期/精度 | 建议采用日 | 证据与动作 |
| --- | --- | --- | --- | --- |
| RC-056 | Meghan Trainor / Thank You，2016年15首Deluxe；Spotify `5nkgosKhWt1yXRzmjXNV2d` | 2017-05-12 / NULL | **2016-05-13 / day** | [索尼2016年发行公告](https://www.sonymusic.co.uk/meghan-trainor-releases-new-album-thank-you/)直接链接此ID；本轮复取15首完整目录和15条ISRC，3条已知成员ID/ISRC全部命中。新来源尚未装入正式缓存；需要明确批准跨年锚点纠正，保留2017年17首重装版。 |
| RC-087 | 汪苏泷 / 慢慢懂，12首2010-11-19版；Spotify `7yjELdNsfaw0fi5J8ndWkf` | 2010-06-01 / NULL | **2010-11-19 / day** | [2010年11月22日同期报道](https://ent.sina.com.cn/y/2010-11-22/10553153872.shtml)记载11月19日发布会及完整专辑发售；同ID索引及现行API日期一致。3条已知成员ID命中1条、缓存ISRC命中2条，未命中者仍保留；06-01来源声明原样保持，不据此断言此前不存在数字发行。 |
| RC-090 | Marvin Gaye / Let’s Get It On，10首Expanded；Spotify `6AmnVWOxXYucWxgidEgwhy` | 1973-08-28 / NULL | **保留1973-08-28，精度至day** | [Motown发行史](https://classic.motown.com/story/marvin-gaye-gets-romantic-soul-landmark/)明确原专辑日；[同ID播放器](https://open.spotify.com/embed/album/6AmnVWOxXYucWxgidEgwhy)及本轮API核实10首目录，API日期与现缓存同为08-28。原1条成员ID未直接命中、缓存ISRC命中；原8首、10首Expanded及41首周年版分别保留。 |

Thank You的05-13表示所选Spotify版及索尼公告的正式发行日；[Apple 15首页](https://music.apple.com/us/album/thank-you-deluxe/1089260132)另有2016-05-06提前独家串流声明，单独保留，不能把05-13表述为全球最早可收听日。索尼台湾的[2017年17首重装版](https://sonymusic.com.tw/album/thank-you-deluxe-edition/)也有独立证据，不将原2017声明当成坏数据删除。

### Title日期已查明，但本批暂缓

[Spotify对应18首Expanded来源](https://open.spotify.com/intl-pt/album/7m2Gzfu5nMgHTiMbNDwPr7)及本轮API均声明2015-01-09；[索尼目录](https://www.sonymusic.es/artista/meghan-trainor/)分别列出2015年Expanded/Deluxe与2025年十周年版。日期与版本证据足以继续治理，不能直接把2025十周年日期当作原专辑首发。

然而四项联合TEMP预演发现：把Title项目从2025-03-28改回2015-01-09后，规划器会将I’ll Be Home（`l1:4447`）从A Very Trainor Christmas（41603）改归Title（41547）。这只是内存规划结果，**没有应用到正式库**。按照保持歌曲归属不变的边界，本批移出RC-055，不通过修改成员、覆盖歌曲归属或只保留旧发布成品掩盖此影响。原四项失败门禁及具体前后决定保留，后续须先解决日期变化与现有归属保护的治理关系。

### 仍未闭合的日期与版别

| 条目 | 本轮核实结果 | 保留边界 |
| --- | --- | --- |
| Jessie J / Who You Are | 缓存/live为16首Platinum、2011-01-01；Apple同名版17首/02-25，环球德国Deluxe11-18。 | 曲数、版本、地区未一致，不能把任一外部日期直接覆盖16首来源。 |
| Mariah Carey / E=MC2 | 16首Deluxe缓存/live与Apple为2008-04-04；环球德国原版CD04-11、日本产品原始日04-16。 | 平台一致不等于标准首发已查实；不把某地区原版日期套给Deluxe。 |
| Nirvana / Nevermind | Sub Pop明确原专辑1991-09-24；现Remastered来源仍09-26。 | 原始来源声明保持，不能仅改项目日绕过冲突。 |
| James Taylor / Gorilla | 艺人官网只给1975年5月，Apple11首Remastered与Spotify给05-01。 | 官网月级资料不能独立证实1日；也不凭月首外观判定provider错误。 |
| Aqua / Aquarium | 当年报道原专辑丹麦03-26；Apple17首Special Edition06-26；Spotify对应17首仍01-01。 | 原版、特殊版与地区日分别保存，暂不选择。 |
| Lana Del Rey / Ultraviolence | 环球德国发行报道2014-06-13，美国厂牌公告06-17；现14首Deluxe来源仍01-01。 | 不用北美日期代替更早地区首发，不改当前来源声明。 |
| Madonna / Celebration | 09-18与09-29仍涉及地区/版本；本轮新取Bonus Track Version实际38首。 | 保持项目09-18及两个37首现有来源；不把38首候选视作同一37首版。 |
| Kristen Bell / Frozen | Disney原始公告及Apple59首Deluxe均2013-11-25，现来源仍01-01。 | 另有原声带署名范围及项目44520所有权问题；不抢占来源或擅自纠正已有day锚点。 |
| 王菲 / 執迷不悔 | 原版仍year；Spotify Remastered为01-01，Apple同名10首为1993-02-05。 | 不升级原year、不改写Remastered原始声明。 |

其余粗日期项仍仅保留已确认年份。已找到的艺人/厂牌日级参考，如Spirit 2007-11-09、Tapestry 1971-02-10、Dizzy Up the Girl 1998-09-22、American Pie 1971-10-24、9 to 5 and Odd Jobs 1980-11-17、東京夜景1978-06-21，均作为独立证据保存，不能直接写成原Spotify来源的day精度。Under My Skin官方不同产品说明、The Moment平台与周年影片索引等仍有地区/版别差异；完整逐项动作以私有checklist为准。

### 验证结果与后续

正式主库全程SQLite URI `mode=ro`，authorizer拒绝主库写入；19次单候选及最终三项联合预演均只改TEMP影子表并回滚。最终三项在24次适用场景均解析到指定ID/日期，所有既有ready的原因、日期及来源无退化。L3前后规划目标归属差异0、问题/排除/冲突集合等语义相等；5条决定仅发行日期排序证据变化。保留原四项含Title的1条目标归属差异，不将其描述为通过。

只绑定来源并常规同步会更新2个项目；Thank You跨年旧锚点仍保持2017-05-12/NULL，需要另外批准精确旧值到2016-05-13/day的治理纠正。最终三项涉及2个日期字符串变化和1个纯精度变化。确认并受控应用后预计剩余40：粗日期21、来源未确认14、艺人署名5；**目前仍43，三项均未批准安装**。

当前原始播放96,881、歌曲10,480、署名10,964、专辑成员3,328、曲目成员8,383、已发布歌曲归属7,015；计数和项目/归属revision与审核基线一致，主库写入尝试0。只读保证覆盖原始记录、成员及归属保全，不用计数相等替代逐行应用证明。本轮无正式应用，未重复HTTP、浏览器、前端构建、全栈或资源测试；既有本地修复与第五批实际验收结论保持，业务补丁摘要不变。

私有证据位于`output/versus-release-cycle-20261021/remaining-review-43/`：review.py、review-with-actions.json、checklist.md、fetch_catalogs.py、live-catalogs.json、live-cache-differences.json、external-evidence.json、new-source-track-evidence.json、propose_four.py、joint-l3-preliminary.json、held-title-attribution.json、propose_three.py、next-three-proposals.json、joint-l3-planner-proof.json、summary.json、remaining-review-43.ipynb、reviewed-sources.json。Notebook三段结果核对已执行；原四项预演拒绝及后续三项通过分别保存。

## 第六批3项正式本地应用与验收

最后核验：2026-10-22。用户明确确认本批3个主发行来源及2项日期调整，并要求原始记录、项目成员、歌曲归属不变，Title继续暂缓。本批已按具体版本完成本地应用和正式验收；上一节的43项审核与未应用状态保留为确认前历史。

| 已应用项目 | 主来源版本与Spotify ID | 日期结果 |
| --- | --- | --- |
| Meghan Trainor / Thank You | 2016年15首Deluxe，`5nkgosKhWt1yXRzmjXNV2d` | **2017-05-12 / NULL → 2016-05-13 / day** |
| 汪苏泷 / 慢慢懂 | 12首11-19版，`7yjELdNsfaw0fi5J8ndWkf` | **2010-06-01 / NULL → 2010-11-19 / day** |
| Marvin Gaye / Let’s Get It On | 10首Expanded，`6AmnVWOxXYucWxgidEgwhy` | **保留1973-08-28，NULL → day** |

本批复用上一节已核实的具体发行证据，没有联网替换已批准的版本或重新解释其他来源。Thank You的2016-05-13为所选Spotify版及索尼公告正式发行日，Apple05-06提前独家串流与2017年17首重装版仍分别留证。慢慢懂06-01来源原样保留；没有将新增主来源关系宣称为不同录音/地区完全等价。

先核对三个项目的主专辑、旧日期pair、完整目录、艺人ID、成员和来源所有权，再从当前正式本地库制作fresh SQLite Online Backup及隔离副本。只为批准的Thank You 2016版新增一条完整15首目录，使用正式日期/专辑艺人证据持久化函数追加4条来源证据（日期观测、署名集合、署名行、署名观测事件各一条），未补造艺人ID或安装其他新候选。既有全部Spotify元数据及日期/署名证据逐行保持。

副本安装新增3条primary关系、1个治理运行和4条治理审计：3条set_primary_release_source，另1条correct_legacy_release_anchor记录Thank You跨年锚点纠正。常规同步只更改慢慢懂与Marvin两个项目；Thank You仍保持旧2017/NULL，必须在用户批准下按精确旧pair单独纠正为2016/day，不修改通用同步保护。三个项目日期pair变化，两个日期字符串变化、一个仅精度变化；重复安装新增关系/事件/写入均0。

副本首轮附加审核把新增元数据的艺人兼容显示误按JSON数组比对，被私有审核守卫拒绝，未切换正式库。按正式persist_album_artists的逗号分隔字符串合同修正审核预期后通过，原失败保留为installation-first-audit.json；没有改业务代码、放宽旧数据保全或重写已有来源。

本批L3规划前后目标归属变化0，问题、排除、冲突及未归属集合保持；仅5条规划决定的日期排序证据改变。已发布7,015条归属保留原决定，只维护上游revision与发布摘要，不采用既有Positions等无关规划差异。Title单独核对完整项目行、来源关系、专辑成员和曲目成员保持2025-03-28/NULL；I’ll Be Home的已发布归属逐字段保持（仅允许本批上游revision维护）。Celebration也保持原项目、来源及成员。

副本搜索四变体、八上下文96个Billboard发布项、四套详情、个人排名及默认消费者均准备并验证。正式切换前155张表及schema与fresh源围栏一致；七库quick_check通过，旧库原inode及首页缓存作为恢复点保留。正式路径重新导入/验证周榜、详情、排名及2022–2026年度和首页消费者，随后恢复日常8000/4173服务；此次数据切换先复用已验前端成品，随后按用户界面反馈完成下述文案调整与成品替换。

隔离及正式各59个HTTP请求通过。本批三个项目在八配置下24次实际选择器比较均采用批准的来源ID和日期；独立从逻辑播放、艺人/大盘逐日次数及已发布周榜名次复算144个指标，与两端真实响应一致，未调用compute_release_metrics。TTPD/Showgirl八配置原六指标、前41项已确认来源、Positions两独立发行和重排、两版Lion King、错误ID/艺人和旧名称歧义保护均通过；全部实际选择器的既有ready无日期/来源退化。本批恢复3项，当前剩余**40项：粗日期21、来源未确认14、艺人署名5**；累计确认44项主来源，原98项恢复58个条目。缺历史发行周播放或周榜可产生0/暂无指标，不能把这种正确结果当作来源不可计算。

真实页面通过Playwright在桌面1440×1000和手机390×844分别搜索选择三项，对应日期和半数播放距与真实接口一致；四类请求都携带正确项目ID并返回200。手机横向滚动及队列重排后日期仍正确对应，单一周期表、页面无横向溢出。初版界面查看4张截图，其中重排绘制过渡图单独保留，3张稳定图通过；按用户反馈移除排障文字后，又查看最终3张稳定截图，均通过。截图位于output/playwright/release-sixth3-20261022/。验收浏览器会话及隔离18813已关闭，日常服务保留。

用户指出“可计算”“窗口内未上榜”“窗口内无播放”等文字不适合作为对外表格内容后，仅修改VersusReleaseCycleSection及现有对应前端测试：首行改为“发行日期”，只显示日期；缺失/不可用指标统一“—”，真实零值保留0；移除表尾排障说明。内部reason仍由接口保留，真实请求失败的重试与加载反馈继续可用，统计、来源与归属计算未改。13项定向前端回归通过，TypeScript/Vite正式构建通过；新成品已应用4173，旧成品及旧资产URL保留，构建输入清单同步。最终桌面/手机实际选择三项，日期/数值、空值/零值、横滚与重排均正确；表格已无上述排障文案。此次纯界面调整复用已完成的数据/API/144指标证据，没有重复后端全量验证。

正式原始播放96,881、歌曲10,480、署名10,964、专辑成员3,328、曲目成员8,383、已发布歌曲归属7,015均逐行/语义保全，人工覆盖保持；原始Spotify来源没有改期。107项其他保护投影在准备期精确相等；启动后仅另追加1条已完成startup_cache_warmup账目、旧任务逐行保持，故106项其余投影仍精确相等，运行账目单独证明。正式全库外键异常0。

证据位于output/versus-release-cycle-20261021/confirmed-sixth-three-apply/：user-confirmation.json、approved-three-sources.json、live-catalogs.json、external-evidence.json、snapshot-proof.json、installation-proof.json、installation-first-audit.json、installed-protection.json、idempotence.json、search-preparation.json、preparation-receipts.json、candidate-api.json、formal-api.json、formal-coverage.json、six-metric-reconciliation.json、metrics-verification.json、formal-data-proof.json、formal-protection-runtime.json、formal-held-projects-proof.json、browser-proof.json（文案调整前）、browser-clean-proof.json（最终）、ui-copy-change.json、acceptance-summary.json及local-activation/。仅本地应用，未提交、推送或生产部署；数据切换阶段业务补丁摘要保持19c1a80d59779541796818998d3155490554b1e49e359f080f6e6b351cb54270，界面文案补修后为8f0fe52f96da786a2bc28397c6da2eba901308591b74aaea1ca274451a7ac261；完成13项定向前端回归、正式构建和双视口复验，没有重复全量后端/全栈或资源实验。

## 第七批40项复核与一项待确认来源

最后核验：2026-10-22。本轮继续只读审核剩余40项，没有安装新来源、纠正日期或更改程序。正式仍为40项：日期仅到年21、来源未确认14、艺人身份待核实5。第六批3项应用和表格文案简化结论保持。

### 可供确认的一个具体选择

建议将Madonna / Celebration（RC-095，项目44911）的主发行来源明确为现有 **Celebration (double disc version)，37首，Spotify `43lok9zd7BW5CoYkXZs7S0`**。项目日期**保留2009-09-18，仅NULL精度确认到day**，无需日期文字调整。所选来源本轮API复取与现缓存的完整37首目录、艺人ID和日期pair一致，无已有其他项目所有权。

[Spotify同版曲目页](https://open.spotify.com/track/3DlRZM6zKSlAZigHbJQ3cp)列出double disc版及09-18。德国[2009年同期报道](https://www.aviva-berlin.de/aviva/content_Kunst%20%2B%20Kultur.php?id=1425477)与[36首双CD商品资料](https://www.jpc.de/jpcng/poprock/detail/-/art/Madonna-Celebration-Inkl-2-New-Tracks/hnum/1065863)支持该地区09-18已发行；这是地区/格式背景，CD商品EAN0093624972969与数字来源UPC093624972945不同，不能据此宣称37首数字商品与36首CD完全等价或同日全球最早可听。拟采用的是明确Spotify版本及项目日期，而非将任意地区日期强行认定为统一标准。

本轮复取的三个完整目录进一步明确了选择边界：

| 来源 | 日期声明 | 完整目录差异 | 本批动作 |
| --- | --- | --- | --- |
| `43lok9zd7BW5CoYkXZs7S0` double disc | 2009-09-18/day | 37首，末曲Celebration - Benny Benassi Remix Edit | 建议明确为主来源，尚未应用 |
| `28Ts8e6rqdmSPH6itDV4KP` Deluxe | 2009-09-29/day | 37首，末曲It’s So Cool | 保留原来源，不改期、不认定目录等价 |
| `4GU7z3q6fg90MWrkTacYYG` Bonus Track | 2009-09-18/day | 38首，另有Felguk Love Remix | 仅私有暂存，不安装、不称38=37 |

[Madonna官网2009年公告](https://www.madonna.com/blogs/news/celebration-in-stores-now)也分别说明18首CD、36首双CD和含独家附加曲的iTunes版，但它是美国发行公告，不是德国发行日证明。

原20条项目成员中，所选来源直接Spotify曲目ID命中2条，已有缓存ISRC命中4条（该37首目录仅15首已有ISRC缓存）。因此这些只作部分录音支持，不声称20条成员均与所选版逐首等价，也不删除未命中成员。额外fresh ISRC复核受TLS中断影响未完成，不计为通过。该建议是用户可确认的项目主来源选择，不是新的目录全等关系或成员归并批准。

只读主库加TEMP影子表预演显示：只新增该来源主关系并常规同步，唯一项目变化是44911的精度NULL→day；四个含精选适用配置均使用指定ID/09-18，全部原ready的来源、日期及原因无退化。L3规划前后目标归属差异0、决定差异0，问题/排除/冲突等集合均相等。Title完整项目和关系保持，I’ll Be Home仍归41603。**正式仍40项；只有明确确认并受控应用验收后才预计降为39项。**

### 全部40项与新版本检索

本轮重新解析40标签/296次出现，48个候选行对应47个既有来源；15次现有单候选TEMP预演，均不写正式库。对21个year条目及7个日期/版本待审条目执行28次Provider检索，共74条命中；其中49个ID此前不在候选清单。49个新命中中只有28个艺人ID匹配，21个不符，因此不能把检索命中数当成合格候选数。艺人匹配也不证明版本或录音等价。

- Spirit新增13首2008-01-28/02-06地区版，与当前17首2007年项目不同；風箏2016重制版、Tapestry 2017现场版不能取代原专辑日期。
- Nevermind新增13/40/70首版仍给09-26，75首30周年版给2021-11-12。[艺人时间线](https://www.nirvana.com/timelines/)明确原版1991-09-24，[官方75首数字商品](https://shop.nirvana.com/products/nevermind-super-deluxe-digital-download)明确2021-11-12；不会为获得day而改用周年日。搜索索引中另一个75首ID显示1991日，但本轮该ID的API复取失败，没有据此形成来源建议。
- Who You Are新增16/19首版仍01-01；Aquarium新11首版仍01-01；Ultraviolence新11首版仍01-01，没有消除原日期疑问。Hands All Over新增亚洲13/14/22首版本，日期与目录/地区尚未闭合。Indigo Girls新12首同名版声明1989-05-17，与此前Apple03-01不同，缺少对应版本的独立证据，不采用。
- 我要的幸福新查到具体销售商品页2000-12-01，但其他资料有12-07/12-09；新增冲突保留，未投票取一个日期。
- 本轮重读[Carole King 2026周年公告](https://www.caroleking.com/news/carole-kings-landmark-album-tapestry-celebrates-its-55th-anniversary)再次确认Tapestry原始1971-02-10；[Don McLean官网](https://donmclean.com/don-mcleans-classic-american-pie-album-celebrates-50th-anniversary/)确认American Pie原专辑1971-10-24；[环球日本商品页](https://www.universal-music.co.jp/teresa-teng/products/upcy-9473/)明确東京夜景原始1978-06-21与2016-05-04复刻日分列。三者都是独立日期证据，不改写现有Spotify year声明。Leona本轮仅取到音乐页壳，Goo Goo Dolls官网本轮403；两者此前日级材料按上一轮证据保留，不声称本轮重新读到正文。

按实际后续动作分为：21项等待独立日级证据治理、11项艺人范围或已有来源所有权、6项日期/版别未闭合、Title一项归属影响暂缓、Celebration一项具体主来源待确认。完整40项清单及每项动作见私有checklist.md。

### 剩余粗日期的修复方向

代码读取确认：当前resolve_release_targets从release_anchor_sources取spotify_album_meta的日期/精度；即使项目手工填了官网已证实的日，只要来源仍year，解析仍返回release_date_coarse。因此剩余21项不能继续靠绑定同一来源或换成年份更晚的重制版解决。这个限制不是缺少再抓一次Spotify，而是尚无独立发行日证据的正式消费合同。

下一步应补充有审核状态的独立发行日期覆盖层，保留Spotify原始pair，逐条记录项目/具体版本、原专辑日或再版日、地区/格式、来源URL、抓取日期、精度、批准人和旧值守卫。统一解析已批准的适用证据；两个明确day冲突仍拒绝自动选择。不能只给对决加一个旁路日期，项目同步、相关榜单cutoff及派生revision必须使用一致事实，避免各页面日期相互矛盾。

实施先以Tapestry、American Pie、東京夜景三项已重读官方日级证据做候选，核对目录/地区适用范围，再扩展其他粗日期。日期变化必须先做L3规划及保护预演；任何会改变歌曲归属的候选继续拦截，Title维持暂缓。每批仅在具体证据和影响可审查后确认数据，随后受控安装并验证；本轮尚未新增表、实现覆盖层或应用这些日期。

### 只读边界与证据

正式数据库全程URI mode=ro，authorizer拒绝main写入，所有试验仅TEMP并回滚；写入尝试0。原始播放96,881、歌曲10,480、署名10,964、专辑成员3,328、曲目成员8,383、已发布归属7,015与第六批一致；这里的保全依据只读连接和写入拒绝，不用计数一致替代应用前后的逐行证明。业务补丁与第六批界面简化后的版本保持，没有构建、重启、提交、推送或部署，也未扩大后端/全栈/浏览器验证。

Spotify复取曾出现TLS EOF；按network-proxy-retry技能与项目六代理变量重试后取得上述三份Celebration完整目录。额外Nirvana ID与fresh ISRC复取仍失败，保留访问限制，停止继续重试；没有由此判定项目程序故障或更改网络配置。

私有证据：output/versus-release-cycle-20261021/remaining-review-40/ 下的review.py、review.json、review-with-actions.json、discover_sources.py、discovered-sources.json、selected-live-catalogs.json、external-evidence.json、network-attempts.json、propose_one.py、next-one-proposal.json、summary.json、checklist.md、remaining-review-40.ipynb及reviewed-sources.json。Notebook结果复核已执行；数据应用与后续独立日期治理均尚未进行。

## 第七批Celebration正式本地应用与验收

最后核验：2026-10-22。用户对上一节唯一具体版本建议回复“确认”，已受控应用Madonna / Celebration（项目44911）的37首double disc主来源 `43lok9zd7BW5CoYkXZs7S0`。**日期保留2009-09-18，精度由NULL确认为day**。这是项目主发行来源选择，不是不同目录全等或新成员归并批准；另37首Deluxe和38首Bonus保持原状，Spotify原始日期、完整缓存及来源证据均未改写。本轮没有重试或补称上一节未完成的fresh ISRC为通过。

从当前日常库fresh Online Backup及只读全表围栏开始，在副本精确核对主专辑578、旧日期pair、完整37首目录、Madonna稳定ID、20条既有成员范围及无其他来源所有权。副本新增1条primary绑定、1个治理运行和1条set_primary_release_source审计；常规同步仅将44911的精度NULL→day，没有日期字符串或其他项目变化。重复安装新增事件、来源写入均0。L3规划目标差异0、决定差异0、问题/排除/冲突集合保持；已发布归属原决定保留，只维护上游revision及摘要，未采用既有无关规划差异。

副本搜索四变体、96个Billboard发布项、四套详情、默认个人排名及年度/首页消费者准备通过。首次实际API验收在含精选配置下，发行周期、普通榜单与个人统计均200，但个人排名503；原失败保留candidate-first-failure.json。代码检查确认已有准备CLI默认只构建当前四个默认个人排名配置（本地设置不含精选），因此显式含精选参数对应的四个custom快照未准备。使用现有CLI的filters-json在隔离副本补建四个有界custom快照，分别保存并合成独立四项manifest；继续保留默认四项，不放宽单manifest四项限制、不在读取时冷建，也不改用户设置或业务代码。此次准备/切换脚本已增加含精选构建及路径重绑定安装，正式切换时默认和含精选两组分别校验导入。

隔离及正式各**27个真实HTTP请求通过**：八配置实际选择器与TTPD/Showgirl的全部原指标、日期、来源保持；Celebration只在含精选的四配置可选，发行周期均使用指定主来源/09-18，个人排名四配置均200，另核对普通榜单、个人统计和重排对应。全选择器逐项核对原ready无退化，包括此前44项确认来源；本批恢复1标签，正式待审**40→39：粗日期21、来源未确认13、艺人身份5**。累计确认45项主来源、原98项恢复59条目。

独立从逻辑播放、艺人/大盘逐日计次及已发布周榜原语复算四组对比共48个指标（Celebration24、对照TTPD24），与隔离及正式HTTP响应逐项一致，没有调用compute_release_metrics；这不是要求历史发行窗口必须存在播放或上榜记录。缺失指标保持空值、真实零值保持0，前端沿用上一轮已应用的日期/数值/—简洁展示。

切换前155张表和schema与fresh源围栏一致，七库quick_check通过；停止已核对身份的日常服务后，保留旧七库原inode及首页缓存，再切换受验副本、重绑定周榜/详情/默认与含精选排名并准备正式年度/首页消费者，随后恢复8000/4173日常服务。隔离18813已优雅关闭。旧库和首页恢复点位于本批local-activation/，没有覆盖或删除前几批恢复材料。前端源与成品均复用，没有新增浏览器回放；本轮不声称在默认不含精选页面实际选择了Celebration，接口对四个含精选配置的验收与上一轮界面证据分别报告。

原始播放96,881、歌曲10,480、署名10,964、专辑成员3,328、曲目成员8,383及7,015条已发布归属逐行/语义保持，全部Spotify元数据与日期/专辑署名证据全字段保持；保全不只比较计数。Title完整项目、来源、专辑/曲目成员仍保持2025-03-28/NULL，I’ll Be Home已发布归属仍为41603。108项其他保护投影在准备期精确相等；正式启动新增的startup_cache_warmup账目另按追加审查，旧任务逐行保持，其余107项精确相等。正式外键异常0。

证据位于output/versus-release-cycle-20261021/confirmed-seventh-one-apply/：user-confirmation.json、approved-one-source.json、snapshot-proof.json、installation-proof.json、idempotence.json、installed-protection.json、preparation-receipts.json、compilation-rank-preparation.json、versus-compilation-ranks.json、candidate-first-failure.json、candidate-api.json、formal-api.json、formal-coverage.json、six-metric-reconciliation.json、metrics-verification.json、formal-data-proof.json、formal-held-projects-proof.json、acceptance-summary.json及local-activation/。业务补丁保持8f0fe52f96da786a2bc28397c6da2eba901308591b74aaea1ca274451a7ac261，未新增业务代码、提交、推送或生产部署；没有重复全量测试、全栈或资源实验。

剩余21项的独立发行日期覆盖层仍为上一节建议，尚未实现或应用其他日期；6项其他日期/版本疑问、11项艺人范围/来源所有权及Title归属影响继续保留。本批应用不能描述为全部来源治理已完成。

## 第八批独立发行日期入口与21项粗日期审核

最后核验：2026-10-22。独立日期入口、隔离副本及正式本地应用均已通过验收；全部待审39→29（粗日期11、来源13、身份5），累计45项已确认主来源不变，原98项恢复69条目。本批10项有适用的同年日级证据，另11项保留待审。Spotify原始声明、项目成员、歌曲归属及Title保持；没有新增主来源绑定，未提交、推送或生产发布。

### 独立日期治理

schema94新增独立日期断言、审核事件和revision三表。`scripts/govern_album_release_dates.py`支持list、stage、approve、reject、revoke；缺省在临时磁盘Online Backup副本演练，apply拒绝配置中的正式库及同inode。登记不生效；批准时核对具体项目、既有来源、完整有序目录、稳定艺人ID、原始pair及旧项目日期，并保存原专辑/版本日、地区、介质、来源URL、核验时间、审核人与理由。

统一日期解析、项目同步和重建消费已批准且守卫匹配的事实，其他项目和明确成员版本不借日期；来源漂移停用，明确日期范围冲突拒绝普通精度批准。Spotify的year声明及原观测不改成独立day。派生项目与上游revision同事务维护，日期规则升级v3，搜索、榜单cutoff、详情、个人排名、年度等准备新成品，GET不联网、建表、审批、冷建或排队。完整规则见[独立日期合同](../reference/release-date-precision.md#独立发行日期登记与审核)。

160项受影响定向回归通过，覆盖待审不生效、幂等、目录/日期/艺人/主专辑漂移、跨年及多来源day冲突拒绝、撤销、只读不建表、迁移及歌曲归属变化整批回滚。迁移测试发现受控seed仍在schema90，按既有构建器更新至94后通过；没有修改用户库以满足测试。Ruff和差异检查通过，未扩大到全量后端、全栈或资源实验。

### 10项独立发行日

原Spotify pair均保留YYYY/year；下列day用于对应派生项目的原专辑锚点，不宣称所有地区、后续附加曲和再版均于同日首次发行。

| 编号 | 项目 | 独立发行日 | 地区及证据 |
| --- | --- | --- | --- |
| RC-020 | Stefanie Sun / 逆光 | 2007-03-22 | TW；[大众娱乐在线当日报道](https://ent.sina.com.cn/v/m/2007-03-22/16371489360.html)、[京华时报庆功会报道](https://ent.sina.com.cn/y/2007-04-03/02431502711.html) |
| RC-023 | Xu Wei / 时光, 漫步 | 2002-12-18 | CN；[许巍时光漫步同期上市报道](https://ent.sina.com.cn/p/i/2002-12-20/1418120887.html) |
| RC-026 | Stefanie Sun / 風箏 | 2001-07-12 | TW；[南方都市报同期专辑回顾](https://ent.sina.com.cn/p/i/2001-09-13/57128.html)、[YesAsia台湾10首风筝商品目录](https://www.yesasia.com/us/風箏/1001812328-0-0-0-zh_TW/info.html) |
| RC-040 | Stefanie Sun / 未完成 | 2003-01-10 | TW；[南方都市报未完成预购公告](https://ent.sina.com.cn/m/2003-01-01/1203123160.html)、[美卡音像发行方同期采访](https://ent.sina.com.cn/p/i/2003-01-06/1555123976.html)、[KISS Radio华纳专辑资料](https://www.kiss.com.tw/music/album.php?id=1871) |
| RC-042 | Stefanie Sun / 是时候 | 2011-03-08 | TW；[新浪当日是时候开卖报道](https://ent.sina.com.cn/y/2011-03-08/10143248256.shtml)、[孙燕姿本人访谈实录](https://ent.sina.com.cn/y/2011-03-04/15213245959.shtml?from=wap) |
| RC-051 | Carole King / Tapestry | 1971-02-10 | US；[Carole King官方55周年公告](https://www.caroleking.com/news/carole-kings-landmark-album-tapestry-celebrates-its-55th-anniversary) |
| RC-068 | The Goo Goo Dolls / Dizzy up the Girl | 1998-09-22 | US；[Rhino专辑纪念页](https://www.rhino.com/aod/dizzy-up-the-girl-goo-goo-dolls-0) |
| RC-071 | Don McLean / American Pie | 1971-10-24 | US；[Don McLean官方50周年公告](https://donmclean.com/don-mcleans-classic-american-pie-album-celebrates-50th-anniversary/) |
| RC-089 | Dolly Parton / 9 To 5 And Odd Jobs | 1980-11-17 | US；[Dolly Parton官方1980年代时间线](https://www.dollyparton.com/decades/1980s) |
| RC-094 | Teresa Teng / 熱唱！テレサ・テン『東京夜景』 | 1978-06-21 | JP；[环球日本東京夜景商品档案](https://www.universal-music.co.jp/teresa-teng/products/upcy-9473/) |

風箏采用同期原稿、台湾具体商品及广播资料的07-12，保留旧论坛07-09冲突核查记录；是时候区分03-01延期计划、03-08实际开售及数字10首/实体隐藏轨。未完成使用同期预告、发行方采访及注明华纳资料的广播专辑卡，11首含My Story Your Song的目录保持。Tapestry、American Pie、Dolly及東京夜景采用艺人/厂牌明确原始日，单曲、纪念及复刻日分列；東京夜景12首顺序与环球商品档案对应。

### 其余11项的具体边界

复用前轮对应目录和已留证来源，并联网补查日期冲突；不以同名、搜索命中数量或多数票代替具体版本适用性。

| 编号 | 项目 | 核实结果与仍需解决的范围 |
| --- | --- | --- |
| RC-007 | 我要的幸福 | 同期南方都市报和注明华纳资料的广播目录支持12-09；Rockmall商品12-01及旧官网转录12-07保持冲突。当前12首/商品与原版关系仍待闭合，不以多数票或仅标题认定。 [来源1](https://shop.rockmall.com.tw/product_view.php?id=79176)、[来源2](https://www.ptt.cc/bbs/Yanzi/M.1146124984.A.156.html)、[来源3](https://ent.sina.com.cn/p/i/2001-09-13/57128.html)、[来源4](https://www.kiss.com.tw/music/album.php?id=1869) |
| RC-021 | The Moment | Apple为19首08-19；同期华纳预告08-22且新加坡20首有国庆曲，未闭合此19首具体版本地区。 [来源1](https://music.apple.com/us/album/the-moment/541856819)、[来源2](https://ent.sina.com.cn/p/i/2003-09-27/1821207682.html) |
| RC-024 | Spirit | 官网/欧区目录11-09，英区11-12；现17首含后续附加曲，不能用13首2008地区版或原版日替代整个17首版。 [来源1](https://www.leonalewismusic.com/music/)、[来源2](https://music.apple.com/hu/album/spirit/500408587) |
| RC-038 | Under My Skin | 艺人目录05-25，艺人/索尼黑胶说明05-19，地区及现13首的适用关系仍未闭合。 [来源1](https://store.avrillavigne.com/pages/catalog-2024)、[来源2](https://shop.sonymusic.ca/products/avril-lavigne-under-my-skin-silver-grey-black-marble-vinyl) |
| RC-041 | 孫燕姿2000台北萬人演唱會 | 可区分04-10 VCD与06-07含两首录音室歌的12首CD；尚未直接重读可识别原CD的发行方日期页，不仅凭2006论坛转录批准。 [来源1](https://www.ptt.cc/bbs/Yanzi/M.1146124984.A.156.html)、[来源2](https://zh.wikipedia.org/wiki/2000台北萬人演唱會) |
| RC-043 | 執迷不悔 | Apple原版/2019 remaster与Spotify remaster的day不一致；当前原版year保留。环球日本商品只证明1993年2月和2024再版日，待原版日级直接证据。 [来源1](https://music.apple.com/us/album/執迷不悔-remastered-2019/1488204120)、[来源2](https://www.universal-music.co.jp/faye-wong/products/uijy-75257/) |
| RC-058 | 自選集 | 旧华纳转录02-01，其他目录/PDF01-05；PDF的官方发布归属未证实，台湾音乐资料库仅2002-01，不把月份扩为某天。 本轮发现KISS标题自選輯的条目实际是2000年同名专辑目录，已排除，不能只按标题当2002自选集证据。 [来源1](https://www.ptt.cc/bbs/Yanzi/M.1146124984.A.156.html)、[来源2](https://pmdb.taipei/database/album/0p126666653826784219) |
| RC-060 | Global Warming: Meltdown (Deluxe Version) | 索尼2014官方公告明确Meltdown版2013-11-25，新增Timber及4首合作曲与本地17首后5首对应。Spotify仍2012/year；跨年冲突不按同年精度补齐安装，登记为pending待专项纠正。 [来源1](https://www.sonymusic.com/sonymusic/fifa-and-sony-music-entertainment-select-we-are-one-ole-ola-by-global-music-sensation-pitbull-featuring-international-superstar-jennifer-lopez-and-brazils-own-claudia-lei/) |
| RC-069 | Christina Aguilera (Expanded Edition) | 索尼明确原版1999-08-24与2019-08-23含rarities/remix的数字Deluxe分列；早期双碟再版另有2000年线索。本地18首Expanded的版本日期未闭合，不把原12首日直接给附加版。 [来源1](https://www.sonymusic.ca/press_release/legacy-recordings-celebrates-the-20th-anniversary-of-christina-aguilera-the-artists-self-titled-debut-album-with-special-releases-coming-friday-august-23rd)、[来源2](https://music.apple.com/us/album/christina-aguilera-expanded-edition/1308542675) |
| RC-081 | Hands All Over | 各地区原版日期不同；当前13首来源目录与历史成员已有ID漂移，不能用新22首亚洲tour版替代，也不动成员。 [来源1](https://www.universal-music.de/maroon-5/musik/hands-all-over-164592)、[来源2](https://en.wikipedia.org/wiki/Hands_All_Over_(album)) |
| RC-084 | Indigo Girls (Expanded Edition) | 原版10首02-28、Apple Expanded12首03-01与另Spotify12首05-17；具体Expanded版本仍无独立日级闭合。 [来源1](https://stereogum.com/2033408/closer-to-fine-at-30-the-legacy-of-indigo-girls-spellbinding-singalong/columns/sounding-board)、[来源2](https://music.apple.com/us/album/indigo-girls-expanded-edition/201265795) |

Global Warming: Meltdown的2013-11-25已由索尼原始公告核实，新增Timber及四首合作曲对应当前17首的后五首。这是明确的版本/年份冲突，已独立登记pending；Spotify2012/year和项目日期保持。普通同年精度批准会拒绝跨年覆盖，后续须单列项目年份纠正及L3影响审阅。不能将它混入本批同年补证。

自選集命中的KISS「自選輯」页实际给2000年，曲目属于首专，已排除，不能按标题当作2002年的自选集证据。Title不在本21项内，继续保持2025-03-28/NULL；I’ll Be Home仍归41603。其余13项主来源和5项身份问题没有扩展处理。

### 应用与验收

从fresh Online Backup及155张旧表/schema围栏开始。10项分别及合批L3规划目标变化0、决定语义及问题/排除集合保持，只有57条日期排序证据变化；保留7015条已发布归属决定，仅维护上游revision与摘要，不采用无关的既有规划漂移。副本追加12条日期断言：10approved、1被补充广播证据取代后rejected、1跨年pending；23条事件、date revision10。旧登记不覆盖，重复批准无新增事件或revision。

已准备四搜索、96个Billboard发布项、四详情、默认四排名及四个含精选custom排名，以及年度/首页消费者，用户设置和单manifest四项限制保持。隔离67个真实HTTP请求通过；八配置中78次适用比较、468项指标与逻辑播放/逐日计数/周榜原语的独立计算一致，未调用compute_release_metrics。全部原ready和TTPD/Showgirl原指标、日期、来源无退化。東京夜景在既有L2含精选选择器中不出现，按真实适用范围计78次，没有伪造80次。

首轮验收脚本误把personal-ranks的实体键当作project_id字段，并假定每项目八配置都可选；现按实际响应合同及既有选择器范围核对，保留脚本失败记录。没有因此修改业务，也不把脚本错误称为应用接口失败。

正式同样67个HTTP请求、468指标和全选择器核对通过，外键异常0。切换前全源围栏一致、七库quick_check通过；旧七库原inode与首页恢复点保留，周榜、详情及两组排名完成路径重绑定并准备正式消费者，8000/4173已恢复，隔离18813已关闭。新增未跟踪源码及受控seed另有文件SHA守卫与私有源码/补丁留存。

原始播放96881、歌曲10480、署名10964、专辑成员3328、曲目成员8383及7015条归属逐行/语义保持；全部Spotify元数据与日期/署名证据全字段保持。副本110项其他保护投影相等；正式仅追加一条已完成startup_cache_warmup账目，旧行及其余109项保持。Title完整项目/来源/成员与I’ll Be Home归属保持。

前端源码及正式成品复用。本轮1280×720真实浏览器选择逆光、Tapestry、東京夜景，页面分别显示2007-03-22、1971-02-10、1978-06-21，发行周播放0及半数播放距944/2713/2459与已验事实相同；没有内部诊断文案。截图formal-browser-period.png，未宣称重新执行全部项目桌面/手机矩阵。

正式只读list返回的12条登记与副本预期逐字段相等；维护CLI对正式库的显式apply实际返回2并在连接前拒绝，没有写入。

私有证据：`output/versus-release-cycle-20261021/independent-date-evidence-20261022/`，含current-21、audit-21、accepted-dates、per-item-l3-preview、expected-date-registry、installation-proof、preparation-receipts、candidate/formal-api、candidate/formal-coverage、six-metric-reconciliation、metrics-verification、formal-data-proof、formal-held-projects-proof、browser-acceptance、acceptance-summary及local-activation恢复材料。旧恢复点保留，独立OOM观察不变。


## 按原始界面回退发行周期表格UI

最后核验：2026-10-22。用户明确要求只修计算和正常显示，撤回本问题链额外加入的UI。以首次修复提交25700cb3的父版本4e70af2d为界面基线，而不是仅回退最后一轮日期补证。**已恢复原来的六项指标和原有表格样式，没有发行日期或计算状态行；计算、数据治理与稳定项目身份修复保留。**

| 本问题链曾修改的展示 | 本次处理 |
| --- | --- |
| 新增计算状态行，后改为发行日期行，曾显示可计算及发行日 | 两种额外行全部移除，恢复仅六项指标 |
| 缺证、窗口未上榜/无播放等诊断文字，以及表下对齐/零值说明 | 保持原版数值/—表达，无额外诊断说明，真实0继续显示 |
| 新增错误提示面板和重新加载按钮、等待/加载文案 | 移除新增控件和状态文案，恢复原版加载中... |
| 表格按136px指标列及每专辑180px计算最小宽度，新增横滚焦点容器，调整内边距、行头语义/字体及固定列背景/层级 | 恢复原GlassCard横滚、300px表格最小宽度、列/行样式、留白和bg-card固定列；保留无视觉变化的表格可访问名称及busy属性 |
| 将周期区从图表容器拆出，额外手机底部留白及队列按钮44px尺寸 | 恢复原正常结果容器与间距、手机留白和队列按钮尺寸；普通榜单失败仍可消费周期事实的逻辑保留 |

六项原指标仍为首发排名、最高排名、发行周播放、艺人影响力、大盘影响力、半数播放距。没有修改指标公式、原始记录、独立日期证据、主来源、项目成员或歌曲归属，也没有回退同名项目的稳定ID、请求/缓存身份、结果列对齐或真实零处理。移动端排名趋势孤立点修复是另一问题，未撤回。

三个展示组件的全部静态className与4e70af2d逐项相等，剩余差异为身份、数据对齐及独立读取的必要逻辑。21项定向前端回归和正式构建通过；更新成品manifest后，4173直接提供新构建，无需重启后端或重建数据。TTPD/Showgirl实际周期接口的全部指标、日期和来源与本轮回退前基线相等；后端补丁逐字节保持。

真实浏览器1280×720及390×844已验收：均只有六指标行，没有日期、状态或诊断；TTPD/Showgirl发行周播放276/297、影响力1.4x/1.9x、大盘1.6x/1.6x、半数播放距20/7均正常显示，两项排名均#1。手机末行可见。临时视口已恢复，原网页状态未替换。证据位于output/versus-release-cycle-20261022-ui-rollback/，包括原版组件、修改前文件与补丁、frontend-tests.log、frontend-build.log、desktop.png、phone.png、browser-acceptance.json和acceptance.json。未提交、推送或生产部署。


## 本地研发收口与交付检查点

2026-10-22按用户要求执行收尾。本次本地研发与验收结束，代码、回归和规则文档统一保存为一个提交；源基线为9e9fb63bc02be50b1d38314d64d72fc58a3339bb，提交仅包含本问题链的明确文件。历史各批“未提交”保持当时语境，以本节为当前交付状态。生产仍为004既有发布版本，本次没有推送、触发CI或生产部署。

最终成品保留原来的六指标UI；计算统一使用正确项目成员、稳定项目ID、已确认发行来源与独立日级证据，真实0正常显示。TTPD/Showgirl原故障已解决，通用来源类型、身份传递、详情快照淘汰及独立日期治理缺口一并修复。累计45项主来源、10项独立发行日已本地应用，原98个待审条目恢复69个；原始Spotify声明、播放记录、项目成员和歌曲归属保持。

剩余29项（粗日期11、来源13、艺人身份5）转为独立元数据治理待办，当前没有继续开发或批量应用计划；仅在取得具体版本证据或人工决定后逐项恢复。Title继续暂缓，Meltdown跨年事实只登记pending，不能自动批准。此边界不阻塞已验收的计算修复收口。

复用第八批160项回归、隔离/正式各67HTTP、468独立指标、全既有ready无退化及数据保护证据；最终UI复用21项前端回归、正式构建和1280×720/390×844真实页面验收。提交前受影响四个后端测试文件129项、三个前端测试文件21项全部通过；217份文档审计、git diff --check及项目提交hooks（ruff、ruff format、mypy、Detect secrets）全部通过。最终结果及提交SHA保存在私有目录output/versus-release-cycle-20261022-closeout/。README的产品边界未变，AGENTS/CLAUDE已检查且一致，无需修改；文档地图、变更日志和状态入口同步收口。

源码处置：仅有当前主工作目录，无临时研发工作树需要清理；保留codex/versus-release-cycle-repair-20261021作为固定READY本地交付检查点，日常8000/4173仍使用此目录，待授权整合/发布后再处理分支。没有合入main，因此不存在本轮源SHA到main SHA映射。七库、首页恢复点及各批私有证据保持原位，数据库、播放数据、截图和output均不加入提交。
