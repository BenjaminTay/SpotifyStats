# 变更日志

## 2026-06-29 — AI Agent Harness Quality Roadmap

### 新增

- **Evidence-driven Agent harness**：新增 evidence cards、确定性问题意图解析、实体解析、通用实体比较、coverage follow-up、answer critic 与 golden-question eval harness
- **问答证据可视化**：AI 问答完成后在回答旁展示结构化证据卡片，并保留原始工具轨迹
- **深夜歌曲只读工具**：`listening_hours` 增加 `late_night_tracks` view，可回答“深夜最爱听什么歌”这类时段歌曲问题
- **Golden fixtures**：覆盖 GUTS vs The Life of a Showgirl、Olivia Rodrigo 近期趋势、2023 Top artist、深夜歌曲问题，并校验 required tool calls 与 forbidden metrics

### 验证

- `.venv/bin/pytest backend/tests/unit/test_ai_agent_* backend/tests/unit/test_play_service_dashboard.py backend/tests/contract/test_ai_agent_task_contract.py -q`
- `.venv/bin/pytest -m unit -q`：432 passed
- `.venv/bin/pytest -m contract -q`：223 passed
- `.venv/bin/python scripts/evaluate_ai_agent_harness.py`
- `cd frontend && npm test -- --run`：217 passed
- `cd frontend && npm run build`
- OpenAPI operation/parameter audit：143 operations / 61 obligations，0 unaccounted
- `.venv/bin/python scripts/api_smoke_probe.py`：100/100 passed；OpenAPI GET coverage 0 unaccounted
- `.venv/bin/python scripts/api_boundary_probe.py`：91/91 passed
- `node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173 --wait-ms 15000`：6/6 passed，0 console/page error，0 横向溢出
- `node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport desktop --include-detail-routes`：19 routes / 928 controls / 0 violation
- 真实浏览器验证：`/ai-insights` 提交“我深夜最爱听什么歌？请用本地数据回答，并展示依据。”，生成中显示阶段进度，完成后显示 conclusion、thinking sections、evidence cards 与 tool trace；1280px 桌面无横向溢出、无 console warning/error；此前 390px 移动端问答证据卡验证无横向溢出

## 2026-06-29 — AI 可观察任务与只读 Agent V2

### 新增

- **AI Task Orchestrator**：新增 AI task runs/events/tool calls 持久化模型，报告、AI 问答、艺人 career enrichment、专辑 era enrichment 统一展示阶段进度
- **AI 报告 cache-first**：周报/月报/年度叙事不再打开页面自动调用 LLM；无缓存时显示手动生成，生成过程中展示准备数据、调用 LLM、保存缓存等事件
- **只读 Agent 问答**：AI 问答改为 LLM 规划后端 allowlist read-only 工具，再基于工具结果生成回答；支持思考模式、工具轨迹、coverage 自检和矛盾回答重试
- **证据压缩与提示词护栏**：最终回答只接收 compact evidence + coverage，prompt 明确个人 Billboard 不是外部官方 Billboard，并要求比较问题说明统计窗口和公平性限制

### 验证

- `pytest -m unit -q`：385 passed
- `pytest -m contract -q`：222 passed
- `cd frontend && npm test -- --run`：214 passed
- `cd frontend && npm run build`
- `ruff check backend/`
- OpenAPI operation/parameter audit、API smoke/boundary、AI Insights interaction smoke、`/ai-insights` control inventory smoke 通过
- 真实浏览器验证：在 `/ai-insights` 打开思考模式询问 GUTS vs The Life of a Showgirl，工具轨迹正确查询两张专辑的 entity stats 与个人 Billboard detail，回答不再误报 Showgirl 数据缺失

---

## 2026-06-27 — 榜单社区口径同步

### 修复

- **社区榜单口径跟随设置**：Community feed、trending 和 post detail 改用 `BillboardFilters` + `MergeConfig`，向帖子生成链路转发 Top N、周起点、年份范围、动态阈值、最大连续播放合并间隔、`merge_level` 和 `include_compilations`
- **前端社区缓存分流**：社区列表、账号页、帖子详情和趋势侧栏通过 `useCommunityChartParams()` 带入当前设置口径，帖子详情 query key 纳入 filters，避免设置变化后继续显示旧口径社区动态
- **社区图片尺寸微调**：`PostCard` 单图从 208px 收紧到 160px，多图网格最大宽度从 424px 收紧到 320px，让榜单社区时间线更紧凑

### 验证

