# 全站封面优化实施与验收

> 问题 ID：`SS-2026-10-03-001`
> 状态：实施中；以下阶段按现场证据继续更新。
> 实施基线：本地 `7b9a1f4e`；生产 `3a4e6310`（2026-10-03 SSH 核验，三服务 healthy）。

## S0 基线和收益依据

前轮现场检查：首页 11 张均原图，其中三个小图显示 54px；播放记录当时挂载 68 张均原图，典型显示 40px；播放排行 20 张均缩略图。音乐档案和当前年度 V2 原图消费由有效组件确认；年度页面零图片的初始观察不作为图片加载验收。

本轮读取生产首页六张样本，保持内容和比例，使用既有 quality=78/method=4 对比：

| 原图 | 原图 bytes / 尺寸 | 160 bytes | 320 bytes | 640 bytes |
| --- | --- | --- | --- | --- |
| albums/2334 | 85,652 / 469×640 | 3,342 | 9,742 | 32,940 |
| albums/20464 | 81,676 / 640×640 | 2,440 | 6,636 | 17,870 |
| albums/20438 | 44,544 / 640×640 | 1,642 | 5,116 | 13,488 |
| artists/68 | 56,673 / 640×640 | 2,626 | 6,808 | 17,688 |
| artists/1 | 90,644 / 538×640 | 3,406 | 9,298 | 25,966 |
| albums/1225 | 126,174 / 640×640 | 2,792 | 8,700 | 32,978 |

640 保持这批源图尺寸，体积降低约 61.5–78.1%；320 显著适用于中图。该结果证明中大图编码优化有收益，不代表用户网络下的实际加载时间。原始 JSON 在本地忽略目录 `output/playwright/cover-images/variant-feasibility.json`。

用户实际入口：`https://stats.benjaminlei.site`，正在采集修复前冷/热三次及视口基线。

## S1–S3 实施

### 当前有效入口库存

| 区域 | 组件/消费链 | 基础档位 |
| --- | --- | --- |
| 首页双版 | `HomePrimitives` + Desktop/Phone 显式场景 | 行 160；旁卡 320；主视觉/大卡 640 |
| 播放统计/排行 | `RecentPlaysSection`、`StatsTables`、`MobileRankList` → 公共封面 | 160 |
| 播放记录 | `PlaybackRecordsPrimitives`、`DiscoverySection`、`HourlySegmentsCard` | 160 |
| 音乐档案双版 | 公共实体行、Library、OtherMedia、ArchiveCover | 行 160；Phone 封套 320；Desktop 封套 640 |
| 年度 V2 双版 | `YearlyReviewPrimitives` → 八章、Phone epilogue 明确覆盖 | 小图 160、中图 320、手机大卡 640 |
| 音乐查找 | Quick Open / 完整页 → `MusicSearchResults` 公共封面 | 160 |
| 音乐详情 | header / phone hero / sheet、版本列表、成员排行 | 摘要 320、专辑手机大图 640、行 160 |
| Billboard 六区域 | 周榜、冠军、总榜、年榜、Records、Versus 共用已有 helper | 160 |
| 设置及兼容入口 | ArtistIdentity、TrackCreditManager、VersionMerge、LegacyTrackDetailRedirect | 160 |
| 社区 | PostCard / PostDetail、AccountAvatar / account banner | 预览 320、多图详情 640、单图完整展示原图；静态头像/banner 原来源 |

高 DPR 首次渲染会提高档位：160 在 DPR > 2 使用 320；320 在 DPR > 1.5 使用 640。纯 URL 映射与显示选择分开；保留 query/hash 和旧 `.thumb.webp` 文件。没有虚假 `srcset` 宽度，也没有先加载原图再改 URL。

图片失败状态绑定源 URL 或图片 key：首页、年度隐藏失败图片换实体恢复；Phone 行、详情、设置头像和社区账号头像切换恢复。列表 lazy/async、首页关键 Hero eager/high；保留既有尺寸和布局。

### 例外与非当前入口

- 旧 `pages/yearly-review` 六组件由旧 `CustomSummary` 组合；当前页面只使用 V2。`AlbumEraOverviewSection`、`AlbumReleaseCompositionSection`、`AlbumEnrichmentView` 无当前详情入口，未恢复旧页签。
- 社区九张静态头像 400×400 合计 161,666B；十张静态 banner 1280×426 合计 814,539B。它们不属于音乐封面路由，维持原 URL，头像 lazy/async、首屏 banner async。
- Spotify profile 头像、LLM provider logo、外部节目/帖子图片不通过本地派生接口；合理的原图完整查看保持原图。CSS 背景只有内嵌 NoiseOverlay SVG，无音乐封面背景漏项。

### 后端与资产

固定 160/320/640；原图字节不变、保比例不放大。GET 不编码、不触发公开写任务，缺失/过期短缓存回退，命中 WebP 七天 private 缓存及 304。生成时比较源状态，派生文件记录源 mtime，避免发布窗口源替换被误认 current。

本地验收使用 SQLite Online Backup 副本，从 schema 81 加性升级至 85，源正式库保持 81；两者播放记录均 94,760。隔离 covers 4,358 张原图，生成 13,074 个变体，`failed=0`。派生目录约 260MiB；该数字属于本地副本，不等同生产资产数量。

完整 quality 首次发现 HEAD 已存在的四个测试文件八处 `Callable.cache_clear` 类型错误，最小替换为无默认值 `getattr(..., 'cache_clear')()`，保留原严格清理行为；对应 43 项测试、定向 mypy/ruff 通过。没有更改业务或降低门禁。

## S4 本地验收

后端图片定向 44 项通过；前端最终专项 5 文件 / 91 项及 build 通过。完整全栈与真实浏览器测量进行中，结果待补。

### 用户 HTTPS 修复前基线

fresh browser context 为 cold，同一 context 普通 reload 为 warm（保留浏览器 HTTP cache，未通过 request interception 禁用缓存）。三次中位数如下；bytes 是唯一本地图片 encoded body，并不表示 warm 仍重新传输全部图片：

| 页面 | Desktop cold bytes / 首屏稳定 ms | Phone cold bytes / 首屏稳定 ms |
| --- | --- | --- |
| 首页 | 639,363 / 5,395 | 557,028 / 4,410 |
| 播放记录 | 4,576,830 / 9,907 | 2,565,445 / 9,183 |
| 音乐档案 | 3,466,976 / 5,794 | 2,031,486 / 4,416 |
| 播放排行 | 50,590 / 4,829 | 待最终配对汇总 |

首页随机回归卡片可能换图，须按共同封面 ID 配对体积，不能简单逐次相减。首屏稳定时间包含 API 与浏览器准备，关键图片完成时间另行登记。已有图片样本均无坏图。

生产 2022–2026 年度接口均返回 404 `年度总结尚未由管理入口生成`，此基线不能当零图片通过或计算图片收益。已在隔离副本生成真实 2026 V2 artifact，用 HEAD 旧前端（5184）和修复前端（5173）对同一 API 测年度章节；生产验收将由已有私有入口有界准备年度 artifact，再测公开真实内容。

## S5 发布及线上验收

待填写固定 SHA、Actions、Online Backup、补建资源与 HTTP/浏览器结果。
