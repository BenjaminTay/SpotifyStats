# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**架构**：FastAPI 后端 + React 前端。

## 功能

- **总览仪表盘** — KPI 卡片、月度趋势、平台分布、周热力图、动态数据洞察
- **播放分析** — stats.fm 风格统计：播放统计（8 KPI + 日历趋势 + 听歌时钟）+ 播放排行（歌曲/专辑/艺人 × 次数/时长）+ 年度总结 + 播放记录（狂热时刻/时间密码/个人王朝/长线陪伴/探索发现/行为奇观）+ 账号中心入口 + 自定义时间范围
- **专辑项目统计** — 标准版/豪华版、先行单曲和确认项目版本按合并级别计入同一 album project；专辑详情页提供原版、豪华版、单曲、精选集等来源拆分
- **年度总结** — 播放分析内的自定义 Wrapped 总结（听歌人格、主曲风、地区流行、语言分布、发现与回归、聆听深度、特殊时刻、年度对比）+ 官方 Wrapped 数据；消费展示通过版本化 taxonomy 将底层四轴事实整理为直观的 `style` 主曲风与 `scene` 地区流行，语言继续使用独立的已审核艺人事实，并保留“尚未归类”、多语言和纯器乐。`context` / `role` 仍保留在治理层，不进入年度主图；基于 genre heuristic 的 Music Map 暂不在消费页展示
- **Billboard 周榜 / 年榜** — 周榜、每周榜首、年度单曲/专辑/艺人榜、走势总榜 Power Score、总榜、榜单记录、对决、发行周期分析；总榜支持表内搜索、独立记忆的推荐字段配置与列宽调整，并展示专辑成员歌曲及艺人歌曲/专辑的跨层级点数和固定全榜排名；对决、总榜与实体详情共享同一统计设置和专辑项目/艺人身份口径
- **榜单社区** — 按当前榜单设置口径生成模拟社区动态、账号时间线和热议趋势，支持精选/全部、时间范围、搜索和帖子详情
- **音乐实体详情 / 查找** — 歌曲/专辑/艺人全局页面，整合个人播放统计、Billboard 成绩、Genius 歌词、Wikipedia 百科；只要当前口径下有有效播放，即使暂未入榜也可从 Masthead 搜索或 `/music/search` 打开完整详情。详情固定保留全部功能 Tab，实体主榜、成员单曲榜和专辑榜成绩独立显示或以精确空态降级；艺人与专辑 enrichment 会展示 Wikipedia/LLM 处理进度
- **账号中心** — 播放分析内的收藏分析（生命周期、化学反应、品味迁徙、Flip Side）+ 搜索编年史、粉丝层级、播客、视频分析
- **AI 洞察** — 自然语言听歌周报/月报/年度叙事 + 自由问答；报告为缓存优先、手动生成，年度叙事默认生成图文音乐年报 artifact，通过 Report Agent 多轮工具调用直接输出报告；图表数据由后端只读 builder 确定性生成；问答通过只读 Agent 工具查询播放、个人 Billboard、账号收藏、搜索历史和社区数据，并展示进度、证据、工具轨迹和 Markdown/表格回答
- **设置** — Spotify OAuth 连接管理、LLM 翻译配置（多提供商 + 档案管理）、数据过滤、数据导入；“音乐源数据管理”以“归并与版本 / 曲目署名 / 艺人身份 / 流派与语言”四个平级模块统一承载人工修订。归并工作区只提供一套 L1/L2/L3、自动检测、已保存分组和手动创建入口，并以对象类型区分歌曲与专辑版本；流派与语言模块继续负责来源置信度和证据审核。个人管理员选择稳定本地实体后可直接应用，无需填写理由/证据；底层 dry-run、revision、append-only 事件和可撤销 override 仍全局生效且不改写原始播放事实。单曲、专辑和艺人详情可精准深链并预填对应管理模块
- **Spotify Web API** — OAuth PKCE 授权，回填收藏日期、Top 排行、最近播放、播放列表、实时播放状态

