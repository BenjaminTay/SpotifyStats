# Artist Genre Taxonomy v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复当前 genre taxonomy 过度合并和高权重艺人标签污染问题，让年度总结、账号画像、Settings 审计和 AI 问答使用更可解释的流派统计口径。

**Architecture:** 保留 raw source genre 和 resolved artist genre，不破坏已有 fallback/审核链路；新增 v2 statistical taxonomy，把 canonical label 拆成 `style`、`scene`、`context`、`role` 等轴，并先以兼容字段输出给现有消费者。Settings 审计面板新增 source mix、top driving artists 和 dominance warning，用真实播放占比暴露“某个标签被单一艺人或单一来源支配”的风险。

**Tech Stack:** FastAPI + SQLite + Pydantic + React + TanStack Query + Vitest + pytest。

---

## Current Findings

- 当前 `singer-songwriter/folk` 语义过粗：`singer-songwriter` 是创作身份/表达方式，`folk` 是风格传统。真实库里该类 456.5h / 11.3%，Taylor Swift 一人贡献 343.4h / 75.2%。
- 当前 `country/americana` 语义过粗：`country` 与 `americana/roots` 不应合并。真实库里该类 383.6h / 9.5%，Taylor Swift 一人贡献 343.4h / 89.5%。
- `c-pop`、`k-pop`、`j-pop` 更像语言/市场 scene；`holiday`、`soundtrack/stage` 是 context；`singer-songwriter` 是 role。它们不应被假装成同一维度的纯风格。
- 当前 “noncanonical passthrough = 0” 只能证明 raw label 都被归并了，不能证明分类语义合理。

## Target Taxonomy v2

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

**Files:**
- Modify: `backend/tests/unit/test_artist_genre_resolution.py`

- [ ] **Step 1: Add failing tests for split labels**

Add these tests near the existing canonicalization tests:

```python
def test_statistical_genres_split_songwriter_folk_country_and_roots():
    assert canonicalize_genres_for_statistics(["singer-songwriter"]) == ["singer-songwriter"]
    assert canonicalize_genres_for_statistics(["folk"]) == ["folk"]
    assert canonicalize_genres_for_statistics(["folk pop"]) == ["pop", "folk"]
    assert canonicalize_genres_for_statistics(["folk rock"]) == ["rock/alternative", "folk"]
    assert canonicalize_genres_for_statistics(["country"]) == ["country"]
    assert canonicalize_genres_for_statistics(["country pop"]) == ["pop", "country"]
    assert canonicalize_genres_for_statistics(["americana"]) == ["americana/roots"]
    assert canonicalize_genres_for_statistics(["red dirt"]) == ["americana/roots", "country"]
```

- [ ] **Step 2: Add failing tests for label axis metadata**

```python
def test_statistical_genre_label_metadata_axes():
    metadata = statistical_genre_label_metadata()

    assert metadata["pop"]["axis"] == "style"
    assert metadata["singer-songwriter"]["axis"] == "role"
    assert metadata["folk"]["axis"] == "style"
    assert metadata["country"]["axis"] == "style"
    assert metadata["americana/roots"]["axis"] == "style"
    assert metadata["c-pop"]["axis"] == "scene"
    assert metadata["soundtrack/stage"]["axis"] == "context"
    assert metadata["holiday"]["axis"] == "context"
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py -q
```

Expected: FAIL because `singer-songwriter/folk`, `country/americana`, and `statistical_genre_label_metadata()` still reflect v1 behavior.

---

## Task 2: Implement Taxonomy v2 Mapping and Axis Metadata

**Files:**
- Modify: `backend/domains/metadata/artist_genres.py`
- Modify: `frontend/src/lib/genre-regions.ts`

- [ ] **Step 1: Replace over-merged mappings**

In `STATISTICAL_GENRE_MAP`, replace the v1 mappings for songwriter/folk/country:

```python
    "singer-songwriter": ("singer-songwriter",),
    "pop singer-songwriter": ("pop", "singer-songwriter"),
    "italian singer-songwriter": ("singer-songwriter",),
    "folk": ("folk",),
    "folk pop": ("pop", "folk"),
    "folk rock": ("rock/alternative", "folk"),
    "indie folk": ("indie/alternative", "folk"),
    "ambient folk": ("folk",),
    "southern gothic": ("folk",),
    "country": ("country",),
    "acoustic country": ("country",),
    "classic country": ("country",),
    "country pop": ("pop", "country"),
    "pop country": ("pop", "country"),
    "country rock": ("country", "rock/alternative"),
    "honky tonk": ("country",),
    "outlaw country": ("country",),
    "red dirt": ("americana/roots", "country"),
    "texas country": ("country",),
    "traditional country": ("country",),
    "americana": ("americana/roots",),
    "bluegrass": ("folk", "americana/roots"),
    "roots rock": ("rock/alternative", "americana/roots"),
```

