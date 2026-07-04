# Artist Genre Seed Accuracy Audit

日期：2026-07-05

## 结论

`missing_completion_2026-07-05_v1` 批次通过准确性审计，可以作为当前缺失 genre 补全的可重建 seed 使用。

- 批次规模：310 个艺人
- 覆盖播放时长：30.9 小时，约占总统计时长 0.8%
- 覆盖结果：`known_pct = 100.0%`，`unknown_pct = 0.0%`
- 审核队列：open 为空
- 统计 taxonomy：310 条全部可映射，`noncanonical_count = 0`

这次没有发现需要改 genre 的硬错误；实际修正集中在 3 个高影响或易歧义艺人的证据元数据，让 seed 更可审计。

## 审计范围

本次审计只看 `data/artist_genre_overrides.seed.json` 中 `source_key = missing_completion_2026-07-05_v1` 的批次。该批次来自 Spotify 未公开 genre 的艺人补全，解析优先级仍低于 Spotify 官方 genre。

按播放时长覆盖：

| 范围 | 小时 | 覆盖批次时长 |
| --- | ---: | ---: |
| Top 20 | 11.67h | 37.8% |
| Top 30 | 14.50h | 46.9% |
| Top 50 | 18.39h | 59.6% |
| Top 60 | 19.94h | 64.6% |
| Top 100 | 24.44h | 79.1% |

重点审计类别：

| 类别 | 艺人数 | 小时 | 判断 |
| --- | ---: | ---: | --- |
| `soundtrack/stage` | 61 | 7.63h | 合理。大量来自 Disney、Wicked、Encanto、Frozen、High School Musical 等本地播放上下文。 |
| `c-pop` | 12 | 1.23h | 合理。Mandopop/C-pop 归入同一 scene 轴，避免重复统计。 |
| `country` | 11 | 1.06h | 合理。主要来自 Olivia Newton-John、Shaboozey、Dasha、Noah Cyrus、Billy Ray Cyrus 等。 |
| `folk + singer-songwriter` | 11 | 1.48h | 合理。不再把 folk 与 singer-songwriter 合并为单类，按 style 与 role 分轴解释。 |
| AI/虚拟/低可信名称 | 2 | 0.08h | 低影响，保守标为 `country/comedy`，不影响主统计。 |
| 4 个以上 canonical 标签 | 4 | 1.72h | 可接受，均为跨风格艺人或多语境播放，不做强行压缩。 |

## 重点样本判断

### 保持不变

- Elias：保留 `pop + soul`。本地上下文是 `Revolution | Entwined`，不是 MusicBrainz 易误命中的 jazz pianist Eliane Elias。外部评论将 `Revolution` 放在 contemporary pop/R&B-soul 语境中，因此不改成 jazz/bossa nova。
- Sebastian Croft：保留 `pop + alternative pop`。本地上下文是 `Tokyo` 和 `Better than ever`，Shazam 对 `Better than ever` 的曲目页标注为 Pop。
- 安沐凡：保留 `c-pop + musical theatre + classical crossover`。本地上下文集中在《劉泉君》，外部评论强调其音乐剧演员身份和叙事型人声表达，因此同时保留 C-pop 与 stage/context 标签。
- Olivia Newton-John：保留 `pop + country pop + disco`。`Physical`、`Xanadu`、`Hopelessly Devoted To You` 横跨 pop、country pop 与 disco/舞曲语境，多个 canonical 标签是合理拆分，不是重复。
- Maggie Rogers / Ashe：保留 `indie/folk/singer-songwriter` 组合。这里 singer-songwriter 是 role 轴，folk/indie 是 style 轴，不再合并。
- The 1975：保留 `indie rock + pop rock + synthpop`。其统计拆分落在 rock/alternative、indie/alternative、pop、electronic/dance，符合跨风格艺人特征。
- 音乐剧/电影 cast：保留 `soundtrack` / `musical theatre`。这类艺人在本地数据中主要作为作品语境出现，不应该强行归入普通 pop。

### 已修正

这次没有修改 genre 本身，只补强了证据元数据，并同步回当前 SQLite：

| 艺人 | 修正 |
| --- | --- |
| Elias | 补 `language=english`、`region=瑞典`、`evidence_url` 与更明确的 evidence summary。 |
| Sebastian Croft | 补 `language=english`、`region=英国`、Shazam evidence URL 与 summary。 |
| 安沐凡 | 补 `language=chinese`、`region=中国`、Sina evidence URL 与 summary。 |

参考链接：

- [i-D - premiere: elias, revolution](https://i-d.co/article/premiere-elias-revolution/)
- [Shazam - Better than ever](https://www.shazam.com/song/1875356365/better-than-ever)
- [新浪 - 安沐凡专辑《刘泉君》解析](https://www.sina.cn/news/detail/5259735189160931.html)

## 风险边界

- 这批补全的播放时长占比很低，主要风险不是主统计被大幅扭曲，而是长尾标签过细导致读数噪声。
- 对 0.0h 级别长尾艺人，本次优先使用 broad genre，不追求高度细分。
- `soundtrack/stage`、`scene`、`context`、`role` 标签不等同于声音风格，需要继续在 UI 和报告中分轴解释。
- Spotify genre 仍是第一优先级；如果未来 Spotify 对这些艺人返回官方 genre，本地 seed 不会覆盖 Spotify。

## 验收命令

```bash
.venv/bin/python scripts/import_artist_genre_overrides.py --json-output /tmp/artist_genre_seed_import_audit_sync.json
.venv/bin/python scripts/artist_genre_coverage_probe.py --json-output /tmp/artist_genre_coverage_seed_after.json --max-unknown-pct 0
.venv/bin/python scripts/review_artist_genre_suggestions.py list --status open --limit 20
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_seed_import.py -q
source .venv/bin/activate && pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/unit/test_wrapped_genre_panorama.py -q
```

验收结果：

- seed 导入：330 loaded / 330 approved / 0 suggested
- coverage：`known_pct = 100.0%`，`unknown_pct = 0.0%`，`top_missing = []`
- review queue：`[]`
- seed import 单测：8 passed
- genre resolution + wrapped panorama 单测：23 passed

