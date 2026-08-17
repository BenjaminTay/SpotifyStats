# SpotifyStats 双运行面实施规划

> 状态：历史归档；当前入口见 `docs/archive/06-productization-closeout/README.md`

日期：2026-08-13  
状态：已实施，最终证据见
`../../reports/2026-08-13-dual-deployment-profile-delivery.md`

## 目标与非目标

目标是让同一次 GitHub 发布在不复制仓库、不维护长期分支、不分叉数据库 schema 的
前提下，按部署配置提供：

- `private-admin`：完整设置、导入、编辑、AI 和 Spotify 连接能力；
- `public-readonly`：只开放批准的个人音乐数据浏览与无副作用计算。

非目标包括：在模式切换时自动操作 Tailscale、自动申请域名、开放宿主后端端口，或
让多台服务器通过网络文件系统共享 SQLite。

## 事实基线

实施前已有两个 loopback Web 网关、运行面 Header、公共 Nginx 防御规则和前端能力
发现，但存在以下缺口：

1. 公共和私人网关依赖网络入口命名，没有正式 deployment mode；
2. 运行面 Header 没有独立的可信网关凭据；
3. 自动部署总会启动两个 Web 容器，不能保持运维人员选择；
4. 公共 API 仍需要从已知敏感路径阻断收口到显式白名单；
5. 缺少公共请求数据库只读防线和双模式 CI 矩阵。

## 实施阶段

### 1. 版本化能力与后端策略

- 用 Git commit SHA 表示代码发布版本；
- 用 access policy version 表示运行面策略版本；
- 每个 OpenAPI operation 显式分类，新接口默认私有；
- 公共运行面只允许公开读取和批准的安全计算；
- 能力发现返回运行面和细粒度功能开关。

### 2. 可信网关

- Nginx 强制覆盖运行面 Header；
- 增加只存在于生产 `.env` 的网关随机密钥；
- Backend 在生产默认拒绝未经过可信网关的请求；
- Nginx 通过 runtime template 注入密钥，构建产物不含密钥。

### 3. 公共只读数据连接

- 公共请求的数据连接启用 SQLite `PRAGMA query_only = ON`；
- 已存在精确缓存可读取，但公共请求不得触发年度冷构建、AI、元数据补全、封面下载
  或后台任务；
- 完全版继续使用正常读写连接。

### 4. 前端能力守卫

- Desktop、Compact、Phone 共用运行时 capability manifest；
- 公共运行面不挂载设置、AI、编辑、导入、生成和治理入口；
- 直接输入私有路由时安全跳转；
- capability 请求失败时 fail closed；后端仍是最终权限边界。

### 5. 部署模式

- `full` 启动 `backend + web`；
- `showcase` 启动 `backend + public-web`；
- `dual` 启动 `backend + web + public-web`；
- 一条命令切换模式，失败恢复原模式；
- 模式命令只管理 loopback Docker 服务，不管理外部入口。

### 6. 自动发布与验收

- 一次构建产出同一 SHA 的 API/Web 镜像；
- CI 静态验证三种 Compose profile；
- push main 只更新服务器当前模式；
- 发布验证数据库完整性、健康、运行面、loopback 和公共写阻断；
- 发布失败恢复上一 SHA 和模式。

## 数据拓扑约束

当前支持的是一台服务器、一个 Backend、一个宿主 SQLite 数据目录、两个 Web 网关。
Web 网关本身不持有数据库连接。

若未来部署到多台服务器：

- 不得用 NFS/SMB/双向同步共享在线 SQLite；
- 纯展示节点可接收单向生成、裁剪并原子替换的只读 SQLite 快照；
- 需要实时多节点读写时迁移 PostgreSQL，并重新设计 migration、备份、连接池和任务锁。

## 完成定义

- 三种模式可以快速切换，非目标网关停止；
- 同一 SHA、同一 Backend、同一 schema 支持两个运行面；
- 伪造 Header 或绕过网关不能升级权限；
- 公共运行面无业务写入副作用；
- GitHub 自动部署保持服务器当前模式；
- 文档明确区分容器运行面与外部网络入口。
