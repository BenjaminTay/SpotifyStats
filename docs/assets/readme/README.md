# README 展示素材

本目录保存根目录 `README.md` 使用的产品截图。截图来自本地运行中的真实页面，使用 README 展示用的本地演示数据，包含播放次数、歌曲名称、封面和榜单内容；它们只用于展示产品界面与统计能力，不代表项目提供公共在线 Demo。

| 文件 | 内容 | 图片尺寸 |
|---|---|---:|
| `home-desktop.png` | Desktop 个人音乐头版 | 1200 × 704 |
| `home-phone.png` | Phone 个人音乐头版 | 390 × 844 |
| `analysis-stats-desktop.png` | 播放统计 | 1200 × 704 |
| `billboard-weekly-desktop.png` | 个人 Billboard 周榜 | 1200 × 704 |

截图更新后，应同步检查根目录 README 的图片引用，并运行：

```bash
python3 scripts/docs_audit.py
python3 scripts/docs_audit.py --include-archive
```
