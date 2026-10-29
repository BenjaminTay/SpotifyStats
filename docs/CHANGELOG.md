# 变更日志

面向使用者，记录可感知的功能和体验变化。逐批数据应用、源码版本、失败和验证计数保存在[交付报告](reports/README.md)与[完整月度历史](archive/changelog/README.md)；当前问题处理进度见[开发状态](DEVELOPMENT_STATUS.md)。

## 未发布

- 重写项目首页，新增使用指南和清晰的开发入口；问题台账、当前规则与滚动路线改用稳定文件名。补齐安装版本、依赖更新与Spotify连接前提说明。

## 2026-10-28 统计内存与备份维护

- 降低播放排行和艺人统计首次读取的内存开销，复用艺人统计与个人排名的必要输入，保持统计结果一致。
- 简化服务器备份：每周压缩一份、仅留2份；每天自动收尾已完成任务的临时及恢复材料，支持清空历史后继续发布。[运维规则](../deploy/production/README.md#发布文件收尾)。

## 2026-10-25 文档整理与导航更新

使用入口、统计说明和文档导航更集中，查找帮助时更容易找到当前内容。详见[文档整理记录](reports/2026-10-25-documentation-cleanup-delivery.md)。

## 2026-10-24 发行周期来源与日期审核

发行周期分析可以更准确地区分参考发行版本与当前专辑；日期存在冲突时，需要明确审核后再应用。[详细交付](reports/2026-10-24-release-cycle-review-and-delivery.md#用户授权后的提交生产发布与上线验收)。

## 2026-10-23 歌曲版本与专辑日期修复

修正发行日期和歌曲版别关系，同时保留已经确认的歌曲归属，避免调整参考版本时影响原有统计。[详细交付](reports/2026-10-23-title-release-attribution-repair.md)。

## 2026-10-23 备份与恢复文件管理

维护者可以按统一的备份、恢复和临时材料规则管理磁盘空间。操作方法见[运维手册](../deploy/production/README.md#发布文件收尾)。

## 2026-10-23 发行周期信息完善

完善发行来源、艺人身份与日期展示，保持原有对决指标表格的阅读方式。[详细交付](reports/2026-10-22-release-cycle-production-delivery.md)。

## 2026-10-21 专辑成绩与榜单对决修复

修正专辑旗下单曲的成绩归属和日期边界，并恢复榜单对决的发行周期分析。[单曲成绩](reports/2026-10-21-album-song-performance-attribution.md)、[发行周期](reports/2026-10-21-versus-release-cycle-repair-acceptance.md)。

## 2026-10-20 本地导入与展示补修

改善增量导入、独唱／合唱版本识别、零播放时长详情和专辑内容归并。各项应用范围见[导入记录](reports/2026-10-20-local-streaming-incremental-import.md)、[归并记录](reports/2026-10-20-album-content-merge-repair.md)和[后续交付](reports/2026-10-21-album-song-performance-attribution.md)。

## 2026-10-19 播放记录与音乐详情内存优化

降低播放记录维护和音乐详情统计的内存开销；长期使用稳定性继续单独观察。[详细交付](reports/2026-10-19-minimal-memory-production-delivery.md)。

## 2026-10-14 后台处理后的内存释放与加载改善

改善后台处理完成后的内存释放与详情加载体验。[详细交付](reports/2026-10-14-native-trim-maintenance-delivery.md#维护完成原生回收生产交付与首次验收)。

## 2026-10-09 榜单对决个人统计优化

榜单对决先显示基础播放统计，再加载完整排名，减少首屏等待。[验收记录](reports/2026-10-08-versus-personal-statistics-performance-acceptance.md)。

## 2026-10-08 发行日期与无播放结果展示

改善发行日期精度与空结果展示，缺少可靠信息时保留未知状态。[详细交付](reports/2026-10-08-release-date-production-acceptance.md#日期精度与详情空统计生产交付验收)。

## 2026-10-07 歌曲署名、链接与时间选择修复

改进合作艺人与标题解析，保留人工确认结果，并修正旧歌曲链接与公开页面的时间选择。[验收记录](reports/2026-10-06-track-credit-resolution-acceptance.md)。

## 2026-10-03 专辑曲目列表与封面改进

专辑曲目列表支持完整分页，艺人信息和发行位置有更可靠的来源，封面可以按展示尺寸加载。[专辑交付](reports/2026-10-03-album-metadata-delivery.md#专辑目录与艺人证据生产交付)、[封面交付](reports/2026-10-03-cover-image-optimization-acceptance.md)。

## 2026-10-02 合作曲排行

合作曲排行使用完整有效署名，相关艺人可以从曲目进入自己的统计详情。[详细交付](reports/2026-10-02-collaboration-ranking-acceptance.md)。

## 2026-09-27 AI任务恢复与日常启动

新增AI任务恢复、年度叙事逐章阅读与日常轻量启动；真实模型、终端和入口条件分别记录。[AI集成](reports/2026-09-27-ai-agent-v6-local-integration.md)、[运行改进](reports/2026-09-22-runtime-resource-optimization.md)。

## 2026-09-27 合作歌曲参与艺人信息补全

更完整地保留歌曲参与艺人的有序署名，存在冲突时继续保留审核边界和人工确认结果。[详细交付](reports/2026-09-24-spotify-track-artists-evidence-delivery.md)。

## 2026-09-21 页面读取与导入恢复改善

改善页面读取稳定性和导入失败后的继续处理，减少反复计算与重复导入。[性能成果](reports/2026-09-21-full-application-performance-optimization-outcome.md)、[导入验收](reports/2026-09-21-import-incident-and-remediation.md#数据导入处理与治理-s6-最终验收报告)。

## 2026-09-13 统计、榜单与导入修复

修正早期统计、榜单和导入中的多项问题，各功能当时的交付范围见[发布记录](reports/2026-09-13-development-closeout-and-release.md)。
