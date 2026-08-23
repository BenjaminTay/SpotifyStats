# SpotifyStats 项目工作约定

本文档是 AI 与开发工具共用的当前项目速查。`AGENTS.md` 与 `CLAUDE.md` 必须保持完全一致；详细规则只在对应参考文档维护，不在这里复制完整历史。

## 交流语言

始终使用中文与项目协作者交流。结论必须区分：已实现、已验证、依赖外部条件、仍有边界。

## 网络代理

访问 GitHub 等外网资源遇到网络问题时，可先设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及其小写变量为本机代理 `http://127.0.0.1:7897` / `socks5://127.0.0.1:7897`。若 Codex 命令出现 `connect EPERM`、DNS 或 registry 失败，还需检查 Codex 的 workspace network access 配置；修改后须重启 Codex Desktop。

## 文档阅读顺序

- 项目介绍与启动：[README.md](README.md)
- 文档地图：[docs/README.md](docs/README.md)
- 当前统计规则：[docs/reference/playback-stats-rules.md](docs/reference/playback-stats-rules.md)
- 音乐档案规则：[docs/reference/account-archive-statistics.md](docs/reference/account-archive-statistics.md)
- 元数据治理：[docs/reference/music-metadata-management.md](docs/reference/music-metadata-management.md)
- 流派与语言：[docs/reference/2026-07-04-artist-genre-taxonomy.md](docs/reference/2026-07-04-artist-genre-taxonomy.md)、[docs/reference/artist-language-statistics.md](docs/reference/artist-language-statistics.md)
- 导入健康：[docs/reference/data-import-and-health.md](docs/reference/data-import-and-health.md)
- 生产运行：[deploy/production/README.md](deploy/production/README.md)
- 交付证据：[docs/reports/README.md](docs/reports/README.md)

## 项目定位

SpotifyStats 是本地优先的单用户 Spotify Extended Streaming History 分析应用：FastAPI 后端 + React 前端 + SQLite。原始播放记录、账号导出、数据库、封面和备份默认属于本地数据，不得提交到 Git 或打入镜像。

## 当前产品边界

- `/` 是个人音乐头版，不再是旧版播放统计 Dashboard；首页事实由确定性后端生成，不因打开首页触发年度或 Billboard 冷构建。
- 顶级入口使用“播放分析”，二级顺序固定为“播放统计 / 播放排行 / 年度总结 / 播放记录 / 音乐档案”。
- `/account` 的产品名称是“音乐档案”；旧人格、chemistry、Habits、Marquee、粉丝等级和旧重型 account 聚合不得恢复。
- `/yearly-review` 是自有年度总结唯一消费入口；官方 Wrapped 仅保留兼容数据和只读接口，不新增消费 UI。
- 音乐查找使用 Quick Open + `/music/search` 两阶段链路：候选索引与完整统计快照分离，搜索 GET 不得冷建 lifetime 播放统计或完整 Billboard。
- 音乐详情首屏使用摘要与播放统计并行加载，其他子视图进入页签后按需请求；歌曲歌词、专辑发行档案、艺人发行周期和艺人生涯暂不作为前端消费入口，旧页签深链回到播放统计。
- Phone、Compact、Desktop 使用互斥 presentation，但共享 URL、Query、过滤指纹、统计事实和实体深链。Phone 主要触控目标至少 44×44px，宽表和重图表不得与桌面 DOM 同时挂载。

## 统计和数据原则

- 播放次数与收听时长是两条轨道：逻辑事件贡献次数，推断收听区间切片贡献时长。
- 连续同曲合并使用服务端 `max_merge_gap_minutes`，默认边界和时间归属以 `playback-stats-rules.md` 为准，前端不得维护独立默认值。
- L2/L3 专辑统计必须使用 album project membership；source album 只用于来源拆分解释。
- 艺人统计必须使用有效曲目署名、canonical artist 和稳定逻辑事件去重；featured artist 不得未经规则 fan-out。
- 元数据人工治理不得重写原始 `plays`、`tracks`、`track_artists`，必须通过独立覆盖层、revision 和审计事件实现。
- 语言和流派事实必须保留 unknown、未归属时长及审核边界，不得使用艺人名称或 genre 做启发式补齐。
- Billboard 只发布完整结束的榜单周；最新播放所在的覆盖边缘周不生成周榜或派生成绩，但其播放仍计入非榜单统计。

