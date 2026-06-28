# 2026-06-20 fix/bugfixes-and-polish 验证跟进报告

分支：`fix/bugfixes-and-polish`

## 结论

- 已按分支纠正要求丢弃错分支未提交改动，并在 `fix/bugfixes-and-polish` 上继续修复。
- 发现并修复一个前端旧分析路由别名回归：`/analysis/behavior` 等旧路径原先挂在 lazy `AnalysisLayout` 内部，首次进入时会短暂显示只有全局导航的空壳，route smoke 可能判定缺少业务内容 marker。
- 修复后，旧别名改为顶层 route 重定向，进入 `/analysis/behavior` 会直接跳转到 `/analysis/stats`，避免被懒加载布局拖慢。
- 新增 Phase 5 架构护栏测试，锁定旧 `/analysis/*` 别名必须位于 lazy `AnalysisLayout` 路由之前。
- 首页 Dashboard 月度趋势按产品偏好保留 ECharts 视觉，并将 ECharts 配置隔离到 `MonthlyTrendEChart` 动态块；`MonthlyTrendChart` wrapper 不再静态导入 `LazyEChart` / `EChartsTheme`，production preview 首页 desktop LCP `2004ms`、CLS `0`、TBT `0ms`，mobile LCP `544ms`、CLS `0`、TBT `0ms`。
- 修复 `frontend_chart_interaction_smoke.mjs` 在 Vite dev 冷态下等待 ECharts 懒加载 chunk 不足导致的假阴性：真实页面已确认 5 个 canvas 正常挂载，默认等待从 5s 调整为 12s，并同步单元护栏。
- 针对 Node/Playwright 拉起系统 Chrome 时的 macOS 启动阶段崩溃，将 6 个前端 CDP smoke 脚本的浏览器选择逻辑收敛到共享 helper，默认优先使用 Playwright `chromium_headless_shell-*`，再回退 Chrome for Testing，系统 Chrome 仅作最后兜底。
- 发现并修复账号页首屏冷路径性能回归：`/account` 原先必须等待重聚合 `/api/account` 返回后才渲染 Hero，生产 preview 桌面 LCP 曾达到 `3532ms`；现在 Hero 并行使用轻量 `/api/profile` 数据先渲染，重聚合继续异步填充，生产 preview 桌面 LCP 降至 `468ms`。
- `/api/account` 聚合结果加入 `account.summary` TTL cache 并在 warmup 阶段预热：本地直连从约 `1.5-1.8s` 的重复聚合降至热路径 `8-11ms`，缓存统计命中可在 `/api/admin/cache-stats` 中看到。
- 修复异步长内容页桌面 CLS 抖动：根元素增加 `scrollbar-gutter: stable`，`/billboard/number-ones` 生产 preview 桌面 CLS 从复现时的 `0.1` 降至 `0`。
- 修复 Spotify OAuth 在 ngrok HTTPS 配置下的回调回跳 origin 问题：当 `SPOTIFY_REDIRECT_URI` 已指向 ngrok 但 `FRONTEND_ORIGIN` 未显式设置时，callback 成功/失败页现在回跳到 ngrok origin，而不是默认 `http://localhost:5173`。
- 2026-06-21 复核：此前 ngrok 证书/CRL 阻塞已解除，固定域名 tunnel 当前可建立；外部 HTTPS `/api/health`、Spotify login URL 生成、invalid-state callback 回跳、Spotify auth data 入口均已通过非破坏性探针。2026-06-28 用户已在真实浏览器中完成人工 Spotify 登录/同意授权，外部探针复核继续 PASS。

## 修复项

