# 2026-06-20 fix/bugfixes-and-polish 验证跟进报告

分支：`fix/bugfixes-and-polish`

## 结论

- 已按分支纠正要求丢弃错分支未提交改动，并在 `fix/bugfixes-and-polish` 上继续修复。
- 发现并修复一个前端旧分析路由别名回归：`/analysis/behavior` 等旧路径原先挂在 lazy `AnalysisLayout` 内部，首次进入时会短暂显示只有全局导航的空壳，route smoke 可能判定缺少业务内容 marker。
- 修复后，旧别名改为顶层 route 重定向，进入 `/analysis/behavior` 会直接跳转到 `/analysis/stats`，避免被懒加载布局拖慢。
- 新增 Phase 5 架构护栏测试，锁定旧 `/analysis/*` 别名必须位于 lazy `AnalysisLayout` 路由之前。
- 首页 Dashboard 月度趋势从 ECharts 改为轻量 DOM 条形图，避免 `/` 首屏预加载 `EChartsTheme` 动态块；生产 preview 首页 encoded resources 从 2026-06-19 记录的约 `1,282KB` 降至本轮 `1,060KB`，减少约 `221KB`（约 `17%`）。
- 修复 `frontend_chart_interaction_smoke.mjs` 在 Vite dev 冷态下等待 ECharts 懒加载 chunk 不足导致的假阴性：真实页面已确认 5 个 canvas 正常挂载，默认等待从 5s 调整为 12s，并同步单元护栏。
- 针对 Node/Playwright 拉起系统 Chrome 时的 macOS 启动阶段崩溃，将 6 个前端 CDP smoke 脚本的浏览器选择逻辑收敛到共享 helper，默认优先使用 Playwright Chromium/Chrome for Testing，系统 Chrome 仅作最后兜底。
- 发现并修复账号页首屏冷路径性能回归：`/account` 原先必须等待重聚合 `/api/account` 返回后才渲染 Hero，生产 preview 桌面 LCP 曾达到 `3532ms`；现在 Hero 并行使用轻量 `/api/profile` 数据先渲染，重聚合继续异步填充，生产 preview 桌面 LCP 降至 `468ms`。
- `/api/account` 聚合结果加入 `account.summary` TTL cache 并在 warmup 阶段预热：本地直连从约 `1.5-1.8s` 的重复聚合降至热路径 `8-11ms`，缓存统计命中可在 `/api/admin/cache-stats` 中看到。
- 修复异步长内容页桌面 CLS 抖动：根元素增加 `scrollbar-gutter: stable`，`/billboard/number-ones` 生产 preview 桌面 CLS 从复现时的 `0.1` 降至 `0`。

## 修复项

| 严重程度 | 问题 | 影响 | 修复 | 验证 |
| --- | --- | --- | --- | --- |
| P3 | `/analysis/behavior`、`/analysis/timeline`、`/analysis/leaderboard`、`/analysis/listening-hours`、`/analysis/artists` 兼容别名嵌在 lazy `AnalysisLayout` 内 | 冷导航时可能先渲染全局导航空壳，业务 marker 未出现；真实浏览器 route smoke 曾在 `/analysis/behavior` 桌面/移动端复现失败 | 将这些旧别名提升为 `AppLayout` 下的顶层 absolute route，并保留原目标跳转 | Browser 验证 `/analysis/behavior` 桌面/390px 移动端均落到 `/analysis/stats`；route smoke 48/48 PASS；新增 `phase5-architecture.test.ts` 护栏 |
| P3 | dev 图表交互 smoke 默认 5s 等待在 Vite 冷态下可能早于 ECharts lazy chunk 完成 | 完整矩阵可能误报 `Expected at least 1 ECharts canvas`，但页面实际 canvas 正常、无 console/page error | 将 `frontend_chart_interaction_smoke.mjs` 默认等待调至 12s，并同步 `test_frontend_chart_interaction_smoke_script.py` 护栏 | Python Playwright DOM 检查 `/analysis/stats` 有 5 个 canvas；默认 chart smoke 3/3 PASS；完整 fullstack verification PASS |
| P4 | 6 个前端 CDP smoke 脚本默认候选优先系统 `/Applications/Google Chrome.app` | 在 Codex/Node 启动器下可触发 macOS `HIServices/TransformProcessType` 阶段 abort，导致验证链路假失败 | 新增 `scripts/lib/chrome_executable.mjs`，显式 `--chrome`/`CHROME_PATH` 仍优先，其次自动查找 Playwright Chromium/Chrome for Testing，系统 Chrome 后置兜底 | `findChrome()` 默认解析到 Playwright `Google Chrome for Testing`；不带 `CHROME_PATH` 的 `/analysis/behavior` route smoke 桌面/移动端 PASS；新增 `test_frontend_chrome_executable_helper.py` |
| P3 | `/account` 首屏 Hero 被重聚合 `/api/account` 阻塞 | 缓存过期或冷启动时账号页桌面 LCP 可超过 3s，且用户先看到整页骨架 | 新增 `useProfile()` 独立 TanStack Query 读取 `/api/profile`，账号页在重聚合加载期间先渲染稳定 Hero + 内容骨架 | `query-hooks.test.tsx` 新增 profile query 护栏；`phase5-architecture.test.ts` 锁定 progressive Hero；production `/account` desktop LCP `3532ms -> 468ms` |
| P3 | 异步加载后页面高度变化未预留滚动条槽位 | `/billboard/number-ones` 桌面 Web Vitals 可记录 CLS `0.1` | 在 `html` 根元素设置 `scrollbar-gutter: stable`，并用后端 unit 护栏防回归 | `test_frontend_global_css_guardrails.py` PASS；production `/billboard/number-ones` desktop CLS `0.1 -> 0` |

