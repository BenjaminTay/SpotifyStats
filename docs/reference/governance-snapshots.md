# 治理 Coverage / Health 持久结果

阶段 6C 只处理 Settings 实际消费的 import health、genre coverage/taxonomy/axis-gaps、language coverage。reviews、L1 风险摘要、L3 health、track credits status 保留原有轻量 SQL / 已发布状态读取。

## 读取与维护

上述五类 GET 在 private 和 public 上都只读取已发布结果，不构建、不写入、不排队；公开面仍遵守原访问白名单，不新增治理入口。精确结果返回 ready；同 family、过滤合同和规则的旧结果返回 warming / last_known_good。旧结果附带 checked_at、checked_revision 和 build_status；没有兼容结果返回 503 snapshot_unavailable，失败另带 build_status=failed，不返回虚假 0 或健康。

`governance_cache.db` 是独立 sidecar，默认位于主库旁，可通过 `SPOTIFY_STATS_GOVERNANCE_CACHE_PATH` 配置。复用已有压缩 JSON、内容校验、active/previous 事务发布格式和 singleflight 模式。一个事务发布本次各 family，并在切换前复查源 revision 和配置；失败保留 active/previous。文件锁在不同进程间合并维护，同 key 的后续维护在锁内重新检查 exact。每个参数合同最多保留两代。

私有启动、导入后维护、identity/credit/Billboard 任务完成、治理及设置写入提交后检查默认合同；只有实际缺失的 family 才排本地任务。审核列表继续实时读取；axis-gaps 只持久化时长与分类结果，当前 review_id/status/pre_review_recommendation 仍由原 SQL 补充，不冻结审核进度。

已有数据库或非默认过滤需要显式补建：

```bash
.venv/bin/python scripts/rebuild_governance.py \
  --db /absolute/path/spotify_stats.db --install-revisions

.venv/bin/python scripts/rebuild_governance.py \
  --db /absolute/path/spotify_stats.db \
  --filters-json '{"max_merge_gap_minutes":45}' \
  --families genre_coverage,genre_taxonomy,genre_axis_gaps,language_coverage
```

命令只做本地检查与派生发布，不调用外部 provider，不导入文件，不执行 metadata backfill。`--install-revisions` 安装或修复本地计数器；正常读取不迁移。生产操作仍须遵守独立的部署与备份约定。

## 共享时长与失效矩阵

同一过滤和源版本只构建一次 `primary_artist_ms`，并持久保存紧凑的 artist_id → integer milliseconds 与 excluded_ms。构建使用原听取区间重建和原主艺人归属函数，canonical alias、人工 attribution、无法归属时长均保留；不对 featured artist fan-out，不从名称、genre 或 language 推断语言。

播放次数阈值不裁掉独立时长轨道中的短片段。读取只选取时长所需列；小型 active identity 关系物化后参与连接，避免旧库反复扫描 fallback 身份。宽 plays DataFrame 不进入内存 LRU 或 sidecar。艺人名称只在 coverage 投影时读取，名称/封面修改不重建主艺人时长。

| 变化 | 共享时长 | Genre 三类 | Language | Import health |
|---|---|---|---|---|
| 播放 / L1 身份与 external IDs | 是 | 是 | 是 | 是 |
| 艺人 canonical alias / metadata attribution | 是 | 是 | 是 | 外键涉及的部分 |
| Genre source / override / Spotify genres | 否 | 是 | 否 | 外键涉及的部分 |
| Language approved source | 否 | 否 | 是 | 外键涉及的部分 |
| 艺人名称 | 否 | 是（名称是原 resolver 的关联键） | 是（缺失艺人名称） | 是（原专辑资格检查的名称关联） |
| Album Project / 来源专辑关系 | 否 | 否 | 否 | 是 |
| 普通封面路径 | 否 | 否 | 否 | 否 |
| Spotify album image_url | 否 | 否 | 否 | 是（原近期元数据完整性条件） |
| identity/credit/L3 任务状态、最近导入错误 | 否 | 否 | 否 | 实时读取并重新组合结论 |

migration 76 使用写事务内触发器维护分域 epoch/counter；无变化 UPDATE 和回滚不改变版本。schema marker 或 counter 缺失时 fail closed；修复使用新 epoch，不使用 TTL、mtime、MAX(ts) 或 revision=0。Import health 包含全库外键检查，因此还登记每个真实 FK 的子字段和父键依赖；这不是把所有列都当作统计依赖。

检查原专辑 eligibility 和 Spotify ID 优先级函数保持不变：single/compilation 的不适用项目、播放时 Spotify ID 优先于旧 tracks.spotify_track_id 的规则均保留。

## Import health 的当前性

数据库完整性、关系、近期元数据和重型身份检查按 revision 发布；它们的 checked_at 是实际构建时间。实时层读取 identity/credit/L3 状态、rebuild_pending、最近持久导入状态和本进程导入任务，并查看数据目录是否存在。实时错误不能被旧检查覆盖。文件存在性状态仅说明当前目录，不代替用户点击的完整 preflight 文件检查；preflight 的原行为与成本保持不变。

Settings 仍以表单配置完成作为表单 ready；导入面板、治理分类结果各自就绪。Desktop 折叠导入面板不启用 health，Phone 按 panel 路由挂载；语言 coverage 仅在语言区展开后启用。LKG 显示检查时间与旧结果提示，缺失/失败显示本地维护说明与重新读取入口。
