# 文档地图

## 总览

| 文档 | 目标读者 | 内容 |
|------|---------|------|
| [`README.md`](../README.md) | 使用者 | 项目介绍、功能列表、快速开始、技术栈 |
| [`AGENTS.md`](../AGENTS.md) | AI Agent | 完整项目上下文、架构细节、所有约定 |
| [`CLAUDE.md`](../CLAUDE.md) | 开发者（速查） | 常用命令、核心约束清单 |
| [`CHANGELOG.md`](CHANGELOG.md) | 所有人 | 变更日志 |
| [`data/README.md`](../data/README.md) | 数据使用者 | Spotify 官方数据格式说明 |

## 架构

| 文档 | 内容 |
|------|------|
| [`backend/CLAUDE.md`](../backend/CLAUDE.md) | 后端四层架构（api/services/domains/core）、模块表、测试策略 |
| [`frontend/CLAUDE.md`](../frontend/CLAUDE.md) | 前端架构、路由表、Feature-first 分层、TanStack Query 约定 |
| [`frontend/UI_STYLE_GUIDE.md`](../frontend/UI_STYLE_GUIDE.md) | "编辑风 × 液态玻璃"设计系统 — 颜色、字体、组件规范 |
| [`architecture/2026-05-30-architecture-optimize.md`](architecture/2026-05-30-architecture-optimize.md) | Phase 4 架构优化决策文档 |

## 播放统计规则

| 文档 | 内容 |
|------|------|
| [`playback-stats/rules.md`](playback-stats/rules.md) | 播放统计规则权威定义：三级合并、Session 边界、Album Projects |
| [`playback-stats/implementation-plan.md`](playback-stats/implementation-plan.md) | 播放统计 Phase C+D 逐阶段实现计划 |
| [`playback-stats/album-project.md`](playback-stats/album-project.md) | Album Project 播放统计专项设计 |
| [`playback-stats/2026-06-12-playback-stats-rules.md`](playback-stats/2026-06-12-playback-stats-rules.md) | 播放统计规则初版（已整合至 rules.md，保留参考） |

## 验证报告

| 文档 | 内容 |
|------|------|
| [`verification/2026-06-19-fullstack-verification.md`](verification/2026-06-19-fullstack-verification.md) | 全栈验证与性能收口最终报告 |
| [`verification/2026-06-20-fix-branch-follow-up.md`](verification/2026-06-20-fix-branch-follow-up.md) | fix 分支修复验证跟进 |

## 产品化台账

| 文档 | 内容 |
|------|------|
| [`productization/2026-06-08-phase5-baseline.md`](productization/2026-06-08-phase5-baseline.md) | Phase 5 产品化收口基线台账 |
| [`productization/2026-06-11-ai-insights.md`](productization/2026-06-11-ai-insights.md) | AI Insights 模块设计（已完成，已归入 Phase 5.4-C/D） |
| [`productization/2026-06-22-phase5-delivery-report.md`](productization/2026-06-22-phase5-delivery-report.md) | Phase 5 最终交付报告 — 零缺陷验证、性能对比、10 分钟快速验证指南 |

## 当前功能设计

| 文档 | 内容 |
|------|------|
| [`superpowers/specs/2026-06-26-billboard-year-end-design.md`](superpowers/specs/2026-06-26-billboard-year-end-design.md) | Billboard 年榜设计：年度单曲/专辑/艺人榜、Year-End Score、荣誉卡片与 UI 组织 |
| [`superpowers/plans/2026-06-26-billboard-year-end.md`](superpowers/plans/2026-06-26-billboard-year-end.md) | Billboard 年榜实现计划与最终落地口径 |

## 历史归档

以下文档记录了项目的演进历程，不再活跃引用。均已完成实现，仅保留设计上下文供参考。

### 功能设计（已实现）

| 文档 | 内容 |
|------|------|
| [`archive/features/account-center/`](archive/features/account-center/) | 账号中心功能设计（plan + spec） |
| [`archive/features/release-cycle/`](archive/features/release-cycle/) | 发行周期分析设计（plan + spec） |
| [`archive/features/yearly-review/`](archive/features/yearly-review/) | 年度总结设计（plan + spec） |
| [`archive/features/enhancements/`](archive/features/enhancements/) | 早期增强功能设计 |

### 历史阶段

| 目录 | 阶段 | 内容 |
|------|------|------|
| [`archive/phase1-2-streamlit/`](archive/phase1-2-streamlit/) | Phase 1-2 | Streamlit 版本功能清单 |
| [`archive/phase3-frontend/`](archive/phase3-frontend/) | Phase 3 | 前端迁移页面规划 |
| [`archive/phase4-architecture/`](archive/phase4-architecture/) | Phase 4 | 架构优化文档与最终验收报告 |

### 历史执行计划

| 文档 | 内容 |
|------|------|
| [`archive/2026-06-19-fullstack-verification-performance.md`](archive/2026-06-19-fullstack-verification-performance.md) | Superpowers 全栈验证执行计划（已执行完成，最终报告见 `verification/`） |