## 性能优化

| 优化项 | 优化前 | 优化后 | 实现说明 |
| --- | ---: | ---: | --- |
| 首页 Dashboard 首屏资源体积 | Production preview `/` desktop encoded resources `1,282.1KB`，mobile `1,280.6KB`（2026-06-19 报告） | Production preview `/` desktop `1,060.6KB`，mobile `1,059.1KB` | `MonthlyTrendChart` 从 ECharts 切换为 DOM/CSS 条形图；Dashboard lazy preload 依赖不再包含 `EChartsTheme`，复杂图表页面继续保留 ECharts |
| 首页资源请求数 | Production preview `/` desktop `17`，mobile `16`（2026-06-19 报告） | Production preview `/` desktop `15`，mobile `14` | 移除首页对 ECharts chunk 及其相关 chart preload 依赖 |
| `/api/account` 聚合热路径 | Python 直连重复请求约 `1616.8ms / 1495.5ms / 1522.4ms`；缓存过期后浏览器首屏仍会等重聚合 | 文件 DB 缓存命中约 `8.7ms / 8.4ms / 8.4ms / 7.7ms`；warmup 后临时 8010 后端首次可见请求约 `11.4ms / 9.5ms / 9.4ms` | `account.summary` 使用统一 Cache Manager TTL cache，file-backed DB 连接按路径作为 cache key，warmup 预热账号 summary |
| `/account` 页面桌面 LCP | Production preview `/account` desktop `3532ms`，dev desktop `3676ms`（重聚合冷路径） | Production preview desktop `468ms`，mobile `404ms`；dev desktop `516ms`，mobile `424ms` | 账号页 Hero 并行使用 `/api/profile` 轻量数据先渲染，重聚合返回后仅补全收藏人格和标签内容 |
| `/billboard/number-ones` 桌面 CLS | Production preview desktop 复现 `0.1` | Production preview desktop/mobile 均 `0` | 根元素稳定滚动条 gutter，避免异步长内容让居中布局在滚动条出现时位移 |

## 本轮验证证据