- [ ] **Step 2: Update inference fallback**

Replace broad fallback inference:

```python
    if "country" in genre:
        inferred.append("country")
    if "americana" in genre or "red dirt" in genre or "bluegrass" in genre:
        inferred.append("americana/roots")
    if "singer-songwriter" in genre:
        inferred.append("singer-songwriter")
    if "folk" in genre:
        inferred.append("folk")
```

- [ ] **Step 3: Add label metadata**

Add near `statistical_genre_labels()`:

```python
STATISTICAL_GENRE_METADATA: dict[str, dict[str, str]] = {
    "pop": {"axis": "style", "label": "Pop"},
    "rock/alternative": {"axis": "style", "label": "Rock / Alternative"},
    "indie/alternative": {"axis": "style", "label": "Indie / Alternative"},
    "r&b/soul": {"axis": "style", "label": "R&B / Soul"},
    "hip hop/rap": {"axis": "style", "label": "Hip Hop / Rap"},
    "electronic/dance": {"axis": "style", "label": "Electronic / Dance"},
    "singer-songwriter": {"axis": "role", "label": "Singer-Songwriter"},
    "folk": {"axis": "style", "label": "Folk"},
    "country": {"axis": "style", "label": "Country"},
    "americana/roots": {"axis": "style", "label": "Americana / Roots"},
    "c-pop": {"axis": "scene", "label": "C-Pop"},
    "k-pop": {"axis": "scene", "label": "K-Pop"},
    "j-pop": {"axis": "scene", "label": "J-Pop"},
    "latin": {"axis": "scene", "label": "Latin"},
    "afrobeats/afropop": {"axis": "scene", "label": "Afrobeats / Afropop"},
    "southeast asian pop": {"axis": "scene", "label": "Southeast Asian Pop"},
    "brazilian": {"axis": "scene", "label": "Brazilian"},
    "caribbean": {"axis": "scene", "label": "Caribbean"},
    "jazz/blues": {"axis": "style", "label": "Jazz / Blues"},
    "classical/instrumental": {"axis": "style", "label": "Classical / Instrumental"},
    "traditional/folk": {"axis": "style", "label": "Traditional / Folk"},
    "soundtrack/stage": {"axis": "context", "label": "Soundtrack / Stage"},
    "holiday": {"axis": "context", "label": "Holiday"},
    "children/family": {"axis": "context", "label": "Children / Family"},
    "comedy/spoken": {"axis": "context", "label": "Comedy / Spoken"},
    "gospel/christian": {"axis": "context", "label": "Gospel / Christian"},
}


def statistical_genre_label_metadata() -> dict[str, dict[str, str]]:
    return STATISTICAL_GENRE_METADATA
```

- [ ] **Step 4: Add frontend region metadata**

Add entries in `frontend/src/lib/genre-regions.ts`:

```ts
  'singer-songwriter': { language: 'english', region: '全球', flag: '🌍' },
  'folk': { language: 'english', region: '全球', flag: '🌍' },
  'country': { language: 'english', region: '美国', flag: '🇺🇸' },
  'americana/roots': { language: 'english', region: '美国', flag: '🇺🇸' },
```

- [ ] **Step 5: Run v2 semantic tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py -q
```

Expected: PASS.

---

## Task 3: Extend Taxonomy API With Dominance and Source Audit

**Files:**
- Modify: `backend/domains/metadata/artist_genres.py`
- Modify: `backend/models/artist_genre_metadata.py`
- Modify: `backend/tests/contract/test_artist_genre_metadata_api.py`

- [ ] **Step 1: Add response model fields**

In `backend/models/artist_genre_metadata.py`, add:

```python
class ArtistGenreTopArtistItem(BaseModel):
    artist_name: str
    hours: float
    share_pct: float
    source: str
    raw_genres: list[str]


class ArtistGenreSourceMixItem(BaseModel):
    source: str
    hours: float
    share_pct: float
```

Extend `ArtistGenreCanonicalItem`:

```python
class ArtistGenreCanonicalItem(BaseModel):
    name: str
    axis: str = "style"
    label: str | None = None
    hours: float
    share_pct: float
    source_mix: list[ArtistGenreSourceMixItem] = Field(default_factory=list)
    top_artists: list[ArtistGenreTopArtistItem] = Field(default_factory=list)
    dominance_warning: str | None = None
```

- [ ] **Step 2: Add contract test for dominance warning**

In the taxonomy contract test fixture, make one artist dominate a label:

```python
def test_artist_genre_metadata_api_returns_taxonomy_dominance_audit(client, artist_genre_metadata_db):
    response = client.get("/api/metadata/artist-genres/taxonomy")

    assert response.status_code == 200
    payload = response.json()
    pop = payload["top_canonical_genres"][0]
    assert pop["name"] == "pop"
    assert pop["axis"] == "style"
    assert pop["source_mix"][0]["source"] == "spotify"
    assert pop["top_artists"][0]["artist_name"] == "Spotify Artist"
    assert pop["top_artists"][0]["raw_genres"] == ["spotify pop"]
