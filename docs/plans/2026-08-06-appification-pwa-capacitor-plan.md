# SpotifyStats App 化路线：PWA → 安全部署 → Capacitor

> 状态：部分完成；PWA、私人管理入口和公共只读展示入口已完成，等待双入口手机真机安装验收，Capacitor 尚未决策<br>
> 日期：2026-08-06<br>
> 前置阶段：[`2026-08-05-mobile-web-design-and-implementation-plan.md`](../archive/06-productization-closeout/2026-08-05-mobile-web-design-and-implementation-plan.md)

## 1. 路线结论

移动网页 M0–M7 已经完成，下一阶段采用以下顺序：

1. **PWA 基线**：让现有移动网页具备主屏幕图标、standalone 启动、安装引导和安全离线说明。
2. **安全远程运行**：确定后端部署位置、HTTPS、API 鉴权、SQLite 持久化/备份和 Spotify OAuth 回跳。
3. **真机验收**：iPhone Safari 与 Android Chrome 各完成一次安装、软键盘、返回、安全区和 OAuth 测试。
4. **Capacitor 容器**：只有远程 API 与真机 PWA 稳定后，才生成 iOS/Android 工程和商店包。
5. **微信小程序**：暂不作为主路线；只有明确存在微信分发、主体认证或平台能力需求时再单独立项。

这条路线最大化复用现有 React、Router、TanStack Query、移动 presentation 和统计契约，不在 App 阶段复制业务逻辑。

## 2. 方案对比

| 方案 | 现有前端复用 | 分发 | 当前主要缺口 | 结论 |
|---|---:|---|---|---|
| PWA | 接近 100% | 浏览器添加到主屏幕 | HTTPS 与可访问后端 | 第一落点 |
| Capacitor iOS/Android | 高 | App Store / 安装包 | 远程 API、深链、原生工程、商店签名 | PWA 稳定后进入 |
| 微信小程序原生重写 | 低 | 微信生态 | React DOM/Router/组件重写，登录与平台审核 | 当前不选 |
| 小程序 WebView 包装 | 中 | 微信入口 | 仍依赖 HTTPS H5，能力与审核边界受平台约束 | 仅有明确微信需求时评估 |

## 3. Phase A：可安装 PWA 基线（已完成）

- `manifest.webmanifest`：应用名称、scope、start URL、standalone、主题色、192/512 maskable 图标与四个快捷入口。
- iOS 元信息：Apple Touch Icon、主屏幕标题、状态栏与 `viewport-fit=cover`。
- `sw.js`：只缓存 PWA 图标、Manifest、离线说明和版本化 `/assets/`；明确绕过 `/api/` 与 `/covers/`。
- `offline.html`：后端或网络不可达时只显示连接说明，不回放个人统计数据。
- 手机 Settings 安装卡片：支持 Chromium 安装提示、iOS Safari 添加到主屏幕说明和已安装状态。
- 主题同步：日/夜主题同时更新浏览器/PWA `theme-color` 与 `color-scheme`。

交付证据见 [`../reports/2026-08-06-mobile-web-and-pwa-delivery.md`](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)。

## 4. Phase B：安全远程运行

PWA 安装并不会自动让手机访问 Mac 上的 SQLite。必须先在以下两种部署形态中选择一种：

### B1. 个人长期部署（当前方案）

- 私人云服务器使用双入口：Tailscale Serve 将私人 HTTPS 映射到 loopback 3001，保留完整管理能力；Tailscale Funnel 8443 将公共 HTTPS 映射到独立的 loopback 3002，只展示只读数据。
- FastAPI 只在 Docker 私网可达；两个 Nginx 覆盖访问面标头，后端按公共能力白名单拒绝设置、编辑、导入、AI、OAuth、歌词、元数据治理、后台任务和其他写操作。前端能力发现只负责隐藏相应 UI。
- 不开放 3000/3001/3002/8000 公网端口。`SPOTIFY_STATS_REQUIRE_AUTH` 只保护部分写端点，不能替代整站边界；私人入口身份由 tailnet 提供，公开链接则对任何持有者可见。
- 为 SQLite、封面与导入目录配置持久卷和定期备份。
- 设置真实 `FRONTEND_ORIGIN`、`SPOTIFY_REDIRECT_URI` 与 Spotify Dashboard 回调地址。
- `.dockerignore` 排除整个个人数据目录；镜像只含代码和依赖，服务器使用独立 `/opt/spotify-stats/data/` 与 `/opt/spotify-stats/backups/`。
- 发布采用 commit SHA 不可变镜像、上线前 SQLite Online Backup、健康检查和失败回滚；服务器本地每日备份还需再配一份异机备份。

### B2. 同一局域网临时真机验收

- 仅在受信任网络中临时绑定局域网地址，测试结束立即关闭。
- 因项目含个人播放时间、账号资料和 OAuth token，不默认把未鉴权的 8000/5173 暴露给局域网。
- 局域网 HTTP 可用于页面交互测试，但正式 PWA 安装与 OAuth 仍应使用 HTTPS。

## 5. Phase C：物理设备验收

每个平台至少完成以下证据：

1. 从浏览器安装/添加到主屏幕，图标、启动页和 standalone 状态正确。
2. Top Bar、Bottom Nav、Sheet 和全屏图表适配安全区、地址栏伸缩与横竖屏。
3. AI 输入框在软键盘弹出后可见，消息区不被遮挡。
4. 系统返回、浏览器历史返回、Sheet 关闭和 Push 详情返回顺序正确。
5. 网络断开只显示离线说明，不出现旧个人数据或误导性的“离线可用”。
6. Spotify OAuth 从 App/PWA 发起后能回到 HTTPS Web 路由并刷新连接状态。

## 6. Phase D：Capacitor 容器

在 Phase B/C 通过后实施：

- 引入 Capacitor CLI/Core，并将 `frontend/dist` 作为 Web 资产目录。
- 先生成 iOS/Android 空容器，锁定 bundle id、App 名称、图标和启动页。
- 生产 App 默认连接 Phase B 的 HTTPS API，不把真实 SQLite 或密钥打包进前端资产。
- 为外部链接、分享、状态栏、键盘、深链和 OAuth 回跳建立最小原生适配层。
- 建立 `npm run build → cap sync → native build` 自动化和真机 smoke。
- 完成签名、隐私说明、数据删除说明和商店元数据后再考虑发布。

## 7. 决策门

进入 Phase B 前需要用户确认部署形态；进入 Capacitor 前必须满足：

- [ ] 有稳定 HTTPS 域名和远程 API。
- [ ] API 鉴权、持久化与备份已验证。
- [ ] iPhone/Android PWA 真机验收通过。
- [ ] Spotify OAuth 真实回跳通过。
- [ ] 明确是否需要 App Store / Android 安装包分发。