## AI 边界

- AI 报告和问答采用 cache-first / 手动生成，不因打开页面自动调用 LLM。
- 年度视觉报告默认使用 `visual_yearly_artifact` 与 `agent_synthesis_v2`；图表数据、统计事实和校验必须来自确定性后端 builder/validator，LLM 不生成事实或图表数据。
- Agent 只能调用后端注册的 read-only 工具，禁止任意 SQL、任意 URL、设置/导入/缓存/歌单写入和未审核路由透传。
- LLM API Key 永不返回前端；日志必须经过敏感信息脱敏。

## 后端约束

- 新增外部 HTTP 必须经过 `HttpClient` 或对应 Provider，业务 service 不得直接新增 `urllib.request.Request`/`urlopen`。
- 环境变量统一从 `backend/core/config.py` 读取，业务代码不得直接 `os.getenv()`。
- 昂贵计算使用规范化 wrapper、缓存和 `singleflight()`，不得在热路径恢复逐行 `apply(axis=1)`、`iterrows()` 或整表重复扫描。
- 串流导入同步更新音乐查找候选索引，六套精确统计快照通过后台队列继续构建；warming 期间不得回退到搜索 GET 冷建或虚假 0。
- 开发后端使用 `uvicorn backend.main:app --reload --reload-dir backend`，避免扫描 `.venv`、`node_modules` 和 `data`。

## 前端约束

- 所有 GET 数据通过 TanStack Query 和 `queryKeys` 获取，禁止模块级 Map 缓存 API 响应。
- 页面容器只做路由入口，业务内容放在 `features/`；新增长列表必须分页、分段、无限查询或虚拟化。
- ECharts 必须通过 `LazyEChart` 按需加载；外部 Markdown 必须使用 `react-markdown` + `rehype-sanitize`。
- 简繁转换使用 `displayName()` 和按需 OpenCC 子包，不得模块初始化时加载完整大字典。
- 新页面必须遵守 [frontend/UI_STYLE_GUIDE.md](frontend/UI_STYLE_GUIDE.md) 和移动端真实视口/浏览器验收矩阵。

## 生产部署边界

- `DEPLOYMENT_MODE=full|showcase|dual` 只决定 loopback Web 网关；Backend 不映射宿主公网端口。
- 3000、3001、3002、8000 不得直接开放公网；完全版外部入口必须另有身份边界，公开展示入口是持链接者可访问，不等于整站认证。
- `data/`、备份和密钥不得进入镜像；发布必须使用 commit SHA、Online Backup、三模式门禁、健康检查和联合回滚。
- 搜索六变体首次冷建只能在明确数据库副本执行；正常发布必须精确复用 ready snapshot，源数据漂移时拒绝替换。
- Tailscale、域名代理和外部 HTTPS 入口是部署外层，脚本不得擅自启用或关闭。

## 验证入口

- 后端：`.venv/bin/pytest -m unit -q`、`.venv/bin/pytest -m contract -q`
- 前端：`cd frontend && npm test`、`cd frontend && npm run build`
- 文档：`python3 scripts/docs_audit.py`
- Phase 5：`sh scripts/phase5_check.sh`
- 全栈：`sh scripts/fullstack_verification_check.sh --backend-url http://127.0.0.1:8000 --frontend-url http://127.0.0.1:5173`

只读审计、真实数据库探针、浏览器验收和生产发布证据必须分别报告，不得把本地单元测试描述成真实部署已通过。

## 文档和 Git 约定

- 规则写入 `docs/reference/`，未完成路线写入 `docs/plans/`，设计决策写入 `docs/designs/`，交付证据写入 `docs/reports/`，已完成或取代内容写入 `docs/archive/`。
- 新增或移动文档后更新 [docs/README.md](docs/README.md)，并运行文档审计。
- 未经明确要求不执行 `git commit` 或 `git push`。
- 若用户明确要求提交，先检查 README、AGENTS、CLAUDE、docs 地图和 CHANGELOG 是否需要同步，再运行 `git diff --check`、测试和项目 hooks。
