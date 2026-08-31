# L3 自动治理执行与验收报告

> 证据日期：2026-08-31
>
> 实现状态：IMPLEMENTED
>
> 真实数据治理：PASS
>
> 功能与响应式验收：PASS
>
> 默认完整全栈门禁：PASS（7 个必需阶段全部通过）
>
> 仓库状态：本轮阶段提交 `2c724016`、`7af494be`；最终收口提交见本轮 Git 历史
>
> 远端状态：UNPUSHED
>
> 部署状态：NOT_DEPLOYED

## 1. 结论

本轮已经把版本治理从“L2 发现冲突后停止”改为真正的分层归并：

- L1 仍是稳定 Spotify owner 层，不执行歌曲业务归并，也不改写原始事实。
- L2 机器归并 canonical artist 与规范化普通歌名相同的同一首基础歌曲；结构性标题保持分离，
  ISRC、时长和来源差异只记 warning。
- Acoustic、Live、Remix、Taylor's Version 等在 L2 保持不同录音，但会作为确定性候选自动进入 L3
  composition，而不是因 L2 rejected 就从后续流程消失。
- L3 以完整 L2 recording group 为不可拆分 child；未进入 L2 组的 L1 owner 以 singleton 参与。
- 专辑 L3 以完整 L2 release project 为 child，按 canonical album artist、受控版本后缀和曲目作品
  重叠建立 composition parent；标准版/Deluxe、Long Pond/Acoustic Collection 的 L2 项目归属不受
  歌曲 L2 录音边界干扰。
- compilation 自动策略仍冻结，没有在本轮擅自改变精选集 membership 或榜单资格。

真实主库运行后，L2 关系摘要完全不变；新增 380 个歌曲 L3 composition group 和 2 个专辑 L3
composition project。原始 `plays`、`tracks`、`track_artists` 的行数与 SHA-256 前后完全一致。

## 2. 实现范围

### 2.1 歌曲 L3

- `track_composition_identity.py` 提供受控基础标题、版本标签与 blocker 解析。
- `l3_track_auto_merge.py` 以完整 L2 组/singleton 为输入，生成候选、cannot-link、warning 和稳定组。
- L2 `semantic_version_conflict` 只表示“当前层级不能合并”；L3 会重新按 composition 规则评价。
- translation、cover、mashup、parody、sample、reprise、结构性标题、艺人不相容和歧义证据保持
  fail closed。
- 人工 `force_separate` 优先于人工 `force_merge`，人工覆盖优先于机器判断；覆盖可通过 API/UI
  清除，审计保留 scope、policy version、evidence 和 before/after。

### 2.2 专辑 L3

- `album_composition_auto_merge.py` 只消费完整活动 L2 release project。
- 自动门禁要求 canonical album artist 相同、基础项目名唯一、受控版本关系成立，且曲目作品重叠
  不低于 60%；最小交集为 `min(5, max(2, ceil(smaller * 0.6)))`。
- compilation、manual project、弱重叠和歧义基础名均不自动归并。
- composition parent 只挂接 release child，不修改 L2 project 或 membership。

### 2.3 联合治理、API 与 UI

- `scripts/apply_version_governance.py` 统一执行 L1 审计、L2、歌曲 L3、Album Project 与专辑 L3，
  并以同一个运行发布关系 revision、四套精确搜索快照及四套详情年榜投影。
- 治理 API 支持 L2/L3 scope、机器/人工来源、policy version，以及清除人工覆盖。
- Settings 同一工作台在 Desktop 与 Phone 复用。390×844 下标签、分组卡片和长 policy version 会
  在容器内换行，不再横向裁切。

## 3. 安全演练与主库执行

### 3.1 副本演练

正式主库运行前，使用 SQLite Online Backup 生成两份彼此独立的数据库副本：

- `/tmp/spotifystats-version-trial1.sFkwWg`
- `/tmp/spotifystats-version-trial2.UbrJ4X`

两份副本均完成完整 `--apply`，随后执行第二次 dry-run。两次复跑的 L1 操作、L2/L3 曲目变更、
L3 专辑变更和归档数量均为 0，证明同一策略对已治理状态幂等。

### 3.2 主库执行

- 数据库：`data/spotify_stats.db`
- run id：`a939e8d8-f889-43b5-87e1-716158b114db`
- schema：67
- track identity revision：8 → 9
- album project revision：3 → 4
- 执行前 Online Backup：
  `data/backups/spotify_stats_20260831T024555Z_before-version-governance.db`
- relationship validation：PASS
- final validation：PASS
- `PRAGMA integrity_check`：`ok`
- foreign key issue：0

主库执行后再次 dry-run，L2/L3 曲目与专辑的 create/update/archive 均为 0；因此主库也已验证收敛。

## 4. 原始事实保护

