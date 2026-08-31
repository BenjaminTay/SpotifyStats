# L2/L3 身份与专辑归属完整性修复交付报告

> 证据日期：2026-09-01
>
> 实现状态：IMPLEMENTED
>
> 真实数据治理：PASS
>
> API 与响应式验收：PASS
>
> 默认完整全栈门禁：PASS（7 个必需阶段单轮全部通过）
>
> 仓库状态：核心提交 `cd6cf621`、定向修复提交 `7fbaf420`；最终证据提交见本轮 Git 历史
>
> 远端状态：UNPUSHED
>
> 部署状态：NOT_DEPLOYED

## 1. 结论

本轮修复了真实数据检查中确认的四个结构性缺口：

- L2 Album Project 现在可以在不同 Spotify release ID 之间，以相同 canonical album artist、完整
  有序曲目表和受控 Remaster/Deluxe/catalog 证据自动归并等价发行；大小写、Unicode、艺人名前后缀
  和中文“同名专辑”标记只扩大候选召回，不单独触发合并。
- L3 stable work key 不再把一个完整 L2 recording group 重新拆成多个 L1 key。
- L3 专辑归属以完整 work universe 为分母，缺少 membership 的作品也必须进入明确归属或排除账本；
  健康接口不能再因漏扫而虚假全绿。
- L1 owner 风险先机器分类，只执行可证明安全的 relink/split；歧义项进入显式 review queue，不以扩大
  规则或批量人工审核阻塞已经收敛的 L2/L3。

真实主库最终状态为：L2 46 组 / 93 个成员，L3 6,285 个作品全部有明确归属，hard issue、未覆盖、
多 owner 和守恒差值均为 0。《孫燕姿同名專輯》与《同名專輯 (Remastered)》已合并为同一 L2
Album Project；2004 年 12 首曲目的《孫燕姿STEFANIE同名專輯》保持独立。

## 2. 实现范围

### 2.1 等价发行 Album Project v2

- 候选发现支持 exact、Remaster、Deluxe/Expanded 和 catalog alias 证据。
- 归并要求 canonical album artist 相同、完整有序 repertoire 相容，并保留来源发行、外部 ID、主发行、
  evidence reason 与 confidence。
- 艺人名前缀/后缀和 `同名專輯` / `同名专辑` 只生成更宽的 family key；最终判断仍由完整证据门禁
  决定，因此 2004 年同名但曲目不同的专辑不会被误并。

### 2.2 Stable work 与归属 coverage v2

- 完整活动 L2 recording group 作为不可拆分 work child；singleton 只用于未分组 L1 owner。
- migration 69 增加 L3 coverage v2 与 exclusion ledger，归属构建扫描完整作品全集。
- Live、重录、Acoustic、Remix 等版本继续在歌曲 L3 合并；专辑统计按唯一原生专辑归属逐曲回流。
- compilation/精选集策略没有在本轮扩大；明确不计入的事件进入 exclusion ledger，并参与守恒对账。

### 2.3 L1 风险与自动修复边界

- 只读探针输出 strong internal identity risk、机器动作和人工队列。
- 自动流程只发布能够确定安全的 provider relink 或 split，并在启动维护中仅修复有界目标闭包。
- 当前 600 个风险 owner 没有安全机器拆分证据，保留为 review queue；这不是 L2/L3 hard issue，也不
  代表已经人工确认无误。

### 2.4 API、Settings 与发布链

- 健康 API 分别报告 L1 risk、L3 attribution、coverage、排除项、revision 和影响范围。
- Settings 在同一治理工作台展示机器分类、review queue、L3 coverage 与技术详情。
- 联合治理运行以 Online Backup、关系 revision、完整验证和四套 L2/L3 × fixed/dynamic 精确快照为
  原子发布边界；第二次 dry-run 必须 `changed=false`。

## 3. 双副本演练与主库执行