```

- [ ] **Step 3: Implement source mix and top artists**

Inside `compute_genre_taxonomy_audit()`, track these counters:

```python
    canonical_source_hours: dict[str, Counter[str]] = defaultdict(Counter)
    canonical_artist_hours: dict[str, Counter[str]] = defaultdict(Counter)
    artist_raw_genres: dict[str, list[str]] = {}
    artist_sources: dict[str, str] = {}
```

When adding canonical hours:

```python
                canonical_hours[genre] += share
                canonical_source_hours[genre][item.source] += share
                canonical_artist_hours[genre][artist_name] += share
                artist_raw_genres[artist_name] = raw_genres
                artist_sources[artist_name] = item.source
```

Add helper functions:

```python
    metadata = statistical_genre_label_metadata()

    def source_mix_rows(genre: str, hours: float) -> list[dict[str, Any]]:
        if hours <= 0:
            return []
        return [
            {
                "source": source,
                "hours": round(float(source_hours), 1),
                "share_pct": round(float(source_hours) / hours * 100, 1),
            }
            for source, source_hours in canonical_source_hours[genre].most_common()
        ]

    def top_artist_rows(genre: str, hours: float) -> list[dict[str, Any]]:
        if hours <= 0:
            return []
        return [
            {
                "artist_name": artist,
                "hours": round(float(artist_hours), 1),
                "share_pct": round(float(artist_hours) / hours * 100, 1),
                "source": artist_sources.get(artist, "unknown"),
                "raw_genres": artist_raw_genres.get(artist, []),
            }
            for artist, artist_hours in canonical_artist_hours[genre].most_common(5)
        ]

    def dominance_warning(genre: str, hours: float) -> str | None:
        top_artists = canonical_artist_hours[genre].most_common(1)
        if not top_artists or hours <= 0:
            return None
        artist, artist_hours = top_artists[0]
        share_pct = float(artist_hours) / hours * 100
        if share_pct >= 70:
            return f"{artist} contributes {share_pct:.1f}% of this label"
        return None
```

Then each canonical row should include:

```python
                "axis": metadata.get(genre, {}).get("axis", "style"),
                "label": metadata.get(genre, {}).get("label", genre),
                "source_mix": source_mix_rows(genre, float(hours)),
                "top_artists": top_artist_rows(genre, float(hours)),
                "dominance_warning": dominance_warning(genre, float(hours)),
```

- [ ] **Step 4: Run contract tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/contract/test_artist_genre_metadata_api.py -q
```

Expected: PASS.

---

## Task 4: Update Settings Audit Panel

**Files:**
- Modify: `frontend/src/types/artist-genre-metadata.ts`
- Modify: `frontend/src/features/settings/components/GenreDataHealthSection.tsx`
- Modify: `frontend/src/tests/genre-data-health-section.test.tsx`

- [ ] **Step 1: Extend frontend types**

Add:

```ts
export interface ArtistGenreSourceMixItem {
  source: string
  hours: number
  share_pct: number
}

export interface ArtistGenreTopArtistItem {
  artist_name: string
  hours: number
  share_pct: number
  source: string
  raw_genres: string[]
}
```

Extend `ArtistGenreCanonicalItem`:

```ts
export interface ArtistGenreCanonicalItem {
  name: string
  axis: string
  label: string | null
  hours: number
  share_pct: number
  source_mix: ArtistGenreSourceMixItem[]
  top_artists: ArtistGenreTopArtistItem[]
  dominance_warning: string | null
}
```

- [ ] **Step 2: Update test payload**

In `genre-data-health-section.test.tsx`, update `taxonomyPayload.top_canonical_genres`:

```ts
{
  name: 'singer-songwriter',
  axis: 'role',
  label: 'Singer-Songwriter',
  hours: 431.3,
  share_pct: 10.7,
  source_mix: [{ source: 'curated_seed', hours: 343.4, share_pct: 79.6 }],
  top_artists: [{
    artist_name: 'Taylor Swift',
    hours: 343.4,
    share_pct: 79.6,
    source: 'curated_seed',
    raw_genres: ['pop', 'country pop', 'singer-songwriter'],
  }],
  dominance_warning: 'Taylor Swift contributes 79.6% of this label',
}
```

- [ ] **Step 3: Assert the audit is visible**

Add assertions:

```ts
expect(within(auditPanel).getByText('role')).toBeInTheDocument()
expect(within(auditPanel).getByText('Singer-Songwriter')).toBeInTheDocument()
expect(within(auditPanel).getByText('Taylor Swift')).toBeInTheDocument()
expect(within(auditPanel).getByText(/79.6%/)).toBeInTheDocument()
expect(within(auditPanel).getByText(/curated_seed/)).toBeInTheDocument()
```

