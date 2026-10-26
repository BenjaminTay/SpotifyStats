# 前端 Agent 执行约定

面向修改 `frontend/` 的Agent。先遵守[根执行约定](../AGENTS.md)，再读[前端开发说明](./README.md)、[关键约束](./README.md#关键约束)与[UI风格指南](UI_STYLE_GUIDE.md)。架构、默认查询配置和组件边界只在开发说明维护。

## 开始工作

- 在[开发状态](../docs/DEVELOPMENT_STATUS.md)确认范围；业务内容放 `features/`，`pages/` 保持路由容器职责。
- GET使用TanStack Query与`queryKeys`，不引入模块级API缓存。搜索、详情和年度请求按对应共用合同执行。
- 多端共享URL、过滤与统计事实，保持互斥presentation、触控尺寸、按需图表与列表策略。
- 外部文本净化、日期时区、API Key、AI手动生成及任务证据展示按开发说明的关键约束逐条执行。

## 验证与交付

默认只运行受影响的组件／架构回归与必要构建；路由、浏览器和真实视口按[验证范围](../docs/reference/fullstack-verification.md#按改动选择验证范围)选择。不能以模拟视口或静态页面壳替代真机、真实API与生产验收。

规则变化更新开发说明或共用参考，状态只更新总表，过程追加主题报告。未经明确要求不提交、推送或发布，不把工具诊断术语加入使用者页面。
