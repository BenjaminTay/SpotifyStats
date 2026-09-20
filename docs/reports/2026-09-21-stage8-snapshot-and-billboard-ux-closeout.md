# 阶段 8：快照可用性与 Billboard 交互连续性收口

> 日期：2026-09-21
>
> 状态：本地实现与定向验收 PASS；未 push、未部署、未修改正式数据

## 目标与边界

本阶段处理阶段 7 后暴露出的两个产品体验问题：普通用户看见“等待发布”等后台术语，以及 Billboard 切实体、切周或切子页面时整页骨架闪动。统计 builder、L2/L3、完整结束周、Search/Billboard 重建架构、AI、外部访问、Docker 与部署均不在本阶段范围。

## 实施结果

### 快照和播放分析

- 移除 `AppLayout` 对全部观察中 Query 的全局扫描；Home、Analysis 与 Billboard 只根据自己实际消费的响应显示更新状态。
- 用户文案改为“数据正在准备 / 数据正在更新，当前显示上一次计算结果”，不再暴露发布管线。
- Analysis Stats / Records 自动维护 lifetime、last_4_weeks、last_6_months 两个 family 共六个精确 key。
- 私有端首次访问 year/month/week/day/custom 缺失范围时，通过独立 POST 只排队、不等待 builder，并轮询只读 GET；公开端不开放维护 POST，GET 仍零构建、零写入、零排队。
- request key、持久 revision、source fence、LKG、失败保留旧代和 16-key 上限均保留；原统计函数未修改。

### Billboard

- `/billboard` 六个子页面共享持久路由外壳，桌面子导航跨页面保持挂载，并在 hover/focus 预取目标 chunk。
- Weekly 切周/实体时保留上一份完整投影；过渡期的选中标签来自旧投影自身，目标响应就绪后才同时替换标签和数据，避免语义错配。
- 成功读取当前周后预取另外两个实体及相邻两周；All-Time 预取同视图其他实体。Query key、AbortSignal、5 分钟 staleTime 和 30 分钟回收边界明确，返回已缓存目标不再请求。
- 只有首次无数据时显示完整骨架；已有页面切换时保留布局与内容，并显示局部切换状态。

## 验收证据

| 项目 | 结果 |
|---|---|
| Analysis snapshot unit + public surface | 42 passed |
| 快照/Analysis 前端定向测试 | 23 passed |
| Billboard projection / architecture / compilation 定向测试 | 通过；含过渡帧语义与缓存回切 |
| Frontend 完整测试 | 661 passed；4 skipped |
| Frontend production build | PASS |
| Backend unit | 1955 passed；1089 deselected |
| Backend contract | 437 passed；2607 deselected |
| OpenAPI operation / parameter audit | 12 passed；新增维护 POST 与 `family` 枚举均已登记 |
| 文档审计 | PASS |
| 真实浏览器 | Chromium：周榜单曲→专辑、周榜→每周榜首；共享导航保持、数据正确切换、无整页骨架回退 |
| Weekly page projection，本机 18 次 | median 57.833 ms；P95 105.250 ms；max 105.250 ms |
| 响应体 | tracks 26,317 B；albums 19,096 B；artists 18,608 B；后端响应模型未改 |

P95 低于本阶段 250 ms 目标。浏览器验收使用本机开发服务与正式本地数据的只读 API；不等同于生产验收。Backend contract 通过，但 pytest 报告了既有后台线程清理警告（Community 重试计时器与测试临时库关闭后的异步访问）；未计为本阶段产品回归，也没有在本阶段扩范围修改。

## Git 与交付边界

- 快照与 Analysis 范围检查点：`1404cfc fix(snapshot-ux): 收口快照状态与播放分析范围可用性`。
- Billboard 连续性、最终测试与本报告组成第二个大步骤提交。
- `data/governance_cache.build.lock` 为既有未跟踪运行时文件，未删除、未暂存、未提交。
- 没有 push、部署、Docker、外部 API 或生产 AI 操作。