### 3.1 第一轮：核心 coverage 修复

两份独立 SQLite Online Backup：

- `/tmp/spotifystats-l3-clone-a.1dJWFV/clone.db`
- `/tmp/spotifystats-l3-clone-b.fVEhOK/clone.db`

两份副本均得到相同结果：track revision `10 → 11`、album revision `5 → 6`，L3
`6,285 / 6,285` 自动归属，issue、exclusion、uncovered、conflict 均为 0；四套搜索快照全部 ready，
共同 semantic base key 为
`0f915...`。第二次 dry-run 的 L1 operation 和 Album Project candidate 均为 0。

主库 run id：`bf2cbb43-...`；执行前备份：
`data/backups/spotify_stats_20260831T130747Z_before-version-governance.db`。

### 3.2 第二轮：孙燕姿同名专辑定向修复

修正候选 family key 后，两份相同副本再次完整治理，结果完全一致：只产生一个等价发行候选，
release group `859`，track revision 保持 `11`，album revision `6 → 7`，四套快照 ready，共同
semantic base key 为
`237d9a874a928361a7001ae3129cca8f1ec155215f7de0a585ee40f6f300a4ef`。第二次 dry-run 候选为 0、
`changed=false`。

主库 run id：`0c6e7163-5079-45b7-9a1a-366c4b5bd7ab`；执行前备份：
`data/backups/spotify_stats_20260831T132712Z_before-version-governance.db`。

最终 `PRAGMA integrity_check=ok`、foreign key issue 为 0。所有正式写入只发生在派生治理与快照表，
没有重写原始播放、曲目或署名事实。

## 4. 原始事实保护

