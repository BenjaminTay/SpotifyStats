# 文档地图

只有两类文档：**活跃文档**（仍被引用或仍在推进）和**历史归档**（已完成，只供回溯）。

## 总览

| 文档 | 目标读者 | 内容 |
|------|---------|------|
| [`../README.md`](../README.md) | 使用者 | 项目介绍、功能列表、快速开始、技术栈 |
| [`../AGENTS.md`](../AGENTS.md) | AI Agent | 完整项目上下文、架构细节、所有约定 |
| [`../CLAUDE.md`](../CLAUDE.md) | 开发者（速查） | 常用命令、核心约束清单 |
| [`CHANGELOG.md`](CHANGELOG.md) | 所有人 | 变更日志 |
| [`../data/README.md`](../data/README.md) | 数据使用者 | Spotify 官方数据格式说明 |

## 活跃文档

### 实现计划 (`plans/`) — 5 个

只保留尚未完成的工作，或仍作为现行产品规格和后续迭代依据的完整计划。

| 计划 | 内容 |
|------|------|
| [`plans/2026-08-12-yearly-review-v2-rebuild-plan.md`](plans/2026-08-12-yearly-review-v2-rebuild-plan.md) | 年度总结 V2 完整重构：数据审计、统一契约、内容编排、桌面体验、Phone 迁移、验证与回滚计划 |
| [`plans/2026-08-06-appification-pwa-capacitor-plan.md`](plans/2026-08-06-appification-pwa-capacitor-plan.md) | App 化现行路线：PWA 基线、安全部署、真机验收与 Capacitor 决策门 |
| [`plans/2026-08-05-mobile-web-design-and-implementation-plan.md`](plans/2026-08-05-mobile-web-design-and-implementation-plan.md) | 移动端网页现行产品规格、M0–M7 完成记录、长期架构契约与验收门禁 |
| [`plans/2026-06-23-playback-records-plan.md`](plans/2026-06-23-playback-records-plan.md) | 播放记录的模块地图、统计定义与现行实现口径 |
| [`plans/2026-06-29-ai-agent-harness-quality-roadmap.md`](plans/2026-06-29-ai-agent-harness-quality-roadmap.md) | AI Agent Harness 质量路线图（持续指引，非单次任务） |

### 设计规格 (`designs/`) — 4 个

只保留仍在活跃迭代的系统的设计。已稳定系统的设计归档到对应开发阶段。

| 设计 | 内容 |
|------|------|
| [`designs/2026-08-12-yearly-review-v2-content-data-contract.md`](designs/2026-08-12-yearly-review-v2-content-data-contract.md) | 年度总结 V2 内容与数据契约：个人音乐年鉴定位、章节职责、证据/覆盖规则与 Desktop/Phone 边界 |
| [`designs/2026-08-05-mobile-web-m0-design-freeze.md`](designs/2026-08-05-mobile-web-m0-design-freeze.md) | 移动端 M0 冻结规格：真实基线、路由状态矩阵、Shell 决策、组件状态、六屏交互原型与 M1/M2 原子任务 |
| [`designs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md`](designs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md) | 现行 Editorial Agent Pipeline 设计 |
| [`designs/2026-07-04-genre-review-settings-design.md`](designs/2026-07-04-genre-review-settings-design.md) | Genre Review Settings 设计 |

### 报告 (`reports/`) — 13 个

一次性验证/交付/审计报告。

