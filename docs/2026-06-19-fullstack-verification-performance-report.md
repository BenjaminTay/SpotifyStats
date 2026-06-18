# 2026-06-19 全栈验证与性能收口报告

分支：`codex/playback-logic-update`

## 结论

- 后端全量测试通过：`552 passed, 2 warnings in 109.70s`
- 前端测试与构建通过：`125 passed`，`npm run build` 通过
- Phase 5 最低验证矩阵通过：unit `226 passed`，contract `126 passed`，前端 test/build 通过
- pre-commit 通过：ruff、ruff format、mypy、detect-secrets 全部通过
- 浏览器路由冒烟通过：12 个核心路由在 1280px 桌面与 390px 移动端均无错误 overlay、无页面级横向滚动；补充 Playwright CLI 采样 24 个路由/视口组合，控制台 error 为 0
- 只读 API 探针通过：66 个高风险只读请求覆盖核心域，修正必填参数后全部返回预期状态并带 `X-Request-ID`

## 修复项

| 严重程度 | 问题 | 影响 | 修复 |
| --- | --- | --- | --- |
| P1 | contract seed fixture 残留 WAL/SHM 导致 `release_groups` 状态漂移 | L3 release group 测试在全量套件中偶发失败 | `build_seed_db.py` 重建前后清理 `seed.db-wal/-shm`，并重新生成 `seed.db` |
| P1 | contract 测试直接写 canonical `seed.db` | 只读/写入路径会污染后续测试，造成测试顺序依赖 | `backend/tests/contract/conftest.py` 改为每次复制临时 seed DB，teardown 删除临时 WAL/SHM |
| P1 | Billboard records 测试清缓存不完整 | `_load_and_rank_cached` / `_compute_records_cached` 污染导致 L2 bootstrap 测试全量失败 | 补齐 `_clear_billboard_runtime_caches()` 的缓存清理范围 |
| P2 | `chart_compute.py` / `chart_staged_cache.py` 超过架构护栏行数 | Phase 5 facade 约束回归 | 新增 `chart_load_rank.py` 承接共享 load/rank cache，facade 回到护栏内 |
| P2 | `import_data()` 遇到缺音频元数据的播放/视频记录可能引用未初始化 `album_id` | Extended Streaming History 中播客、视频或缺元数据条目会中断完整导入流程 | 每条记录先将 `album_id` 初始化为 `None`，新增临时 SQLite 导入测试覆盖音频、视频、featured artist、空 `source_album_id` 与预聚合表 |
| P2 | 390px 移动端页面可横向滚动 47.5px | `/analysis/stats`、`/analysis/charts` 等页面移动端体验不稳 | `AppLayout` 增加页面级 `overflow-x-clip`，Masthead nav 增加 `basis-full/max-w-full`，Dashboard skeleton 改为 `w-full max-w-*` |
| P2 | pre-commit ruff hook 扫描冻结 Streamlit `app/` 与旧脚本 | `pre-commit run --all-files` 因历史页名/未用变量失败 | `.pre-commit-config.yaml` 将 ruff 与 ruff-format 限定到 `backend/`，与项目日常质量命令一致 |

## 性能优化

| 项目 | 优化前 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| records 直接 profile 冷算 | 4.791s / 19,188,063 calls | 3.090s / 10,941,286 calls | 时间 -35.5%，调用数 -43.0% |
| `/api/billboard/records` 冷请求 | 2.19s | 1.871s | -14.6% |
| `/api/billboard/records` 热请求 | 0.01-0.02s | 0.012-0.013s | 持平 |
| OpenCC 默认懒加载包 | `full-yTi_27TG.js` 1,121.76KB / gzip 494.12KB | 简体路径 `t2cn-g7W6-1pz.js` 64.27KB / gzip 38.78KB；繁体路径 `cn2t-DJnOUolw.js` 1,059.13KB / gzip 457.19KB | 默认完整包消除；简体路径 gzip -455.34KB，繁体路径 gzip -36.93KB |
| ECharts 图表懒加载包 | `esm-CBcusPEn.js` 1,134.42KB / gzip 376.65KB | `EChartsTheme-*.js` 673.19KB / gzip 225.67KB | 原始体积 -461.23KB，gzip -150.98KB |
| `/account` 前端资源加载 | 桌面 250 requests / 24,632.6KB / TBT 132ms / LCP 2,480ms；移动 250 requests / 25,488.7KB / TBT 132ms / LCP 2,412ms | 桌面 92 requests / 7,565.5KB / TBT 0ms / LCP 2,132ms；移动 91 requests / 7,455.4KB / TBT 0ms / LCP 2,320ms | requests -63%，资源体积 -69%~-71%，TBT -132ms，LCP 小幅改善 |