| 严重程度 | 问题 | 影响 | 修复 | 验证 |
| --- | --- | --- | --- | --- |
| P3 | `/analysis/behavior`、`/analysis/timeline`、`/analysis/leaderboard`、`/analysis/listening-hours`、`/analysis/artists` 兼容别名嵌在 lazy `AnalysisLayout` 内 | 冷导航时可能先渲染全局导航空壳，业务 marker 未出现；真实浏览器 route smoke 曾在 `/analysis/behavior` 桌面/移动端复现失败 | 将这些旧别名提升为 `AppLayout` 下的顶层 absolute route，并保留原目标跳转 | Browser 验证 `/analysis/behavior` 桌面/390px 移动端均落到 `/analysis/stats`；route smoke 48/48 PASS；新增 `phase5-architecture.test.ts` 护栏 |
| P3 | dev 图表交互 smoke 默认 5s 等待在 Vite 冷态下可能早于 ECharts lazy chunk 完成 | 完整矩阵可能误报 `Expected at least 1 ECharts canvas`，但页面实际 canvas 正常、无 console/page error | 将 `frontend_chart_interaction_smoke.mjs` 默认等待调至 12s，并同步 `test_frontend_chart_interaction_smoke_script.py` 护栏 | Python Playwright DOM 检查 `/analysis/stats` 有 5 个 canvas；默认 chart smoke 3/3 PASS；完整 fullstack verification PASS |
| P4 | 6 个前端 CDP smoke 脚本默认候选优先系统 `/Applications/Google Chrome.app` | 在 Codex/Node 启动器下可触发 macOS `HIServices/TransformProcessType` 阶段 abort，导致验证链路假失败 | 新增 `scripts/lib/chrome_executable.mjs`，显式 `--chrome`/`CHROME_PATH` 仍优先，其次自动查找 Playwright `chromium_headless_shell-*`、Chrome for Testing，系统 Chrome 后置兜底 | `findChrome()` 默认解析到 Playwright `chromium_headless_shell-*`；最小 CDP `/json/version` 启动返回 `HeadlessChrome/148.0.7778.96`；新增 `test_frontend_chrome_executable_helper.py` |
| P3 | `/account` 首屏 Hero 被重聚合 `/api/account` 阻塞 | 缓存过期或冷启动时账号页桌面 LCP 可超过 3s，且用户先看到整页骨架 | 新增 `useProfile()` 独立 TanStack Query 读取 `/api/profile`，账号页在重聚合加载期间先渲染稳定 Hero + 内容骨架 | `query-hooks.test.tsx` 新增 profile query 护栏；`phase5-architecture.test.ts` 锁定 progressive Hero；production `/account` desktop LCP `3532ms -> 468ms` |
| P3 | 异步加载后页面高度变化未预留滚动条槽位 | `/billboard/number-ones` 桌面 Web Vitals 可记录 CLS `0.1` | 在 `html` 根元素设置 `scrollbar-gutter: stable`，并用后端 unit 护栏防回归 | `test_frontend_global_css_guardrails.py` PASS；production `/billboard/number-ones` desktop CLS `0.1 -> 0` |
| P3 | ngrok HTTPS OAuth 配置下 callback 成功/失败后仍默认回跳 localhost | 用户从 ngrok 域名进入 Spotify 授权后，回调完成会掉回 `http://localhost:5173/settings`，外部 HTTPS 验证体验不闭环 | `_get_frontend_origin()` 在 `FRONTEND_ORIGIN` 仍为默认值时，从 `SPOTIFY_REDIRECT_URI` 推导前端 origin；显式配置的 `FRONTEND_ORIGIN` 仍优先 | 新增 `test_spotify_callback_origin_follows_ngrok_redirect_uri_when_frontend_origin_is_default`；invalid-state callback probe 返回 `Location: https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state` |

## 性能优化