| 报告 | 内容 |
|------|------|
| [`reports/2026-08-13-billboard-artist-aggregate-fix.md`](reports/2026-08-13-billboard-artist-aggregate-fix.md) | 艺人榜逻辑播放事件预聚合修复：根因、影响范围、真实数据库重建、原始/预聚合对账与回归验证 |
| [`reports/2026-08-12-yearly-review-v2-delivery.md`](reports/2026-08-12-yearly-review-v2-delivery.md) | 年度总结 V2 唯一完整交付报告：审计、契约、编排、API/缓存、后台预生成、Desktop/Phone 双 presentation、验收问题修复、四年真实性能与三浏览器证据 |
| [`reports/2026-08-06-mobile-web-and-pwa-delivery.md`](reports/2026-08-06-mobile-web-and-pwa-delivery.md) | 移动端 M0–M7、PWA Phase A 与验收后修复综合交付：阶段范围、架构契约、全栈门禁、专项复验和未完成边界 |
| [`reports/2026-07-28-billboard-v3-sensitivity-analysis.md`](reports/2026-07-28-billboard-v3-sensitivity-analysis.md) | Billboard V3 年榜积分敏感性分析：竞争强度、个体统治力与纯排名反事实对照 |
| [`reports/2026-07-16-genre-source-quality-audit.md`](reports/2026-07-16-genre-source-quality-audit.md) | Genre 来源可信度审核：高影响无链接 LLM 来源标签的证据与处置结果 |
| [`reports/2026-07-15-genre-language-pre-review-execution.md`](reports/2026-07-15-genre-language-pre-review-execution.md) | Genre/Language 首轮预审：分轴解析、覆盖缺口与 suggested 审核队列 |
| [`reports/2026-06-19-fullstack-verification-performance.md`](reports/2026-06-19-fullstack-verification-performance.md) | 全栈验证与性能收口执行计划 |
| [`reports/2026-06-19-fullstack-verification.md`](reports/2026-06-19-fullstack-verification.md) | 全栈验证与性能收口最终报告 |
| [`reports/2026-06-20-fix-branch-follow-up.md`](reports/2026-06-20-fix-branch-follow-up.md) | fix 分支修复验证跟进 |
| [`reports/2026-06-22-phase5-delivery-report.md`](reports/2026-06-22-phase5-delivery-report.md) | Phase 5 最终交付报告 — 零缺陷验证、性能对比、10 分钟快速验证指南 |
| [`reports/2026-07-03-ai-question-test-matrix.md`](reports/2026-07-03-ai-question-test-matrix.md) | AI 问答测试问题清单；可用 `scripts/evaluate_ai_question_matrix.py` 做静态完整性检查 |
| [`reports/2026-07-03-ai-question-matrix-test-report.md`](reports/2026-07-03-ai-question-matrix-test-report.md) | AI 问答矩阵验收执行报告、失败样本、修复建议与实施记录 |
| [`reports/2026-07-05-artist-genre-seed-audit.md`](reports/2026-07-05-artist-genre-seed-audit.md) | Artist Genre Seed 准确性审计 |

### 参考文档 (`reference/`) — 4 个

规则定义与权威口径，被 CLAUDE.md/AGENTS.md 引用。

| 参考 | 内容 |
|------|------|
| [`reference/playback-stats-rules.md`](reference/playback-stats-rules.md) | 播放统计规则权威定义：三级合并、Session 边界、Album Projects |
| [`reference/music-metadata-management.md`](reference/music-metadata-management.md) | 音乐源数据管理：有效曲目署名、人工覆盖、审计撤销、统一归并工作区与深链规则 |
| [`reference/2026-07-04-artist-genre-taxonomy.md`](reference/2026-07-04-artist-genre-taxonomy.md) | Artist Genre Taxonomy：来源优先级、四轴治理、consumer_v1 展示映射与审计边界 |
| [`reference/data-import-and-health.md`](reference/data-import-and-health.md) | 导入前文件预检、导入后数据库健康报告与当前精简边界 |

## 历史归档 (`archive/`)

按项目开发阶段组织，已实现或被取代的文档均保留对应阶段目录下，供回溯上下文。

### 01 · Streamlit MVP（2026-05）

全功能 Streamlit 原型：Billboard 周榜、发行周期、封面系统、版本合并引擎。

| 目录 | 内容 |
|------|------|
| [`archive/01-streamlit-mvp/phase1-2-streamlit/`](archive/01-streamlit-mvp/phase1-2-streamlit/) | Streamlit 版本功能清单 |
| [`archive/01-streamlit-mvp/phase3-frontend/`](archive/01-streamlit-mvp/phase3-frontend/) | React 前端迁移页面规划 |
| [`archive/01-streamlit-mvp/phase4-architecture/`](archive/01-streamlit-mvp/phase4-architecture/) | 架构优化白皮书与 Phase 4 验收报告 |
| [`archive/01-streamlit-mvp/features/account-center/`](archive/01-streamlit-mvp/features/account-center/) | 账号中心设计 |
| [`archive/01-streamlit-mvp/features/release-cycle/`](archive/01-streamlit-mvp/features/release-cycle/) | 发行周期分析设计 |
| [`archive/01-streamlit-mvp/features/yearly-review/`](archive/01-streamlit-mvp/features/yearly-review/) | 年度总结设计 |
| [`archive/01-streamlit-mvp/features/enhancements/`](archive/01-streamlit-mvp/features/enhancements/) | 早期增强功能设计 |

### 02 · React 产品化（2026-06-08~18）

React 重写、大文件拆分、API 契约硬化、AI Insights 模块、播放统计规则引擎。

