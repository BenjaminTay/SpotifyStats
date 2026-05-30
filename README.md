# Spotify Stats

从 Spotify 官方导出的 Extended Streaming History 及账号数据中导入播放记录，提供多维度交互式统计分析仪表盘。

**架构**：FastAPI 后端 + React 前端。Streamlit 原有应用已冻结维护。

## 功能

- **总览仪表盘** — KPI 卡片、月度趋势、平台分布、周热力图、动态数据洞察
- **播放分析** — stats.fm 风格统计：8 KPI + 日历趋势 + 听歌时钟 + 个人排行榜（歌曲/专辑/艺人 × 次数/时长）+ 自定义时间范围
- **年度回顾** — 自定义 Wrapped 总结（听歌人格识别 6 型、曲风五大洲全景、发现与回归、聆听深度金字塔、特殊时刻、年度对比）+ 官方 Wrapped 数据
- **Billboard 周榜** — 12 子 Tab：周榜、每周榜首、单曲/艺人/专辑历史、走势总榜 Power Score、总榜、榜单记录、对决、发行周期分析
- **音乐实体详情** — 歌曲/专辑/艺人全局页面，整合个人播放统计、Billboard 成绩、Genius 歌词、Wikipedia 百科
- **账号中心** — 收藏分析（生命周期、化学反应、品味迁徙、Flip Side）+ 搜索编年史、粉丝层级、播客、视频分析
- **设置** — Spotify OAuth 连接管理、LLM 翻译配置（多提供商 + 档案管理）、数据过滤、版本合并、数据导入
- **Spotify Web API** — OAuth PKCE 授权，回填收藏日期、Top 排行、最近播放、播放列表、实时播放状态

## 快速开始

```bash
# 安装
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 启动后端（端口 8000）
uvicorn backend.main:app --reload --reload-dir backend

# 启动前端（端口 5173，自动代理 /api → 后端）
cd frontend && npm run dev

# Spotify OAuth 需要 HTTPS，开发环境用 ngrok
ngrok http --url=stuffing-nebula-tamer.ngrok-free.dev 5173

# 测试
pytest backend/tests/ -v          # 后端 244 个测试（unit/contract/integration）
cd frontend && npm test           # 前端 20 个 vitest 单测

# 代码质量
ruff check backend/ && ruff format --check backend/
pre-commit run --all-files
```

首次启动自动导入 JSON 数据到 SQLite。浏览器打开 `http://localhost:5173` 使用 React 界面，`http://localhost:8000/docs` 查看 API 文档。

## 技术栈

**后端**：FastAPI · Pandas · SQLite (WAL) · Pydantic v2 · pytest (244 tests) · Ruff · Mypy

**前端**：React 19 · TypeScript 6.0 · Vite 8 · Tailwind CSS v4 · shadcn/ui · React Router v7 · TanStack React Query · ECharts 6 · Vitest

**基础设施**：AES-256-GCM 加密 · OAuth PKCE · 统一 Cache Manager (LRU+TTL) · 版本化 Migration · 后台 Job Queue · OpenAPI 自动生成类型

## 项目结构

```
SpotifyStats/
├── backend/           # FastAPI 后端（api/ → services/ → domains/ → core/）
├── frontend/          # React 前端（components/ | pages/ | hooks/ | lib/）
├── app/               # Streamlit 旧应用（冻结维护）
├── data/              # SQLite 数据库 + JSON 源数据
├── docs/              # 架构文档
├── scripts/           # 工具脚本（性能基准、封面下载等）
└── requirements.txt
```

## 详细文档

- 后端架构细节见 [`backend/CLAUDE.md`](backend/CLAUDE.md)
- 前端架构细节见 [`frontend/CLAUDE.md`](frontend/CLAUDE.md) 和 [`frontend/README.md`](frontend/README.md)
- UI 风格指南见 [`frontend/UI_STYLE_GUIDE.md`](frontend/UI_STYLE_GUIDE.md)
- 数据目录说明见 [`data/README.md`](data/README.md)
- 架构优化文档见 [`docs/2026-05-30-architecture-optimize.md`](docs/2026-05-30-architecture-optimize.md)

## License

MIT
