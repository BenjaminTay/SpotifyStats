# 合作曲排行实施与验收

日期：2026-10-02。旧代码基线：`194fd1138da4bacfea45b9578923d9f4c301fb6f`。实施提交：`fa683d972d052d6e24d7a882648e99725334a05e`，已推送并发布。当前状态：S1–S6 全部完成并验收。

## 交付范围

三个合作榜共用有效署名、canonical 艺人去重后的合作逻辑事件。歌曲与占比每个事件一次，专辑沿用项目归属，艺人统计全部参与者；不是只统计 featured。L3 先识别实际合作版本，再汇总歌曲，独唱播放不会获得合作 credit。

保留原始数据、导入标题兜底和人工署名优先级，不新增审核工作台或逐条核对任务。列表输出稳定曲目身份、完整署名；已知曲目无封面时不借用同名歌曲封面。

Records 合同升级为 `2026-10-02-effective-collaboration-v4`，年度内容版本升级为 `yearly_review_v2_17`。migration 85 补齐自动署名的分析修订触发器；GET 继续只读持久结果，显式维护负责构建。

验收发现并修复 L2/L3 合并时 `representative_track_id` 变成 `_x/_y` 的问题。保留实际播放版本的代表键，歌曲和时长 frame 同步修复；年度范围裁剪前建立完整历史逻辑事件键，避免跨年重复源 ID 错配。

## 服务器副本前后对比

使用服务器 2026-10-02T14:57:55Z SQLite Online Backup；副本完整性 `ok`，原始播放 94,760 条。固定动态门槛、30 秒基础门槛、连续播放合并及 5 分钟间隔、lifetime、不含精选集。全部有效逻辑播放为 67,881 次，两次计算均未改写数据库。

| 对比 | 旧标题识别 | 新有效署名识别 |
| --- | --- | --- |
| 合作逻辑播放 | 3,236 | 6,518 |
| 占全部有效播放 | 4.8% | 9.6% |
| We Found Love | 未纳入 | 7 次；Rihanna、Calvin Harris |
| Hold Me Closer | 未纳入 | 35 次；Elton John、Britney Spears，均为 primary |
| 无标题标记的榜内示例 | 少年未纳入 | 少年 117 次；Michael Wong、Gary Chaw |

L2、L3 均与独立有效署名筛选得到的 6,518 个事件完全一致。移除合作板块和生成时间后，整个 Records 响应逐字段相同。艺人榜由客串榜变为参与榜，例如 Taylor Swift 1,574 次；艺人次数相加不是歌曲播放分母。

另沿实际年度 orchestrator 的预加载准备方式，对比 2025 年 L3 的 standalone 与年度范围：动态、静态门槛下三个合作榜均逐字段相同；两种配置本轮均为 17,577 次有效播放中的 1,584 次合作播放。

L2 旧/新完整 Records 构建耗时 14.182 / 9.818 秒，L3 为 12.961 / 11.752 秒。仅作该副本本轮观察，不作为稳定性能基准。

可复现工具：`scripts/verify_collaboration_ranking.py --db-copy <明确副本> --baseline-ref 194fd1138da4bacfea45b9578923d9f4c301fb6f --merge-level 2 --json-output <全新本地结果路径>`；L3 同理。完整结果含个人历史，仅保留在本地临时验收目录，不提交。

## 迁移与自动化验证

同一副本启动应用完成 84→85；`plays`、`tracks`、`track_artists`、`spotify_auto_track_credits`、`track_credit_overrides` 的有序行摘要前后一致，行数分别为 94,760 / 10,026 / 10,496 / 8,970 / 34。专项测试另证明搜索来源指纹不变、重复安装幂等。

| 验证 | 结果 |
| --- | --- |
| 完整后端 unit | 2,104 passed |
| 完整后端 contract | 443 passed |
| 完整前端测试 | 690 passed，4 skipped |
| 后端及对比脚本 Ruff | PASS |
| 前端构建 | PASS；保留既有大 chunk 警告 |
| 文档审计（含归档）、CI 检查对齐 | PASS |
| full/showcase/dual 静态部署矩阵 | PASS |

合作专项覆盖共同主唱、三人、别名、人工增删、标题误导、独唱/合作 L3 合并、重复 play_id、相同时间戳、同名曲、专辑 owner 与项目重复归属、精确时长切片、可靠预加载、空数据和缺失身份。快照测试覆盖旧合同不命中、新修订、人工/自动变更和 canonical 合并；年度测试覆盖预加载及跨年事件键。

上述是本地自动化与副本验证，不是默认完整全栈 PASS、真机验收或生产已完成的声明。

## 浏览器与生产