| 文件/目录 | 内容 |
|------|------|
| [`archive/02-react-productization/2026-06-08-phase5-baseline.md`](archive/02-react-productization/2026-06-08-phase5-baseline.md) | Phase 5 产品化基线台账 |
| [`archive/02-react-productization/2026-06-11-ai-insights.md`](archive/02-react-productization/2026-06-11-ai-insights.md) | AI Insights 模块设计 |
| [`archive/02-react-productization/playback-stats/`](archive/02-react-productization/playback-stats/) | 播放统计实现计划、Album Project、规则 v1 |

### 03 · 全栈质量门禁（2026-06-19~27）

61 个 commits：验证矩阵、性能收口、Billboard 年榜、Settings UX 打磨。

| 文件 | 内容 |
|------|------|
| [`archive/03-quality-gate/2026-06-22-settings-page-ux-polish.md`](archive/03-quality-gate/2026-06-22-settings-page-ux-polish.md) | Settings 页面 UX 打磨 |
| [`archive/03-quality-gate/2026-06-24-import-derived-data-maintenance.md`](archive/03-quality-gate/2026-06-24-import-derived-data-maintenance.md) | 导入派生数据维护方案 |
| [`archive/03-quality-gate/2026-06-26-billboard-year-end.md`](archive/03-quality-gate/2026-06-26-billboard-year-end.md) | Billboard 个人年榜实现计划 |
| [`archive/03-quality-gate/2026-06-26-billboard-year-end-design.md`](archive/03-quality-gate/2026-06-26-billboard-year-end-design.md) | Billboard 年榜设计规格 |

### 04 · AI Agent 中间层（2026-06-28~07-03）

AI Observable Agent Orchestrator、Universal Analytical Harness、证据链与回答契约。

| 文件 | 内容 |
|------|------|
| [`archive/04-ai-agent-harness/2026-06-28-mobile-navigation-orientation.md`](archive/04-ai-agent-harness/2026-06-28-mobile-navigation-orientation.md) | 旧移动导航增量方案；现行移动端设计已由 `plans/2026-08-05-mobile-web-design-and-implementation-plan.md` 取代 |
| [`archive/04-ai-agent-harness/2026-06-28-ai-observable-agent-orchestrator.md`](archive/04-ai-agent-harness/2026-06-28-ai-observable-agent-orchestrator.md) | AI Observable Agent Orchestrator V2（plan） |
| [`archive/04-ai-agent-harness/2026-06-28-ai-observable-agent-orchestrator-design.md`](archive/04-ai-agent-harness/2026-06-28-ai-observable-agent-orchestrator-design.md) | AI Observable Agent Orchestrator V2（design） |
| [`archive/04-ai-agent-harness/2026-06-29-ai-agent-universal-analytical-harness.md`](archive/04-ai-agent-harness/2026-06-29-ai-agent-universal-analytical-harness.md) | 通用分析中间层（plan） |
| [`archive/04-ai-agent-harness/2026-06-29-ai-agent-universal-analytical-harness-design.md`](archive/04-ai-agent-harness/2026-06-29-ai-agent-universal-analytical-harness-design.md) | 通用分析中间层（design） |
| [`archive/04-ai-agent-harness/2026-06-29-ai-project-context-prompt.md`](archive/04-ai-agent-harness/2026-06-29-ai-project-context-prompt.md) | Project Context Prompt（plan） |
| [`archive/04-ai-agent-harness/2026-06-29-ai-project-context-prompt-design.md`](archive/04-ai-agent-harness/2026-06-29-ai-project-context-prompt-design.md) | Project Context Prompt（design） |
| [`archive/04-ai-agent-harness/2026-07-03-ai-harness-matrix-fixes.md`](archive/04-ai-agent-harness/2026-07-03-ai-harness-matrix-fixes.md) | Harness 矩阵验收后修复 |

### 05 · AI 年报与流派（2026-07-03~05）

图文年度报告 12 轮迭代、Music Search、Genre Taxonomy 体系。

| 目录 | 内容 |
|------|------|
| [`archive/05-yearly-report-genre/ai-yearly-report/`](archive/05-yearly-report-genre/ai-yearly-report/) | 年报完整迭代链：agentic_longform → visual_artifact → editorial_agent → final_quality_gate |
| [`archive/05-yearly-report-genre/music-search/`](archive/05-yearly-report-genre/music-search/) | 音乐查找入口与榜单摘要 |
| [`archive/05-yearly-report-genre/genre-taxonomy/`](archive/05-yearly-report-genre/genre-taxonomy/) | Genre 解析、Taxonomy v2、Axis Confidence 早期迭代 |
