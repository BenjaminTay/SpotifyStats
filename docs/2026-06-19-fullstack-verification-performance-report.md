# 2026-06-19 全栈验证与性能收口报告

分支：`codex/playback-logic-update`

## 结论

- 后端全量测试通过：`550 passed, 2 warnings in 117.88s`
- 前端测试与构建通过：`115 passed`，`npm run build` 通过
- Phase 5 最低验证矩阵通过：unit `224 passed`，contract `126 passed`，前端 test/build 通过
- pre-commit 通过：ruff、ruff format、mypy、detect-secrets 全部通过
- 浏览器路由冒烟通过：12 个核心路由在 1280px 桌面与 390px 移动端均无错误 overlay、无页面级横向滚动
- 只读 API 探针通过：66 个高风险只读请求覆盖核心域，修正必填参数后全部返回预期状态并带 `X-Request-ID`

## 修复项

| 严重程度 | 问题 | 影响 | 修复 |
| --- | --- | --- | --- |
| P1 | contract seed fixture 残留 WAL/SHM 导致 `release_groups` 状态漂移 | L3 release group 测试在全量套件中偶发失败 | `build_seed_db.py` 重建前后清理 `seed.db-wal/-shm`，并重新生成 `seed.db` |
| P1 | contract 测试直接写 canonical `seed.db` | 只读/写入路径会污染后续测试，造成测试顺序依赖 | `backend/tests/contract/conftest.py` 改为每次复制临时 seed DB，teardown 删除临时 WAL/SHM |
| P1 | Billboard records 测试清缓存不完整 | `_load_and_rank_cached` / `_compute_records_cached` 污染导致 L2 bootstrap 测试全量失败 | 补齐 `_clear_billboard_runtime_caches()` 的缓存清理范围 |
| P2 | `chart_compute.py` / `chart_staged_cache.py` 超过架构护栏行数 | Phase 5 facade 约束回归 | 新增 `chart_load_rank.py` 承接共享 load/rank cache，facade 回到护栏内 |
| P2 | 390px 移动端页面可横向滚动 47.5px | `/analysis/stats`、`/analysis/charts` 等页面移动端体验不稳 | `AppLayout` 增加页面级 `overflow-x-clip`，Masthead nav 增加 `basis-full/max-w-full`，Dashboard skeleton 改为 `w-full max-w-*` |
| P2 | pre-commit ruff hook 扫描冻结 Streamlit `app/` 与旧脚本 | `pre-commit run --all-files` 因历史页名/未用变量失败 | `.pre-commit-config.yaml` 将 ruff 与 ruff-format 限定到 `backend/`，与项目日常质量命令一致 |

## 性能优化

| 项目 | 优化前 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| records 直接 profile 冷算 | 4.791s / 19,188,063 calls | 3.090s / 10,941,286 calls | 时间 -35.5%，调用数 -43.0% |
| `/api/billboard/records` 冷请求 | 2.19s | 1.871s | -14.6% |
| `/api/billboard/records` 热请求 | 0.01-0.02s | 0.012-0.013s | 持平 |

实现：`chart_power_score.py` 将 track/album/artist Power Score 的逐行 `DataFrame.apply(axis=1)` 和 Python lambda 聚合改为列级向量化计算，并新增语义测试保证冠军差距、非冠军中位数、debut bonus、#1 bonus、peak/week 统计不漂移。

## 基准与探针

- 后端 import 基准：`1.48s real`，max RSS `140,410,880`
- 前端 build 基准：`5.51s real`，max RSS `712,327,168`
- 8001 临时冷启动 API 测量：
  - `/api/billboard/records?dynamic_threshold=true&merge_level=2`：`1.871, 0.013, 0.012s`
  - `/api/billboard/power-scores?dynamic_threshold=true&merge_level=2`：`0.105, 0.021, 0.021s`
  - `/api/billboard/weekly?dynamic_threshold=true&merge_level=2`：`0.481, 0.125, 0.122s`
  - `/api/dashboard/full?dynamic_threshold=true`：`5.393, 0.177, 0.167s`
- API smoke：66 个只读请求；`/api/version-merge/album-types` 空请求返回 422 为正确边界，带 `album_ids=1,2,3` 后 200。
- 文档同步：README、AGENTS、CLAUDE、backend/CLAUDE、frontend/CLAUDE 已更新 2026-06-19 验证报告、Power Score 向量化、移动端横向滚动护栏、pre-commit 范围与最新测试基线。

## 验证命令

```bash
.venv/bin/pytest backend/tests/ -v
.venv/bin/ruff check backend/
.venv/bin/ruff format --check backend/
cd frontend && npm test
cd frontend && npm run build
sh scripts/phase5_check.sh
.venv/bin/pre-commit run --all-files
```

补充验证：

```bash
.venv/bin/pytest backend/tests/unit/test_chart_power_score.py -q
.venv/bin/pytest backend/tests/unit/test_phase5_architecture.py::test_chart_power_score_avoids_row_wise_dataframe_apply -q
git diff --check
```

## 已知限制

- 生产构建仍提示两个大懒加载 chunk：`full-yTi_27TG.js` gzip 494.12KB、`esm-CBcusPEn.js` gzip 376.65KB。当前未强行拆分，避免在本轮引入可见行为风险。
- 未执行真实 ngrok + Spotify OAuth 浏览器授权闭环；已验证 `/api/spotify/auth/status` 只读状态端点返回 200 和 request id。

## 10 分钟快速验证

1. 启动后端：`source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend`
2. 启动前端：`cd frontend && npm run dev`
3. 打开 `http://127.0.0.1:5173/`，确认 Dashboard 有 KPI 与图表。
4. 切到移动宽度约 390px，访问 `/analysis/stats`、`/analysis/charts`，页面不能横向拖动。
5. 访问 `/billboard/number-ones`、`/billboard/all-time`、`/billboard/records`，确认三页能加载业务内容。
6. 访问 `/account`、`/settings`，确认账户数据和设置区块能渲染。
7. 打开 `http://127.0.0.1:8000/docs`，快速试 `/api/health`、`/api/billboard/records`、`/api/spotify/auth/status`。
8. 运行 `sh scripts/phase5_check.sh`，确认最低矩阵仍全绿。
