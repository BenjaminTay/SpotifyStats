# 音乐封面传输规则

## 来源和尺寸

前端本地音乐图片统一由 `frontend/src/lib/cover-thumbnail.ts` 选择：数字 ID 的 `/covers/albums/`、`/covers/artists/` 支持 160、320、640 和 original。`coverArtworkUrl` 负责纯地址映射；渲染使用 `coverDisplayUrl`，在首次请求前考虑当前 DPR。外部 URL 和其他类型不得凭名称或 URL 猜测新地址。

| 场景 | 目标文件 | 典型 CSS 尺寸 |
| --- | --- | --- |
| 列表封面、头像 | `id.thumb.webp` | 40–64px |
| 详情摘要、档案手机封面 | `id.320.webp` | 80–160px |
| 首页主视觉、档案桌面封面、大卡片 | `id.640.webp` | 200–350px |
| 原图查看或更大展示 | `id.jpg` | 按原始图片能力展示 |

选择应兼顾 DPR、图片纵横比和实际源图尺寸。派生图保留比例且不放大；不能把最长边当实际宽度填入 `srcset`。首次到达页面时不要先加载原图再换缩略图。query/hash 随选择保留，同一 URL 变体可以重新选择。

高密度显示规则：160 在 DPR > 2 时使用 320；320 在 DPR > 1.5 时使用 640；640/original 保持不变。`coverThumbnailUrl` 兼容入口也使用该规则。这样 156/158px 手机大图在 DPR 3 下不会仍使用 320px；非方源图的清晰度以原图能力为上限。

## 持久化与回退

160 保留既有 `data/covers/thumbnails/{type}/{id}.webp`；320/640 使用同目录的 `{id}.{size}.webp`。原图仍在 `data/covers/{type}/{id}.jpg`。这些文件不进入 Git 或镜像。

新下载后生成固定尺寸，派生失败不阻止原图发布。源文件状态变化时拒绝发布过时结果；使用原子替换。请求路径不执行编码。

变体命中时使用 WebP、ETag/Last-Modified 和现有七天 private 缓存。缺失或过期时回退原图，使用 60 秒短缓存，补建后即可恢复变体；原图缺失时继续既有原图路由回退。公开展示仅读取已知来源，不触发 Spotify 查询或后台下载。

## 页面行为

仅关键首屏视觉按需使用 eager/high；其他章节和列表 lazy/async。布局提前保留图片空间。源图片变化时重置失败/隐藏状态，保留现有占位及点击行为。

当前年度 V2、音乐档案 Desktop/Phone 都消费公共选择规则。旧年度展示、暂不开放的详情页签不因封面改动恢复。外部社区头像、节目图等记录为来源边界，不算本地派生覆盖。

## 验证

通过 `scripts/cover_image_probe.py` 固定路由、视口、DPR，测首屏/完整滚动、冷/热缓存和图片体积。未准备、错误和没有图片的页面必须说明状态，不能充当图片加载成功。用户外部 HTTPS 与服务器 loopback 分别标记，传输字节下降与实际时间下降分别报告。

补建命令及生产回滚见[生产手册](../../deploy/production/README.md)；本次实施和基线见[方案](../plans/2026-10-03-cover-image-optimization-plan.md)、[验收报告](../reports/2026-10-03-cover-image-optimization-acceptance.md)。
