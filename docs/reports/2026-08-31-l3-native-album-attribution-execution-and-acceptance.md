# L3 原生专辑归属执行与验收报告

> 证据日期：2026-08-31
>
> 实现状态：IMPLEMENTED
>
> 真实数据治理：PASS
>
> API 与响应式浏览器验收：PASS
>
> 默认完整全栈门禁：PASS（7 个必需阶段全部通过）
>
> 远端状态：PUSHED（`origin/main`；当前主线 `d37e8aaf`）
>
> 部署状态：DEPLOYED（dual；生产代码版本 `b0d674bd`）

## 1. 结论

L3 已从“歌曲版本归并后由消费者临时猜测专辑”改为两段确定性投影：先把原版、Taylor's
Version、Acoustic、Live、Remix 等归入同一歌曲作品，再把每个歌曲作品唯一归属到一个原生专辑
项目。Taylor's Version 专辑采用完整作品并集；Live、Acoustic、Remix 等发行不整张挂接，而是
逐曲回流，无法可靠回流的现场独有曲、翻唱和 Medley 继续留在来源项目。

本轮发布了 6,218 条机器归属，人工、冲突和未覆盖均为 0。L2 仍保持独立录音/发行语义，原始
`plays`、`tracks`、`track_artists` 行数与内容 hash 完全不变。两份独立 Online Backup 副本、
本地主库、第二次 dry-run、真实 API、Desktop 与 390px 浏览器均已通过。

## 2. 已实施范围

- schema 68 新增歌曲到专辑归属、状态、问题和人工覆盖层；关系可重建、可审计，不重写原始事实。
- 使用稳定 work key 和输入 digest；发布时检查 revision fence，归属与 revision 原子切换。
- 机器优先级为：人工覆盖、录音室专辑、Deluxe/EP/Soundtrack、单曲、精选集 residual、
  Live/alternate residual；稳定 ID 只处理证据完全相同的最终 tie。
- 只有 Taylor's Version/明确重录专辑建立整张 album composition；Live、Acoustic、Remix 只做
  逐曲归属。
- L3-only 单曲可作为归属目标但不重复暴露为默认专辑实体。
- Billboard、音乐查找、实体统计、年度总结、Wrapped、AI 只读工具和缓存 source fence 共用同一
  attribution revision，不再各自按 album name 或排序去重决定 owner。
- Settings 提供健康、问题、机器理由、人工覆盖与重建入口；专辑详情提供 residual、已回流曲目和
  完整来源解释。
- 标题策略升级为 `nfkc_t2s_composition_relation_v2`：识别由括号或分隔符隔开的具名
  `... Version`，同时让 Intro、Outro、Interlude、Medley 等结构性标题继续 fail closed。

## 3. 两份独立副本的确定性演练

两份 424 MiB Online Backup 初始文件 SHA-256 均为
`1e27d6c...ab7fd`。两份副本均从 schema 67 升至 68，完成 apply 和第二次显式 dry-run；结果如下：

| 证据 | 副本 1 | 副本 2 |
|---|---|---|
| track identity revision | 9 → 10 | 9 → 10 |
| album project revision | 4 → 5 | 4 → 5 |
| attribution revision | 1 | 1 |
| 自动 / 人工 / 冲突 / 未覆盖 | 6,218 / 0 / 0 / 0 | 6,218 / 0 / 0 / 0 |
| input digest | `1672bf27ac2700f3d59c97ead110987ff032eefe3e4f6044ff03cca415f63edb` | 相同 |
| composition projection hash | `325ccf6aa07f3a78a0e4a9c9c41ca7daabc8c63051bad2f313694eb8902a7dce` | 相同 |
| attribution projection hash | `d435a45ba235506befdf682c548694917889537876319253d4958f80ba8ef6ee` | 相同 |
| state mapping digest | `475ac03df1f6fb06bb93a9e427485dd0b9bc2ed3c71035ca907caa328f03c4fb` | 相同 |

第二次 dry-run 中 L2、歌曲 composition、专辑 composition 和 attribution 均无变更；完整性、外键、
关系问题均为 0，四套音乐查找快照 ready、failed 为 0。

## 4. 主库执行与原始事实保护

- run id：`b16fcb9c-d15f-4f3f-9d22-6ccae9d72ce8`
- 执行前 Online Backup：
  `data/backups/spotify_stats_20260831T095731Z_before-version-governance.db`
- schema：67 → 68
- track identity revision：9 → 10
- album project revision：4 → 5
- attribution revision：1
- L2 / L3 搜索实体：7,873 / 7,438
- 搜索 builder：`music_search_snapshot_v9_l3_album_owner`
- 第二次 dry-run：完全收敛
- 主库 projection hash：与两份副本逐项相同

