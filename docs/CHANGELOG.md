# 变更日志

## 2026-06-20 — fix/bugfixes-and-polish 分支

### 修复

- 修复旧 `/analysis/*` 别名嵌套在 lazy `AnalysisLayout` 内导致的冷导航空壳风险
- 首页 Dashboard 月度趋势从 ECharts 改为轻量 DOM 条形图，production preview 首页 encoded resources 从约 `1,282KB` 降至 `1,060KB`
- 账号页新增轻量 `/profile` 首屏 Hero 查询，`/api/account` 聚合加入 TTL cache + warmup，production `/account` desktop LCP 从 `3532ms` 降至 `468ms`
- 根级 `scrollbar-gutter: stable` 将 `/billboard/number-ones` desktop CLS 从 `0.1` 压到 `0`
- Spotify OAuth 在 ngrok `SPOTIFY_REDIRECT_URI` 且未显式设置 `FRONTEND_ORIGIN` 时，callback 回跳 origin 从 redirect URI 推导，避免授权后掉回 localhost
- 图表交互 smoke 默认冷态等待调至 12s；前端 CDP smoke 脚本默认优先使用 Playwright `chromium_headless_shell-*`，避免系统 Chrome 启动阶段崩溃造成假失败

### 验证

- Backend full 692、unit 320、contract 172、frontend 134、完整 fullstack verification PASS
- ngrok agent 因本机网络/DNS/证书出口无法建立固定域名 tunnel，真实外部 Spotify 授权仍需可用 tunnel

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

**测试基线**：backend full 692 / unit 320 / contract 172 / frontend 134。
