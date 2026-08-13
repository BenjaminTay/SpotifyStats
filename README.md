# Spotify Stats

个人 Spotify 播放历史档案：把 Spotify 导出的播放记录和账号数据导入本地 SQLite，在个人音乐头版中回看近期变化，再深入播放分析、年度总结、个人 Billboard 榜单和音乐实体详情。

[![Phase 5 Baseline](https://github.com/BenjaminTay/SpotifyStats/actions/workflows/phase5-baseline.yml/badge.svg)](https://github.com/BenjaminTay/SpotifyStats/actions/workflows/phase5-baseline.yml)

**技术架构**：FastAPI 后端 + React 前端。项目是本地优先的单用户工具，不提供公共在线 Demo；你的播放历史和账号数据默认只保存在本机。

**移动网页**：`<768px` 使用独立 Phone presentation（Top Bar、Bottom Nav、栏目 Sheet、纵向榜单和触控图表），`768–1023px` 为 Compact，`>=1024px` 保留桌面工作台。手机和 PC 共用路由、API、过滤口径与排名事实；数据导入、元数据治理、凭据和系统维护仍建议在电脑端完成。

**App 化状态**：已完成可安装 PWA 基线（主屏幕图标、standalone、安装引导与不缓存个人数据的离线说明），并建立单用户私人云生产配置。生产容器只在服务器 loopback 暴露 Web，由 Tailscale Serve 向私人 tailnet 提供 HTTPS；个人数据通过宿主持久目录迁移，不进入 Docker 镜像或镜像仓库。路线继续按私有部署 → 手机真机验收 → Capacitor 决策推进，详见 [`docs/plans/2026-08-06-appification-pwa-capacitor-plan.md`](docs/plans/2026-08-06-appification-pwa-capacitor-plan.md)。

## 你可以用它做什么

- **个人音乐头版**：用真实播放记录生成每日头条、音乐档案、最近 4 周、最新个人 Billboard、年度年鉴入口与旧爱重听；Desktop 与 Phone 使用各自的编辑式编排
- **播放统计**：播放趋势、听歌时段、歌曲/专辑/艺人排行和播放记录
- **年度总结**：Desktop/Compact 与 Phone 共用同一套八章年度事实和后台预生成链路；桌面呈现完整杂志年鉴，Phone 使用独立“口袋音乐年鉴”编排、纵向时间线、章节 Sheet 与无宽表的全屏榜单。切换页面不会重置等待时间，页面只保留自有年度总结
- **个人 Billboard**：歌曲、专辑、艺人周榜与年榜、走势总榜、榜单记录、对决和发行周期分析
- **音乐详情**：歌曲、专辑和艺人详情，整合个人播放统计、榜单成绩、歌词与百科信息
- **账号分析**：收藏、歌单、搜索历史、播客和视频等 Spotify Account Data 分析
- **AI 洞察**：缓存优先的周报、月报、年度叙事和自然语言问答；需要自行配置 LLM
- **数据管理**：Spotify OAuth、数据过滤、版本归并、曲目署名、艺人身份和流派/语言审核

## 快速开始

### 1. 准备 Spotify 数据

从 [Spotify 隐私设置](https://www.spotify.com/account/privacy/) 请求 **Extended Streaming History** 和 **Account Data**。下载并解压后，将文件放入：

```text
data/
├── streaming/    # Streaming_History_Audio_*.json
└── account/      # Wrapped、YourLibrary、Playlist、SearchQueries 等 JSON
```

完整的文件清单和字段说明见 [`data/README.md`](data/README.md)。

### 2. 安装依赖

建议使用 Python 3.9+ 和 Node.js 22+：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm ci
cd ..
```

### 3. 启动应用

在两个终端分别运行：

```bash
# 终端一：后端，http://localhost:8000
source .venv/bin/activate
uvicorn backend.main:app --reload --reload-dir backend
```

```bash
# 终端二：前端，http://localhost:5173
cd frontend
npm run dev
```

首次启动只会创建或迁移 SQLite 数据库，不会自动导入个人 JSON。打开前端后，进入「设置 → 数据导入」，先运行只读的「导入前检查」，再手动导入 Streaming History 和 Account Data；导入完成后可在同一区域查看「数据健康」报告。检查范围与状态含义见 [`docs/reference/data-import-and-health.md`](docs/reference/data-import-and-health.md)。

浏览器访问 `http://localhost:5173`，API 文档访问 `http://localhost:8000/docs`。

查看手机效果时，可直接把浏览器响应式视口切换到 390×844，或缩窄到 768px 以下；完整发布矩阵可运行：

```bash
node scripts/frontend_route_smoke.mjs \
  --base-url http://localhost:5173 \
  --api-base-url http://127.0.0.1:8000 \
  --viewport matrix \
  --max-scroll-overflow 0 \
  --fail-on-console-warning
```

### Docker 部署

```bash
docker compose build
docker compose up -d
```

Docker 部署后，前端访问 `http://localhost:3000`，后端访问 `http://localhost:8000`。Spotify OAuth、LLM 和封面/百科增强需要额外配置环境变量，详见开发文档。

### 个人私有云部署

单用户长期运行使用 [`deploy/production/`](deploy/production/README.md) 中的独立生产配置：API 只存在于 Docker 私网，Web 只绑定服务器 `127.0.0.1:3001`，再由 Tailscale Serve 提供仅私人 tailnet 可达的 HTTPS PWA。不要启用 Tailscale Funnel，也不要把 3000、8000 或 3001 开放到公网。

`.dockerignore` 会排除整个 `data/` 和备份目录；SQLite 必须使用 Online Backup API 生成一致性副本后单独迁移。生产脚本提供每日备份、完整性检查、显式恢复、SHA 镜像发布和失败回滚。首次部署与手机验收步骤见生产目录说明。

## 数据与隐私

播放历史可能包含精确时间、IP 地址和账号信息。`data/streaming/`、`data/account/`、SQLite 数据库和封面缓存均属于本地运行数据，已加入 `.gitignore`，请勿将真实导出文件提交到 GitHub。

导入完成后，应用会在本地构建播放统计和 Billboard 所需的派生数据。若已有数据的封面、专辑关系或专辑榜不完整，可运行：

```bash
.venv/bin/python scripts/refresh_import_derived_data.py \
  --json-output /tmp/spotify_import_maintenance.json
```

Spotify OAuth 需要 HTTPS。开发环境可使用 ngrok；具体配置和外部验证步骤见项目文档。

## 开发与测试

```bash
# 后端单元测试与契约测试
source .venv/bin/activate
pytest -m unit -q
pytest -m contract -q

# 前端测试与生产构建
cd frontend
npm test
npm run build
```

完整命令、架构约束和 CI 验证矩阵见 [`CLAUDE.md`](CLAUDE.md)。

## 技术栈

- **后端**：FastAPI、Pandas、SQLite、Pydantic、pytest、Ruff、Mypy
- **前端**：React、TypeScript、Vite、Tailwind CSS、React Router、TanStack React Query、ECharts、Vitest
- **数据与基础设施**：SQLite WAL、版本化 Migration、OAuth PKCE、后台任务队列、缓存管理、GitHub Actions

## 项目结构

```text
SpotifyStats/
├── backend/          # FastAPI API、业务服务和领域逻辑
├── frontend/         # React 页面、组件、Hooks 和 API 类型
├── data/             # 本地 JSON 输入、SQLite 数据库和运行时缓存
├── scripts/          # 导入、维护、验证和性能检查脚本
├── docs/             # 规则、架构、计划、报告和历史归档
└── requirements.txt
```

## 文档

- 数据准备与 JSON 字段说明 → [`data/README.md`](data/README.md)
- 文档地图与项目资料 → [`docs/README.md`](docs/README.md)
- 前端开发说明 → [`frontend/README.md`](frontend/README.md)
- UI 风格指南 → [`frontend/UI_STYLE_GUIDE.md`](frontend/UI_STYLE_GUIDE.md)
- 变更日志 → [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

## License

MIT