| 优化项 | 优化前 | 优化后 | 实现说明 |
| --- | ---: | ---: | --- |
| 首页 Dashboard 首屏 Web Vitals | Production preview `/` desktop encoded resources 约 `1,282KB`，ECharts 视觉保留 | Production preview `/` desktop LCP `2004ms` / CLS `0` / TBT `0ms`，mobile LCP `544ms` / CLS `0` / TBT `0ms` | `MonthlyTrendChart` 只保留空态和 lazy boundary，`MonthlyTrendEChart` 承载 ECharts 配置；保留图表质感，同时避免 wrapper 静态导入 ECharts runtime |
| 首页资源请求数 | Production preview `/` desktop `17`，mobile `16`（2026-06-19 报告） | Production preview `/` desktop/mobile `17` | 保留 ECharts 视觉后资源数不再宣称下降；当前仍低于资源预算 120 |
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
| 后端全量测试 | `.venv/bin/python -m pytest backend/tests/ -q` | 694 passed, 1 environment warning |
| Ruff | `.venv/bin/ruff check backend/` / `.venv/bin/ruff format --check backend/` | PASS；`UP038` 兼容忽略已收敛到 pre-commit hook 参数，`.venv` Ruff 不再输出 removed-rule warning |
| pre-commit | `.venv/bin/pre-commit run --all-files` | ruff / ruff format / mypy / detect-secrets 全部 PASS |
| Phase 5 最低矩阵 | `sh scripts/phase5_check.sh` | unit 322 passed；contract 172 passed；frontend 134 passed；build PASS，production build 约 425ms |
| Spotify OAuth ngrok origin contract | `.venv/bin/pytest backend/tests/contract/test_spotify_auth_contract.py -q` | 8 passed；新增默认 `FRONTEND_ORIGIN` + ngrok `SPOTIFY_REDIRECT_URI` 的 callback origin 护栏 |
| 后端 contract 扩展矩阵 | `.venv/bin/pytest -m contract -q` | 172 passed, 520 deselected；新增 OAuth ngrok origin contract 纳入基线 |
| Spotify OAuth 本地非破坏性探针 | `curl http://localhost:5173/api/spotify/auth/login` + invalid-state callback | login 生成的 Spotify 授权 URL 使用 ngrok `redirect_uri`；invalid-state callback 307 回跳到 `https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state`，未交换 token、未写入连接状态 |
| API smoke | `.venv/bin/python scripts/api_smoke_probe.py` | 96/96 PASS；OpenAPI GET 95/104 covered, 9 excluded, 0 unaccounted |
| API boundary | `.venv/bin/python scripts/api_boundary_probe.py` | 85/85 PASS |
| API benchmark | `.venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --json-output /tmp/spotify_api_benchmark.json` | slow_count=0；无 hot P95 超过 500ms |
| 快速启动 | `.venv/bin/python scripts/quickstart_smoke.py --require-running --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --json-output /tmp/spotify_quickstart_timing_localhost_fullstack2.json` | PASS；最终聚合矩阵预检复用已启动服务时总耗时 `52.5ms`，backend health `2.4ms`，docs `2.1ms`，frontend shell `3.1ms`，frontend API proxy `6.5ms` |
| 前端 route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes` | 24 路由 × 2 视口全部 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端交互 smoke | `node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173` | 6/6 PASS；0 console error/warning；0 横向溢出 |
| 控件库存 smoke | `node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --viewport both --include-detail-routes --chrome <Chrome for Testing>` | 36 组合 / 1821 控件 / 0 violation |
| 首页 production Web Vitals | `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --wait-ms 5000` | 产品偏好调整后保留 ECharts：desktop LCP `2004ms`、CLS `0`、TBT `0ms`、17 resources / `1283.7KB`；mobile LCP `544ms`、CLS `0`、TBT `0ms`、17 resources / `1283.7KB` |
| 当前工作树 dev Web Vitals（2026-06-21 复核） | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy node scripts/frontend_web_vitals_probe.mjs --base-url http://localhost:5173 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-scroll-overflow-px 0` | PASS；dev server 只门禁 LCP/CLS/TBT/横向溢出，避免 Vite 模块请求噪声误判生产资源预算；最大 LCP `968ms`、最大 CLS 0、最大 TBT `22ms`、横向溢出 0px；资源数/encoded 仍记录但不作为 dev 门禁 |
| 当前工作树 production Web Vitals（2026-06-21 复核） | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0` | 历史 DOM 版本 PASS；12 个 route/viewport 组合全部在预算内；该数据用于对比，当前首页已按产品偏好恢复 ECharts |
| 最终 production Web Vitals spotcheck | `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --wait-ms 5000 --output /tmp/spotify_home_web_vitals_echarts_lazy.json` | 当前 ECharts lazy 版本首页 desktop `2004ms/0/0ms`、17 resources / `1283.7KB`；mobile `544ms/0/0ms`、17 resources / `1283.7KB`；预算仍 PASS |
| 首页 production route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --max-scroll-overflow 0 --fail-on-console-warning --chrome <Chrome for Testing>` | desktop/mobile PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端 production route smoke | `node scripts/frontend_route_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes --chrome <Chrome for Testing>` | 24 路由 × 2 视口全部 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 前端 production chart interaction smoke | `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --chrome <Chrome for Testing>` | `chart-hover-tooltip` / `legend-toggle` / `datazoom-drag` 3/3 PASS；0 console error/warning；0 page error；0 横向溢出 |
| 图表 smoke 冷态复核 | `node scripts/frontend_chart_interaction_smoke.mjs --base-url http://localhost:5173` | 默认参数 3/3 PASS；`chart-hover-tooltip` / `legend-toggle` / `datazoom-drag` 均为 0 console error/warning、0 page error、0 横向溢出 |
| 图表/浏览器/聚合脚本护栏 | `.venv/bin/python -m pytest backend/tests/unit/test_frontend_chrome_executable_helper.py backend/tests/unit/test_frontend_chart_interaction_smoke_script.py backend/tests/unit/test_frontend_route_smoke_script.py backend/tests/unit/test_frontend_interaction_smoke_script.py backend/tests/unit/test_frontend_long_list_smoke_script.py backend/tests/unit/test_frontend_control_inventory_smoke_script.py backend/tests/unit/test_frontend_web_vitals_probe_script.py backend/tests/unit/test_fullstack_verification_check_script.py backend/tests/unit/test_quickstart_smoke_script.py backend/tests/unit/test_runtime_resource_probe_script.py -q` | 35 passed；默认等待常量、三类 ECharts 交互覆盖、Playwright headless shell 优先级、6 个 smoke 脚本共享浏览器查找逻辑、localhost dev 默认入口和 dev/preview Web Vitals 预算职责同步 |
| 默认浏览器 route smoke | `env -u CHROME_PATH node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --routes /analysis/behavior --viewport both --max-scroll-overflow 0 --fail-on-console-warning --output /tmp/spotify_default_chrome_route_smoke.json` | desktop/mobile PASS；0 console error/warning；0 page error；0 横向溢出；当前 `findChrome()` 默认解析到 Playwright `chromium_headless_shell-*`，脚本默认 dev 入口为 `http://localhost:5173` |
| CI parity | `.venv/bin/python scripts/ci_baseline_parity.py` | GitHub Actions baseline 与本地 Phase 5 核心命令一致 |
| 完整 fullstack verification | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --preview-api-url http://127.0.0.1:8000 --quickstart-preflight --quickstart-json /tmp/spotify_quickstart_timing_localhost_fullstack2.json --benchmark-json /tmp/spotify_api_benchmark_localhost_fullstack2.json --openapi-operation-audit-json /tmp/spotify_openapi_operation_audit_localhost_fullstack2.json --openapi-parameter-boundary-audit-json /tmp/spotify_openapi_parameter_boundary_audit_localhost_fullstack2.json --web-vitals --resource-snapshot --resource-snapshot-json /tmp/spotify_runtime_resources_localhost_fullstack2.json --resource-max-total-rss-mb 1400 --resource-max-total-cpu-percent 220 --web-vitals-max-lcp-ms 3000 --web-vitals-max-cls 0.01 --web-vitals-max-tbt-ms 100 --web-vitals-max-resource-count 120 --web-vitals-max-encoded-resource-kb 11000 --web-vitals-max-scroll-overflow-px 0 --skip-cross-browser` | PASS；quickstart 52.5ms；backend 694 passed；pre-commit PASS；Phase 5 unit 322 / contract 172 / frontend 134 / build PASS；OpenAPI operation 134/0 unaccounted；parameter obligations 59/0 unaccounted；API smoke 96/96；boundary 85/85；benchmark 无 hot P95 >500ms；runtime resource 总 RSS 631.1MB / CPU 67.9%；dev route 48/48、interaction 6/6、chart 3/3、control inventory 36 组合 / 1821 控件 / 0 violation、long-list 6/6、dev Web Vitals 主体预算 PASS；production preview route 48/48、interaction 6/6、chart 3/3、control inventory 36 组合 / 1821 控件 / 0 violation、long-list 6/6、production Web Vitals 全资源预算 PASS。跨浏览器 smoke 已在独立复核中通过 Chromium/Firefox/WebKit，本次聚合为脚本/Web Vitals/localhost 入口专项复跑，使用 `--skip-cross-browser` 节省重复耗时 |
| ngrok HTTPS tunnel 复核（2026-06-21） | `ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173` + `curl http://127.0.0.1:4040/api/tunnels` | PASS；本地 ngrok API 返回 `public_url=https://stuffing-nebula-tamer.ngrok-free.dev`，转发目标为 `http://localhost:5173` |
| Spotify OAuth ngrok 初段/回跳探针（2026-06-21） | `curl https://stuffing-nebula-tamer.ngrok-free.dev/api/health`；`/api/spotify/auth/login`；invalid-state callback；`/api/spotify/auth/data` | PASS；外部 `/api/health` 200；login 生成 `accounts.spotify.com` 授权 URL，`redirect_uri=https://stuffing-nebula-tamer.ngrok-free.dev/api/spotify/auth/callback`，state/code_challenge 存在；invalid-state callback 307 回跳 `https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state` 且返回 `X-Request-ID`；Spotify auth data 入口返回 200 |
| Runtime resource | `.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --json-output /tmp/spotify_runtime_resources_localhost_fullstack2.json --max-total-rss-mb 1400 --max-total-cpu-percent 220 --fail-on-missing` | PASS；总 RSS 631.1MB，总 CPU 67.9%；backend 488.4MB / 67.9%，frontend 86.6MB / 0%，preview 56.1MB / 0% |

