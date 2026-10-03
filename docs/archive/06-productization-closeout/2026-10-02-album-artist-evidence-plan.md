# 专辑艺人稳定 ID 与有序证据实施方案

> 原本地阶段状态：SS-2026-09-24-002；2026-10-02；基线 `fa683d97`；IMPLEMENTED / PARTIAL（本地专项完成） / COMMITTED（本次本地提交登记） / NOT_DEPLOYED。

## 调查结论与范围

本地只读库有 3,234 个 Album 元数据记录，schema 81。名称含逗号的 Earth, Wind & Fire、Tyler, The Creator 在专辑缓存中实际存在，旧逗号拆分验证会误拒绝。同名不同 ID 在 Track 缓存有 3 组，只作为身份风险旁证，不能当成 Album API 对账；同一 ID 改名未发现真实样本。

写入口包括 Spotify refresh、version_merge 补取、release_cycle 批取/搜索以及 fetch_covers 脚本。消费者包括 release cycle、Billboard 元数据筛选、Album Project/健康候选、自动归并、Records 可信原版判断。显示字符串与歌曲署名仍保持各自职责。

## 实施步骤

1. 独立 Album evidence set、ordered credits 和 append-only event，复用现有 schema、身份 map 与 revision。名称只做显示；ID 解析不创建或按名称合并本地艺人。
2. 缺失/非法数组或 provider ID 集合冲突保留上一可靠证据，拒绝观察进入审计；本地歧义动态标为 ambiguous，人工 canonical 治理优先。
3. 所有 Album 写入口共享保存函数；消费者优先 ID，旧值兼容匹配明确为 legacy，strict 验证不得冒充 ID 验证。修正含逗号整名匹配。
4. 必要的 Analysis、Billboard、年报及健康缓存依赖纳入 revision，不改变 Track 自动署名和播放贡献。
5. 新库/旧库副本迁移、重复刷新、失败、身份治理与实际消费者测试；真实库 Online Backup 上有界证据演练，正式库只读。
6. 更新规则、报告、开发总表、台账与索引，运行文档审计与 diff 检查。

## 并行与交付边界

隔离工作树 `/Users/benjaminlei/Code/202605-SpotifyStats-album-artists`，分支 `codex/album-artist-evidence` 从 `fa683d97` 创建。主目录的未提交文档复制为只读来源基线，未写回；分页工作树当前有 migration 87，新增迁移实施时选用 88。无分页接口依赖，共享文件合入时逐段协调并复验。此方案留在 plans，直到正式回填/合入验收完成；用户已于本轮授权本地提交；不推送、部署、正式库回填或向其他 session 发消息。

## 实施结果（2026-10-03）

上述六步已完成本地实施与验证，详细数值见[验证报告](../../reports/2026-10-02-album-artist-evidence-verification.md)。待办仅为共享文件合入、另行授权正式库回填和生产验收；未开展分页和日期精度开发。

## 2026-10-03 生产收口

daf098ca 已推送、CI通过并正式发布，schema85→88及限定Album维护完成，原始播放/歌曲/署名和人工治理保持。最终生产样本、额外简化曲目元数据补齐、实际入口验收及未解析边界见[生产报告](../../reports/2026-10-03-album-metadata-production-delivery.md)。本方案归档，前文保留各阶段的授权与验证历史；日期精度及身份审批不属于本任务。