| 表 | 行数 | 治理前后 SHA-256 |
|---|---:|---|
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` |

两轮两份副本和两次主库执行后，上述行数与哈希均保持一致。

## 5. 真实数据最终状态

最终只读探针连续运行两次，得到完全一致的数据库 fingerprint
`9c40456be7a5b6c9899bb63326d771b5f84cc569433a7dcee987bd89ddd011c3` 和 core digest
`f40082072296527994e471548b23fc8d235ebb8cb8241d4f7f774b3fed84f624`。

| 检查项 | 结果 |
|---|---:|
| L1 多 provider ID owner | 817 |
| L1 机器保留 / 安全拆分 / review queue | 217 / 0 / 600 |
| L1 hard issue | 0 |
| L2 活动组 / 成员 | 46 / 93 |
| L2 overlap / undersized / invalid primary / duplicate split | 0 / 0 / 0 / 0 |
| L2 group 被拆到多个 L3 work | 0 |
| L3 work / 已明确归属 | 6,285 / 6,285 |
| L3 uncovered / issue / multi-owner / orphan | 0 / 0 / 0 / 0 |
| 默认逻辑事件 | 66,475 |
| compilation 明确排除事件 | 6,168 |
| 已归属事件 | 60,307 |
| 守恒差值 | 0 |

健康总状态显示 warning 只因为 600 个 L1 review queue；L2/L3 本身为 ready/healthy，且没有把人工
队列误算成 hard issue 或静默丢弃。

## 6. 《孫燕姿同名專輯》定向验收

| 发行 | 本地 album | 最终项目 | 结果 |
|---|---:|---:|---|
| `孫燕姿同名專輯`（2000，10 首） | 1302 | 42176 | 主发行 |
| `同名專輯 (Remastered)`（2000，10 首） | 1523 | 42176 | `remaster_equivalent`，confidence 0.99 |
| `孫燕姿STEFANIE同名專輯`（2004，12 首） | 1688 | 42359 | 独立项目 |

release group `859` 的 canonical name 为 `孫燕姿同名專輯`。前两张发行的 Spotify external ID 都
挂在项目 42176，完整曲序等价；2004 年专辑曲目不同，没有被同名 marker 穿透证据门禁。

真实搜索 API 在 L2 和 L3 都只返回一个合并后的 2000 年项目，同时保留独立的 2004 年项目；从成员
发行名进入后，统计、排行、明细和日历使用同一个稳定 Album Project，而来源发行仍可解释。

## 7. API 与浏览器验收

- `/api/health`：200。
- `/api/version-merge/l1-identity-risks/health`：应用 run 可见，217 / 0 / 600 分类可追溯。
- `/api/version-merge/l3-album-attributions/health`：healthy，revision 3，6,285 个 work，issue 0，
  coverage reconciled。
- `/api/import/health`：核心统计 `safe_to_use=true`；237 条无 Track 的 audio 记录为既有信息项，不是
  本轮治理问题。
- `同名專輯` 真实搜索：2000 年两发行解析为 project 42176，2004 年 project 42359 保持独立。
- Settings Desktop：L1 分类和 L3 归属健康可见；浏览器 console error/warning 均为 0。
- 390×844：`clientWidth=390`、`scrollWidth=390`，无横向溢出，console error/warning 均为 0。
- `Anti-Hero` L3 搜索卡显示 `归属：Midnights · 来源：Midnights`，验证消费端使用原生专辑归属。

## 8. 自动化与门禁

已通过：

- 核心实现前完整 unit：1,588 passed；完整 contract：411 passed。
- 前端完整测试：612 passed；production build：PASS。
- 修正同名专辑 family key 后定向回归：68 passed。
- migration 69 与 L3 定向回归：18 passed；Ruff：PASS；文档审计：PASS。
- 最终默认完整全栈的 quality 阶段：PASS；完整后端：2,542 passed、4 warnings；OpenAPI operation
  audit：218 operations、0 unaccounted；API smoke：146/146；API boundary：113/113。

默认完整全栈首次运行在迁移版本断言仍固定为 68 时失败；同步到 schema 69 后，下一轮功能阶段全部
通过，但 API benchmark 与另一任务的 8015/5185 隔离全栈探针并发，出现
`/api/billboard/data` 超时和 `/api/dashboard/full` 热 P95 871ms。无竞争复测后，所有热 P95 恢复到
240ms 以内，确认该轮为共享主机竞争，不是本轮代码回归。

随后完整轮次在 `/analysis/records` 与 `/billboard/year-end` Desktop 首次冷建时，只渲染页面壳，
分别缺少“高光时刻”和“阶段领先单曲”marker；同轮 Mobile 在缓存就绪后均通过，且无 console、page
error 或 overflow。缓存就绪后的最终默认完整轮没有使用 `--from` / `--only`，7 个必需阶段单轮全部
通过：

- 总耗时：3,154,332ms（52 分 34.332 秒）；
- quality 102,438ms；backend 1,306,977ms；API 875,207ms；
- browser-routes 468,374ms；browser-interactions 94,338ms；
  browser-inventory 89,655ms；browser-compat 217,112ms；
- 54 个 Desktop/Phone 路由与 30 个五视口组合全部通过，0 console error/warning、0 page error、
  0 overflow；
- 40 个 inventory 路由/视口共 2,053 个控件、394 个主要触控目标，尺寸违规为 0；7 个长列表场景
  全部通过；
- Chromium、Firefox、WebKit 的路由 marker、搜索焦点和核心交互全部通过；
- 热 P95：Billboard data 240ms、weekly 150ms、dashboard full 230ms，全部低于 500ms。

## 9. 边界与回滚

- 600 个 L1 review queue 仍需未来独立治理；当前没有足够证据安全机器拆分，本轮没有扩大自动规则。
- 精选集产品策略仍冻结；6,168 个 compilation 事件以明确 exclusion ledger 参与守恒，不是静默漏算。
- 两个主库备份必须保留，可按对应治理批次回滚；临时 `/tmp` 副本在交付完成后删除。
- 本轮未 push、未部署；本地数据库已治理不等于生产环境已更新。