本地真实 Chromium 浏览器在 1280×800、360×800、390×844、430×932、768×1024 验证歌曲/专辑/艺人切换，摘要均为 6,518 / 9.6%，页面横向溢出均为 0。桌面与手机完整榜单均显示《For Good》六位艺人，手机实际点击 `/music/tracks/4453` 进入对应详情并返回播放记录。

1280/390 的零合作 0 次 / 0% 与空榜通过明确标注的浏览器网络 fixture 验证，不代表修改真实数据。封面、长署名、空态和详情截图均完成视觉检查；无 console warning/error，只有开发环境 React DevTools 信息。证据在忽略目录 `output/playwright/collab-local-*.png` 及对应快照，浏览器 session 已关闭。

正式[发布流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/37026172888)全部 success；源码、两套镜像及实际 capabilities 的 release SHA 均为 `fa683d972d052d6e24d7a882648e99725334a05e`。服务器继续保持 dual，三个容器 healthy；`verify.sh` 通过 loopback、运行面与写入边界、SQLite 完整性及四个搜索变体语义检查。未改变外部入口或访问控制。

发布使用既有 Online Backup 与副本预检，保护点为服务器 `backups/spotify-stats-pre-release-fa683d972d05-20261002T154104Z.db`；预检报告 `music-search-preflight-fa683d972d05-20261002T154104Z.json` 确认 migration 85、四个统计 fingerprint 全部精确复用、候选复用、orphan=0、integrity=ok，没有重新冷建全库搜索统计。

服务器实际只读探针再次确认五张来源表的行数和有序摘要与发布前完全一致，Records 合同及年度内容版本为上述新值。线上旧/新完整 Records 响应移除合作板块、生成时间和 snapshot 元信息后逐字段相同。

| 生产快照范围 | 合作播放 | 占比 | 状态 |
| --- | --- | --- | --- |
| lifetime，L2 | 6,518 | 9.6% | ready / current |
| 最近 4 周，L2 | 72 | 9.8% | ready / current |
| 最近 6 个月，L2 | 728 | 8.7% | ready / current |
| lifetime，L3，私有 prepare 受控构建 | 6,518 | 9.6% | ready / current |

上述快照 source/target revision 均为 `b2ea5d704b915f8c0d8adf2fc5d0ef9cbfa9dc8d7f5a25d5ca0b6e14af6d6c57`，不是旧标题结果的 LKG。切换后的短暂 503 准备状态结束后才登记 ready，GET 没有同步构建。

通过仅本机 loopback 的 SSH 隧道，使用内置浏览器验收服务器实际页面：1280×800、390×844 的三视图切换、6,518 / 9.6% 摘要、完整署名、封面和稳定链接正确，横向溢出 0；手机实际进入 `/music/tracks/4453`，详情显示 Taylor Swift / Sabrina Carpenter 并返回记录页。console warning/error 均为 0，生产截图在本次会话留存并已视觉检查。CLI 会话因环境自动关闭而切换验收工具，不影响统计结论。

这是服务器运行面与浏览器视口验收，不是物理手机、外部 HTTPS 或默认完整全栈的验收。临时浏览器、视口覆盖及本地副本服务已关闭，数据库副本与服务器保护点保留。

## 阶段收口

S1 副本基线、S2 共用事实、S3 修订/缓存/年度、S4 页面及规则、S5 自动化/真实数据/浏览器、S6 提交/推送/正式发布/生产快照与页面，全部完成。已完成计划移入 `docs/archive/06-productization-closeout/2026-10-02-collaboration-ranking-plan.md`。共享工作区另一项状态文档的变更未混入业务提交。

## 2026-10-03：署名链接补修

用户反馈合作曲歌曲行的艺人不能点击，且名字使用顿号分隔。原来的完整署名是纯文本；现已在播放记录共用歌曲/专辑单元格复用榜单 `ArtistLinks`，每位艺人独立跳转，并用 ` · ` 分隔，保留完整多艺人换行和单艺人兜底。没有修改统计、快照合同或来源数据。

播放记录专项 25 passed；前端全量 693 passed / 4 skipped；构建、改动文件 ESLint 与 diff 检查通过。使用上轮隔离副本的真实浏览器，在桌面和 390×844 实际点击 Sabrina Carpenter 进入其艺人详情并返回；360/390/430/768/1280 视口横向溢出均为 0，手机嵌套链接 0，console error/warning 0。截图 `output/playwright/collab-artist-links-{desktop,phone}.png` 已视觉检查，浏览器及临时服务已关闭。

用户已授权提交并部署。本地补修验收通过，正式发布及生产交互验证待登记；此前 `fa683d97` 的发布结论不自动代表本次补修已上线。