| 类型 | 命令或探针 | 结果 |
| --- | --- | --- |
| 前端架构回归 | `cd frontend && npm test -- --run phase5-architecture` | 67 passed |
| 前端 query hook 回归 | `cd frontend && npm test -- --run query-hooks` | 18 passed；新增 `/profile` 独立 TanStack Query 护栏 |
| 前端全量测试 | `cd frontend && npm test` | 8 files / 134 tests passed |
| 前端生产构建 | `cd frontend && npm run build` | PASS，完整矩阵构建约 395ms，最终 focused build 约 422ms；Dashboard 依赖不再包含 `EChartsTheme`；`AccountCenterPage` chunk gzip 约 9.95KB；仍有非首页动态大 chunk 提示 |
| 后端账号缓存/样式护栏 | `.venv/bin/pytest backend/tests/unit/test_frontend_global_css_guardrails.py backend/tests/unit/test_account_service_cache.py backend/tests/unit/test_warmup.py -q` | 5 passed；覆盖 `account.summary` TTL cache、warmup 预热和根级 `scrollbar-gutter` |
| 后端全量测试 | `.venv/bin/python -m pytest backend/tests/ -v` | 691 passed, 2 environment warnings |
| Ruff | `.venv/bin/ruff check backend/` / `.venv/bin/ruff format --check backend/` | PASS；保留既有 `UP038` removed-rule warning |
| pre-commit | `.venv/bin/pre-commit run --all-files` | ruff / ruff format / mypy / detect-secrets 全部 PASS |
| Phase 5 最低矩阵 | `sh scripts/phase5_check.sh` | unit 320 passed；contract 171 passed；frontend 134 passed；build PASS，production build 约 395ms |
| API smoke | `.venv/bin/python scripts/api_smoke_probe.py` | 96/96 PASS；OpenAPI GET 95/104 covered, 9 excluded, 0 unaccounted |
| API boundary | `.venv/bin/python scripts/api_boundary_probe.py` | 85/85 PASS |
| API benchmark | `.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json` | slow_count=0；无 hot P95 超过 500ms |
| 快速启动 | `.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json` | PASS；最终聚合矩阵预检复用已启动服务时总耗时 `44.7ms`，backend health `2.5ms`，docs `5.8ms`，frontend shell `1.2ms`，proxy `4.2ms` |
| 前端 route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:5173 --api-base-url http://127.0.0.1:8000 --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes` | 24 路由 × 2 视口全部 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端交互 smoke | `node scripts/frontend_interaction_smoke.mjs --base-url http://127.0.0.1:5173` | 6/6 PASS；0 console error/warning；0 横向溢出 |
| 控件库存 smoke | `node scripts/frontend_control_inventory_smoke.mjs --base-url http://127.0.0.1:5173 --api-base-url http://127.0.0.1:8000 --viewport both --include-detail-routes --chrome <Chrome for Testing>` | 36 组合 / 1787 控件 / 0 violation |
| 首页 production Web Vitals | `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --wait-ms 5000 --chrome <Chrome for Testing>` | desktop LCP 1188ms、CLS 0、TBT 0ms、15 resources / 1060.6KB；mobile LCP 632ms、CLS 0、TBT 0ms、14 resources / 1059.1KB |
| 当前工作树 dev Web Vitals | `env -u CHROME_PATH node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:5173 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 125 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0 --output /tmp/spotify_web_vitals_dev_after_profile_split.json` | PASS；12 个 route/viewport 组合全部在预算内；最大 LCP `852ms`，最大 CLS 0，最大 TBT 0ms，最大资源数 106，最大 encoded resources 9808.6KB，横向溢出 0px；`/account` desktop `516ms` |
| 当前工作树 production Web Vitals | `env -u CHROME_PATH node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0 --output /tmp/spotify_web_vitals_prod_after_profile_split.json` | PASS；12 个 route/viewport 组合全部在预算内；最大 LCP `2144ms`（`/` desktop），最大 CLS 0，最大 TBT 0ms，最大资源数 46，最大 encoded resources 3757.7KB，横向溢出 0px；`/account` desktop `468ms`、mobile `404ms`；首页仍为 desktop 15 resources / 1060.6KB、mobile 14 resources / 1059.1KB |
| 最终 production Web Vitals spotcheck | `env -u CHROME_PATH node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/billboard/number-ones,/account --viewport both --wait-ms 5000 ... --output /tmp/spotify_web_vitals_prod_final_spotcheck.json` + warmed `/` 复跑 | `/account` desktop `388ms`、mobile `460ms`；`/billboard/number-ones` desktop/mobile CLS 0；首页首个新 Chrome 会话 desktop 出现一次 FCP/LCP 冷启动尖刺 `4832ms`，立即 warmed 复跑为 desktop `1208ms`、mobile `620ms`，资源体积仍为 15/14 requests、约 1060KB/1059KB |
| 首页 production route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --max-scroll-overflow 0 --fail-on-console-warning --chrome <Chrome for Testing>` | desktop/mobile PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端 production route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes --chrome <Chrome for Testing>` | 24 路由 × 2 视口全部 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端 production chart interaction smoke | `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --chrome <Chrome for Testing>` | `chart-hover-tooltip` / `legend-toggle` / `datazoom-drag` 3/3 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 图表 smoke 冷态复核 | `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:5173` | 默认参数 3/3 PASS；`chart-hover-tooltip` / `legend-toggle` / `datazoom-drag` 均为 0 console error/warning、0 page error、0 横向溢出 |
| 图表/浏览器 smoke 脚本护栏 | `.venv/bin/python -m pytest backend/tests/unit/test_frontend_chrome_executable_helper.py backend/tests/unit/test_frontend_chart_interaction_smoke_script.py backend/tests/unit/test_frontend_route_smoke_script.py backend/tests/unit/test_frontend_interaction_smoke_script.py backend/tests/unit/test_frontend_long_list_smoke_script.py backend/tests/unit/test_frontend_control_inventory_smoke_script.py backend/tests/unit/test_frontend_web_vitals_probe_script.py -q` | 26 passed；默认等待常量、三类 ECharts 交互覆盖、Chrome for Testing 优先级和 6 个 smoke 脚本共享浏览器查找逻辑同步 |
| 默认浏览器 route smoke | `env -u CHROME_PATH node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:5173 --api-base-url http://127.0.0.1:8000 --routes /analysis/behavior --viewport both --max-scroll-overflow 0 --fail-on-console-warning --output /tmp/spotify_default_chrome_route_smoke.json` | desktop/mobile PASS；0 console error/warning；0 page error；0 横向溢出；`findChrome()` 默认解析到 Playwright `Google Chrome for Testing` |
| CI parity | `.venv/bin/python scripts/ci_baseline_parity.py` | GitHub Actions baseline 与本地 Phase 5 核心命令一致 |
| 完整 fullstack verification | `env -u CHROME_PATH -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing_fix_branch_final2.json --benchmark-json /tmp/spotify_api_benchmark_fix_branch_final2.json --openapi-operation-audit-json /tmp/spotify_openapi_operation_audit_fix_branch_final2.json --openapi-parameter-boundary-audit-json /tmp/spotify_openapi_parameter_boundary_audit_fix_branch_final2.json` | PASS；quickstart 44.7ms；backend 691 passed；pre-commit PASS；Phase 5 unit 320 / contract 171 / frontend 134 / build PASS（约 395ms）；OpenAPI operation 134/0 unaccounted；parameter obligations 59/0 unaccounted；API smoke 96/96；boundary 85/85；benchmark 无 hot P95 >500ms；route 48/48；interaction 6/6；chart 3/3；control inventory 36 组合 / 1787 控件 / 0 violation；long-list 6/6；Chromium/Firefox/WebKit PASS |
| ngrok HTTPS 初段探测 | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173` + `http://127.0.0.1:4040/api/tunnels` | 未建立 tunnel；带代理启动时报 `ERR_NGROK_9009`，清空代理后 ngrok 进程无报错但本地 API 连续返回 `tunnels 0`，固定域名返回 404；未进入 Spotify 登录授权 |
| Runtime resource | `.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --json-output /tmp/spotify_runtime_resources.json --max-total-rss-mb 1200 --max-total-cpu-percent 200` | PASS；总 RSS 1125.4MB，总 CPU 6.1%；backend 964.7MB，frontend 160.7MB |
| 当前工作树 Runtime resource | `.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173 --preview-url http://127.0.0.1:4173 --json-output /tmp/spotify_runtime_resources_fix_branch_final2.json --max-total-rss-mb 1400 --max-total-cpu-percent 220 --fail-on-missing` | PASS；总 RSS 1183.3MB，总 CPU 5.8%；backend 940.5MB，frontend 186.6MB，preview 56.2MB |

