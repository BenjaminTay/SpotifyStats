# SpotifyStats 双运行面交付报告

日期：2026-08-13  
范围：后端访问策略、公共只读连接、前端能力守卫、生产部署模式、CI 门禁与文档

## 交付结论

项目已从“Tailscale 专用双入口”收口为与入口技术无关的双运行面：同一次 commit SHA
发布同一组镜像，由生产配置选择 `full`、`showcase` 或 `dual`。模式切换只调整
loopback Docker 网关，不会自动恢复 Tailscale、Funnel 或其他公网分享。

## 已交付能力

### 可信运行面

- 私人和简化网关分别固定 `private-admin`、`public-readonly`；
- 两个 runtime Nginx template 注入服务器本地网关密钥；
- Backend 在生产校验 `X-SpotifyStats-Gateway-Token`；
- 浏览器 Header 会被网关覆盖，未知入口 fail closed；
- 网关密钥不进入仓库、镜像或 Actions artifact。

### 公共只读

- 公共 API 采用显式允许策略，新 operation 默认不公开；
- 所有未批准写操作拒绝，敏感功能不对公共面呈现；
- 公共数据连接启用请求级 SQLite 只读保护；
- 年度总结、封面和其他 cache-first 页面不得由公共访问触发后台写入。

### 部署与发布

- Compose profiles：`full`、`showcase`、`dual`；
- `set-deployment-mode.sh` 一条命令切换；
- `deploy.sh` 沿用当前模式，并同时回滚镜像和模式；
- 旧服务器缺网关密钥时在服务器本地安全生成；
- 旧服务器缺 mode 时按旧双容器行为迁移为 `dual`；
- Actions 以一个 SHA 构建 API/Web，增加三模式静态矩阵；
- Actions 上传运行时模板、模式切换和验证脚本；
- `verify.sh` 不再默认探测或操作 Tailscale。

## 数据部署事实

`dual` 模式不是两套应用数据：两个 Web 网关都进入同一个 Backend，Backend 使用
同一个 `/opt/spotify-stats/data` 持久目录。两种运行面的 schema、缓存 key 和统计
语义因此保持一致。

这不等于支持把 SQLite 放到多台服务器共享：不得通过 NFS、SMB、对象存储挂载或
双向同步让多个在线 Backend 操作同一个 SQLite 文件。跨服务器展示应使用只读快照；
跨服务器实时读写需要迁移 PostgreSQL。

## 运维命令

```bash
cd /opt/spotify-stats
./set-deployment-mode.sh full
./set-deployment-mode.sh showcase
./set-deployment-mode.sh dual
./verify.sh
./validate-deployment-config.sh all
```

外部入口仍由运维人员单独决定。停止某个外部入口不影响 GitHub 后续更新镜像；自动
发布也不会自行重新开启该入口。

## 验收证据

发布前本地门禁：

- Phase 5 基线：`910 unit + 326 contract`；
- 前端：`71` 个测试文件、`514` 项测试，生产构建通过；
- 生产部署契约：`16` 项通过；
- `validate-deployment-config.sh all`：`full/showcase/dual` 全部通过；
- Ruff check / format check、Shell 语法与 `git diff --check`：通过；
- 两份 Nginx runtime template 已在真实服务器的现行 Web 镜像中完成 `nginx -t`；
- 对本地真实 `spotify_stats.db` 与 `yearly_review_cache.db` 执行代表性公开读取、
  被拒写入、AI/未知路由隐藏和未可信入口测试，前后 SHA-256 完全一致。

线上发布与真实服务器验收：

- 主分支发布 SHA：`71839871452811993a4c6b8ecd61a43483c28104`；
- [Phase 5 Baseline](https://github.com/BenjaminTay/SpotifyStats/actions/runs/31703679803)
  与 [生产部署流水线](https://github.com/BenjaminTay/SpotifyStats/actions/runs/31703679954)
  均成功，三模式矩阵、镜像构建和服务器部署全部通过；
- 在服务器依次实切 `dual -> showcase -> full`，每个模式的 `verify.sh` 均通过；
- `dual` 下私人面为 `private-admin/full`、展示面为
  `public-readonly/showcase`，两端的 release SHA 和 policy version 一致；
- 展示面设置写入返回 `403`，AI 与未知 GET 返回 `404`；代表性公开读取前后，
  `spotify_stats.db` 与 `yearly_review_cache.db` 的 SHA-256 均未变化；
- `showcase` 下只监听 `127.0.0.1:3002`，`full` 下只监听
  `127.0.0.1:3001`，Backend 的 `8000` 未映射到宿主机；
- 最终已恢复 `full`，公开 3002 端口关闭，Tailscale 保持 `Stopped`，未恢复任何
  外部分享入口；
- 主数据库和年度缓存执行 `PRAGMA quick_check` 均为 `ok`，发布前在线备份已生成。

GitHub Actions 当前仅有 actions 运行时 Node.js 20 被强制升级到 Node.js 24 的弃用提示，
不影响本次门禁、构建与部署结果；后续可随上游 action 大版本升级单独处理。
