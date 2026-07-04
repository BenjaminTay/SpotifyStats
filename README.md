# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**架构**：FastAPI 后端 + React 前端。原 Streamlit 应用（`app/`）已冻结维护。

## 功能

- **总览仪表盘** — KPI 卡片、月度趋势、平台分布、周热力图、动态数据洞察
- **播放分析** — stats.fm 风格统计：播放统计（8 KPI + 日历趋势 + 听歌时钟）+ 播放排行（歌曲/专辑/艺人 × 次数/时长）+ 年度总结 + 播放记录（狂热时刻/时间密码/个人王朝/长线陪伴/探索发现/行为奇观）+ 账号中心入口 + 自定义时间范围
- **专辑项目统计** — 标准版/豪华版、先行单曲和确认项目版本按合并级别计入同一 album project；专辑详情页提供原版、豪华版、单曲、精选集等来源拆分
- **年度总结** — 播放分析内的自定义 Wrapped 总结（听歌人格识别 6 型、曲风五大洲全景、发现与回归、聆听深度金字塔、特殊时刻、年度对比）+ 官方 Wrapped 数据
- **Billboard 周榜 / 年榜** — 周榜、每周榜首、年度单曲/专辑/艺人榜、走势总榜 Power Score、总榜、榜单记录、对决、发行周期分析
- **榜单社区** — 按当前榜单设置口径生成模拟社区动态、账号时间线和热议趋势，支持精选/全部、时间范围、搜索和帖子详情
- **音乐实体详情 / 查找** — 歌曲/专辑/艺人全局页面，整合个人播放统计、Billboard 成绩、Genius 歌词、Wikipedia 百科；可通过 Masthead 搜索图标或 `/music/search` 直接查找并打开详情页，结果展示与详情页口径一致的播放次数和个人 Billboard 摘要；艺人与专辑 enrichment 会展示 Wikipedia/LLM 处理进度
- **账号中心** — 播放分析内的收藏分析（生命周期、化学反应、品味迁徙、Flip Side）+ 搜索编年史、粉丝层级、播客、视频分析
- **AI 洞察** — 自然语言听歌周报/月报/年度叙事 + 自由问答；报告为缓存优先、手动生成，年度叙事默认生成图文音乐年报 artifact，并通过 Editorial Agent 写作流水线完成研究简报、故事规划、长文撰写、编辑、事实核对和口味评分；图表数据仍由后端只读 builder 确定性生成；问答通过只读 Agent 工具查询播放、个人 Billboard、账号收藏、搜索历史和社区数据，并展示进度、证据、工具轨迹和 Markdown/表格回答
- **设置** — Spotify OAuth 连接管理、LLM 翻译配置（多提供商 + 档案管理）、数据过滤、版本合并、数据导入
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
├── app/                   # Streamlit 旧应用（冻结维护）
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
