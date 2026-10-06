# 曲目署名覆盖与标题解析验收（进行中）

> 问题：SS-2026-10-06-001；最后核验：2026-10-06。
> 当前：S0–S3代码与副本专项已完成；完整全栈、固定提交和生产发布尚未收口。

## 真实副本前后对照

生产发布基线 `daf098ca`，一致 Online Backup 为 `spotify-stats-pre-credit-resolution-20261006T143200Z.db`，integrity_check=ok。本地封存副本只读，另建可写验收副本；未用本地较旧正式库代替生产对照。

基线：10,026曲目、1,907艺人、10,496原始署名、94,760播放记录、8,970自动署名、34条人工覆盖，revision37。比较旧 `75c161d8` 共用 resolver 和本次规则，身份映射与原始内容相同。新规则自动调整14个原始曲目；加上既有覆盖层的 My Heart 曲目级纠正，副本共15个曲目变化，有效署名11,789→11,771。只新增1条 remove，revision37→38；同幂等键重跑不新增事件或revision。

| 真实曲目 | 修改前 | 修改后 |
| --- | --- | --- |
| Safe & Sound | Taylor Swift、整体占位、Joy Williams、John Paul White | Taylor Swift、Joy Williams、John Paul White |
| Holidays | Meghan Trainor、完整乐队、Earth、Wind、Fire | Meghan Trainor、Earth, Wind & Fire |
| Fly To You、Get Lucky 两版 | 独立成员及拼接占位同时存在 | 仅独立结构化成员 |
| Mitchell Ayres / Jeff Goldblum 两首组合 | 完整组合及误拆实体同时存在 | 完整组合各一个，不展开成员 |
| Easy | Kacey Musgraves feat. Mark Ronson 占位与独立成员同时存在 | Troye Sivan、Kacey Musgraves、Mark Ronson |
| The Last Time、Rush、Mother I Sober | 带 of 团体说明的占位 | 独立成员，不添加所属团体 |
| Quit Playing Games (With My Heart) | Backstreet Boys、My Heart | Backstreet Boys；仅副本已纠正，生产尚未执行 |

逐行核对 `plays`、`tracks`、`track_artists`、`artists`、`spotify_auto_track_credits` 完全一致；原有34条人工覆盖逐行一致，完整性检查ok。All Night Parking、Fields.、Machine Gun Kelly / mgk、98° / 98º、魏如萱 / Waa Wei 的有效署名保持；不猜别名，也不以Spotify缺席删除真实补充。

Come Alive 的历史改名、Henri René and / & 名称变体、Super Freaky Girl 含 Maliibu Mitch / Miitch 的完整片段仍无法唯一覆盖，作为例外保留；新导入不再从这些未知字符串创建艺人。不新增全库逐条审核流程。

## 已执行验证

- 解析及实际音频/视频导入、变更集与contract专项133项通过；补成员所属说明后解析/导入/署名组合98项通过。
- 覆盖与人工操作专项18项通过；独立审查定位跨别名撤销时序，修复后两类fixture及79项专项通过。
- 缓存消费者146项、维护/聚合/快照157项、导入变更集25项、生产准备脚本41项通过；无新schema或独立revision系统。
- 前端全量744 passed / 4 skipped，生产构建通过；合法歌曲ID修正仅限旧deployment-profile测试fixture。
- Ruff、Mypy、detect-secrets hooks与文档审计通过。初次unit/contract2696通过、1个报告fixture失败（缺新policy字段），已在相关脚本组修复验证，不将初次运行记为全量Pass。
- 首轮默认全栈预检/质量通过，在真实副本暴露成员所属说明边界后主动停止；最终版本另跑默认完整门禁。

验证服务早期启动遗漏显式Billboard/Analysis sidecar路径，曾在本地 `data/` 写入副本上下文的派生缓存；已停止并用六类明确临时sidecar路径重启。缓存不属于原始事实，本地主库仍保持旧时间戳；不声称所有本地缓存未写。当前验证及后续维护全部指向明确副本，生产原始库未修改。

## 后续收口

完成最终副本聚合/搜索、默认完整全栈和桌面/手机视口显示与点击；按大阶段固定提交，再执行CI、受控准备和发布。生产My Heart纠正、备份、源漂移检测、四精确搜索变体及API/浏览器结果单独补记；结束后归档[实施计划](../plans/2026-10-06-track-credit-resolution-plan.md)。
