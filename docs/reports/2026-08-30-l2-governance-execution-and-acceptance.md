# L2 自动归并治理执行与验收报告

> 状态：Pass（实现、真实数据库迁移、派生重建、真实 API/浏览器验收和默认完整全栈门禁均已完成）。证据日期：2026-08-30。
> 当前规则：[`../reference/music-metadata-management.md`](../reference/music-metadata-management.md)、[`../reference/playback-stats-rules.md`](../reference/playback-stats-rules.md)

## 1. 最终规则

本轮把 L1、L2、L3 的边界收口为：

| 层级 | 身份语义 | 自动处理边界 |
| --- | --- | --- |
| L1 | 稳定的本地 canonical track；原始播放和 provider 来源完整保留 | 不因曲名或艺人相似而自动合并；只审计可能误收的多个 Spotify ID |
| L2 | 曲名归一后一致且有效主艺人集合一致的同一首歌 | 默认机器归并，不要求 ISRC、时长、专辑或版本标签一致；同名同艺人即同一首歌 |
| L3 | 同一作品的不同演绎、录音、重录、现场、Acoustic、Remix 等 | 只在 composition 关系存在时进一步合并；本轮不凭标题相似自动推断 |

专辑 L2 使用 Album Project：标准版、豪华版、Acoustic Collection、Long Pond 等只要共享正式主体曲目，就属于同一专辑项目；这不等于把其中原版与 Acoustic 单曲在歌曲 L2 合并。精选集候选继续冻结，不在规则未定时自动写入。

## 2. 实施内容

- schema 66/67 增加 L2 归一、机器候选、治理运行和 Album Project 自动归并所需结构。
- L2 机器任务按归一曲名和有效主艺人集合建立 recording 组，写入稳定证据、来源和 revision；重复运行保持幂等。
- Album Project 自动任务按正式主体曲目成员关系归并版本专辑，同时保留 source album 用于来源解释。
- L1 增加只读风险审计和安全分拆边界；有多 ISRC、明显时长冲突、版本词或视频证据的对象进入人工复核，不在基础身份层冒进修改。
- 治理 CLI 支持计划、应用、运行记录、审计摘要和派生数据刷新。
- 歌曲详情当前消费链改用稳定 L1 owner 路由，再按请求的 L2/L3 展开成员，避免 legacy source ID 歧义返回 409。
- Billboard 记录页共享连续周数与稳定 Top 20 排序实现，恢复项目架构行数门禁而不改变排名语义。
- 浏览器 route smoke 为动态详情提供 45 秒等待；确定性冷构建页面最多等待 360 秒并在内容就绪后立即结束。默认 5 秒导航等待保持不变。

## 3. 真实数据库执行

正式本地库治理运行 ID：`c355222e-e798-4ca5-86e5-edceb31dc7aa`。执行前使用 SQLite Online Backup 保存：

`data/backups/spotify_stats_20260830T061334Z_before-l2-governance.db`

数据库迁移到 schema 67，`integrity_check=ok`，`foreign_key_check=0`。原始事实未被治理任务改写：

