# OOM 冷个人统计：曲目聚合与Top250切片输入投影

2026-10-14；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。唯一研发树 `codex/album-rank-cost`，HEAD仍为`dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06`。继续本地隔离最小修复，未提交、推送、整合业务到main或部署。

**保留局部冷专辑候选；整体资源Partial。** 既有Dockerfile mmap阈值与Records启动重排冻结。本轮只增加曲目榜单聚合六列投影及Top250切片前八列投影，三个冷专辑stats的采样峰增量低36–39MiB。三个有效新窗口各33次读取、完整响应与六份业务事实一致，strict通过。整体读取最高峰和驻留未下降，最高峰已转到艺人统计首次请求；不以局部收益关闭整体OOM。

## 归因与最小实现

上轮读阶段加权表约71k行×41列、37k行×57列；曲目聚合只消费track_id、track_name、artist_name、album_name、ts、ms_played，但拼接时复制了完整宽表及附属元数据。Top250还在聚合前展开全宽时长轨道，每个冷专辑重复该临时工作集。

1. `analysis_stats_service::_chart_agg` 仅在track分支先解析显式/附属时长，再投影六字段进入加权。清除的attrs仅属于新投影，原事件与时长不修改；加权结果八列。album/artist分支保持原路径，原canonicalization、聚合、排序和序列化AST不变。
2. `entity_stats_service::_published_album_top250_counts` 沿用已有`build_duration_frame(source_columns=...)`，切片前只留六业务字段、ts_date及显式listening intervals。ts_date保留无interval的兼容输入；有interval时仍按原小时边界展开，保留低于次数门槛的时长。保持一次完整时长展开、三窗口独立过滤、L2兼容排序、250行边界、并列/多presentation及取消检查。

没有减少缓存预算、清缓存、强制GC、新增trim或写入公开GET；没有更改统计口径、schema或发布版本。实现复用现有投影接口，不恢复历史混合OOM补丁。

## 正确性与封装

67项Top250/排名/取消专项与84项图表/快照/时长/缓存消费回归共151个不重复用例通过。15项新增用例覆盖四配置×三个时间范围的完整次数/时长榜单、limit/offset、隐式附属时长、跨午夜、无计数有时长、原输入独立性及展开前字段预算。参考路径关闭投影后仍执行原完整宽表加权/排序；既有完整legacy个人统计、seed catalog、250边界及时间切片oracle保持。

三项所有权/宽度用例在恢复原函数的基线上预期失败，候选通过。首个测试观察器未兼容baseline的duration_frame=None而报AttributeError，原失败保存；修正观察器后基线确实因宽字段断言失败，不将初次工具错误记成回归证据。Ruff/format与项目mypy hook通过。

本轮使用[此前封存基底封装](2026-10-14-oom-image-startup-bounded-verification.md)的同一运行时；不重试默认Python基镜像、不联网构建。三个镜像均不挂backend源码，518个Python文件与冻结上下文一致，mmap阈值在Python初始化前生效，依赖相同。

| 变体 | 本地完整镜像ID |
| --- | --- |
| 已冻结启动候选 | `sha256:ee0637db224de6c07fa8b942500df10a9dd255bc75114e050a656a6a8bf2240d` |
| 仅六列加权输入 | `sha256:f8ea594414049e44b4aa4350c5790f99d0e254f2ec44c4ed2e6901316c6ecb03` |
| 六列加权+八列切片输入 | `sha256:36fd0f4ff920b8bac75455be8123dce7c10b4734a8d3b3ddb4accb379a3d5e56` |

默认基镜像发布成品验证仍未完成；封存基底包装与原生准入分列，未上传registry。

## 有界Linux对照

沿用关闭七文件历史输入，不是最新生产等价备份。每变体均新建副本并正常启动一次；规范rank validate/install/verify绑定本地lineage，warmup=0、11维护完成。4GiB/2CPU、无网络/端口、只读根、3GiB进程/900秒窗口守卫。三有效窗串行运行，同一33请求序列：原9次及八新增实体三轮，最大两并发；未热重启或追加复测选较好结果。

