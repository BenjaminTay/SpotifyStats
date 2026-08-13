# 音乐档案 Phase 0 与 archive-overview 交付记录

日期：2026-08-13
分支：`codex/account-archive-rebuild`
范围：数据止损、来源治理、严格首屏接口与只读证据；不包含正式页面 UI。

## 结论

本批次已建立可继续重构的本地优先底座：重复导入 `YourLibrary.json` 不再清掉已有收藏日期；收藏日期明确记录为 `oauth / manual / legacy`；新接口只返回音乐档案首屏所需白名单字段，不包含 profile、原始搜索词、prompts、inferences 或 banned item 明细；接口运行时不调用 Spotify Web API。

旧 `/api/account` 与 `/api/account/collection-insights` 暂时保留作兼容，新页面后续只消费分拆后的严格接口。

## 已落地

- Migration 31：新增 `saved_tracks.added_date_source` 与 `account_archive_state` 两类 revision。
- `YourLibrary` 导入：按 `track_uri` 携带已有日期与来源；返回保留/缺失日期数；失败 importer 回滚未提交写入。
- Spotify 显式同步：只补空日期，来源记为 `oauth`；不覆盖 `manual / legacy` 现有日期；更新后提升日期 revision 并清理相关缓存。
- `GET /api/account/archive-overview`：严格 Pydantic 契约、最多四个封面角色、覆盖期、数据状态、日期来源、关联与时长覆盖。
- 缓存：以账号导入 revision、日期 revision、收藏/播放边界和实体治理 revision 组成的 opaque data revision 分流；TTL 300 秒。
- `scripts/account_archive_probe.py`：只读核验真实 SQLite，可设置期望收藏数和日期数作为回归门槛。

## 真实 SQLite 只读证据

数据库：原 worktree 的 `data/spotify_stats.db`，以 SQLite `mode=ro` + `query_only` 打开，未执行 Migration 31，未修改数据。

| 指标 | 结果 |
|---|---:|
| 收藏歌曲 | 800 |
| 有收藏日期 | 800（100%） |
| 可关联本地播放历史 | 762（95.3%） |
| 有准确曲长 | 800（100%） |
| 已知收藏曲总时长 | 195,475,714 ms |
| 收藏专辑 / 艺人 / 节目 | 250 / 59 / 3 |
| 歌单 / 歌单曲目 | 27 / 681 |
| 收藏日期范围 | 2022-06-30T17:25:48Z 至 2026-05-12T07:32:42Z |
| 播放日期范围 | 2022-07-01 至 2026-07-24 |
| 7 / 30 / 90 / 365 天仅按右边界筛选的初步候选 | 800 / 800 / 794 / 584 |
| 非法收藏日期 | 0 |

由于现有日期生成时尚未记录来源，Migration 31 会诚实回填为 `legacy`，不会倒推为 `oauth`。今后通过显式 Spotify 同步新增的日期才标记为 `oauth`。

> 后续 `collection-cohorts` 已加入 URI 匹配、规范曲目去重、左侧数据覆盖和有效播放语义，正式合格分母修正为 761 / 761 / 755 / 560。上表只保留为 Phase 0 初步只读候选证据，不能作为正式回访率分母。

## 接口预算验收

在真实数据上通过独立 FastAPI app 挂载同一路由、覆盖只读连接后采样：

| 指标 | 预算 | 结果 |
|---|---:|---:|
| HTTP 状态 | 200 | 200 |
| raw response | ≤ 40 KB | 1,936 bytes |
| 冷响应 | ≤ 750 ms | 约 157–200 ms |
| 热响应 p95 | ≤ 75 ms | 约 6–9 ms |
| 缓存采样 | revision 分流 | 1 miss / 11 hits |

真实数据状态为 `partial`，原因不是日期缺失，而是仍有 38 首收藏无法关联到本地曲目/播放事实。收藏浏览与收藏时间线可用，收藏—播放交叉分析按 95.3% 覆盖明确降级。

## 自动验证

- account archive 新增单元/接口测试：11 项通过。
- migration 全量幂等与核心表测试：通过。
- account route response model / OpenAPI schema 契约：通过。
- Ruff check、Ruff format check、`git diff --check`：通过。

## 下一批

1. 建立统一 account archive 过滤上下文，固定有效播放、连续合并、merge level、时区与 observation window。
2. 实现 `collection-journey` 与 `collection-cohorts`，明确右删失和 7/30/90/365 天合格分母。
3. 实现 returns / discovery / library 分页接口，再进入 Desktop / Compact / Phone presentation。
4. 正式页面切换后退役旧重型 `/api/account` 消费链，但暂不删除兼容端点。
