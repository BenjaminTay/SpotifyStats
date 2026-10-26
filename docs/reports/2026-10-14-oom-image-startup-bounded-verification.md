# OOM 后续：镜像封装、启动重排与有界读取验证

2026-10-14；`SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。研发树 `codex/album-rank-cost`，HEAD `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06`。本轮只做本地隔离实现与验证，未提交、推送、整合业务到 main 或部署。

**本地启动候选保留；整体资源 Partial。** 在此前 Dockerfile 固定 mmap128KiB 的候选上，仅将 Records 的艺人历史构建提前到曲目/专辑投影分配之前。两侧封装镜像、同源新副本各完成一次正常启动及33次读取，启动采样峰低90.129MiB，完整事实一致；读取峰、末尾与读取增量略高，不能称为读取内存优化。默认 Python 基镜像的完整构建尚未通过，封存运行时替代基底的本地封装验证单独记账。

## 改动与正确性

`backend/services/analysis_records_service.py::_build_entity_frames` 先建立原有逻辑事件ID，然后执行原有艺人载入、时间范围和异常回退，再建立曲目/专辑结果。原艺人 try/except 与其余 builder 语句的 AST 均完全一致，仅执行次序改变。没有恢复上轮未采用的复制删除/中间表释放补丁，没有改变统计口径、公开读取边界、缓存容量或维护回收调用。

新增两项所有权用例覆盖正常与艺人异常回退：艺人构建入口只持有必要的一份事件输入副本，而基线同时持有五份；断言放在 builder 外，避免异常回退吞掉断言。另核对源输入独立性、曲目/专辑身份、时长及输出修改不影响源和艺人结果。新用例基线2 fail、候选2 pass；41项专项与128项消费/包装合同共169通过（含12项包装合同，不重复计数）。Ruff和项目mypy hook通过。

## 镜像结果与边界

精确候选 Dockerfile 的 backend stage 使用仅含 tracked backend/scripts/requirements 的构建上下文，不含私人库、导出和密钥。默认 `python:3.9-slim` 构建先遭 PyPI超时/TLS断连，再遭既有 Docker Hub镜像源502。将已经解析的官方 amd64基镜像 digest固定到 named context后，analytics层成功，API依赖下载超时；一次复用已完成层的重试出现 Pillow索引解析错误，保留所有原失败，不修改全局Docker/Codex配置或依赖版本。

已有封存运行时实际安装 Pillow11.3.0、Python3.9.25，包元数据Requires-Python为≥3.9；[Pillow官方支持表](https://pillow.readthedocs.io/en/stable/installation/python-support.html)也列出该组合。不能把索引失败直接归因于版本不兼容，也未为此升级Python或放宽依赖。

随后将既有c0d镜像作为本地测试基底，通过named context运行相同Dockerfile的完整backend stage，构建两份封装镜像；无构建网络，依赖保持已有版本。这是封存基底的包装证据，**不是默认Python基底的发布成品准入**。

| 镜像 | 本地完整ID |
| --- | --- |
| 固定mmap基线 | `sha256:2695b2a3b82d8721328d36a96ca7628480b13b9954839900c9b7629e3cc3c2f9` |
| 加启动重排 | `sha256:ee0637db224de6c07fa8b942500df10a9dd255bc75114e050a656a6a8bf2240d` |

镜像内518个Python源文件均与各自冻结上下文一致，两侧仅Records service一个Python文件不同。容器不挂载backend源码；实际Config.Env的`MALLOC_MMAP_THRESHOLD_=131072`在Python初始化前生效，构建代理未进入运行环境。两侧Python3.9.25/glibc2.41及pandas2.3.3/numpy2.0.2等依赖相同，容器SQLite载荷检查通过。未构建前端/发布镜像，不上传registry。

## 两个有效隔离窗口

原始输入沿用上轮关闭七文件封存，不是新生产等价备份。新窗口分别从原输入复制，不重用已热过的副本。四默认排名清单经规范validate/install/verify绑定本地lineage；warmup=0、正常维护11项。4GiB/2CPU、无网络/端口、只读根、3GiB进程守卫、每窗900秒。

每侧原专辑L3 fixed含/不含排名各三轮、艺人dynamic含排名三轮共9次；再增加folklore、Melodrama、reputation、Mine、happiness、Billie Eilish、Adele、Lorde共八目标三轮。前三个专辑和曲目采用已发布默认配置，艺人使用已就绪dynamic=true。首次六目标串行，再两个冷目标最多两并发；后两轮最多两并发。共33次200，八个新增目标均found=true且含排名响应有效，未清缓存、强制GC或添加trim。

| MiB | 固定mmap封装基线 | 加启动重排 | 候选−基线 |
| --- | ---: | ---: | ---: |
| 启动采样峰值 | 1230.609 | 1140.480 | −90.129 |
| 就绪RSS | 528.859 | 532.266 | +3.406 |
| 读取采样峰值 | 713.266 | 724.609 | +11.344 |
| 原9次读取末尾idle | 605.020 | 613.633 | +8.613 |
| 扩展33次最终idle | 646.371 | 655.594 | +9.223 |
| 就绪→最终增长 | 117.512 | 123.328 | +5.816 |
| 最终合法帧预算 | 321.388 | 321.388 | 0 |

启动收益是这项候选的保留理由；上表读取变化完整保留。上一报告的无mmap基线不能直接与本轮新序列拼成同窗对照。

两侧33份完整body逐字节一致；latest lifetime/last4weeks/last6months的stats/Records六份业务事实一致，跨构建仅剔除`meta.generated_at`。strict读取比较不放宽任何时钟：源表、治理、队列、发布及六sidecar均保持。完成队列均8103 done/38 failed，历史failed完整行相同；两有效容器均退出0、OOMKilled=false，原七文件SHA不变。

最大实际采样间隔基线0.733s、候选1.091s。环境仍为ARM Linux引擎上的amd64仿真；不推断原生CPU/时延、全站并发上界或生产OOM准入。

## 读取增长的剩余结论

两侧扩展后帧预算固定321.388MiB、13项，低于384MiB上限；没有达到预算饱和或证明淘汰行为。扩展三轮idle：基线646.367/646.371/646.371MiB；候选654.477/655.020/655.566MiB。支持有限序列内驻留趋稳；观察器本身保留有限测量记录，不据约1MiB差异诊断泄漏，也不宣称长期平台已关闭。

首次串行stats的采样峰增量：folklore基线79.688/候选83.340MiB，Melodrama79.645/81.473，reputation动态106.914/107.520；对应完成后增量约0–28MiB。读阶段观察到加权表约71k行×41列、37k行×57列，后续可进一步拆分冷排名/加权计算的临时工作集；本轮未据此追加业务修改。

这些是含排名个人`stats`，不是默认`overview`。规划[默认overview资源门槛](../archive/06-productization-closeout/2026-10-09-music-detail-chart-performance-plan.md)的64MiB指标不能套用为此次stats门禁失败；默认overview逐请求验证仍另行开放。并发窗口的内存是共享观测，不冒充单请求归因。

## 原失败、处置与恢复

首个封装基线窗口因未发布的艺人dynamic=false排名配置返回snapshot_unavailable/503，退出1；未运行其候选侧，原日志/配置/探针/输入及中止状态全部保留。核对已发布配置后，新建v2两份副本完成上述序列，未重启原窗口或热重试。默认镜像的网络/索引失败与所有权基线的预期失败同样保留。

研发树保留Dockerfile、Records顺序调整及新增所有权测试，均未提交；共享文档只在main维护，整合树不改。独立恢复入口 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/oom-image-startup-20261014/`：冻结源码/补丁/测试、构建上下文和失败、镜像配置与源核验、有效及原失败运行副本、完整body、采样/分配器/阶段、strict和六事实oracle、协调文档快照。归档校验和本轮自有停止容器清理收据独立保存；封装镜像暂留本地，不清理其他镜像、卷或Docker服务。

当前可本地审阅三文件候选。默认基镜像完整构建、原生资源验证、默认overview64MiB和长期/更广并发仍未完成；冷stats临时工作集已有定位线索。整体OOM继续OPEN，本轮不自动提交、推送或部署。
