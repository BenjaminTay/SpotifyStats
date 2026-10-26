# SpotifyStats 移动端 M0 视觉原型

这是移动端网页 M0 设计冻结阶段的可交互方向稿，不是生产实现。

## 包含画板

- 首页。
- 播放统计。
- 播放排行。
- 个人 Billboard 周榜。
- 单曲详情。
- AI 问答。

六个画板共同验证 Mobile Top Bar、Bottom Nav、Section Switcher、Filter Sheet、移动榜单行、推入式详情以及 AI 输入态。

## 查看方式

在仓库根目录启动静态服务器：

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1
```

打开：

```text
http://127.0.0.1:8765/docs/archive/06-productization-closeout/mobile-web-m0-prototype/
```

原型支持：

- 360 / 390 / 430 三档手机画板宽度。
- 白日 / 夜间主题。
- 六个代表页面切换。
- 栏目、时间、筛选、实体数据和证据 Bottom Sheet。
- 底部主导航和推入层返回。

## 归档和素材

2026-10-25归档。封面改为随原型保存的通用占位图，不依赖本机data目录；原画板与交互保留，当前UI以frontend/UI_STYLE_GUIDE.md为准。Inter字体沿用前端安装依赖中的文件，未安装前端依赖时使用系统字体回退。

## 边界

- 原型使用静态示例数据，不请求 API。
- 页面文字和数字用于展示信息层级，不作为统计事实验收依据。
- 正式实现必须复用现有 API、TanStack Query、过滤指纹和实体链接规则。
- 社区、年度总结、播放记录等页面已纳入完整设计规格，但不在六屏原型中重复制作。

对应冻结规格：[`../2026-08-05-mobile-web-m0-design-freeze.md`](../2026-08-05-mobile-web-design-and-plan.md#spotifystats-移动端网页-m0-设计冻结规格)。
