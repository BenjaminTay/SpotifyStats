# Billboard Records 一致性与排行稳定性修复交付

> 日期：2026-08-29
> 状态：PASS（本修复范围）；默认完整全栈门禁未运行，由既有耗时开放项继续跟踪
> 实施基线：detached HEAD `c21ad22841dcc98b3ce7fa20c9306d4830a1da15`
> 本地提交：`0b23c4425c1635d4f3dc36f5ccd29e0758d1749f`
> 仓库状态：原一致性修复已在本地 `main` 提交为 `0b23c442`；2026-08-30 全板块排序补充已提交为 `46fc7afa93210a74d29eec05a37d1c8f39c01269`，尚未 push
> 部署状态：未将 `0b23c442` 或 `46fc7afa` 部署到生产；验收期间未用修复代码替换主 checkout 正在运行的服务
> 关联规划：[`../plans/2026-08-29-billboard-records-consistency-and-ranking-hardening-plan.md`](../plans/2026-08-29-billboard-records-consistency-and-ranking-hardening-plan.md)

## 1. 最终结论

- 历史 28/34 类问题在当前 canonical track、L2/L3、有效署名和完整周规则下没有复现；Taylor Swift 的 Records、艺人统计摘要、艺人详情与周榜有效署名集合在四个统计变体中均为 34，稳定 `track_id` 差集为空。
- 本轮发现的五个独立加固项 B1–B4、R1 已全部实现。它们分别属于聚合 proof、完整/staged Records 展示输入、前端参数传播、可见列表稳定排序，以及普通播放排行 tie-breaker；R1 不属于 Billboard 周榜根因。
- 主 SQLite 只刷新了 Billboard 派生聚合和 `agg_config` proof。92,908 条原始播放、总播放毫秒和 play ID 边界均未变化，数据库快速检查为 `ok`。

## 2. 代码交付

### 2.1 聚合 proof 与安全发布

- [`backend/core/db.py`](../../backend/core/db.py) 新增共享 `build_aggregation_semantic_proof()`、`aggregation_partial_base_is_compatible()` 和 `refresh_aggregation_semantic_proof()`；全量及分区构建统一使用当前 artist identity、track credit、track identity、generation/dataset digest 和非可变依赖证明。
- [`backend/services/track_credit_rebuild_service.py`](../../backend/services/track_credit_rebuild_service.py) 与 [`backend/services/artist_identity_rebuild_service.py`](../../backend/services/artist_identity_rebuild_service.py) 在 role-only 或局部发布前校验可复用基底；依赖不兼容时转为安全全量重建，不再手工拼接不完整 hash 冒充 ready。
- [`backend/domains/music_search/track_credit_delta.py`](../../backend/domains/music_search/track_credit_delta.py) 复用完整 proof 刷新；[`backend/domains/music_search/snapshot.py`](../../backend/domains/music_search/snapshot.py) 的聚合命中判断包含 `track_identity_revision`。

### 2.2 Records 一致性与参数传播

- 新增 [`backend/domains/billboard/chart_record_inputs.py`](../../backend/domains/billboard/chart_record_inputs.py)，完整 [`chart_compute.py`](../../backend/domains/billboard/chart_compute.py) 和 staged [`chart_staged_cache.py`](../../backend/domains/billboard/chart_staged_cache.py) 在计算 Power Score/Records 前共用同一 track/artist 展示 enrichment。
- [`frontend/src/pages/RecordsPage.tsx`](../../frontend/src/pages/RecordsPage.tsx) 使用 `useAnalysisFilters()` 与 `buildBillboardContextParams()`；URL merge level 只覆盖完整过滤对象中的对应字段。
- [`frontend/src/hooks/useBillboard.ts`](../../frontend/src/hooks/useBillboard.ts) 的请求、预取和 TanStack Query key 接收同一完整 params，并支持 settings-loading `enabled` 门禁。

### 2.3 稳定排序

