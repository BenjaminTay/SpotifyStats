# 开发与维护指南

面向修改源码、验证改动和维护部署的协作者。日常使用与数据导入见[使用指南](docs/user-guide.md)；开始开发前先查看[当前事项与负责人](docs/DEVELOPMENT_STATUS.md)。

## 环境与开发启动

使用 Python 3.9+、Node.js 22.x（最低 22.13.0，建议安装 22.x 最新维护版本）。依赖安装见[环境准备](docs/user-guide.md#准备环境)，更新现有环境见[更新项目](docs/user-guide.md#更新项目)，Spotify 应用及授权前提见[Spotify连接](docs/user-guide.md#spotify-连接)。项目根目录为后端命令的工作目录；前端命令在 `frontend/` 执行。

在两个终端分别启动：

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --reload-dir backend
```

```bash
cd frontend
npm run dev
```

前端为 <http://localhost:5173>，API 文档为 <http://localhost:8000/docs>。后端 reload 仅扫描 `backend/`，避免监听依赖和数据目录。

日常入口使用 `scripts/start_daily.py`；开发入口使用 reload 和 Vite dev。日常入口只绑定 loopback、采用 minimal 预热并复用前端正式构建。`--build` 会在构建成功后保存前端输入清单；普通 `npm run build` 不生成该清单，日常入口会要求执行一次 `--build`。端口冲突时退出，不停止已有服务；`Ctrl-C` 只结束该入口创建的两个进程。

## 架构与代码入口

后端采用 FastAPI、Pandas、SQLite 与 Pydantic；前端采用 React、TypeScript、Vite、Tailwind CSS、TanStack Query 与 ECharts。Python 依赖以 [requirements.txt](requirements.txt) 及其引用的子清单为准，子清单变化同样需要从根清单重新安装；前端依赖声明与锁定版本分别见 [package.json](frontend/package.json) 和 [package-lock.json](frontend/package-lock.json)。

```text
SpotifyStats/
├── backend/          # API、服务、领域逻辑与基础设施
├── frontend/         # React 页面、组件、查询和类型
├── data/             # 个人输入与运行时数据
├── scripts/          # 维护、验证与性能工具
├── deploy/           # 本地及生产运行配置
└── docs/             # 使用、规则、计划、报告和归档
```

- [后端架构与开发](backend/README.md)：依赖注入、数据访问、服务／领域划分、外部调用与测试。
- [前端架构与开发](frontend/README.md)：路由、数据获取、页面组织和交互约束。
- [UI风格指南](frontend/UI_STYLE_GUIDE.md)：设计系统及多端布局。
- [当前技术参考](docs/README.md#维护者与共用参考)：统计、元数据、缓存和AI运行合同。
- [数据格式参考](data/README.md)：JSON字段、导入管线及运行文件。

## 按改动验证

先选受影响范围；工具用途、局部与完整门禁的判定见[验证规则](docs/reference/fullstack-verification.md#按改动选择验证范围)。

```bash
# 后端单元与契约入口；实际开发可先选择相关测试文件
.venv/bin/pytest -m unit -q
.venv/bin/pytest -m contract -q

# 前端入口
cd frontend
npm test
npm run build
```

需要浏览器验收时，按[验证工具入口](docs/reference/fullstack-verification.md#验证工具入口)选择路由、交互、图表和多浏览器范围。例如后端与前端已启动时，在根目录检查移动视口：

```bash
node scripts/frontend_route_smoke.mjs \
  --base-url http://localhost:5173 \
  --api-base-url http://127.0.0.1:8000 \
  --viewport matrix \
  --max-scroll-overflow 0 \
  --fail-on-console-warning
```

文档改动执行 `python3 scripts/docs_audit.py --include-archive` 和 `git diff --check`，同时核对读者定位、内容迁移和受影响链接。修改审计脚本时再运行 `python3 -m unittest scripts.tests.test_docs_audit`。测试数据库与派生文件必须遵守[测试隔离规则](docs/reference/backend-test-isolation.md)。

## 协作与提交

一个问题链维护唯一负责人和活跃分支，复用现有工作树，保护无关未提交改动。当前状态、优先级、下一步和核验日期只维护在总表；台账保存问题身份与判断，报告保存过程证据。具体整合、恢复与收尾见[交付规则](docs/reference/development-delivery-workflow.md)。

提交标题采用 Conventional Commits，小写英文类型前缀和可选scope，冒号后使用中文摘要，例如 `docs: 按读者整理项目文档入口`。复杂提交在空行后说明背景、关键变化、影响边界与实际验证。提交前核对staged diff与相关文档，执行差异检查、必要验证和项目hooks。Agent未经明确要求不提交或推送。

## 文档职责与命名

- 项目首页用于向使用者介绍产品；操作放使用指南，开发细节放本文及各模块README，运维操作放生产手册。
- `AGENTS.md`／`CLAUDE.md` 是Agent指令入口。共享规则在技术参考中维护，开发者无需依赖Agent文件查找架构。
- 长期维护的台账、当前规则和滚动路线采用稳定主题文件名，创建及修订日期写入正文。冻结方案、发布／验收报告和历史归档保留日期；有实际合同含义的版本号保留。
- 每份文档围绕一个主要用途组织。迁移内容后更新入链和章节锚点，不复制出人类与Agent两套事实；文档总导航在[文档地图](docs/README.md)。

## 部署与数据保护

本地Docker运行、长期部署、网关、备份与回滚由[生产手册](deploy/production/README.md)统一说明。个人播放记录、数据库、账号资料、封面和密钥不提交、不进入镜像。部署与实际线上验收分别记录，局部本地通过不能推定生产通过。