## 快速开始

```bash
# 安装依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 启动后端（端口 8000）
uvicorn backend.main:app --reload --reload-dir backend

# 启动前端（端口 5173，自动代理 /api → 后端）
cd frontend && npm run dev
```

首次启动自动导入 JSON 数据到 SQLite。浏览器打开 `http://localhost:5173` 使用 React 界面，`http://localhost:8000/docs` 查看 API 文档。

Streaming History 导入会先写入基础播放事实，再自动刷新 Spotify 元数据、重建 album projects、重建 Billboard 预聚合并返回维护状态。若已经导入过新数据但封面、专辑关系或专辑榜缺失，可手动运行：

```bash
.venv/bin/python scripts/refresh_import_derived_data.py --json-output /tmp/spotify_import_maintenance.json
```

> Spotify OAuth 功能需要 HTTPS。开发环境可使用 ngrok：
> ```bash
> ngrok http --url=your-domain.ngrok-free.dev 5173
> ```
> 固定域名 tunnel 建立后，可运行非破坏性外部探针确认 OAuth 初段和回跳：
> ```bash
> .venv/bin/python scripts/spotify_oauth_external_probe.py --base-url https://your-domain.ngrok-free.dev --json-output /tmp/spotify_oauth_external_probe.json
> ```
> 该探针不会交换真实授权 code；如需重新验证 fresh consent，仍需在浏览器中人工点击 Spotify 同意授权。

### 运行测试

```bash
# 后端
source .venv/bin/activate && pytest backend/tests/ -v
pytest -m unit -q        # 单元测试
pytest -m contract -q    # 契约测试

# 前端
cd frontend && npm test
```

### Docker 部署

```bash
docker compose build
docker compose up -d
# 前端 → http://localhost:3000
# 后端 → http://localhost:8000
```

## 技术栈

**后端**：FastAPI · Pandas · SQLite (WAL) · Pydantic v2 · pytest · Ruff · Mypy

**前端**：React 19 · TypeScript · Vite · Tailwind CSS v4 · shadcn/ui · React Router v7 · TanStack React Query · ECharts 6 · Vitest

**基础设施**：AES-256-GCM 加密 · OAuth PKCE · Cache Manager (LRU+TTL) · 版本化 Migration · 后台 Job Queue · AI Task Orchestrator · OpenAPI 自动生成类型 · Request ID 链路追踪 · Provider 错误分类 · GitHub Actions CI

## 项目结构

```
SpotifyStats/
├── backend/               # FastAPI 后端（api/ → services/ → domains/ → core/）
├── frontend/              # React 前端
│   └── src/
│       ├── features/      # 业务组件（billboard/music/settings/account/ai-insights/ai-tasks/community）
│       ├── pages/         # 路由级页面容器（React.lazy 分包）
│       ├── components/    # ui/charts/layout/shared
│       ├── hooks/         # 自定义 Hooks
│       └── api/           # QueryClient + queryKeys + OpenAPI 类型
├── data/                  # SQLite 数据库 + JSON 源数据
├── docs/                  # 项目文档
├── scripts/               # 工具脚本
└── requirements.txt
```

## 文档索引

- 开发速查（命令 + 约束）→ [`CLAUDE.md`](CLAUDE.md)
- 完整项目上下文 → [`AGENTS.md`](AGENTS.md)
- 后端架构 → [`backend/CLAUDE.md`](backend/CLAUDE.md)
- 前端架构 → [`frontend/CLAUDE.md`](frontend/CLAUDE.md)
- UI 风格指南 → [`frontend/UI_STYLE_GUIDE.md`](frontend/UI_STYLE_GUIDE.md)
- 数据格式说明 → [`data/README.md`](data/README.md)
- 文档地图 → [`docs/README.md`](docs/README.md)
- 变更日志 → [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

## License

MIT
