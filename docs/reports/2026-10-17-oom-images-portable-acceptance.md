# 资源对照镜像与可移植验收包

核验日期：2026-10-17。事项 `SS-2026-10-08-001`，关联 `SS-2026-10-09-001`。R1本地准备完成，工具可移交；原生资源准入、最终整合、CI与发布均未完成，整体仍OPEN / Partial。

## 当前交付

R0业务候选为 `c844b98f260b85b92ae298e9d135fdab6cb05de2`；R1工具与构建参数形成一个研发阶段提交 `bdcf0cbe5cceff9d0d8959b1535b996fe439efed`，5文件。未推送，main尚未应用业务或工具源码，源SHA到main的业务映射留给R4。完整路线见[收口规划](../plans/2026-10-17-oom-resource-closeout-plan.md)，R0采用范围见[候选审阅](2026-10-17-oom-candidate-freeze-review.md)。

新增三个命令行脚本提供init、pack、preflight、run、summarize、restore、cleanup及合成selftest。独立HTTP客户端负责完整正文缓冲与哈希，strict审计也使用独立有界容器；Backend仅共享隔离loopback网络。采样用固定容量原生缓冲，逐行导出，并读取内核cgroup memory.peak，避免历史样本展开污染Backend驻留。失败、缺证、NaN、未完成维护、未真正淘汰等情况不能输出资源通过。

独立审阅已关闭首版发现的退出码、证据缺失、客户端污染、维护重叠、LRU增长、弱浏览器收据、工具超时残留及干净checkout依赖问题。提交hooks首轮仅将五个公开工具SHA256误报为secret；补充局部allowlist注释，AST与已审阅版本相同，四hooks随后及提交时通过，没有修改secret扫描基线或放宽规则。

## 实际镜像及启动

两版均使用实际Dockerfile backend target、相同amd64 Python基础镜像 `sha256:dad5b29e3506c35e0fd222736f4d4ef25d21b219acdd73f7bb41d59996ca8e0d`。Python 3.9.25、glibc 2.41、45项依赖一致，含pandas 2.3.3 / numpy 2.0.2 / cryptography 50.0.2；不能与旧依赖环境直接拼接因果收益。

| 角色 | 实际image ID | 镜像源码标签 |
| --- | --- | --- |
| baseline | `sha256:d07c2f4bc2f308b284057d43aa6eaddfe9ee1c0e4029e4cb01d19badf63f3fe7` | `dc1cf9ad713d31e5c1ea0e9749460ad86dce0c06` |
| candidate | `sha256:956c7d4692dad5cc8fc194a21d10fa770c1cc4a1e1302579dd41c6d47bc541d2` | `c844b98f260b85b92ae298e9d135fdab6cb05de2` |

每版537份应用文件逐份核对构建上下文；未挂载业务源码，没有数据库或私密dotenv，pip check通过。candidate正常allocator ENV为 `MALLOC_MMAP_THRESHOLD_=131072`。R1工具独立随验收包挂载，不把镜像标签改称新的工具commit。

构建保留两次原始失败：PyPI TLS EOF及15秒下载超时。实际Dockerfile增加仅构建期 `ARG PIP_DEFAULT_TIMEOUT=120`，两版采用相同参数后构建成功；没有改变Python或依赖约束，proxy/timeout未成为运行ENV。不能据此把所有TLS问题都归于超时。

两版用小型owned seed、镜像原uvicorn CMD及默认warmup=1启动，health200，正常退出0、无OOM，随后核验归档并删除owned运行副本及容器。这是启动能力smoke，不是维护全部完成或真实规模资源验收。实际镜像及当前工具验证均在ARM Docker引擎运行amd64仿真。

## 固定矩阵与本地验证

固定114个独立窗口：72冷进程、12启动、8自然交互、2 LRU、2长期、10实际故障、8功能边界。另要求baseline/candidate各自执行原90浏览器场景；保留原runner定义、顺序、直接访问after-shell口径和独立镜像/前端身份收据，不接受旧生产时延或手写PASS。