## 2026-06-27 当前复核补充

| 项目 | 命令/探针 | 结果 |
| --- | --- | --- |
| 后端 full | `.venv/bin/python -m pytest backend/tests/ -q` | 739 passed, 1 warning |
| Phase 5 最低矩阵 | `sh scripts/phase5_check.sh` | PASS；unit 344 passed / contract 192 passed / frontend 175 passed / build PASS |
| OpenAPI 参数边界审计 | `.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit_current.json` | 60 obligations / 0 unaccounted；`max_merge_gap_minutes` nullable schema 边界已纳入 |
| API boundary | `.venv/bin/python scripts/api_boundary_probe.py --base-url http://127.0.0.1:8000` | 90/90 PASS |
| API benchmark | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy .venv/bin/python scripts/benchmark_api.py --base-url http://127.0.0.1:8000 --runs 3 --slow-ms 500 --fail-on-slow --json-output /tmp/spotify_api_benchmark.json` | PASS；无 hot P95 超过 500ms，`/api/billboard/data` hot P95 0.20s，`/api/dashboard/full` hot P95 0.16s |
| Runtime resource | `.venv/bin/python scripts/runtime_resource_probe.py --backend-url http://127.0.0.1:8000 --frontend-url http://localhost:5173 --preview-url http://127.0.0.1:4173 --max-total-rss-mb 1200 --max-total-cpu-percent 200 --fail-on-missing` | PASS；总 RSS 826.4MB，总 CPU 77.7%；backend 630.2MB / 77.7%，frontend 120.2MB / 0%，preview 76.0MB / 0% |
| 前端 dev smoke | route / interaction / chart / control inventory / long-list / cross-browser | 全部 PASS；control inventory 38 组合 / 1613 控件 / 0 violation；long-list 7/7，其中 Year-End 当前为 50 行 capped 单页验收；Chromium/Firefox/WebKit PASS |
| 前端 production preview smoke | route / interaction / chart / control inventory / long-list / cross-browser | 全部 PASS；control inventory 38 组合 / 1612 控件 / 0 violation；Chromium/Firefox/WebKit PASS |
| Production Web Vitals | `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000 --max-lcp-ms 3000 --max-cls 0.01 --max-tbt-ms 100 --max-resource-count 120 --max-encoded-resource-kb 11000 --max-scroll-overflow-px 0` | PASS；首页保留 ECharts，desktop LCP 2060ms / CLS 0 / TBT 0ms / 17 resources / 1131.2KB，mobile LCP 612ms / CLS 0 / TBT 0ms |
| ngrok HTTPS tunnel | `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173` + `curl http://127.0.0.1:4040/api/tunnels` | PASS；代理变量存在时 ngrok 会报 `ERR_NGROK_9009`，清空代理后固定域名 tunnel 可建立 |
| Spotify OAuth ngrok 初段/回跳 | 外部 `/api/health`、`/api/spotify/auth/status`、`/api/spotify/auth/data`、`/api/spotify/auth/login`、invalid-state callback | PASS；login URL 使用 `redirect_uri=https://stuffing-nebula-tamer.ngrok-free.dev/api/spotify/auth/callback`；invalid-state callback 307 回跳 `https://stuffing-nebula-tamer.ngrok-free.dev/settings?spotify_error=invalid_state` |
| 2026-06-28 ngrok/OAuth 当前态复核 | `ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173` + `.venv/bin/python scripts/spotify_oauth_external_probe.py --json-output /tmp/spotify_oauth_external_probe.json` | PASS；4040 API 显示固定域名转发到 `http://localhost:5173`；外部 health 200 且有 `X-Request-ID`；Spotify status 200 且 `connected=true`；auth data 200，返回 artists/tracks/recently_played/followed_artists/playlists；login URL 指向 `accounts.spotify.com` 且使用 ngrok callback、state 和 code_challenge 均存在；invalid-state callback 307 回跳 ngrok settings 并带 `X-Request-ID`；探针结束后已停止 ngrok |
| 2026-06-28 fresh OAuth consent 人工闭环 | 用户从 ngrok 设置页点击 Spotify 登录并同意授权；随后运行 `.venv/bin/python scripts/spotify_oauth_external_probe.py --json-output /tmp/spotify_oauth_external_probe_after_consent.json` | PASS；用户确认人工授权成功；复核探针显示固定域名 tunnel 可达、外部 health 200、Spotify status `connected=true`、auth data 可读、login URL 仍使用 ngrok callback、invalid-state callback 仍回跳 ngrok settings 并带 `X-Request-ID` |
| 脚本/质量门 | focused script tests、`test_fullstack_verification_check_script.py`、`.venv/bin/pre-commit run --all-files`、`sh scripts/fullstack_verification_check.sh ... --web-vitals --resource-snapshot` | 相关脚本单测 PASS；pre-commit ruff / ruff format / mypy / detect-secrets PASS；完整 fullstack verification 最终 PASS |