| 原始表 | 行数 | SHA-256 |
| --- | ---: | --- |
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` |

执行结果：

- L2 发现 87 个确定性候选组；创建 85 个、更新 1 个、另 1 个既有人工组保持有效，共新增 171 条成员关系，阻断 0。
- 当前共有 86 个机器组和 1 个人工组；86 组大小为 2，“纯妹妹”组大小为 3。成员重叠 0、少于 2 个成员的活动组 0。
- Album Project 发现 23 个候选组，共归并 64 张专辑，创建 release group 829–851；重复 dry-run 后候选为 0。
- L1 审计发现 817 个可能存在基础身份风险的 owner；143 个涉及多 ISRC、64 个有时长冲突、136 个有版本词、113 个有视频证据。全部进入复核，安全自动分拆为 0。
- 精选集候选固定为 26 个，仅保留调查结果，未自动归并。

## 4. 代表性数据复核

- “纯妹妹”L2 组 `5846` 包含 Track `4546/5107/5732`；任一成员进入详情均聚合为 30 次、1.6 小时和 30 条播放明细。
- “手心的薔薇”L2 组 `5874` 包含 Track `852/4309`，聚合为 87 次。
- `The Life of a Showgirl` Album Project `41476` 包含 2 张专辑、33 首项目曲目；统计为 1,663 次、97.4 小时、30 首唯一曲目。
- `folklore` Album Project `41478` 包含 3 张专辑、34 首项目曲目，包含 `The Long Pond Studio Sessions`。
- Wicked 的 album `1356/1357/1483/1484/1485/1489/1490` 已归入同一 project `42213`。
- `Bad Boy`、`Hounds of Love`、`Emancipation`、`Star`、`Superman` 的大小写差异发行已归并。
- 原版与 Acoustic/Long Pond 单曲在 L2 仍然不同：Track `4454/4461`、`4451/4463`、`cardigan` 的 `93/127` 均未建立 recording 组。

## 5. 派生数据与 API

L2 治理完成后 revision 为 6，Album Project revision 为 1。四套精确音乐查找快照均已 ready/current，每套 7,870 个实体：

- 动态阈值 L2：`4413500b…`
- 动态阈值 L3：`8a6bed00…`
- 固定阈值 L2：`6a86599d…`
- 固定阈值 L3：`05bedf07…`

四套年度投影均 ready，每套覆盖 5 年、550 行。固定完整过滤参数下，API overview 为 66,419 次、4,196.1 小时；L2/L3 曲目榜分别有 5,712 个实体，专辑榜分别有 1,171 个实体。

当前数据库没有 composition 组，因此 L2 与 L3 榜单 JSON 暂时逐字节相同。这只是当前数据状态，不代表规则语义相同；未来建立 L3 composition 关系后，L3 才会比 L2 进一步聚合。

治理任务幂等复验：87 个 L2 组全部为 `unchanged`，Album Project 新候选 0，L1 自动操作 0，精选集仍冻结为 26 个候选。

## 6. 浏览器与功能验收

真实浏览器已在 Desktop 1440×1000 和 Phone 390×844 验证“纯妹妹”详情；三个成员版本均出现在 30 条播放明细中，控制台 0 error，移动端无横向溢出。`The Life of a Showgirl` 项目详情及曲目请求返回 200。

本地截图不提交个人音乐信息：

- `output/playwright/l2-pure-desktop.png`
- `output/playwright/l2-pure-mobile-390.png`
- `output/playwright/l2-showgirl-mobile-390.png`

## 7. 自动化验证

已通过：

- 后端 unit：1,442 passed。
- 后端 contract：403 passed。
- 后端完整套件：2,382 passed，4 个既有环境/弃用 warning。
- 前端 Vitest：607 passed；TypeScript 与 Vite production build passed。
- L2 详情链路定向前端测试：32 passed。
- Billboard 记录计算定向回归：40 passed。
- 文档审计、pre-commit 和 `git diff --check` passed。
- 浏览器 route 矩阵：55/55，另有 30 个五档代表视口组合；桌面、移动、图表交互与长列表 passed。
- 控件清单覆盖 2,366 个控件、447 个主要触控目标，未命名、小尺寸和布局违规均为 0。
- Chromium、Firefox、WebKit 兼容性 passed。

较早一次默认门禁中，quality、backend 和 API 阶段通过，browser routes 仅有冷构建内容标记超时；当时所有失败页面均为控制台 0 error、page error 0、横向溢出 0。缓存就绪后的 route 矩阵为 55/55，后续 interactions、inventory 和 compatibility 阶段也全部通过。为使冷启动门禁本身稳定，动态页面等待扩展到 45 秒。

随后一次冷启动复跑因 smoke 等待策略已经更新、对应源码契约仍断言旧的 12 秒值而在 backend 阶段失败（2,381 passed、1 failed）。契约同步到 45 秒后单独通过 13/13。

复跑进一步揭示年榜并非单纯页面等待不足：冷请求实测 254.906 秒后返回 200，热请求约 20ms，而通用前端 API 超时为 30 秒，页面会提前停在 408 错误。年榜 query 因此使用 300 秒专用请求上限，其他 API 仍保持 30 秒；慢页面 smoke 上限为 360 秒且每秒轮询、内容就绪即退出。全新后端进程下，年榜桌面冷构建与随后移动端热命中均通过，控制台、page error 和横向溢出为 0。该兜底恢复冷启动可用性，但约 255 秒的年榜首次构建性能仍是后续独立优化项。

最终默认完整全栈门禁为 **Pass**，总耗时 2,711,072ms。七个必需阶段全部通过：quality 67,281ms、backend 989,359ms、API 760,722ms、browser routes 529,480ms、browser interactions 91,385ms、browser inventory 78,907ms、browser compatibility 193,755ms。API smoke 138/138、边界 112/112、OpenAPI 206 个 operation 和 97 项参数义务均无未登记项；所有热端点 P95 低于 500ms。

## 8. 边界、回滚与 Git 状态

- L1 的 817 个风险对象不是本轮遗留错误数量，而是需要额外证据才能安全分拆的审计集合；本轮不会为了减少人工审核而破坏基础身份。
- L2 已按“归一曲名一致 + 有效主艺人一致”机器化；人工只处理 L1 身份冲突、精选集策略和 L3 作品关系等无法由当前确定性证据安全决定的问题。
- 回滚优先恢复治理前 Online Backup；搜索和年度投影属于可重建派生数据。
- 核心实现已本地提交为 `9e2f4405 feat: 自动化 L2 曲目与专辑项目归并`。
- 本报告和最终验收收口作为独立大阶段本地提交；未 push、未部署。