实现：`chart_power_score.py` 将 track/album/artist Power Score 的逐行 `DataFrame.apply(axis=1)` 和 Python lambda 聚合改为列级向量化计算，并新增语义测试保证冠军差距、非冠军中位数、debut bonus、#1 bonus、peak/week 统计不漂移。

前端补充实现：`displayName()` 将 OpenCC 默认 `full` 包拆为 `opencc-js/t2cn` 与 `opencc-js/cn2t` 两条按需路径；ECharts 统一通过 `LazyEChart` 动态加载 `echarts-for-react/esm/core` 并只注册当前用到的 bar/line/pie/heatmap、tooltip、legend、dataZoom、visualMap 与 mark 组件，避免 `echarts-for-react` 默认入口静态拉入完整 ECharts runtime。

账号页补充实现：`ChemistryBlock` 将每类滚动预览限制到 8 条，保留全量分类计数；账号页深层封面图统一加 `loading="lazy"` 与 `decoding="async"`，避免收藏化学反应的数百张示例封面抢占首屏资源。

## 基准与探针

- 后端 import 基准：`1.48s real`，max RSS `140,410,880`
- 前端 build 基准：`4.97s real`，max RSS `667,516,928`
- 8001 临时冷启动 API 测量：
  - `/api/billboard/records?dynamic_threshold=true&merge_level=2`：`1.871, 0.013, 0.012s`
  - `/api/billboard/power-scores?dynamic_threshold=true&merge_level=2`：`0.105, 0.021, 0.021s`
  - `/api/billboard/weekly?dynamic_threshold=true&merge_level=2`：`0.481, 0.125, 0.122s`
  - `/api/dashboard/full?dynamic_threshold=true`：`5.393, 0.177, 0.167s`
- API smoke：66 个只读请求；`/api/version-merge/album-types` 空请求返回 422 为正确边界，带 `album_ids=1,2,3` 后 200。
- 导入/WAL probe：临时 JSON + 临时 SQLite 验证音频/视频缺元数据记录不会中断导入，featured artist 写入 `track_artists`，空来源写入 `source_album_id IS NULL`；临时 DB 验证 WAL 下读事务快照不阻塞独立写提交，新读连接可见提交后数据。
- 前端交互 probe：Playwright CLI 覆盖 12 路由 × 2 视口；`/analysis/stats` 与 `/analysis/charts` 的 `role=tab` 切换后无错误；Billboard 路由执行 `/billboard` → `/number-ones` → `/all-time` → `/records` 并通过浏览器后退/前进验证路由状态，控制台 error 为 0。
- Web Vitals lab probe（Vite dev server + headless Chrome + CDP）：6 路由 × 桌面/390px 移动端；最终采样 CLS 全部 0，合成点击 FID 0.7-3.6ms，TBT 全部 0ms，非账号页 LCP 416-896ms，账号页 LCP 2,132ms（桌面）/ 2,320ms（移动）。
- 文档同步：README、AGENTS、CLAUDE、backend/CLAUDE、frontend/CLAUDE 已更新 2026-06-19 验证报告、Power Score 向量化、移动端横向滚动护栏、pre-commit 范围与最新测试基线。

### Web Vitals Lab 采样

> 命令：`node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000`
> 说明：该数据来自本地 Vite dev server，不等同生产 Lighthouse/RUM；FID 为合成点击 first-input，TBT approx 为 FCP 后 5 秒内 long task 近似值。

