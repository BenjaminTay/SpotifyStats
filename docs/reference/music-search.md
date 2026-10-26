# 音乐搜索候选与统计读取合同

适用读者：维护者与Agent。本文是共用技术参考；日常操作见[使用指南](../user-guide.md)，实施与验收证据见[报告索引](../reports/README.md)。

最近核对：2026-10-25。Quick Open 和 `/music/search` 共用两阶段链路：先定位实体候选，再读取精确统计context。候选索引、完整统计快照和附属详情投影具有各自生命周期。

## 两阶段读取

| 请求 | 内容 | 边界 |
| --- | --- | --- |
| `GET /api/music/search?response_mode=candidates` | 按关键词、类型、资格和分页返回歌曲、专辑、艺人候选 | 不冷建lifetime统计或完整Billboard |
| `GET /api/music/search/context` | 按稳定entity key读取与已服务过滤指纹匹配的统计 | 缺失不能显示虚假0或回退全库构建 |

候选generation可与统计快照分离发布；候选ready不代表统计ready。精确统计缺失、warming或stale按返回状态展示。只有真实就绪的0才显示0；不可用和请求失败不能被空结果替代。旧候选或统计的复用必须满足各自语义及过滤合同。

## 身份和过滤

歌曲使用track owner，专辑使用稳定项目身份并以艺人消歧，艺人使用canonical身份。名称用于匹配和展示，不能取代稳定实体key；L2/L3统计按[统计规则](playback-stats-rules.md)的membership和有效署名读取。

Query身份包含完整语义过滤、规范化关键词、类型、分页和资格。context使用ready过滤指纹与排序去重的entity keys。后端设置是服务端过滤事实源；当前发布集合为L2/L3 × 动态/固定阈值四套精确变体，不能跨过滤指纹复用结果。L1仅保留兼容或陈旧证据，不属于当前必须发布集合，边界与[导入合同](data-import-and-health.md)一致；具体变体以[注册表](../../backend/domains/music_search/variants.py)为准。

## 前端请求和交互

- 所有GET通过TanStack Query与queryKeys获取；候选请求消费AbortSignal，使用 `retry: 0`，仅在同一完整过滤身份下保留上一批结果。
- 查询输入共用220ms防抖、IME composition和短查询门禁。高亮与搜索复用标准化规则；无Intl.Segmenter时仍保持Unicode和grapheme安全。
- 仅成功响应中的统计warming/stale或候选LKG按2/4/8/10秒退避观察；终态、error、页面隐藏和卸载停止。
- Quick Open处理快捷键、方向键、焦点归还和触控；完整页处理URL、焦点及仅POP时的延迟滚动恢复。private recent受runtime capability控制。
- 缺图URL不能触发GET下载或同步重建。当前结果页对旧候选做有界元数据校验，规则见[V6中的搜索封面边界](ai-agent-runtime-v6.md#7-billboard-工具与搜索封面边界)。

## 发布和维护

串流导入同步维护候选索引，精确统计快照由后台队列继续构建。有效署名变化走可证明的有界增量；条件不足时由私有维护回退完整构建，GET仍只读。重建期间保留符合合同的上一可用版本，完成后原子切换；失败不发布假ready。

生产首次四变体冷建只在明确数据库副本执行。正常发布精确复用ready成品，源revision、身份或过滤漂移时拒绝替换。详情summary、overview、project在同一exact-ready上下文读取目标事实；年榜及其他附属投影只由维护期发布，详见[公开读取合同](public-snapshot-read-contract.md)。

## 实现和证据

- [API路由](../../backend/api/music.py)、[候选索引](../../backend/domains/music_search/index.py)、[快照与发布](../../backend/domains/music_search/snapshot.py)、[变体](../../backend/domains/music_search/variants.py)。
- [前端候选和context hooks](../../frontend/src/features/music/search/useMusicSearch.ts)、[输入控制](../../frontend/src/features/music/search/searchInputController.ts)。
- [候选与统计分离交付](../reports/2026-08-16-music-search-baseline-and-delivery.md#音乐查找性能与体验优化交付报告)、[零停机与署名增量](../reports/2026-08-28-music-search-zero-downtime-and-credit-delta.md)、[真实delta可达性](../reports/2026-09-20-search-build-and-delta-delivery.md#阶段-5csearch-真实-delta-可达性与-identity-revision-精度)。