## Chrome 崩溃说明

本轮验证中，Codex 沙箱内由 Node 拉起系统 `/Applications/Google Chrome.app` 时出现一次 macOS crash report，栈停在 `HIServices/TransformProcessType` 并由 Chrome 自身 `abort()`。该崩溃发生在浏览器注册/启动阶段，不是前端页面 JavaScript 崩溃。

后续使用 Playwright 的 `Google Chrome for Testing` 并在沙箱外运行同一类 CDP smoke，dev/prod-preview route smoke、production chart interaction smoke 与 control inventory 均通过，因此该事件按测试运行器/系统浏览器启动异常记录，不作为应用缺陷。为避免后续默认脚本再次优先命中系统 Chrome，`scripts/lib/chrome_executable.mjs` 已把 Playwright Chromium/Chrome for Testing 放在系统 Chrome 之前；不带 `CHROME_PATH` 的 route smoke 已验证默认解析到 Chrome for Testing 并通过。

## 剩余风险

- 本轮没有执行真实 ngrok HTTPS + Spotify 外部 OAuth 浏览器授权闭环；现有证据仍来自本地 OAuth PKCE contract、Spotify auth JSON 端点与状态 API。已尝试 ngrok 初段探测，但固定域名 tunnel 未建立：带代理启动触发 `ERR_NGROK_9009`，清空代理后本地 ngrok API 仍返回 `tunnels 0`。
- Playwright WebKit 仍只能代表 Safari-family 引擎 smoke，不等同用户真实 Safari.app 手工会话。
- 生产构建仍提示动态大 chunk：`EChartsTheme` 仍服务于分析/详情等复杂图表页，OpenCC `cn2t` 字典仍是用户切换繁体时按需加载的大字典；它们已不再属于首页 Dashboard 的 preload 依赖。
- 代码变更仍保持未提交状态；本轮未收到显式 `git commit` 指令，因此没有创建提交。