- [`backend/services/analysis_stats_service.py`](../../backend/services/analysis_stats_service.py)：`metric=plays` 使用 `plays DESC → hours DESC → stable entity key → normalized name`；`metric=hours` 使用 `hours DESC → plays DESC` 后追加同一稳定键。
- [`backend/domains/billboard/records_championship.py`](../../backend/domains/billboard/records_championship.py)：冠军艺人及同周多曲记录在 cutoff 前完成稳定排序。
- [`backend/domains/billboard/details.py`](../../backend/domains/billboard/details.py)：艺人和专辑曲目保留 `peak ASC → weeks DESC`，再追加 `track_id/name`。

## 3. 数据与 API 证据

### 3.1 备份与主库

主库：`/Users/benjaminlei/Code/202605-SpotifyStats/data/spotify_stats.db`，schema migration 63。

变更前 Online Backup：

```text
/Users/benjaminlei/Code/202605-SpotifyStats/data/backups/
spotify_stats_20260829T031500Z_before-billboard-hardening.db
SHA256 94c59d0fc2e94b8463d4b92eb5a44f25ccdc4988444952c61900e0793ecfd1f9
PRAGMA quick_check = ok
plays = 92,908
```

副本完整重建后四张派生表分别为：

```text
agg_weekly_tracks        37,800
agg_weekly_track_sources 51,931
agg_weekly_albums        17,210
agg_weekly_artists       10,253
```

副本验收通过后，主库使用当前设置 `min_ms=30000`、仅音乐、合并连续播放、5 分钟 gap、周五 12:00、dynamic threshold=true 完成同一全量派生重建：

```text
param_hash              222fbd0a3bcca38b
builder_version         billboard_aggregation_v3_l1
identity_revision       18
track_credit_revision   35
track_identity_revision 5
build_strategy          full
PRAGMA quick_check      ok
```

主库重建前后原始事实指纹均为：

```text
plays count       92,908
SUM(ms_played)    15,347,703,793
MIN(play_id)      2,205,903
MAX(play_id)      2,298,810
```

### 3.2 四变体对账

工作树后端连接 Online Backup 的可写副本，固定完整 query 参数，对 L2/L3 × dynamic true/false 逐一请求：

| merge level | dynamic | `/data.records == /records.records` | Records | summary top1 | detail top1 | 详情冠军 ID | 差集 | 301 行指标差异 |
|---:|:---:|:---:|---:|---:|---:|---:|---:|---:|
| 2 | true | 是 | 34 | 34 | 34 | 34 | 0 | 0 |
| 2 | false | 是 | 34 | 34 | 34 | 34 | 0 | 0 |
| 3 | true | 是 | 34 | 34 | 34 | 34 | 0 | 0 |
| 3 | false | 是 | 34 | 34 | 34 | 34 | 0 | 0 |

已发布的最后完整周为 `2026-08-14`；覆盖边缘开放周 `2026-08-21` 仍未发布。

主库派生重建后另以工作树源码直接读取当前主库完成 L2/dynamic=true 探针：`records_equal=true`、`artist_track_counts.top1=34`、Records `冠单数=34`、详情 `info.top1=34`、详情冠军稳定 ID 共 34 个。

### 3.3 播放排行

真实 `/api/analysis/charts?entity=track&metric=plays` 返回中，同为 180 次的样本现在为：

```text
drivers license  180 plays  11.9h
Midnight Rain    180 plays   8.6h
```

这证明普通播放排行按未取整的 `hours DESC` 作为第二键；Billboard 周榜原有 `play_count DESC → total_ms DESC → stable key` 未修改。

## 4. 测试与浏览器验收

### 4.1 自动化

```text
后端 unit       1,421 passed, 2 skipped
后端 contract     396 passed
前端 test          76 files, 598 tests passed
前端 build          passed
目标后端测试         20 passed
Records contract    15 passed
目标前端测试         85 passed
```

contract 完整轮退出码为 0；pytest 临时数据库清理后出现一次既有后台 AI 任务线程日志（临时表已拆除），不影响 396 项测试结果，但不将其误报为业务失败。

### 4.2 真实浏览器

- Desktop Records：冠军圣殿 Taylor Swift 显示 34 首、56 冠周。
- 390px Records：移动卡片仍显示 34 首；`clientWidth=390`、`scrollWidth=390`。
- Desktop/390px 艺人详情：单曲成绩显示入榜曲目 301、`#1 曲目 34`、冠军周数 56；390px 无横向溢出。
- Desktop/390px 播放排行：180 次样本以 11.9h 在 8.6h 前；移动端使用独立卡片 presentation。