### 首次串行冷专辑stats采样峰增量

| MiB | 已冻结启动候选 | 六列加权 | 加切片前投影 | 最终−基线 |
| --- | ---: | ---: | ---: | ---: |
| folklore L3 fixed | 82.539 | 49.875 | 43.777 | −38.762 |
| Melodrama L2 fixed | 76.887 | 47.586 | 40.418 | −36.469 |
| reputation L3 dynamic | 106.566 | 74.789 | 68.816 | −37.750 |

这些是带排名个人stats，逐次以前基准取真实进程采样峰；不是default overview64MiB门禁。完成后驻留增量约0–27MiB，不用历史VmHWM相减，也不以并发共享窗口冒充单请求。

### 总窗口结果

| MiB | 已冻结启动候选 | 六列加权 | 加切片前投影 |
| --- | ---: | ---: | ---: |
| 启动采样峰 | 1153.715 | 1153.852 | 1173.363 |
| 就绪RSS | 532.750 | 537.492 | 530.445 |
| 读取采样峰 | 712.582 | 716.180 | 719.070 |
| 最终idle RSS | 644.516 | 648.465 | 651.648 |
| 就绪→最终增长 | 111.766 | 110.973 | 121.203 |
| 最终合法帧预算 | 321.388 | 321.388 | 321.388 |

最终变体较基线启动峰高19.648MiB、读取峰高6.488、末尾高7.133、增长高9.438；没有整体驻留/最高峰收益声明。基线最高读取点位于reputation首次；两个投影变体最高点均位于Taylor Swift艺人stats首次，active-stage标记为空，当前证据只定位请求段，未声称已定位艺人内部确切分配栈。曲目加权缩列确实降低局部专辑工作集，另一路艺人冷载入仍主导全窗口峰。

三轮扩展idle：基线644.516/644.516/644.516；六列646.395/646.551/646.695；最终651.621/651.621/651.621MiB。各侧帧预算固定321.388MiB/13项，未达到384MiB上限，不证明饱和淘汰或全站长期平台。观察器也保留有限记录，不根据小幅差异断言泄漏。

三侧33份完整body逐字节一致（两份基线对账交叉核对同一body SHA）；latest三范围stats/Records六份业务事实一致，跨构建仅移除meta.generated_at。每侧strict未放宽时钟：来源、治理、队列、发布与六sidecar保持；完成均8103 done/38 failed，历史failed完整行相同，容器均退出0/OOMKilled=false，原七文件SHA不变。

最大实际采样间隔依次0.845/0.773/0.886秒。ARM引擎/amd64仿真，一窗每变体；只支持当前同源方向，不证明原生CPU/时延、生产峰值或整体OOM准入。

## 处置与恢复

最终本地候选共六文件：Dockerfile、Records service与原所有权测试、analysis stats service、entity stats service与新投影测试。已有启动候选未重写；六列单独试验及所有原始结果也保存。共享状态仅main维护，整合树保持原HEAD且干净，全部未暂存/提交/推送/部署。

独立恢复入口 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/oom-track-chart-projection-20261014/`：基线/两投影源码及补丁/测试、封装上下文/源核验、三份运行副本、33完整body、采样/阶段/原生分配器、strict、六事实oracle、观察器初败与修正、协调文档快照。归档校验和三个自有已停容器清理收据独立保存；私人数据不进入Git/镜像，镜像暂留本地，不清理其他Docker资源。

下一定位目标是艺人stats首次请求段，先分解有效署名fan-out、canonical artist与范围载入的活对象重叠。默认镜像、原生、overview64MiB及长期/更广并发仍OPEN。本轮局部冷读候选可审阅，整体OOM继续Partial，暂不发布。
