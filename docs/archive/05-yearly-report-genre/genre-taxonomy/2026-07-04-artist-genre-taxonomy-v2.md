# Artist Genre Taxonomy v2 Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** 修复当前 genre taxonomy 过度合并和高权重艺人标签污染问题，让年度总结、账号画像、Settings 审计和 AI 问答使用更可解释的流派统计口径。

**Architecture:** 保留 raw source genre 和 resolved artist genre，不破坏已有 fallback/审核链路；新增 v2 statistical taxonomy，把 canonical label 拆成 `style`、`scene`、`context`、`role` 等轴，并先以兼容字段输出给现有消费者。Settings 审计面板新增 source mix、top driving artists 和 dominance warning，用真实播放占比暴露“某个标签被单一艺人或单一来源支配”的风险。

**Tech Stack:** FastAPI + SQLite + Pydantic + React + TanStack Query + Vitest + pytest。

---

## Current Findings

- 当前 `singer-songwriter/folk` 语义过粗：`singer-songwriter` 是创作身份/表达方式，`folk` 是风格传统。真实库里该类 456.5h / 11.3%，Taylor Swift 一人贡献 343.4h / 75.2%。
- 当前 `country/americana` 语义过粗：`country` 与 `americana/roots` 不应合并。真实库里该类 383.6h / 9.5%，Taylor Swift 一人贡献 343.4h / 89.5%。
- `c-pop`、`k-pop`、`j-pop` 更像语言/市场 scene；`holiday`、`soundtrack/stage` 是 context；`singer-songwriter` 是 role。它们不应被假装成同一维度的纯风格。
- 当前 “noncanonical passthrough = 0” 只能证明 raw label 都被归并了，不能证明分类语义合理。

### Label Axis

| Axis | 用途 | Examples |
|------|------|----------|
| `style` | 音乐风格主体 | `pop`, `rock`, `alternative/indie`, `r&b/soul`, `hip hop/rap`, `electronic/dance`, `folk`, `country`, `americana/roots`, `jazz/blues` |
| `scene` | 语言、地区或市场场景 | `c-pop`, `k-pop`, `j-pop`, `latin`, `afrobeats/afropop`, `southeast asian pop`, `brazilian`, `caribbean` |
| `context` | 使用场景、媒介或内容来源 | `soundtrack/stage`, `holiday`, `children/family`, `comedy/spoken`, `gospel/christian` |
| `role` | 创作/表演身份或表达方式 | `singer-songwriter` |

### Immediate Split Rules

| Current | v2 |
|---------|----|
| `singer-songwriter/folk` | `singer-songwriter` + `folk` |
| `country/americana` | `country` + `americana/roots` |
| `rock/alternative` | keep temporarily, but audit `rock`, `alternative`, `indie`, `punk/emo/metal` separately before v3 |
| `c-pop` | keep, mark as `scene` |
| `soundtrack/stage`, `holiday` | keep, mark as `context` |

---

## Files

- Modify: `backend/domains/metadata/artist_genres.py`
  - Split v2 labels.
  - Add label axis metadata.
  - Add dominance/source audit fields.
- Modify: `backend/models/artist_genre_metadata.py`
  - Extend taxonomy response models with `axis`, `source_hours`, `top_artists`, `dominance_warning`.
- Modify: `backend/tests/unit/test_artist_genre_resolution.py`
  - Add taxonomy v2 split and axis tests.
- Modify: `backend/tests/contract/test_artist_genre_metadata_api.py`
  - Add taxonomy response contract tests.
- Modify: `frontend/src/types/artist-genre-metadata.ts`
  - Add axis/source/dominance fields.
- Modify: `frontend/src/features/settings/components/GenreDataHealthSection.tsx`
  - Render axis label, source mix, driving artists, dominance warning.
- Modify: `frontend/src/tests/genre-data-health-section.test.tsx`
  - Cover v2 audit fields.
- Modify: `frontend/src/lib/genre-regions.ts`
  - Add entries for `singer-songwriter`, `folk`, `country`, `americana/roots`.
- Modify: `docs/productization/2026-07-04-artist-genre-taxonomy.md`
  - Update taxonomy explanation and snapshot.
- Optional create: `scripts/artist_genre_taxonomy_audit.py`
  - Print source dominance and top driving artists for release checks.

---

## Task 1: Lock v2 Taxonomy Semantics With Failing Backend Tests

涉及文件：`backend/tests/unit/test_artist_genre_resolution.py`。

- Add failing tests for split labels

Add these tests near the existing canonicalization tests:

- Add failing tests for label axis metadata

---

## Task 2: Implement Taxonomy v2 Mapping and Axis Metadata

涉及文件：`backend/domains/metadata/artist_genres.py`、`frontend/src/lib/genre-regions.ts`。

- Replace over-merged mappings
- Update inference fallback