- [ ] **Step 4: Render axis and dominance details**

In `GenreDataHealthSection`, for each canonical genre row, render:

- label/name
- axis chip
- share percentage
- warning line if `dominance_warning`
- top 2 driving artists
- top source mix item

Use compact text; do not add a separate card inside the existing card.

- [ ] **Step 5: Run frontend focused tests**

Run:

```bash
cd frontend && npm test -- genre-data-health-section
```

Expected: PASS.

---

## Task 5: High-Impact Artist Review Policy

**Files:**
- Modify: `docs/productization/2026-07-04-artist-genre-taxonomy.md`
- Optional modify: `data/artist_genre_overrides.seed.json`

- [ ] **Step 1: Document the policy**

Add a section:

```markdown
## High-Impact Artist Policy

When one artist contributes at least 70% of a canonical label, that label is considered dominance-sensitive. The data may still be valid, but the UI and AI answers must phrase it as "driven by <artist>" rather than a general listening preference.

For cross-era artists, broad artist-level labels such as `country pop` should not be used unless most local playback comes from that era. If local playback is mixed or unknown, prefer a conservative artist-level fallback such as `pop` + `singer-songwriter`, and leave era-specific genre claims to future track/album-level enrichment.
```

- [ ] **Step 2: Decide Taylor Swift seed handling**

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

- [ ] **Step 3: Re-import seeds only if seed policy changes**

Run:

```bash
.venv/bin/python scripts/import_artist_genre_overrides.py --seed data/artist_genre_overrides.seed.json
```

Expected: imported/updated rows include Taylor Swift only if the seed file changed.

---

## Task 6: Consumer and AI Wording Checks

**Files:**
- Modify if needed: `backend/services/wrapped_service.py`
- Modify if needed: `backend/services/account_service.py`
- Modify if needed: AI report/chat prompt or answer contract files that mention genre caveats.
- Test: existing genre consumer tests.

- [ ] **Step 1: Check consumer output keys**

Run:

```bash
.venv/bin/python -m pytest backend/tests/contract/test_artist_genre_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py -q
```

Expected: PASS or failures only from expected label rename snapshots.

- [ ] **Step 2: Update expectations from v1 to v2 labels**

Replace expectations:

```python
"singer-songwriter/folk"
```

with:

```python
"singer-songwriter"
```

or:

```python
"folk"
```

depending on fixture input.

Replace:

```python
"country/americana"
```

with:

```python
"country"
```

or:

```python
"americana/roots"
```

- [ ] **Step 3: AI answer caveat**

Ensure AI/report wording can say:

```text
Genre labels are normalized for statistics. Some labels are scenes or contexts, and dominance-sensitive labels may be driven by a single high-play artist.
```

Expected: AI does not present `country` or `singer-songwriter` as broad personal preference when the taxonomy audit says one artist dominates the label.

---

## Task 7: Verification Matrix and Snapshot

**Files:**
- Modify: `docs/productization/2026-07-04-artist-genre-taxonomy.md`

- [ ] **Step 1: Run backend checks**

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/contract/test_artist_genre_metadata_api.py backend/tests/contract/test_artist_genre_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py -q
.venv/bin/ruff check backend/
```

Expected: all tests pass; ruff passes.

- [ ] **Step 2: Run frontend checks**

```bash
cd frontend && npm test -- genre-data-health-section
cd frontend && npm run build
```

Expected: focused Vitest passes; production build passes.

- [ ] **Step 3: Run real DB snapshot**

```bash
.venv/bin/python - <<'PY'
from backend.api.artist_genre_metadata import _load_artist_play_hours
from backend.core.db import get_db
from backend.domains.metadata.artist_genres import compute_genre_taxonomy_audit

conn = get_db(readonly=True)
try:
    report = compute_genre_taxonomy_audit(conn, _load_artist_play_hours(conn))
    print("raw_genre_count", report["raw_genre_count"])
    print("canonical_genre_count", report["canonical_genre_count"])
    print("noncanonical_passthrough_count", report["noncanonical_passthrough_count"])
    for row in report["top_canonical_genres"][:12]:
        print(row["name"], row["axis"], row["hours"], row["share_pct"], row["dominance_warning"])
finally:
    conn.close()
PY
```

Expected:

- `singer-songwriter/folk` no longer appears.
- `country/americana` no longer appears.
- `singer-songwriter`, `folk`, `country`, and `americana/roots` appear separately when data supports them.
- Dominance warnings appear for labels where one artist contributes at least 70%.
- Noncanonical passthrough remains 0, or each passthrough label is intentionally documented.

- [ ] **Step 4: Update docs snapshot**

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
