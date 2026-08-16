# 音乐查找 M0 基线与契约冻结报告

日期：2026-08-16
阶段：M0 — 契约冻结与基准固化
结论：**Pass；M5 已补齐生产镜像检查**

## 1. 阶段结论

M0 已固定当前搜索性能基线、分段计时、候选/上下文响应合同、稳定实体键、查询标准化规则、
三类详情一致性 golden cases 和公开只读边界。

当前本机 Python SQLite runtime 已验证支持 FTS5 与 trigram；由于执行时 Docker daemon 未运行，
`python:3.9-slim` 生产容器中的精确 SQLite runtime 尚未实机确认。后续索引实现必须保留 doctor 与
有界 fallback，M5 生产镜像门禁必须重新验证容器内 FTS5/trigram，未通过时不得把 degraded 状态
描述为完整性能交付。

> M5 收口更新：Docker Desktop 启动后已实测 `python:3.9-slim` 为 SQLite 3.46.1，FTS5 与
> trigram tokenizer 均可用；包含本次代码的 backend target doctor 返回 `ready / fts5_trigram`。
> 完整证据见 `docs/reports/2026-08-16-music-search-optimization-delivery.md`。

## 2. 只读性能探针

新增：

- `scripts/music_search_performance_probe.py`
- `backend/tests/unit/test_music_search_performance_probe_script.py`

探针通过 SQLite URI `mode=ro` 打开数据库，并显式设置 `PRAGMA query_only=ON`。它支持
candidate、context 和 legacy end-to-end 三种模式、fresh-process cold 与 same-process warm、JSON/
人类可读输出、P50/P95 和预算退出码。报告只保留查询编号、长度、聚合结果数和耗时，不输出搜索词
原文、实体名称、链接或播放历史行。

固定命令示例：

```bash
.venv/bin/python scripts/music_search_performance_probe.py \
  --mode candidate --warm-repeat 1 \
  --json-output /tmp/music-search-candidate-probe.json

.venv/bin/python scripts/music_search_performance_probe.py \
  --mode candidate --query love --cold \
  --json-output /tmp/music-search-candidate-cold-probe.json

.venv/bin/python scripts/music_search_performance_probe.py \
  --mode end-to-end --query love --cold \
  --json-output /tmp/music-search-end-to-end-probe.json
```

## 3. 测量环境与数据量

| 项目 | 实测值 |
|---|---:|
| 系统 | Darwin 25.6.0 arm64 |
| Python | 3.9.6 |
| 逻辑 CPU | 10 |
| SQLite | 3.51.0 |
| FTS5 runtime | 可用 |
| FTS5 trigram runtime | 可用 |
| 数据库大小 | 80.613 MiB |
| plays | 91,286 |
| tracks | 12,362 |
| albums | 5,316 |
| artists | 1,189 |

Cold 表示每个样本使用新的 Python 进程，但不清除操作系统 page cache；Warm 表示同一进程、同一连接
预热一次后测量。candidate warm 使用 3 个固定非敏感查询，各测 1 次；其余基线为单个固定查询。

## 4. 当前基线

| 路径 | 条件 | P50/单次 | P95 | 主要分段 |
|---|---|---:|---:|---|
| Candidate（不加载过滤 lifetime frame，不算 Billboard） | warm | 214.479ms | 215.693ms | resolver 查询与组装 |
| Candidate | fresh process | 214.150ms | 214.150ms | resolver 查询与组装 |
| Legacy end-to-end | warm | 6,466.721ms | 6,466.721ms | filtered frames 3,982.439ms；chart 609.706ms |
| Legacy end-to-end | fresh process | 13,951.602ms | 13,951.602ms | filtered frames 6,342.706ms；chart 5,667.940ms |
| Context snapshot | 当前 runtime | unavailable | unavailable | M3 前不伪造测量 |

这组证据确认：当前 6–14 秒阻塞主要来自查询时重建过滤播放 frame 与完整 Billboard；即使只使用
旧 resolver，候选本身约 214–216ms，已足以证明“候选先出、上下文后补”能显著改善首屏，但仍未
达到最终候选 API 热 P95 150ms 预算。M2 必须通过专用派生索引继续降低候选查询成本。

## 5. 冻结的合同

- 稳定实体键只接受 `track:<id>`、`album:<id>`、`album_project:<id>`、`artist:<id>`；ID 必须为
  正整数且无前导零。
- 候选响应版本为 `music_search_v2`，含 normalized query、snapshot status、filter fingerprint、
  page、page size、准确 totals 与三类候选。
- 上下文响应版本为 `music_search_context_v1`，只按 entity key 返回精确快照统计。
- Candidate 与 Context 必须分型；上下文未加载不能被序列化或展示为 0 次播放。
- 普通消费搜索没有精确 ready snapshot 时返回 warming/unavailable，不回退到未证明资格的 raw
  candidate；`any_local` 只供 private Settings 治理消费者。
- 当前 legacy 合同保留，迁移期间不暗改默认 response mode。

## 6. 标准化与短查询策略

后端最终事实源执行 NFKC、常见引号/破折号/中日韩全角标点统一、Unicode casefold、trim 与连续
空白折叠。标准化不修改展示文本。简繁搜索变体通过可注入、可版本化的 expander 提供；默认不猜测
转换。

稳定测试向量覆盖全角字符、`ß`、Unicode 空白、弯引号、连字符、CJK 标点、显式简繁扩展去重，
以及汉字、假名、韩文、Latin、数字和其他脚本的短查询门禁。

## 7. 公开只读安全评审

- 既有 `/api/music/search` 是显式 public-safe GET，不依赖路径前缀自动开放。
- 合同测试确认 public 请求使用 public-readonly surface 且搜索可读。
- 后续 `/api/music/search/context` 必须单独加入精确白名单。
- public 只允许 `eligibility=current`；不得开放 `any_local`、写后台任务、写快照状态、外部封面补全
  或 imported Spotify 搜索历史。
- public snapshot 不 ready 时只能返回 unavailable，不能触发构建。

## 8. 验证结果

M0 定向测试共 93 项通过：

- 搜索标准化：36 项；
- 性能探针：8 项；
- entity key / response model / Server-Timing；
- legacy service、API、公开只读与三类详情统计一致性。

Ruff check、Ruff format check 和 `git diff --check` 均通过。既有 urllib3/LibreSSL warning 与本次
搜索修改无关。

## 9. M1 入口条件

M1 可以进入实现，但必须遵守以下硬边界：

1. Candidate service 的自动化测试 monkeypatch `load_period_plays()` 与 `compute_billboard_data()`，
   任何调用都失败；
2. legacy response 继续通过；
3. Candidate 与 Context 前端状态分离并消费 AbortSignal，搜索请求 `retry: 0`；
4. 普通消费 UI 在 M3 精确 snapshot 完成前不得以 raw candidate 作为生产默认结果。