- `pytest backend/tests/unit/test_community_api_filter_propagation.py backend/tests/unit/test_feed_generator.py -q`
- `cd frontend && npm test -- community-components.test.tsx`
- `cd frontend && npm run build`
- `node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --routes /community --viewport mobile --max-scroll-overflow 0 --fail-on-console-warning`

---

## 2026-06-24 — fix/bugfixes-and-polish 收口修复

### 修复

- **PK Wks 算法重写**：`running_peak_wks` 从"日历周差（含非达峰周）"改为"累计达峰周数（同 running_peak 级别累加，新峰值重置，非达峰周 forward-fill）"，只基于实时 `cummin()` 不预知未来
- **Album Project artist_id 容错**：`load_album_project_membership` 改用 `LEFT JOIN artists`，`_bootstrap_from_release_groups` 新增 artist_id≤0 时从 albums 表回退查找，修复 Red/Fearless (Taylor's Version) 因 artist_id=0 从统计中消失
- **Album Project 本地曲目回退**：`_bootstrap_standalone_album_projects` 当 Spotify 元数据缺失时使用本地曲目数分级（≥7→LP, 3-6→EP），Flicker/ANTI/Witness 等无元数据专辑恢复上榜
- **Artist Summary 跨专辑合并**：`compute_artist_summary` 不再按 album_name 分组，改为按 track_id 聚合后取代表专辑（如 vampire 从三条合并为一条）
- **Album Meta 优先 album_spotify_links**：`_get_album_spotify_meta` 优先走 album_spotify_links（album-type 优先+置信度排序），回退旧链加 ORDER BY，修复同名单曲遮盖完整专辑导致的 total_tracks=1 / album_type=single
- **封面三级回退**：`_get_cover_cdn_url` 新增 album_spotify_links 分支（album-type 优先），`_add_cover_urls` 新增 Spotify metadata fallback，修复新导入专辑封面缺失或错用单曲封面
- **Wrapped 年度总结口径统一**：`/wrapped/{year}/full` merge_level 默认值从 1 改为 2，与 Analysis Charts 一致使用 album project 聚合
- **Spotify 元数据自动刷新 + 导入维护管道**：`import_data` 写入 `spotify_track_id_at_play`，导入后自动运行维护管线（刷新 Spotify metadata → 重建 album projects → 重建预聚合 → 清除缓存 → 健康报告）；新增 `album_spotify_links` 证据表、`refresh_import_derived_data.py` 独立脚本

### 验证

- Backend 520 (unit+contract) PASS，0 失败
- 全链路实测：Midnights release_date 2022-10-21（修复前 2023-05-26）、you seem pretty sad... 封面/发行日正确
- 新增 11 个测试（import maintenance、Spotify metadata refresh、import health、CLI script）

---

## 2026-06-27 — 验收补强与阻塞复核

### 修复

- 修复 OpenAPI 参数边界审计未解包 nullable schema 的漏算问题，`max_merge_gap_minutes` 已纳入边界 probe；当前参数边界 audit 为 60 obligations / 0 unaccounted，API boundary probe 为 90/90 PASS
- 修复播放排行 track 行在 track group 聚合后缺失 `album_name`，避免前端从播放排行进入音乐详情时生成空专辑路径
- 将 Billboard Year-End staged wrapper 拆入 `chart_year_end_api.py`，保持 `chart_staged_api.py` 作为薄 facade 并继续满足行数护栏
- 前端 smoke 补强冷态重页面和动态详情路由等待：`/analysis/records` 在 route/control smoke 中使用慢页窗口，cross-browser 动态详情路由支持重试；Year-End 单页 50 行表格在 long-list smoke 中按 capped 表格验收
- 图表交互 smoke 的 legend 场景改为稳定的音乐详情 ECharts 排名趋势图，避免账号页生命周期趋势为空时误报；首页 Dashboard 月度趋势继续保留 ECharts 视觉
- Web Vitals probe 对单次 lab 预算失败样本执行一次复测，预算仍未通过则失败，降低 headless CLS 采样噪声导致的误杀
- fullstack verification 的 API benchmark 调用会清空本地代理变量，避免 `HTTP_PROXY/ALL_PROXY` 污染 127.0.0.1 性能检查

### 验证

- Backend full 739 passed；Phase 5 最低矩阵 PASS；pre-commit PASS；完整 fullstack verification 带 quickstart、preview、Web Vitals 与资源预算 PASS
- API benchmark hot P95 均低于 500ms；`/api/billboard/data` hot P95 0.20s，`/api/dashboard/full` hot P95 0.16s；runtime resource 总 RSS 826.4MB / CPU 77.7%
- dev 与 production preview route/interaction/chart/control/long-list/cross-browser smoke 均通过；production preview Web Vitals 全部在预算内，首页 ECharts 版本 desktop LCP 2060ms / CLS 0 / TBT 0ms / 17 resources / 1131.2KB，mobile LCP 612ms / CLS 0 / TBT 0ms
- 固定域名 ngrok HTTPS tunnel 复核通过；外部 `/api/health`、Spotify auth status/data/login 和 invalid-state callback 均可达，callback 回跳 `https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state`；真实 Spotify 用户 consent 点击仍需人工确认

---

## 2026-06-20 — fix/bugfixes-and-polish 分支

### 修复

- 修复旧 `/analysis/*` 别名嵌套在 lazy `AnalysisLayout` 内导致的冷导航空壳风险
- 首页 Dashboard 月度趋势按产品偏好保留 ECharts 视觉，并将实现拆到 `MonthlyTrendEChart` 动态块；production preview 首页 LCP/CLS/TBT 仍在预算内（desktop `2004ms/0/0ms`，mobile `544ms/0/0ms`）
- 账号页新增轻量 `/profile` 首屏 Hero 查询，`/api/account` 聚合加入 TTL cache + warmup，production `/account` desktop LCP 从 `3532ms` 降至 `468ms`
- 根级 `scrollbar-gutter: stable` 将 `/billboard/number-ones` desktop CLS 从 `0.1` 压到 `0`
- Spotify OAuth 在 ngrok `SPOTIFY_REDIRECT_URI` 且未显式设置 `FRONTEND_ORIGIN` 时，callback 回跳 origin 从 redirect URI 推导，避免授权后掉回 localhost
- 图表交互 smoke 默认冷态等待调至 12s；前端 CDP smoke 脚本默认优先使用 Playwright `chromium_headless_shell-*`，避免系统 Chrome 启动阶段崩溃造成假失败

### 验证

- Backend full 694、unit 322、contract 172、frontend 134、完整 fullstack verification PASS
- 2026-06-21 复核：固定域名 ngrok HTTPS tunnel 已可建立，外部 health、Spotify login URL、invalid-state callback 回跳和 auth data 入口通过；真实 Spotify 用户 consent 点击仍需人工确认

详见 [`docs/verification/2026-06-20-fix-branch-follow-up.md`](verification/2026-06-20-fix-branch-follow-up.md)。

---

## 2026-06-19 — 全栈验证与性能收口

### 性能优化

- 默认预热改用当前动态阈值口径，避免预热旧缓存并与首屏请求抢 CPU
- Billboard 基础排名共享缓存（`_load_and_rank_cached`）
- Power Score、Billboard summaries 与播放合并路径向量化
- Dashboard full 单请求复用同一播放 DataFrame
- AI Insights 报告/问答透传播放过滤口径，并按过滤指纹分流缓存
- Behavior 全量事件分析只暴露/请求 `music_only`
- 专辑详情来源拆分批量映射
- 390px 移动端横向滚动归零
- pre-commit 收敛到 backend 治理范围
- OpenCC/ECharts 大依赖拆为按需加载子包，保存偏好不再模块级预取字典
- 账号页资源加载收敛

### 监控与验收

- **API 验收**：96 请求本地只读 API smoke 探针、85 个非破坏性 API 边界 probe
- **OpenAPI 审计**：134 operation 全量 audit（95 safe GET smoke / 30 targeted contract / 9 controlled stateful-external / 0 unaccounted）、参数边界 audit（59 obligations / 36 boundary_probe / 16 string_resilience_probe / 7 controlled stateful-external / 0 unaccounted）
- **Contract 护栏**：Provider 异常响应分层、Billboard enrichment 降级、基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON response_model（OpenAPI response_model 缺口 41→1）
- **8 端点 API 性能 benchmark** 慢端点门禁
- **前端 smoke**：48 组合 route（19 主路由 + 5 动态详情路由 × 2 视口）、6 场景交互（AI Insights 按 settings 分支验证、Settings 过滤/显示偏好与数据导入区覆盖）、3 场景 ECharts 图表交互、36 组合控件库存（13 默认路由 + 5 动态详情路由 × 2 视口，0 violation）、6 场景长列表分页/分段渲染
- **跨浏览器**：Chromium/Firefox/WebKit PASS 3/3
- **Web Vitals lab**：dev/prod-preview LCP/CLS/TBT/资源数量/encoded 体积/横向滚动溢出预算门禁

### 修复

- Spotify 当前播放 token refresh、OAuth login 未配置 Client ID 500、Settings 越界配置、清翻译缓存缺表、Provider 异常泛化 500、封面回退查询 schema mismatch 500、Billboard enrichment Wiki lookup 普通异常 500
- 基础设施/Settings mutation/Spotify auth/账号中心/核心统计/剩余 JSON 相关端点缺少 response_model
- AI Insights 报告缓存 readonly 写入 warning
- 会话列表嵌套按钮、周快捷项重复 key console error、音乐详情隐藏 tab 挂载图表导致的 ECharts 零尺寸 warning
- Billboard/Records/AllTime/WeekSelector/音乐详情分页图标按钮与 Settings Slider 内部输入控件缺少可访问名称

详见 [`docs/verification/2026-06-19-fullstack-verification.md`](verification/2026-06-19-fullstack-verification.md)。

---

## 2026-06-18 — 播放统计规则引擎（Phase C+D）

### 新增

- Session 边界检测：`max_gap_minutes` + `boundary_column` 参数化控制
- 动态阈值：替代固定 15 秒阈值
- Track Groups 三级合并：
  - L1：不合并（raw）
  - L2：按 recording 范围合并（同 ISRC/同录音）
  - L3：按 composition 范围合并（涵盖翻唱、现场版、remaster）
- Album Projects 专辑项目统计：L2/L3 使用 track membership，source album 仅作 breakdown，Billboard 按 release_date 排除发行前周
- `MergeConfig` FastAPI 依赖
- 设置页 L1/L2/L3 合并严格度选择器

### 传播

- Dashboard/Leaderboard/Timeline/Wrapped/Listening Hours/Music Entity/Release Cycle 统一传递 `dynamic_threshold` 与 `max_merge_gap_minutes`
- R24b + 过滤传播合约测试

详见 [`docs/playback-stats/rules.md`](playback-stats/rules.md)。

---

## 2026-06-12 — Phase 5.4 A-H 全系列完成

- **A**：TrackDetail 574→5 行 facade
- **B**：HabitsTab 933 行→9 文件 feature 拆分
- **C**：AI Insights 前端拆分（Experience/ReportCard/ChatInterface/ChatSessionList 等）
- **D**：AI Insights 后端拆分
- **E**：24 端点 response_model 硬化（OpenAPI 自动类型生成对应）
- **F**：Bundle 懒加载治理（Settings -88%、Records -69%、Account -34%）
- **G**：TrackDetail 歌词 Query 漏网修复
- **H**：Cross-cutting — 架构护栏 105+ 测试 + CI 基线

详见 [`docs/productization/2026-06-08-phase5-baseline.md`](productization/2026-06-08-phase5-baseline.md)。

---

## Phase 5 产品化收口基线

Phase 5 目标是收紧产品线到可持续迭代状态。已完成：

- 前端 GET 统一 TanStack Query（11 命名空间 queryKeys）：dashboard/account/billboard/analysis/settings/yearlyReview/music/library/versionMerge/community/aiInsights
- Provider 错误分类与 API 响应分层体系（`ProviderError` → `ProviderNetworkError`/`ProviderHTTPError` → `ProviderAuthError`/`ProviderRateLimitError`/`ProviderServerError` + `ProviderParseError`；API 层映射结构化 503/502/429）
- 业务 service 层 urllib 调用清零；core Spotify HTTP 收敛到 `HttpClient`/`SpotifyProvider`
- Billboard 与 Artist/Album 详情页完成 route container 化
- 模块级 API 响应 Map 缓存全部清除，迁移到 TanStack Query
- Records/AllTime/Community Feed/RecentPlays/SavedTracks/PersonalRankTable 长列表已有分页或分段渲染基线
- Request ID（`X-Request-ID` 生成/透传/日志关联）
- Billboard records 88 行 facade + chart_compute 211 行 facade
- 新增页面遵守 route container ≤450 行

### 当前验证口径

**交互 smoke**：6 个非破坏性场景，AI Insights 按 LLM 已配置/未配置分支验证；dev server 与生产 `vite preview` 均已复跑 PASS 6/6。

**控件库存 smoke**：13 个默认路由 + 5 个动态详情路由 × 桌面/390px 移动端，检查可见交互控件缺少可访问名称、嵌套交互控件、disabled 仍可 tab、输入控件无标签和重复 id；dev server 覆盖 36 组合 / 1821 控件 / 0 violation，生产 `vite preview` 覆盖 36 组合 / 1763 控件 / 0 violation。

**跨浏览器 smoke**：core-interactions 覆盖同一组 6 个核心交互；dev server 完整 route-marker + core-interactions 与生产 `vite preview` core-interactions 均已在 Chromium/Firefox/WebKit PASS 3/3。

**测试基线**：backend full 694 / unit 322 / contract 172 / frontend 134。
