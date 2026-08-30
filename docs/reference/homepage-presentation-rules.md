# 首页展示与长期记忆规则

> 最近修订：2026-08-30
> 状态：当前规则
> 适用范围：`/` 个人音乐头版、`/api/home/overview` 以及首页 Desktop / Phone presentation

本文说明首页 Billboard 冠军状态、榜单卡片布局和“从记忆中重逢”的事实筛选与展示选择。它补充
[`playback-stats-rules.md`](playback-stats-rules.md) 的 Billboard 周榜规则；首页不改变播放次数、收听时长或榜单统计口径。

## 1. Billboard 冠军状态

首页卡片消费后端生成的 `HomeChartChampion.movement`，不能仅根据当前周是否有
`previous_rank` 推断“新入榜”。在同一完整过滤上下文下，状态含义为：

- `new`：该实体在完整已发布历史中此前从未上榜；
- `re`：该实体曾在更早的完整已发布周上榜，但在上一完整周缺席，本周重新进入；
- `up` / `down` / `same`：本周与上一完整周都上榜，分别表示名次上升、下降或持平。

最新播放所在的覆盖边缘周不是完整 Billboard 周，不参与上述历史判定。`previous_rank=null` 可能同时出现在“新入榜”和“重回榜”，因此不是判定依据。

Desktop 的单曲、专辑、艺人冠军卡片共用一行艺人/归属信息槽；即使曲目没有艺人副标题，也保留该槽的最小高度，使三张卡片的“新入榜 / 重回榜 / 播放次数”行保持水平对齐。Phone 只改变布局，不改变 movement 语义。

## 2. “从记忆中重逢”的候选事实

候选池由后端依据当前首页统计上下文确定性生成。对每首规范首页曲目聚合后，必须同时满足：

1. 历史有效播放次数至少为 10 次；
2. 上次播放早于最新有效数据日之前 90 天；
3. 曲目、艺人、封面和最后播放日可以由本地事实解析。

候选按以下稳定顺序取前 20 首：历史播放次数降序、最后播放日升序、稳定曲目 ID 升序。这样候选池可以安全缓存、测试和复核；随机性只属于前端的展示选择，不改变后端统计事实。

`/api/home/overview` 同时返回：

- `rediscovery_candidates`：完整候选池，供新客户端选择；
- `rediscovery`：按最新数据周稳定选择的单项兼容字段，供尚未消费候选池的旧客户端使用。

空数据或没有满足条件的曲目时，候选池为空，首页显示长期记忆空态，不编造歌曲。

## 3. 刷新时的随机选择

首页首次载入或浏览器完整刷新时，前端从候选池随机选择一首。选择记忆按
`filter_fingerprint` 写入当前浏览器 tab 的 `sessionStorage`；候选池多于一首时，下一次完整刷新会排除上一首，再从其余候选中随机选择。因此“刷新后换一首”是展示层的通常行为，不承诺候选池只有一首时也能换歌。

以下场景不会重新抽取：

- React 重新渲染；
- 首页后台 warming 更新同一候选池；
- Desktop / Phone presentation 切换；
- 候选内容和过滤指纹没有变化的普通 Query 更新。

切换过滤上下文会使用新的指纹重新选择。`sessionStorage` 不可用时仍会随机展示，但无法跨刷新记住上一首；这不影响统计正确性。

## 4. 契约、缓存与实现状态

- `HomeOverviewResponse.rediscovery_candidates` 是向后兼容的可选前端字段；后端模型对空值返回空数组。
- 候选池加入首页事实响应后，首页事实缓存版本提升为 `home-facts-v4`，避免复用没有候选池的旧快照。
- 后端实现位于 `backend/domains/home/overview.py`、`backend/models/home.py` 和 `backend/services/home_service.py`；前端选择位于 `frontend/src/hooks/useHome.ts`，入口位于 `frontend/src/pages/DashboardPage.tsx`。
- Billboard 状态的历史事实由后端 movement 生成；前端只负责文案映射和布局展示。

当前实现状态：`IMPLEMENTED`。候选池、刷新换曲、重渲染稳定性、首页契约和缓存版本均有针对性测试；本地 frontend build、相关 frontend tests、后端 unit / contract 测试已验证。当前提交不代表已 push 或已部署，运行中的旧服务需要重启后才会消费新的首页响应字段。
