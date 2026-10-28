# 清理后恢复基线重建与生产发布重试

日期：2026-10-28；事项：SS-2026-10-28-001；负责人：当前聊天Codex。

## 范围与原始失败

用户确认旧备份已删除，授权为当前线上dacdb862建立新的完整恢复基线，修复保留记录，再重试c6f8ea73发布并验收。不提交或推送Git，不改变业务事实，不降低容量门槛。

原Production Release 40520933594第一次执行在2026-10-27音乐搜索副本容量预检失败，未替换线上数据库或镜像。c6f8ea73质量CI 40520933529成功。用户清理后可用磁盘约23.4GiB，线上dacdb862健康，旧current/previous数据库恢复点及私密manifest已不在backups中，但镜像归档存在；不得把新备份描述为已删除历史恢复点。

## 执行与验收

### 当前版新恢复基线

服务器操作目录为 `/opt/spotify-stats/backups/recovery-baseline-20261028T044708Z/`。短暂停止Backend，checkpoint七库并确认无剩余WAL，旧版Billboard及四默认排名停服exact检查通过。七库原inode以硬链接保留在originals目录；独立封存data完整目录（含七库、首页缓存、封面、原始输入和导入控制资料），部署配置、secrets、原保留记录及标记另存recovery/config。七库逐库integrity_check=ok，封存副本SHA256与停止时原文件一致。恢复须先停服，用封存副本写回保留inode再联合还原，具体见服务器RESTORE.md。

本次创建今日时间戳的dacdb862主库、Analysis、Billboard三份标准备份；不冒充10-24历史备份。保存旧保留记录后，将current保留为dacdb862、previous置空，并移除已经失效的旧previous标记。旧f153数据库恢复点已丢失，未伪造新备份；其镜像归档仍在，后续按正常两版轮转。修复后清理预览通过：保留当前三份标准备份，零删除候选。Backend恢复healthy；建基线后磁盘仍可用约19.7GiB。

### 发布重试

连接器重跑权限返回403（Resource not accessible by integration），转用本机GitHub CLI重试同一失败作业。第2次尝试成功，实际部署作业为122638521255；见下节。


### 发布结果与独立生产验收

[Production Release 40520933594，第2次尝试](https://github.com/BenjaminTay/SpotifyStats/actions/runs/40520933594/attempts/2)于北京时间2026-10-28 12:59:31完成success；部署作业122638521255。复用已有质量、三模式及构建结果，不为重试追加全量测试；目标仍为main的c6f8ea73082d63cb21b4ca35ac78498a5e901ad2，schema96。原第1次容量失败保留。

容量预检before为磁盘17111MiB、可用内存2640MiB；after为15774MiB和2632MiB；磁盘要求5347MiB、内存要求640MiB，全部通过。四套统计精确复用，未首次冷建。正常停服后源一致性、详情投影、排名与Billboard成品验证、原子切换、健康检查和收尾全部通过。

独立验收：

- 三个生产容器均使用c6f8ea73并healthy；dual与public访问模式保持。Backend不映射宿主端口，两个Web仅监听127.0.0.1:3001/3002。
- `verify.sh`通过：schema96、搜索v13四变体4/4、聚合v6、orphan=0；精确/模糊/CJK/短CJK搜索通过；四套默认排名exact-ready；简化版写入返回403。另行调用当前详情投影及Billboard运行门禁，均通过。
- 9项HTTP请求全部200，覆盖health、能力、首页、搜索上下文、候选搜索、Records、目标专辑summary与stats，以及公开展示HTTPS健康入口。五张源表plays/tracks/track_artists/albums/artists行数与新基线一致；这不是逐行全事实重新复算。
- 应用内浏览器实际检查六入口：首页、播放统计、年度总结、Records、音乐查找、设置。桌面1280×720/800、手机390×844共12项内容/响应式检查通过，零横向溢出；捕获控制台warn/error为0。统计KPI、年度完整年鉴及手机设置实际可见。没有执行物理手机、真实OAuth或真实模型调用。
- 原CDP门禁第一轮因SSH隧道超时中止；重建保活隧道后HTTP正常，但CDP导航/加载事件仍超时，故改用应用内浏览器完成验收。失败日志原样保留，不将原脚本标成通过。

### 最终保留状态与证据

最终current=c6f8ea73、previous=dacdb862；两版镜像归档均存在，每版三份标准主库/Analysis/Billboard备份齐全。清理预览通过，保留6份、零删除候选；末次空间核对16609MiB可用。新七库完整基线继续登记在dacdb862上，沿上一版本生命周期保留。旧f153历史数据库已丢失，未伪造其恢复点；正常CAS激活将其从两版集合退出。

服务器基线与恢复说明：`/opt/spotify-stats/backups/recovery-baseline-20261028T044708Z/`；`baseline.json`记录七库校验与inode，`data-file-metadata.json`补充数据目录权限/属主元数据，`RESTORE.md`说明联合恢复。`recovery/data`是独立封存内容，`originals-*`保存原文件身份；不能把重启旧服务后可能继续变化的硬链接单独当作静态备份。HTTP收据为同目录`http-acceptance.json`。没有为验收实际回滚生产。

本地私有收据：`data/maintenance/recovery-baseline-20261028/`（基线元数据、操作脚本、发布watch、独立运行与HTTP日志）；浏览器收据和原失败位于`output/playwright/recovery-release-20261028/`，以`ui-acceptance.json`为最终页面验收入口。生产数据和配置不入Git。

本轮只改交付报告、报告索引及开发状态，没有提交/推送Git。工作期间出现的另一组备份策略/定时清理修改属于其他会话，保留原样，不计入c6f8ea73发布和本轮源码验收。长期内存、私有DNS、真实模型/终端及独立数据治理边界保持。