| Route | Viewport | LCP | CLS | FID | TBT approx | Resources | Encoded resources | Scroll width |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/` | desktop | 896ms | 0 | 1.9ms | 0ms | 77 | 7,185.7KB | 1280 / 1280 |
| `/` | mobile | 616ms | 0 | 2.3ms | 0ms | 76 | 7,176.4KB | 390 / 390 |
| `/analysis/stats` | desktop | 416ms | 0 | 0.7ms | 0ms | 106 | 8,265.2KB | 1280 / 1280 |
| `/analysis/stats` | mobile | 420ms | 0 | 2.6ms | 0ms | 106 | 8,265.2KB | 390 / 390 |
| `/analysis/charts` | desktop | 416ms | 0 | 1.3ms | 0ms | 99 | 6,960.8KB | 1280 / 1280 |
| `/analysis/charts` | mobile | 428ms | 0 | 3.5ms | 0ms | 97 | 6,785.9KB | 390 / 390 |
| `/billboard/number-ones` | desktop | 704ms | 0 | 2.7ms | 0ms | 104 | 9,808.3KB | 1280 / 1280 |
| `/billboard/number-ones` | mobile | 668ms | 0 | 3.0ms | 0ms | 99 | 9,399.9KB | 390 / 390 |
| `/account` | desktop | 2,132ms | 0 | 3.6ms | 0ms | 92 | 7,565.5KB | 1280 / 1280 |
| `/account` | mobile | 2,320ms | 0 | 0.8ms | 0ms | 91 | 7,455.4KB | 390 / 390 |
| `/settings` | desktop | 484ms | 0 | 2.5ms | 0ms | 85 | 5,159.4KB | 1280 / 1280 |
| `/settings` | mobile | 480ms | 0 | 2.8ms | 0ms | 85 | 5,159.4KB | 390 / 390 |

## 覆盖矩阵

| 目标项 | 当前证据 | 状态 |
| --- | --- | --- |
| 后端现有测试全量通过 | `pytest backend/tests/ -v`：`552 passed, 2 warnings in 109.70s` | 已自动验证 |
| OpenAPI/核心 API 只读覆盖 | 122 paths / 134 operations schema 存在；66 个高风险只读请求覆盖 Dashboard、Billboard、Analysis、Community、AI Insights、Account、Settings、Spotify status | 已覆盖只读核心路径；mutation/破坏性端点未逐一实打 |
| Extended Streaming History 完整导入 | 新增临时 JSON 导入测试覆盖音频、视频、缺元数据、featured artist、预聚合 | 已自动验证最小完整流程 |
| 多版本与 Billboard 语义 | contract/full tests 覆盖 Version Merge、Album Project、Power Score、播放过滤参数传播与 Billboard invariants | 已自动验证 |
| SQLite WAL 并发读写 | 新增临时 DB WAL reader snapshot + writer commit 测试 | 已自动验证 |
| OAuth/加密/缓存/Job Queue/Request ID | AES、cache manager、job queue 单测；API smoke 验证 `X-Request-ID`；Spotify status 只读 200 | 自动验证基础设施；真实 OAuth 外部授权未闭环 |
| 前端路由与响应式 | Playwright CLI 12 路由 × 桌面/390px 移动端，无错误文案、无横向溢出、控制台 error 为 0；图表入口由架构护栏防止回退到完整 ECharts/OpenCC 默认包；Web Vitals lab 覆盖 6 路由 × 2 视口 | 已自动验证主路径 |
| 前端交互 | 分析页 Tab、Billboard 前进/后退路由、长列表可见分页按钮采样 | 部分自动验证；所有按钮/表单/ECharts 细交互未逐项人工穷尽 |
| 性能优化 | records profile、API 冷/热请求、build/import、bundle chunk、Web Vitals lab 与账号页资源/TBT 均有前后对比 | 已量化关键瓶颈；仍缺真实 RUM 与生产静态托管 Lighthouse |

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
.venv/bin/pytest backend/tests/unit/test_import_data_flow.py -q
.venv/bin/pytest backend/tests/unit/test_phase5_architecture.py::test_chart_power_score_avoids_row_wise_dataframe_apply -q
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "Chinese conversion"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "lightweight ECharts"
cd frontend && npm test -- src/tests/phase5-architecture.test.ts -t "account chemistry"
cd frontend && ANALYZE=true npm run build
node scripts/frontend_web_vitals_probe.mjs --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
git diff --check
```

## 已知限制

- 生产构建仍提示两个大懒加载 chunk：`cn2t-DJnOUolw.js` gzip 457.19KB、`EChartsTheme-*.js` gzip 225.67KB。旧 `full-yTi_27TG.js` 与 `esm-CBcusPEn.js` 已消除；剩余体积分别来自繁体词典和当前图表能力集合，未牺牲简繁转换语义或图表功能继续强拆。
- 未执行真实 ngrok + Spotify OAuth 浏览器授权闭环；已验证 `/api/spotify/auth/status` 只读状态端点返回 200 和 request id。
- 未在 Firefox/Safari 真机浏览器中执行同等交互；当前浏览器自动化证据来自本地 Chromium/Playwright CLI 与前端测试。
- 未逐一实打所有 mutation/破坏性端点，例如断开 Spotify、清空缓存、导入生产数据、同步远程账号数据等，避免污染本地真实状态。
- Web Vitals 已用 headless Chrome lab probe 采集 LCP/CLS/合成 FID/TBT；仍未采集真实用户 RUM、Firefox/Safari Web Vitals，也未在生产静态托管环境跑 Lighthouse。

## 10 分钟快速验证

1. 启动后端：`source .venv/bin/activate && uvicorn backend.main:app --reload --reload-dir backend`
2. 启动前端：`cd frontend && npm run dev`
3. 打开 `http://127.0.0.1:5173/`，确认 Dashboard 有 KPI 与图表。
4. 切到移动宽度约 390px，访问 `/analysis/stats`、`/analysis/charts`，页面不能横向拖动。
5. 访问 `/billboard/number-ones`、`/billboard/all-time`、`/billboard/records`，确认三页能加载业务内容。
6. 访问 `/account`、`/settings`，确认账户数据和设置区块能渲染。
7. 打开 `http://127.0.0.1:8000/docs`，快速试 `/api/health`、`/api/billboard/records`、`/api/spotify/auth/status`。
8. 运行 `sh scripts/phase5_check.sh`，确认最低矩阵仍全绿。