## Chrome 崩溃说明

本轮验证中，Codex 沙箱内由 Node 拉起系统 `/Applications/Google Chrome.app` 时出现一次 macOS crash report，栈停在 `HIServices/TransformProcessType` 并由 Chrome 自身 `abort()`。该崩溃发生在浏览器注册/启动阶段，不是前端页面 JavaScript 崩溃。

后续使用 Playwright 的 `chromium_headless_shell-*` 并运行同一类 CDP smoke，dev/prod-preview route smoke、production chart interaction smoke 与 control inventory 均通过，因此该事件按测试运行器/系统浏览器启动异常记录，不作为应用缺陷。为避免后续默认脚本再次优先命中系统 Chrome，`scripts/lib/chrome_executable.mjs` 已把 Playwright headless shell / Chrome for Testing 放在系统 Chrome 之前；当前不带 `CHROME_PATH` 的最小 CDP 启动已验证默认解析到 headless shell 并返回 `HeadlessChrome/148.0.7778.96`。

## 剩余风险

- Playwright WebKit 仍只能代表 Safari-family 引擎 smoke，不等同用户真实 Safari.app 手工会话。
- 生产构建仍提示动态大 chunk：`EChartsTheme` 仍服务于分析/详情等复杂图表页，OpenCC `cn2t` 字典仍是用户切换繁体时按需加载的大字典；它们已不再属于首页 Dashboard 的 preload 依赖。

