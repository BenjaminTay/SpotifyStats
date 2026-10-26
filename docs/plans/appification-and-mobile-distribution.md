# PWA真实终端验收与原生分发路线

面向维护者的滚动路线。原记录日期：2026-08-06；本轮修订：2026-10-26；当前状态、排期与环境余量以[开发状态](../DEVELOPMENT_STATUS.md)为准。

路线依据（2026-10-25记录）：PWA、移动网页和双运行面工程已有交付，剩余真实终端与OAuth验收；Capacitor暂缓，只有明确原生分发需求才重启。

## 已交付工程

[移动网页与PWA Phase A](../reports/2026-08-06-mobile-web-and-pwa-delivery.md)包含manifest、安装提示、standalone、安全离线页和主题；[私有云PWA基线](../reports/2026-08-13-private-cloud-and-deployment-delivery.md#个人私有云与-pwa-phase-b-交付报告)及[双运行面](../reports/2026-08-13-private-cloud-and-deployment-delivery.md#spotifystats-双运行面交付报告)保存当时服务器验收。Service Worker不缓存API或个人统计；安装PWA不会自动获得本机SQLite的远程访问。

## 剩余外部验收

- iPhone Safari与Android Chrome分别验证安装、图标、standalone、安全区、横竖屏、地址栏、软键盘和系统返回。
- 从真实PWA/HTTPS入口发起Spotify OAuth并成功回跳，刷新连接状态。
- 断网仅显示离线说明，不回放旧个人数据；Sheet和详情返回顺序正确。
- 按需要使用当前受控HTTPS入口。最新报告的展示HTTPS和SSH隧道通过，不代替私有域名DNS直连；具体入口结论见[10-24报告](../reports/2026-10-24-release-cycle-review-and-delivery.md#发行周期共用能力六项目副本验收与五项生产交付)。

部署、端口、身份边界、备份和回滚只按[当前生产手册](../../deploy/production/README.md)执行。旧每日及异机备份要求不覆盖当前三类备份决定；是否新增异机备份作为移动发布前置，需另行明确。

## Capacitor重启条件和范围

必须已有双平台真机和真实OAuth证据，且明确App Store或Android安装包分发需求。通过后才规划CLI/Core、bundle ID、签名、图标、深链、键盘/状态栏、OAuth回跳和 `build → cap sync → native build`。

原生容器继续复用React、Router、Query和现有统计合同，连接受控HTTPS API，不打包真实SQLite或密钥。隐私、删除说明和商店资料随实际分发要求处理。微信小程序不作为当前路线；明确微信分发和平台能力需求后独立评估。

## 完成和停止条件

记录每个平台、浏览器及OAuth实际结果，缺失条件继续PARTIAL / EXTERNAL。无原生分发需求时保持Capacitor暂缓，不为完成路线创建原生工程或定期探测任务。