| 原始表 | 行数 | 执行前后 SHA-256 |
|---|---:|---|
| `plays` | 92,908 | `bfa9f79b095d4ca865a6d84a10997f83e1f2fd44db9262c784c8cc1be9e1ad37` |
| `tracks` | 9,549 | `c8add4d665b193f495760d791d2136dbbd1f3df4e4a94c54a2ed8db5329f5593` |
| `track_artists` | 9,983 | `6cfbaf91359011d726211c9be73ea382d3d85fbf854a4974b67503821dfcc879` |

数据库和备份均属于本地数据，没有进入 Git。

## 5. 真实规则样本

### 5.1 Taylor's Version 与 Vault

- `Say Don't Go` 的来源项目是 `1989 (Taylor's Version)`，L3 原生目标为 `1989`，理由为
  `rerecord_union`。
- 原版与重录版专辑在 L2 仍是独立发行；L3 以并集纳入原曲和只存在于重录版的 Vault 曲目。

### 5.2 嵌套版本标题

真实数据发现 `willow - dancing witch version (Elvira remix)` 未被旧策略归入 `willow`。策略升级后
新增 5 个 composition group，并更新 `willow` 组；L3 work 数由 6,226 降至 6,218，消除 8 个重复
作品，同时不放宽裸文本 `Song Anniversary Version` 等歧义标题。

### 5.3 Live 逐曲回流和守恒

`Speak Now World Tour Live` 的实际来源播放为 53 次：

- 12 首可对应原生专辑的歌曲回流到 `Speak Now`，合计 43 次；
- 4 首 residual 保留在现场项目，合计 10 次：Medley 6 次、`Drops Of Jupiter` 2 次、
  `Bette Davis Eyes` 1 次、`I Want You Back` 1 次；
- `10 + 43 = 53`，来源与最终归属守恒；
- `Bette Davis Eyes - Live/2011` 保留在现场项目，没有错误归入其他艺人的原唱作品。

这证明现场专辑不是整张消失：能回流的逐曲回流，现场独有/翻唱/Medley 仍可组成有效 residual
专辑实体。

## 6. API 与浏览器验收

- `/api/health`：`ok`。
- `/api/version-merge/l3-album-attributions/health`：healthy，revision 1，6,218 条归属，冲突、未覆盖、
  issue 均为 0。
- `willow`、`Say Don't Go` 和 `Bette Davis Eyes - Live/2011` 的真实查询均返回上述预期 owner。
- 专辑项目 API 返回 `Speak Now World Tour Live` 的 4 首 residual、12 首 transferred 和完整来源。
- Desktop 与 390×844 Settings 均显示健康计数、机器理由、搜索、人工目标/原因和重建入口。
- Desktop 与 390×844 专辑详情均显示“保留在本项目”和“已回流到原生专辑”；控制台
  0 error / 0 warning。

## 7. 测试与已知边界

- 后端 unit：1,572 passed；contract：411 passed。
- 后端全量：2,522 passed，4 warnings；默认完整门禁的 backend 阶段耗时约 16 分钟。
- 前端：76 files / 612 tests passed。
- 前端生产构建：PASS。
- 当前改动文件的 Ruff、格式、mypy、detect-secrets 和定向 ESLint：PASS。
- 仓库级前端 ESLint 仍有 174 个既有错误，均不在本轮改动文件；因此不把它描述为本轮回归。
- 专辑项目 `view=project` 已绕过完整 Billboard 详情构建。真实冷请求由约 4 分钟降至约 60 秒，
  revision cache 命中后为即时返回；冷路径仍有继续优化空间，但不影响本轮归属正确性与缓存后消费。

默认完整全栈门禁在 `321cb9b5` 加本轮未提交详情快路径/报告的工作区上执行，7 个必需阶段全部
PASS，总耗时 2,974,754 ms（约 49 分 35 秒）：

| 阶段 | 状态 | 耗时 |
|---|---|---:|
| quality | PASS | 46.157s |
| backend | PASS | 970.187s |
| api | PASS | 871.699s |
| browser-routes | PASS | 691.855s |
| browser-interactions | PASS | 93.656s |
| browser-inventory | PASS | 84.088s |
| browser-compat | PASS | 216.921s |

其中 API smoke 145/145、边界探针 113/113；217 个 OpenAPI operation 与 102 项参数 obligation 的
未归类数均为 0。40 个控件清单路由/视口共检查 2,014 个控件和 394 个主要触控目标，违规为 0；
Chromium、Firefox、WebKit 全部通过。

## 8. Git、远端与部署状态

- `fec889c0 feat: 实现 L3 歌曲原生专辑归属`
- `321cb9b5 fix: 补齐 L3 嵌套版本自动归并`
- 最终验收与详情快路径已在同一个阶段级提交中收口；提交 hash 以当前 Git 历史为准。
- 原始验收轮当时未获得 push 和部署授权；2026-09-13 后续交付已将对应代码推进到 `origin/main` 并随 `b0d674bd` 部署。