## 完成度审计

| 目标要求 | 当前证据 | 判定 |
| --- | --- | --- |
| 在正确分支继续 | `git branch --show-current` 为 `fix/bugfixes-and-polish` | 已满足 |
| 后端所有现有测试通过 | `pytest backend/tests/ -q`：744 passed | 已满足 |
| API 端点与 OpenAPI 覆盖 | OpenAPI operation audit：136 operations / 0 unaccounted；API smoke 98/98；boundary 90/90；parameter boundary 60 obligations / 0 unaccounted | 已满足 |
| Provider 错误分层、response_model、基础设施 contract | 完整 fullstack verification 包含 pre-commit、Phase 5、OpenAPI audits、API probes 与 contract 测试；相关 response-model probes 已纳入测试基线 | 已满足 |
| 前端页面无白屏、无 console error/warning、无横向溢出 | dev/prod-preview route、interaction、chart、control inventory、long-list、Chromium/Firefox/WebKit smoke 均 PASS；control inventory 当前覆盖 38 组合；long-list 当前 7/7 | 已满足 |
| 性能量化与资源占用 | API benchmark 无 hot P95 >500ms；production Web Vitals 在资源预算内，首页 ECharts 版本 production preview desktop LCP 2060ms / CLS 0 / TBT 0ms、mobile LCP 612ms / CLS 0 / TBT 0ms；runtime resource probe 总 RSS 826.4MB / CPU 77.7% | 已满足 |
| 文档与交付报告 | README、AGENTS、CLAUDE、backend/CLAUDE 与本报告已同步最新测试基线、修复项、性能数据和 10 分钟复核步骤 | 已满足 |
| 真实 ngrok HTTPS + Spotify 外部 OAuth 浏览器授权闭环 | 本地 OAuth PKCE contract、Spotify auth JSON 端点、login ngrok redirect_uri、invalid-state callback ngrok origin、外部 HTTPS health/status/data/login 入口均已验证；2026-06-28 固定域名 tunnel 已可建立，用户已在真实浏览器中完成人工 Spotify 登录/同意授权，复核探针显示外部 status 为 `connected=true` 且 auth data 可读 | 已满足 |
| 生成代码提交 | 本轮修复按功能拆分提交，分支领先远端；未执行 push | 已满足本地提交要求 |