Replace broad fallback inference:

- Add label metadata
- Add frontend region metadata

---

## Task 3: Extend Taxonomy API With Dominance and Source Audit

涉及文件：`backend/domains/metadata/artist_genres.py`、`backend/models/artist_genre_metadata.py`、`backend/tests/contract/test_artist_genre_metadata_api.py`。

- Add response model fields

Extend `ArtistGenreCanonicalItem`:

- Add contract test for dominance warning

In the taxonomy contract test fixture, make one artist dominate a label:

- Implement source mix and top artists

---

## Task 4: Update Settings Audit Panel

涉及文件：`frontend/src/types/artist-genre-metadata.ts`、`frontend/src/features/settings/components/GenreDataHealthSection.tsx`、`frontend/src/tests/genre-data-health-section.test.tsx`。

- Extend frontend types

Extend `ArtistGenreCanonicalItem`:

- Update test payload
- Assert the audit is visible

Add assertions:

- Render axis and dominance details
- label/name
- axis chip
- share percentage
- warning line if `dominance_warning`
- top 2 driving artists
- top source mix item

Use compact text; do not add a separate card inside the existing card.

---

## Task 5: High-Impact Artist Review Policy

涉及文件：`docs/productization/2026-07-04-artist-genre-taxonomy.md`。

- Optional modify: `data/artist_genre_overrides.seed.json`
- Document the policy

Add a section:

```markdown
## High-Impact Artist Policy

When one artist contributes at least 70% of a canonical label, that label is considered dominance-sensitive. The data may still be valid, but the UI and AI answers must phrase it as "driven by <artist>" rather than a general listening preference.

For cross-era artists, broad artist-level labels such as `country pop` should not be used unless most local playback comes from that era. If local playback is mixed or unknown, prefer a conservative artist-level fallback such as `pop` + `singer-songwriter`, and leave era-specific genre claims to future track/album-level enrichment.
```

- Decide Taylor Swift seed handling

Recommended data policy:

```json
{
  "artist_name": "Taylor Swift",
  "genres": ["pop", "singer-songwriter"],
  "primary_genre": "pop",
  "evidence_summary": "Conservative artist-level fallback; country-pop is era-specific and should not be applied to all local playback without track/album-level evidence."
}
```

Do not apply this silently if the user wants to preserve early Taylor country influence. If not changing the seed, keep dominance warning as the safety mechanism.

- Re-import seeds only if seed policy changes

历史验收预期： imported/updated rows include Taylor Swift only if the seed file changed.

---

## Task 6: Consumer and AI Wording Checks

涉及文件：`backend/services/wrapped_service.py`、`backend/services/account_service.py`。

- Check consumer output keys
- Update expectations from v1 to v2 labels

depending on fixture input.

- AI answer caveat

Ensure AI/report wording can say:

```text
Genre labels are normalized for statistics. Some labels are scenes or contexts, and dominance-sensitive labels may be driven by a single high-play artist.
```

历史验收预期： AI does not present `country` or `singer-songwriter` as broad personal preference when the taxonomy audit says one artist dominates the label.

---

## Task 7: Verification Matrix and Snapshot

涉及文件：`docs/productization/2026-07-04-artist-genre-taxonomy.md`。

- `singer-songwriter/folk` no longer appears.
- `country/americana` no longer appears.
- `singer-songwriter`, `folk`, `country`, and `americana/roots` appear separately when data supports them.
- Dominance warnings appear for labels where one artist contributes at least 70%.
- Noncanonical passthrough remains 0, or each passthrough label is intentionally documented.
- Update docs snapshot

Update:

- raw genre count
- canonical genre count
- noncanonical passthrough count
- top canonical genres
- any dominance-sensitive labels
- whether Taylor seed changed or only warning-based audit was added

---

## Acceptance Criteria

- `singer-songwriter/folk` and `country/americana` are removed from v2 statistical output.
- `singer-songwriter`, `folk`, `country`, and `americana/roots` are represented separately.
- Each canonical label includes an `axis`, so UI/AI can distinguish style, scene, context, and role.
- Settings taxonomy audit shows source mix and top driving artists.
- Labels dominated by one artist or one fallback source are visible as warnings.
- Real DB snapshot no longer overstates Taylor-driven `country` or `folk` as broad listening preference without caveat.
- Existing consumers continue to function with updated labels.
- Docs explain why `noncanonical_passthrough = 0` is not enough to prove semantic correctness.

## Rollback Plan

If consumers break or the v2 split makes charts too noisy:

1. Keep backend v2 mapping code in place.
2. Add a temporary API flag `taxonomy_version=v1|v2` only for audit endpoints.
3. Keep Settings audit on v2.
4. Leave yearly/account consumers on v1 until chart copy and tests are updated.

Do not delete raw source genres or approved local fallback rows; rollback should only affect statistical mapping and display.
