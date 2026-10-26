# 后端 Agent 执行约定

面向修改 `backend/` 的Agent。先遵守[根执行约定](../AGENTS.md)，再阅读[后端架构与开发](./README.md)及[关键约束](./README.md#关键约束)。模块地图、默认值和详细规则只在开发文档与共用参考维护。

## 开始工作

- 在[开发状态](../docs/DEVELOPMENT_STATUS.md)确认事项、范围和负责人；按[问题台账](../docs/issues/README.md)复用稳定ID。
- API、service、domain与core保持各自职责；过滤参数必须传到最终统计入口。
- 外部HTTP、环境变量、缓存、统计身份和只读边界按后端开发文档逐条执行，不能用临时回退绕过合同。
- 涉及搜索、年度、AI或快照时，先读[文档地图中的当前参考](../docs/README.md#维护者与共用参考)，再检查实际拥有者源码。

## 验证与交付

选择受影响的unit／contract，遵守[测试隔离](../docs/reference/backend-test-isolation.md)与[验证范围](../docs/reference/fullstack-verification.md#按改动选择验证范围)。真实模型、数据库探针、默认完整全栈和生产验收分别记录，不默认全部执行。

状态变化更新总表，实施证据追加主题报告，当前规则更新对应参考。未经明确要求不提交、推送或部署；不改写原始播放及无关工作区内容。