## 10 分钟快速复核

1. 运行 `.venv/bin/python scripts/quickstart_smoke.py --json-output /tmp/spotify_quickstart_timing.json`，确认 8000/5173 默认启动链路可用。
2. 打开 `http://localhost:5173/analysis/behavior`，确认地址最终为 `/analysis/stats` 且页面出现 `播放统计`。
3. 在 390px 移动宽度重复访问 `/analysis/behavior`，确认无横向滚动。
4. 运行 `node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --api-base-url http://127.0.0.1:8000 --routes /analysis/behavior --viewport both --max-scroll-overflow 0 --fail-on-console-warning`；默认会优先使用 Playwright `chromium_headless_shell-*` / Chrome for Testing，如需指定浏览器再传 `--chrome` 或 `CHROME_PATH`。
5. 访问首页 `/`，确认“月度播放趋势”仍正常显示；需要量化资源体积时，用生产 preview 跑 `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes / --viewport both --wait-ms 5000`。
6. 访问 `/account`，确认账号 Hero 先显示，收藏/习惯内容随后填充；需要量化 LCP 时用 `node scripts/frontend_web_vitals_probe.mjs --base-url http://127.0.0.1:4173 --api-base-url http://127.0.0.1:8000 --routes /account --viewport both --wait-ms 5000`。
7. 如需复核外部 OAuth 初段，先运行 `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173`，再运行 `.venv/bin/python scripts/spotify_oauth_external_probe.py --json-output /tmp/spotify_oauth_external_probe.json`；该探针不会交换真实授权 code，如需重新验证 fresh consent，仍需浏览器人工点击。
7. 运行 `sh scripts/phase5_check.sh`，确认最低验证矩阵仍全绿。