私密manifest已固定真实七库身份、ready JSON身份、259个LRU目标、每长期窗850请求及各窗请求上限。72冷进程、50%整体峰/驻留、64MiB、500/100ms、90分钟长期流程及原缓存预算均未减项。正常资源窗口拟采用warmup=0、隔离环境external-covers=0；前者来自此前保存的目标配置，最终原生运行前仍须核对适用环境，不能当作本轮已刷新生产。

本地证据：

- 33项纯编排测试通过；145000槽原生视图覆盖120分钟×50ms容量，未展开为样本列表。CLI selftest、Ruff、diff check、四hooks通过；12项Docker契约通过。唯一测试warning为本机既有LibreSSL提示。
- 实际candidate镜像的合成工具链自检通过：两个真实TCP客户端、到达Backend后的取消、独立namespace探针、原生采样、三个独立strict握手、工具超时及归档恢复。网络namespace相同，cgroup namespace不同；9个owned容器均移除，Backend退出0、无OOM。采样12点，仅证明工具通路，不能推断资源收益。
- 合成七库strict前后不变；46文件归档CRC及实际恢复SHA核验通过，owned原运行库与恢复副本随后移除。没有为自检复制真实七库。
- 脱离工作树在`/tmp`运行standalone自检成功；复用已核验bundle离线重封、完整性和源包不变通过。最终预检按预期exit2，列出14项未定原生条件，未尝试真实资源窗口。
- 原前端源码相同，Node 22.15.0 / npm 10.9.2实际build成功，既有chunk size提示保留；157份dist文件及原浏览器工具归档读回通过。这不是正式Web镜像或新的浏览器验收。

最终参数化包位于研发树 `output/oom-closeout-execution-20261017/bundle/portable-ready/`，manifest canonical SHA256为 `929df922ba1a9de4acad8321cf0e35787143ba9c6fa77fc50a994b7d24ffb562`。目录名READY只表示本地工具可移交，manifest仍为frozen=false、resource_admission=false；不得直接运行后声称原生通过。

## 恢复入口与下一步

独立恢复目录：`~/.codex/archives/spotifystats-delivery/oom-closeout-execution-20261017/`。

| 成品 | 大小 / SHA256 | 核验 |
| --- | --- | --- |
| `R1-backend-images.tar.gz` | 136744584字节；`dba669ada202948a436b77f029fcb5dba0e079292e61fa1bf8b3c52c1a05eae2` | gzip CRC及完整解压hash；不含真实数据 |
| `R1-frontend-fixture.zip` | 2832401字节；`f615332ec83733f0b5be5a37b30b621ed9f4fe2fd2d8235088551a5b01db92b4` | CRC及157份dist逐文件读回 |
| `R1-portable-resource-acceptance.zip` | 799115字节；`69507174ef364512ec6d16d997ad498b542ba63d4ff72dc803384e208e174cdb` | 154文件CRC/实际恢复hash，含5份源码、patch、工具、审阅与原始日志；不含真实数据库 |

相邻receipt记录每份成品及阶段提交。README产品说明与AGENTS/CLAUDE规则无需改变，两份约定一致；协调状态、索引与CHANGELOG由main维护。旧full8仅按R0报告范围复用，R4最终整合版仍须新跑默认完整门禁。

下一步为原生环境及私密数据通道决定，然后填host/engine、实际容量与重型维护并发、owned输出路径，使用新run_id离线重封并预检。真实七库和ready JSON单独私密传输，不放入Git、镜像或普通CI artifact。当前没有非生产原生amd64环境，没有租用、上传或生产压力测试。

空间须按整个批次准备：七库共671264768字节（640.168MiB）；114份数据库归档按不压缩数据量约71.269GiB，另需采样、响应、镜像、单活动副本和12GiB保留量。manifest现有10GiB是单活动窗口规划量，不能误当全批次归档总量；建议目标至少预留120GiB可用磁盘，再按实际配置冻结。每窗完成均CRC/恢复后释放owned运行库；保留首轮失败，不通过删除原始证据或生产旁压测补齐R2。
