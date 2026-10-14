# 原生回收研发分支 CI 与发布准备

2026-10-13；SS-2026-10-08-001，关联SS-2026-10-09-001。

## 当前结论

用户授权仅推送现有研发分支并检查CI，再完成发布准备；不推送main、不部署。精确 `6c74b9b416dbba47b354b850bdfe678f26ece63a` 已推送到 `codex/album-rank-cost`，远端main仍为c0d699e5。本轮没有触发正式发布。

**发布状态：HOLD，生产触发条件不满足。** 私密输入和静态部署检查已经准备，但只读核对发现当前生产Backend的 `SPOTIFY_STATS_WARMUP=0`。本补丁仅在完整预热结束时调用trim，当前配置不会进入该调用点；本地完整预热驻留收益不能直接代表当前生产启动。

不调整生产配置、不自动启用full预热、不增加生产探针或重启来补成成功。建议下一阶段保持warmup=0，以现有重型维护完成边界为候选触发点，单独审阅最小修正并做匹配实际启动方式的有界验证；本轮未实施该修正。

## 推送与 CI

- 普通精确refspec仅推送 `HEAD:refs/heads/codex/album-rank-cost`，实际退出0，未force-push、未推送其他分支。
- 独立ls-remote确认研发分支为6c74b9b4、main为c0d699e5，与推送前main一致。
- [日常CI 38414168750](https://github.com/BenjaminTay/SpotifyStats/actions/runs/38414168750)：精确head 6c74b9b4，attempt1成功，实际job `115354026493` 成功。原日志记录unit2735 passed/2 skipped、contract571 passed、前端803 passed/4 skipped；文档、lint与构建通过。Production deployment contract checks步骤因inputs=false为skipped，不称部署契约远端通过。
- NoDeploy部署契约workflow的路径条件不匹配本次四backend文件和文档，未触发；production-release仅匹配main或显式dispatch，本轮未触发。三模式静态检查在本地单独执行，不把它称作远端NoDeploy通过。
- 初次GitHub直连长时间无输出，最终HTTP2 framing error/实际128；使用项目既有代理和HTTP/1.1后查询、推送及CI读取成功。保留原失败，不修改Codex或Git全局网络配置。
- CI watch在完成前一次API读取EOF而实际退出1；独立run/job最终API及完整job日志确认attempt1成功。watch工具退出与workflow结论分开保留，不重跑CI。

## 已准备材料

当前c0d与目标6c的backend/scripts/deploy/workflow差异仅四个native/warmup及测试文件，发布事实CLI、builder、schema、统计规则和发布脚本均未改变。

以当前已发布镜像运行规范只读verify/export/validate，数据目录以同一 `/app/data` 命名空间只读挂载。关闭warmup、搜索重建、L3调和及外部封面；工具禁网、无端口、只读根文件系统。输出只写独立私密临时目录，不进入生产数据或backups部署目录。

| 材料或检查 | 结果与范围 |
| --- | --- |
| 四默认个人排名 | verify/export/validate实际0；目标release_sha绑定6c74b9b4 |
| 四默认详情投影 | verify/export/validate实际0；源lineage和治理检查保留 |
| Billboard现成发布 | live verify实际0，48目标；本次live export在512MiB隔离工具内退出137，未产出可用新清单 |
| Billboard复用清单 | 原c0d封存清单字节复用；规范validate在独立关闭七文件副本实际0，48目标；轻量只读live核对确认source fence与builder相同 |
| full/showcase/dual | 本地profile-only三项实际0；仅静态配置，不连接或部署生产 |

三份目标SHA私密JSON已取回并封存为600权限；复制SHA与规范验证记录一致。未提交Git、未进入镜像或CI artifact、未上传服务器部署目录。目标镜像尚未构建，不能把当前镜像事实工具的验证称为目标镜像准入；未来激活前必须重新验证source fence及成品。

本地Billboard验证峰值观察约855MiB，受2GiB/120s有界守卫约束，未停止；原始七文件备份与自有验证副本均保持字节一致。没有builder、import或提高生产内存后重试export。

## 生产只读核对与失败保留

核对时三容器仍为c0d且healthy，schema90、plays94760、活动任务0。Backend StartedAt仍为2026-10-13T02:52:51.869156096Z，当前warmup为0；容器身份、镜像身份、启动时间及源数据库/sidecar/WAL/SHM物理状态在受限导出前后均一致。没有个人统计GET、冷构建、排队、停服或部署。

工具exit137对应内核 `CONSTRAINT_MEMCG`：512MiB独立导出容器中的python被杀，cgroup与生产Backend不同。此为本轮隔离工具OOM，不能隐去或描述成整体窗口无OOM，也不等于生产Backend遭global OOM。失败输出、内核定位和后置身份核对保存。

轻量fence工具前两次错误导入不存在的module而退出1，均保留；改为规范CLI自身cache对象后实际0，未涉及产品修改。服务器自有临时目录完整取回并校验后移除，仅清理本轮工具输出，不动数据库或部署目录。

## 下一阶段与发布条件

1. 本分支精确SHA的实际CI已核对通过，原工具失败保存，不新增CI重跑。
2. 维持main推送与部署暂停，先解决warmup=0条件下的回收调用点；不以开启完整预热来绕过问题，因为新增构建峰值没有准入证据。
3. 最小修正若另获授权，冻结新源码并验证其在warmup=0、minimal/full及维护失败时的调用边界、缓存保留、完整响应和资源收益，再决定新固定版本。
4. 新版本发布前重新绑定排名release_sha并核对所有私密输入与当前源；正常发布仍使用Online Backup、statistics-reuse-only、精确rank/detail/Billboard门禁、健康与联合回滚。当前准备不会替代这些激活门禁。
5. 发布后仅使用正常启动的首个窗口采集，不额外预暖、重启或热重跑；原生CPU/RSS、逐请求64MiB、平台期、构建峰值和整体OOM仍需独立判定。

现有[候选本地整合](2026-10-13-native-trim-candidate-review.md)及其full8/仿真证据继续有效，但范围明确为完整预热场景。当前生产触发条件新证据改变的是发布决定，不改写旧实验结果。

## 独立恢复入口

归档ID：`native-trim-release-preparation-20261013-20261013T144725Z`，共同父目录 `/Users/benjaminlei/.codex/archives/spotifystats-delivery/`。材料包含push/远端ref、CI实际job日志、source/容器只读核对、失败导出与kernel记录、本地清单验证、三份私密输入、临时目录清理和后续发布步骤说明；数据库和payload保持私密，不进入Git。

本报告及共享状态为本轮协调文档，当前未新增提交或推送，不影响已检查CI的6c74b9b4源码。

## 后续本地阶段

保持预热关闭的队列完成边界候选已另行实施，见[新三文件专项](2026-10-13-native-trim-maintenance-candidate.md)；未提交/整合或新增推送部署。旧6c的CI、私密输入准备和本报告原失败仍保持原范围，新补丁尚无完整门禁/CI。

后续本地交付（2026-10-14）：新维护结束回收三文件`8f46b3cb`已按授权提交并以同SHA进入main，代码与上述冻结门禁版本一致；十份协调文档及同步/恢复记录见[提交映射](2026-10-14-native-trim-maintenance-submission-review.md)。此前“未提交/整合”等保留为各检查点范围；当前仍未推送/新CI/部署，原生峰值与OOM继续OPEN。