| 表 | 行数 | 治理前 SHA-256 | 治理后 |
|---|---:|---|---|
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` | 相同 |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` | 相同 |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` | 相同 |

L2 relationship digest 治理前后均为
`53c1fdee41111f57bddec69b3149911a2f6d6f60ae79ce0dbe2438057ac198dc`。这证明 L3 新增关系没有
拆散或改写 L2。

## 5. 真实关系与候选统计

| 层级 | 活动组 | membership / child | 结果 |
|---|---:|---:|---|
| L2 recording | 46 | 93 | 保持不变 |
| L3 track composition | 380 | 873 | 新建并发布 |
| L3 album composition | 2 | 4 release children | 新建并发布 |

歌曲 L3 共写入 786 条候选证据，其中 accepted 642、rejected 144、pending 0；5 个既有 L2 recording
group 被完整挂接到 composition parent。warning 统计为：ISRC 不相交 631、强时长差异 353、
source context 32。warning 不改变 accepted 结果。

专辑 L3 的两个自动结果为：

| composition | release children | 匹配作品 | 最小覆盖率 |
|---|---|---:|---:|
| `1989` | 原版 + Taylor's Version | 16 | 84.2105% |
| `Speak Now` | 原版 + Taylor's Version | 16 | 94.1176% |

审计事件包含 380 次 composition group create、642 次 composition candidate accepted、144 次
composition candidate rejected、2 次 album composition create；已抽查 evidence 与 after payload，空
payload 数为 0。

## 6. 派生数据发布

四套公开搜索上下文以 `shared_full_snapshot_rebuild` 同组构建并原子发布，周账本 ready，年榜投影
与核心上下文一起 ready：

| merge level | dynamic | snapshot key 前缀 | 实体数 | 年数 / 投影行 |
|---:|:---:|---|---:|---:|
| L2 | 否 | `acf0c5a82cd8` | 7,873 | 5 / 550 |
| L2 | 是 | `fcee4fbaa46e` | 7,873 | 5 / 550 |
| L3 | 否 | `7ea336ef4c40` | 7,460 | 5 / 550 |
| L3 | 是 | `f996d68ff53f` | 7,460 | 5 / 550 |

四个 snapshot 和四个 projection 均为 `ready`，failed count 为 0。

## 7. 真实 API 语义验收

### 7.1 同作品跨版本

`Anti-Hero` 在 L2 搜索返回 7 个独立结果，在 L3 返回 1 个作品结果：

- 原版 track 157，L2：315 次、17.3 小时、1 个实际曲目、1 张专辑。
- Acoustic track 445，L2：9 次、0.5 小时。
- 从任一成员按 L3 请求：362 次、19.9 小时、7 个实际曲目、3 张专辑，代表 ID 和合计完全一致。

这证明版本没有在 L2 误并，同时已经自动进入 L3。

### 7.2 结构性标题

`intro (end of the world)` 的原版、extended 和 live 在 L3 搜索仍为 3 个结果，且三者均未进入活动
track group。结构性标题 blocker 没有被“同名就合并”规则穿透。

### 7.3 专辑作品层

- `1989` L2：412 次、24.5 小时，project 41520。
- `1989 (Taylor's Version)` L2：961 次、58.3 小时，project 41882。
- 两个 child 在 L3 都解析到 project 43290：1,373 次、82.8 小时、39 首去重曲目、4 个来源专辑。

### 7.4 治理 API

- `/api/version-merge/track-groups` 返回 426 个活动组：46 个 recording + 380 个 composition。
- 响应携带 `identity_policy_version` 和 `automatic_version_tag`。
- 清除覆盖 DELETE endpoint 已进入 OpenAPI、operation audit、parameter boundary audit 和 contract 测试。

## 8. UI 与浏览器验收

Desktop Settings 已验证 L2“同一录音”和 L3“同一作品”标签、426 个保存分组、机器/人工来源与
policy version 均可见，控制台无 error/warning。

390×844 真视口首次检查发现任务标签和 policy badge 可能超出卡片。修复 `min-width`、grid/button
收缩和长策略换行后复验：三个任务按钮均为 111px，策略 badge 宽 283px 并正常换行，
`innerWidth`、document 和 body 宽度均为 390px，控制台无 error/warning。

全栈浏览器矩阵随后覆盖：

- 54 个 Desktop/Phone 路由组合；
- 30 个五视口组合；
- Desktop、Phone 与 chart 交互；
- 40 个 inventory 路由/视口、2,297 个控件、382 个触控目标、7 个长列表；
- Chromium、Firefox、WebKit。

所有已执行浏览器阶段均无 overflow、undersized touch target、console error 或 page error。WebKit
在第一次兼容性局部运行遇到一次加载态文本过短的瞬时失败，按完全相同范围重跑后 Chromium、
Firefox、WebKit 全部通过；该过程如实保留，不把瞬时失败隐去。

## 9. 自动化验证

- 后端 unit：1,561 passed，947 deselected。
- 后端 contract：409 passed，2,099 deselected。
- 完整后端阶段：2,508 passed，4 warnings。
- OpenAPI operation audit：212 operations，0 unaccounted。
- OpenAPI parameter boundary audit：101 obligations，0 unaccounted。
- API smoke：143/143。
- API boundary：113/113。
- 热端点 benchmark：全部 P95 < 500ms。
- 前端关联测试：18 passed。
- 前端完整测试：76 files / 611 tests passed（受控 workers）。
- 前端 production build：PASS。
- 文档审计：见本轮最终门禁结果。
- 默认完整全栈门禁：PASS；完整模式依次通过 quality、backend、api、browser-routes、
  browser-interactions、browser-inventory、browser-compat，耗时 3,042.570 秒。该次默认运行没有用
  局部 `--from` 结果代替整套状态，最终报告 `overall_status=PASS`。

## 10. 边界与后续

- 本轮没有修改、删除或重写原始播放与署名事实。
- compilation 仍是明确冻结的产品决策；当前自动 L3 不越权处理精选集。
- 机器规则仍对未知后缀、翻唱、翻译、采样、mashup、parody、reprise、艺人不相容与歧义证据
  fail closed；必要时使用可审计人工覆盖，而不是扩大模糊匹配。
- 本轮只在本地完成实现、主库治理、验证和 Git 提交；未 push、未部署，不能据此声称生产已更新。