## 5. 剩余边界与回滚

- 收尾时主 checkout 服务仍在线：后端 `/docs` 与 `/api/settings` 为 HTTP 200，前端 `http://localhost:5173/` 为 HTTP 200；localhost 探针需绕过当前 shell 的外网代理。
- 未运行默认完整 `fullstack_verification_check.sh`。该门禁已有独立 `SS-2026-08-24-004` 耗时开放项；本轮已完成后端全量 unit/contract、前端全量测试/build、真实数据库副本、主库 proof 和真实浏览器验收，因此本修复范围判定 PASS，整站默认门禁状态不据此改变。
- 修复已在本地 `main` 提交为 `0b23c442`，尚未 push，也未部署到生产。验收期间未用修复代码替换主 checkout 正在运行的服务；主库派生事实已刷新，后续部署代码时仍需按常规流程重启后端以清空旧进程内缓存。
- 如需数据回滚，可在停止写入后使用上述 Online Backup 恢复；排序与参数传播只需回退对应代码，不需要恢复原始事实表。

## 6. 2026-08-30 Records 全板块排序补充

### 6.1 修复范围

- 新增统一的 `stable_record_sort()`，覆盖 6 个 Records 子页面、8 个后端记录模块，共 51 个列表；业务排序完成后才应用列表上限，最终用稳定实体键裁决同值行。
- 冠军名人堂拆分单曲和专辑候选集。单曲排序为“冠军单曲数 DESC → 单曲冠军周数 DESC”，专辑排序为“冠军专辑数 DESC → 专辑冠军周数 DESC”；专辑候选集过滤 `冠军专辑数 > 0`，不再让无冠军专辑的艺人以 0 张进入该榜。
- 其他 Records 列表分别补齐周数、日期、Peak、走势评分、播放差额、实体数量等业务二级/后续指标；前端冠军圣殿、名人堂、奇趣纪录的本地排序切换与后端保持同一 fallback。双空冠 payload 统一为 `debut_artist`，不再泄漏 merge 后的 `_x/_y` 字段。

完整排序表和缺失值/稳定键边界见当前规则的 [`R39.1`](../reference/playback-stats-rules.md)。本补充不改变 Billboard 周榜既有的 `play_count DESC → total_ms DESC → 稳定实体键` 规则，也不改变冠军事实、实体集合或原始播放数据。

### 6.2 真实 API 全板块巡检

在固定 `min_ms=30000`、仅音乐、连续播放合并、5 分钟 gap、L2/L3、dynamic true/false、周五 12:00 周边界、`30/20/20` Top N、无年度范围且不含精选集的参数和同一 revision 下：

| 接口 | Records 列表数 | 排序违规 | `/data.records` 与 `/records.records` |
|---|---:|---:|---|
| `/api/billboard/records` | 51 | 0 | 与兼容接口相等 |
| `/api/billboard/data` | 51 | 0 | 与主接口相等 |

冠军专辑名人堂真实结果前五为 Taylor Swift `12/96`、Michael Wong `7/25`、Olivia Rodrigo `3/21`、Ariana Grande `3/8`、Kacey Musgraves `3/6`（冠军专辑数/专辑冠军周数）；不存在以 0 张冠军专辑进入该列表的尾部行。双空冠返回字段为 `debut_album`、`debut_artist`、`debut_track`、`debut_track_id`、`debut_week`。

### 6.3 补充验证

- 后端 unit：`1,425 passed`；Billboard 相关 contract：`58 passed`。
- 前端：`76 files / 598 tests passed`，生产构建通过。
- 真实浏览器：Desktop 六个 Records 页签无错误；390px 下六个页签均无错误/空态，冠军专辑卡片显示 `12 张冠军专辑` 与 `冠周 96`，页面宽度无横向溢出。
- 默认完整 `fullstack_verification_check.sh` 仍未在本次 HEAD 运行，继续作为 `SS-2026-08-24-004` 的独立 `PARTIAL` 尾项；本报告结论仅覆盖本修复范围。