## 完成度审计

| 目标要求 | 当前证据 | 判定 |
| --- | --- | --- |
| 在正确分支继续 | `git branch --show-current` 为 `fix/bugfixes-and-polish` | 已满足 |
| 后端所有现有测试通过 | `pytest backend/tests/ -q`：691 passed | 已满足 |
| API 端点与 OpenAPI 覆盖 | OpenAPI operation audit：134 operations / 0 unaccounted；API smoke 96/96；boundary 85/85 | 已满足 |
| Provider 错误分层、response_model、基础设施 contract | 完整 fullstack verification 包含 pre-commit、Phase 5、OpenAPI audits、API probes 与 contract 测试；相关 response-model probes 已纳入测试基线 | 已满足 |
| 前端页面无白屏、无 console error/warning、无横向溢出 | route smoke 48/48；interaction 6/6；chart 3/3；control inventory 36 组合 / 1787 控件 / 0 violation；long-list 6/6；Chromium/Firefox/WebKit PASS | 已满足 |
| 性能量化与资源占用 | API benchmark 无 hot P95 >500ms；Web Vitals dev/prod 在预算内；runtime resource probe 总 RSS 1183.3MB / CPU 5.8%；性能表列出前后对比 | 已满足 |
| 文档与交付报告 | README、AGENTS、CLAUDE、backend/CLAUDE 与本报告已同步最新测试基线、修复项、性能数据和 10 分钟复核步骤 | 已满足 |
| 真实 ngrok HTTPS + Spotify 外部 OAuth 浏览器授权闭环 | 当前只有本地 OAuth PKCE contract、Spotify auth JSON 端点与状态 API 证据；ngrok 固定域名 tunnel 未建立，未进行真实用户登录授权 | 未完成，需可用 ngrok tunnel 与用户 Spotify 授权 |
| 生成代码提交 | 变更保持在工作树中，未执行 `git commit` | 未完成，等待用户明确提交指令 |

## 10 分钟快速复核

1. 运行 `.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json`，确认 8000/5173 默认启动链路可用。
2. 打开 `http://127.0.0.1:5173/analysis/behavior`，确认地址最终为 `/analysis/stats` 且页面出现 `总体播放统计`。
3. 在 390px 移动宽度重复访问 `/analysis/behavior`，确认无横向滚动。
4. 运行 `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:5173 --api-base-url http://127.0.0.1:8000 --routes /analysis/behavior --viewport both --max-scroll-overflow 0 --fail-on-console-warning`；默认会优先使用 Playwright Chromium/Chrome for Testing，如需指定浏览器再传 `--chrome` 或 `CHROME_PATH`。
5. 访问首页 `/`，确认“月度播放趋势”仍正常显示；需要量化资源体积时，用生产 preview 跑 `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --wait-ms 5000`。
6. 访问 `/account`，确认账号 Hero 先显示，收藏/习惯内容随后填充；需要量化 LCP 时用 `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /account --viewport both --wait-ms 5000`。
7. 运行 `sh scripts/phase5_check.sh`，确认最低验证矩阵仍全绿。
