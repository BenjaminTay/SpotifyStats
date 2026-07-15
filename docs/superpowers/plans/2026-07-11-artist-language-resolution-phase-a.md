# Artist Language Resolution Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable artist-level language metadata workflow, truthful primary-artist language statistics, a Settings review UI, and a yearly-review consumer that no longer infers language from genre.

**Architecture:** Add three SQLite tables through migration 24, then place registry/resolution/statistics in `backend/domains/metadata/artist_languages.py` and review transactions in `artist_language_review.py`. Expose five FastAPI endpoints, reuse `/api/music/search`, integrate a stable language fact revision into Wrapped caching, and keep the frontend language UI isolated in two focused Settings components.

**Tech Stack:** Python 3.12, SQLite, FastAPI, Pydantic v2, pandas, pytest, React 19, TypeScript, TanStack Query, Base UI, Vitest, Playwright-based smoke scripts.

---

## Execution Rules

- Follow TDD inside every task: failing focused test, minimal implementation, focused pass, then broader regression.
- Preserve the existing genre workflow. Language resolution never calls `resolve_artist_genres_map()`.
- Use primary artist attribution from `tracks.artist_id`; never use `load_plays_for_artists()` for language distribution.
- Do not write approved facts directly from legacy data. Legacy import creates suggested reviews only.
- Do not run a production database import until its dry-run JSON has been reviewed.
- Commit commands below are checkpoints for an implementation run. Do not execute them unless the user has explicitly authorized commits.

## File Map

**Backend create:**

- `backend/domains/metadata/language_registry.py` — canonical code/variant registry and labels.
- `backend/domains/metadata/artist_languages.py` — resolver, validator, primary-artist attribution, distribution, fact revision.
- `backend/domains/metadata/artist_language_review.py` — review/source/evidence state transitions and transactions.
- `backend/models/artist_language_metadata.py` — request and response models.
- `backend/api/artist_language_metadata.py` — five language metadata endpoints.
- `scripts/import_artist_language_sources.py` — reviewed seed and legacy-suggestion importer.
- `data/artist_language_sources.seed.json` — reviewed seed payload, initially an empty JSON array until evidence is approved.

**Backend modify:**

- `backend/core/migrations.py` — migration 24.
- `backend/api/router.py` — language router registration.
- `backend/models/music_search.py` — optional `artist_id`.
- `backend/services/music_search_service.py` — populate artist search IDs.
- `backend/models/wrapped.py` — dynamic language distribution models.
- `backend/services/wrapped_service.py` — primary-artist language distribution and metadata cache revision.
- `scripts/api_smoke_probe.py` — safe GET coverage for language metadata.
- `scripts/openapi_operation_audit.py` — targeted evidence for five endpoints.
- `scripts/openapi_parameter_boundary_audit.py` — status, limit, review ID, and filter parameter evidence.

**Frontend create:**

- `frontend/src/types/artist-language-metadata.ts` — UI types.
- `frontend/src/hooks/useArtistLanguageMetadata.ts` — queries and mutations.
- `frontend/src/components/ui/dialog.tsx` — Base UI dialog wrapper matching existing primitives.
- `frontend/src/features/settings/components/ArtistLanguageHealthSection.tsx` — compact health/review list.
- `frontend/src/features/settings/components/ArtistLanguageReviewDialog.tsx` — source and evidence editor.

**Frontend modify:**

- `frontend/src/api/query-keys.ts` — `metadata.artistLanguages` keys.
- `frontend/src/types/music-search.ts` — optional `artist_id`.
- `frontend/src/types/yearly-review.ts` — dynamic distribution type.
- `frontend/src/features/settings/components/GenreDataHealthSection.tsx` — title and child composition only.
- `frontend/src/pages/yearly-review/GenrePanorama.tsx` — render backend buckets independently from genre.
- `frontend/src/lib/genre-regions.ts` — remove `inferLanguageDist()`.
- `frontend/src/api/generated/openapi.json` and `api-types.ts` — regenerated contract.
- `scripts/frontend_interaction_smoke.mjs` — Settings language review smoke.

**Tests create:**

- `backend/tests/unit/test_artist_language_migration.py`
- `backend/tests/unit/test_language_registry.py`
- `backend/tests/unit/test_artist_language_resolution.py`
- `backend/tests/unit/test_artist_language_review.py`
- `backend/tests/unit/test_artist_language_distribution.py`
- `backend/tests/unit/test_artist_language_seed_import.py`
- `backend/tests/contract/test_artist_language_metadata_api.py`
- `backend/tests/contract/test_artist_language_consumers.py`
- `frontend/src/tests/artist-language-health-section.test.tsx`
- `frontend/src/tests/artist-language-review-dialog.test.tsx`
- `frontend/src/tests/artist-language-hooks.test.tsx`
- `frontend/src/tests/yearly-language-distribution.test.tsx`

## Spec Coverage Map

| Spec requirement | Implementation task |
| --- | --- |
| Three-table schema and invariants | Task 1 |
| Canonical code/variant registry and API models | Task 2 |
| Evidence rules, approved-only resolver, primary-artist conservation, fact revision | Task 3 |
| Review lifecycle, replacement transaction, insufficient evidence | Task 4 |
| Five endpoints, PlayFilters, music-search reuse, error contracts | Task 5 |
| Reviewed seed, legacy suggestions, unresolved/conflicted handling | Task 6 |
| Wrapped dynamic distribution and cache invalidation | Task 7 |
| TanStack Query, generated/manual types, dialog primitive | Task 8 |
| Settings card 06 composition and human review UI | Task 9 |
| Removal of genre-to-language inference in yearly review | Task 10 |
| OpenAPI/API/UI smoke ownership | Task 11 |
| Durable docs, dry-run evidence, browser and release gates | Task 12 |

---

### Task 1: Add Migration 24 and Database Invariants

**Files:**

- Modify: `backend/core/migrations.py`
- Create: `backend/tests/unit/test_artist_language_migration.py`

- [ ] **Step 1: Write migration tests before the migration exists**

```python
from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_024


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL UNIQUE);
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id)
        );
        INSERT INTO artists VALUES (1, 'Artist');
        INSERT INTO tracks VALUES (10, 'Track', 1);
        """
    )
    return conn


def test_migrate_024_creates_language_tables_and_indexes() -> None:
    conn = _conn()
    migrate_024(conn)
    migrate_024(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "artist_language_sources",
        "artist_language_evidence",
        "artist_language_review_queue",
    } <= tables
    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "uq_artist_language_one_approved" in indexes
    assert "uq_artist_language_one_open_review" in indexes
    assert "uq_artist_language_source_review" in indexes


def test_migrate_024_enforces_core_checks() -> None:
    conn = _conn()
    migrate_024(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_sources(
                   artist_id, classification, origin, source_key
               ) VALUES (1, 'single_language', 'manual', 'missing-code')"""
        )
    cursor = conn.execute(
        """INSERT INTO artist_language_sources(
               artist_id, classification, primary_language_code, origin, source_key
           ) VALUES (1, 'single_language', 'en', 'manual', 'valid-source')"""
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO artist_language_evidence(
                   source_id, evidence_kind, performer_attribution,
                   evidence_url, evidence_title, evidence_accessed_at, evidence_summary
               ) VALUES (?, 'artist_profile', 'artist_vocal_confirmed',
                         'http://example.com', 'Title', '2026-07-11', 'Summary')""",
            (int(cursor.lastrowid),),
        )
```

- [ ] **Step 2: Run the tests and confirm the migration is missing**

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_migration.py -v`

Expected: collection fails because `migrate_024` does not exist.

- [ ] **Step 3: Add `@migration(24, "artist_language_resolution")`**

Append `migrate_024(conn)` before the migration runner in `backend/core/migrations.py`. Its `conn.executescript()` must contain exactly the three tables and six indexes in the approved spec, including these invariants:

```python
@migration(24, "artist_language_resolution")
def migrate_024(conn: sqlite3.Connection):
    """Persist artist language facts, evidence, and review decisions."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artist_language_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            classification TEXT NOT NULL,
            primary_language_code TEXT,
            language_variant TEXT,
            raw_language TEXT,
            origin TEXT NOT NULL,
            source_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'suggested',
            replaces_source_id INTEGER REFERENCES artist_language_sources(source_id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_id, origin, source_key),
            CHECK (classification IN ('single_language', 'multilingual', 'instrumental')),
            CHECK (
                (classification = 'single_language' AND primary_language_code IS NOT NULL) OR
                (classification IN ('multilingual', 'instrumental') AND primary_language_code IS NULL)
            ),
            CHECK (classification = 'single_language' OR language_variant IS NULL),
            CHECK (origin IN ('manual', 'curated_seed', 'legacy_import')),
            CHECK (status IN ('suggested', 'approved', 'rejected', 'superseded')),
            CHECK (replaces_source_id IS NULL OR replaces_source_id != source_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_one_approved
            ON artist_language_sources(artist_id) WHERE status = 'approved';
        CREATE INDEX IF NOT EXISTS idx_artist_language_sources_artist
            ON artist_language_sources(artist_id, status);

        CREATE TABLE IF NOT EXISTS artist_language_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES artist_language_sources(source_id),
            local_track_id INTEGER REFERENCES tracks(track_id),
            claimed_language_code TEXT,
            claimed_language_variant TEXT,
            evidence_kind TEXT NOT NULL,
            performer_attribution TEXT NOT NULL,
            evidence_url TEXT NOT NULL,
            evidence_title TEXT NOT NULL,
            evidence_accessed_at TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (evidence_kind IN (
                'artist_profile', 'artist_repertoire', 'editorial_source',
                'track_credit', 'track_language'
            )),
            CHECK (performer_attribution IN (
                'artist_vocal_confirmed', 'artist_instrumental_confirmed',
                'track_language_only', 'not_applicable'
            )),
            CHECK (claimed_language_variant IS NULL OR claimed_language_code IS NOT NULL),
            CHECK (evidence_url LIKE 'https://%'),
            CHECK (length(trim(evidence_title)) > 0),
            CHECK (length(trim(evidence_accessed_at)) > 0),
            CHECK (length(trim(evidence_summary)) > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_artist_language_evidence_source
            ON artist_language_evidence(source_id, local_track_id);

        CREATE TABLE IF NOT EXISTS artist_language_review_queue (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            suggested_source_id INTEGER REFERENCES artist_language_sources(source_id),
            play_hours_snapshot REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            resolution_note TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (play_hours_snapshot >= 0),
            CHECK (length(trim(reason)) > 0),
            CHECK (status IN ('open', 'approved', 'rejected', 'insufficient_evidence')),
            CHECK (
                status = 'open' OR (
                    reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND
                    resolution_note IS NOT NULL AND length(trim(reviewed_by)) > 0 AND
                    length(trim(reviewed_at)) > 0 AND length(trim(resolution_note)) > 0
                )
            ),
            CHECK (status NOT IN ('approved', 'rejected') OR suggested_source_id IS NOT NULL)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_one_open_review
            ON artist_language_review_queue(artist_id) WHERE status = 'open';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_source_review
            ON artist_language_review_queue(suggested_source_id)
            WHERE suggested_source_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_artist_language_reviews_status
            ON artist_language_review_queue(status, play_hours_snapshot DESC);
        """
    )
```

- [ ] **Step 4: Run migration tests and the existing migration suite**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_artist_language_migration.py -v
.venv/bin/pytest backend/tests/unit/test_migrations.py -v
```

Expected: both pass; migration 24 is idempotent.

- [ ] **Step 5: Commit checkpoint after authorization**

```bash
git add backend/core/migrations.py backend/tests/unit/test_artist_language_migration.py
git commit -m "feat: 新增艺人语言元数据表"
```

---

### Task 2: Add the Canonical Language Registry and API Models

**Files:**

- Create: `backend/domains/metadata/language_registry.py`
- Create: `backend/models/artist_language_metadata.py`
- Create: `backend/tests/unit/test_language_registry.py`

- [ ] **Step 1: Write registry tests**

```python
import pytest

from backend.domains.metadata.language_registry import (
    LANGUAGE_REGISTRY_VERSION,
    language_label,
    normalize_language_claim,
)


def test_registry_normalizes_legacy_aliases() -> None:
    assert normalize_language_claim("english", None) == ("en", None)
    assert normalize_language_claim("chinese", "Mandarin") == ("zh", "mandarin")
    assert language_label("zh") == "中文"
    assert LANGUAGE_REGISTRY_VERSION == "artist-language-v1"


def test_registry_rejects_unknown_codes_and_invalid_variants() -> None:
    with pytest.raises(ValueError, match="unsupported language code"):
        normalize_language_claim("xx-invalid", None)
    with pytest.raises(ValueError, match="unsupported variant"):
        normalize_language_claim("en", "cantonese")
```

- [ ] **Step 2: Run the registry tests and confirm imports fail**

Run: `.venv/bin/pytest backend/tests/unit/test_language_registry.py -v`

Expected: FAIL because the registry module does not exist.

- [ ] **Step 3: Implement the registry as the only label source**

```python
from __future__ import annotations

LANGUAGE_REGISTRY_VERSION = "artist-language-v1"

LANGUAGE_LABELS = {
    "en": "英文",
    "zh": "中文",
    "ja": "日文",
    "ko": "韩文",
    "es": "西班牙文",
    "fr": "法文",
    "de": "德文",
    "pt": "葡萄牙文",
    "it": "意大利文",
    "ru": "俄文",
    "ar": "阿拉伯文",
    "hi": "印地文",
    "th": "泰文",
    "vi": "越南文",
    "id": "印尼文",
    "ms": "马来文",
}

LANGUAGE_ALIASES = {
    "english": "en",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "portuguese": "pt",
}

LANGUAGE_VARIANTS = {
    "zh": {"mandarin", "cantonese", "minnan", "hakka"},
    "pt": {"brazilian", "european"},
}


def normalize_language_claim(code: str, variant: str | None) -> tuple[str, str | None]:
    normalized_code = LANGUAGE_ALIASES.get(code.strip().lower(), code.strip().lower())
    if normalized_code not in LANGUAGE_LABELS:
        raise ValueError(f"unsupported language code: {code}")
    normalized_variant = variant.strip().lower() if variant and variant.strip() else None
    if normalized_variant and normalized_variant not in LANGUAGE_VARIANTS.get(normalized_code, set()):
        raise ValueError(f"unsupported variant for {normalized_code}: {variant}")
    return normalized_code, normalized_variant


def language_label(code: str) -> str:
    return LANGUAGE_LABELS[code]
```

- [ ] **Step 4: Add typed request/response models**

Create Pydantic models with the exact public fields below. Public Settings request models and read-only response models have different provenance boundaries: the public PUT body accepts only language facts and evidence content, while response models expose persisted audit fields. Use `Literal` for classifications, origins, evidence kinds, attributions, review statuses, and actions; use `Field(default_factory=list)` for arrays and `ConfigDict(extra="forbid")` on public PUT input models so clients cannot inject provenance fields.

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LanguageClassification = Literal["single_language", "multilingual", "instrumental"]
LanguageOrigin = Literal["manual", "curated_seed", "legacy_import"]
ReviewAction = Literal["approve", "reject", "insufficient_evidence"]


class ArtistLanguageEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_track_id: int | None = None
    claimed_language_code: str | None = None
    claimed_language_variant: str | None = None
    evidence_kind: Literal[
        "artist_profile", "artist_repertoire", "editorial_source",
        "track_credit", "track_language",
    ]
    performer_attribution: Literal[
        "artist_vocal_confirmed", "artist_instrumental_confirmed",
        "track_language_only", "not_applicable",
    ]
    evidence_url: str
    evidence_title: str
    evidence_summary: str


class ArtistLanguageSourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: LanguageClassification
    primary_language_code: str | None = None
    language_variant: str | None = None
    raw_language: str | None = None
    evidence: list[ArtistLanguageEvidenceInput] = Field(default_factory=list)


class ArtistLanguageReviewCreateRequest(BaseModel):
    artist_id: int
    reason: str = "manual_research"


class ArtistLanguageReviewDecisionRequest(BaseModel):
    action: ReviewAction
    resolution_note: str


class ArtistLanguageBucket(BaseModel):
    key: str
    label: str
    classification: str
    hours: float
    share_pct: float
    artist_count: int


class ArtistLanguageMissingItem(BaseModel):
    artist_id: int
    artist_name: str
    hours: float


class ArtistLanguageCoverageResponse(BaseModel):
    eligible_hours: float
    excluded_unattributed_hours: float
    classified_hours: float
    unknown_hours: float
    classified_pct: float
    unknown_pct: float
    buckets: list[ArtistLanguageBucket] = Field(default_factory=list)
    source_hours: dict[str, float] = Field(default_factory=dict)
    top_missing: list[ArtistLanguageMissingItem] = Field(default_factory=list)
    caveat: str


class ArtistLanguageEvidenceItem(BaseModel):
    evidence_id: int
    source_id: int
    local_track_id: int | None = None
    claimed_language_code: str | None = None
    claimed_language_variant: str | None = None
    evidence_kind: str
    performer_attribution: str
    evidence_url: str
    evidence_title: str
    evidence_accessed_at: str
    evidence_summary: str
    created_at: str


class ArtistLanguageSourceItem(BaseModel):
    source_id: int
    artist_id: int
    classification: str
    primary_language_code: str | None = None
    language_variant: str | None = None
    raw_language: str | None = None
    origin: str
    source_key: str
    status: str
    replaces_source_id: int | None = None
    created_at: str
    updated_at: str
    evidence: list[ArtistLanguageEvidenceItem] = Field(default_factory=list)


class ArtistLanguageReviewItem(BaseModel):
    review_id: int
    artist_id: int
    artist_name: str
    suggested_source_id: int | None = None
    play_hours_snapshot: float
    reason: str
    status: str
    resolution_note: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str
    updated_at: str
    source: ArtistLanguageSourceItem | None = None


class ArtistLanguageReviewListResponse(BaseModel):
    items: list[ArtistLanguageReviewItem] = Field(default_factory=list)


class ArtistLanguageReviewMutationResponse(BaseModel):
    review_id: int
    review_status: str
    source_id: int | None = None
    source_status: str | None = None
```

`ArtistLanguageEvidenceItem` and `ArtistLanguageSourceItem` intentionally retain `evidence_accessed_at`, `origin`, and `source_key`: these are read-only audit fields returned after persistence, not fields accepted from Settings. For every public PUT, the service must persist `origin="manual"`, generate a `manual:<uuid4>` source key for a new candidate, and stamp each evidence row with current UTC. Only the importer may call the internal service payload path with validated `curated_seed`/`legacy_import` provenance, deterministic source keys, and recorded evidence access times.

- [ ] **Step 5: Run registry tests and import the models**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_language_registry.py -v
.venv/bin/python -c "from backend.models.artist_language_metadata import ArtistLanguageCoverageResponse"
```

Expected: PASS and no import error.

- [ ] **Step 6: Commit checkpoint after authorization**

```bash
git add backend/domains/metadata/language_registry.py backend/models/artist_language_metadata.py backend/tests/unit/test_language_registry.py
git commit -m "feat: 建立艺人语言代码注册表"
```

---

### Task 3: Implement Resolution, Validation, Distribution, and Fact Revision

**Files:**

- Create: `backend/domains/metadata/artist_languages.py`
- Create: `backend/tests/unit/test_artist_language_resolution.py`
- Create: `backend/tests/unit/test_artist_language_distribution.py`

- [ ] **Step 1: Write resolver and revision tests**

Create an in-memory fixture with the migration 24 schema, two artists, one approved source, one suggested source, and evidence. Lock these behaviors:

```python
def test_resolver_only_reads_approved_sources(language_conn) -> None:
    resolved = resolve_artist_languages_map(language_conn, [1, 2, 999])
    assert resolved[1].classification == "single_language"
    assert resolved[1].primary_language_code == "en"
    assert resolved[2].classification == "unknown"
    assert resolved[999].classification == "unknown"


def test_fact_revision_changes_only_when_approved_fact_changes(language_conn) -> None:
    first = artist_language_fact_revision(language_conn)
    language_conn.execute(
        "UPDATE artist_language_sources SET raw_language='draft edit' WHERE status='suggested'"
    )
    assert artist_language_fact_revision(language_conn) == first
    language_conn.execute(
        "UPDATE artist_language_sources SET status='approved' WHERE status='suggested'"
    )
    assert artist_language_fact_revision(language_conn) != first
```

- [ ] **Step 2: Write validator tests for all classifications**

Test these exact cases: valid single overview; single rejected when only `track_language`; valid multilingual with `en` plus `zh/mandarin`; invalid multilingual with `zh/NULL` plus `zh/mandarin`; valid instrumental overview; invalid instrumental track-only; track evidence rejected when `track_artists` does not credit the artist.

- [ ] **Step 3: Write primary-attribution and conservation tests**

```python
def test_primary_artist_hours_do_not_fan_out_collaborations(language_conn) -> None:
    plays = pd.DataFrame([
        {"track_id": 10, "ms_played": 3_600_000},
        {"track_id": 20, "ms_played": 1_800_000},
        {"track_id": None, "ms_played": 600_000},
    ])
    hours, excluded_ms = build_primary_artist_ms(language_conn, plays)
    assert hours == {1: 3_600_000, 2: 1_800_000}
    assert excluded_ms == 600_000


def test_distribution_conserves_eligible_milliseconds(language_conn) -> None:
    bucket_ms = _compute_language_bucket_ms(
        language_conn,
        {1: 3_600_000, 2: 1_800_000, 3: 900_000},
    )
    assert sum(bucket_ms.values()) == 6_300_000
    result = compute_artist_language_distribution(
        language_conn,
        {1: 3_600_000, 2: 1_800_000, 3: 900_000},
        excluded_ms=600_000,
    )
    assert result["excluded_unattributed_hours"] == pytest.approx(1 / 6)
```

- [ ] **Step 4: Run tests and confirm the module is missing**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_artist_language_resolution.py -v
.venv/bin/pytest backend/tests/unit/test_artist_language_distribution.py -v
```

Expected: FAIL on missing imports.

- [ ] **Step 5: Implement the public domain contract**

`artist_languages.py` must expose these exact symbols:

```python
@dataclass(frozen=True)
class ResolvedArtistLanguage:
    artist_id: int
    classification: str
    primary_language_code: str | None
    language_variant: str | None
    origin: str
    source_id: int | None


class ArtistLanguageValidationError(ValueError):
    pass


def resolve_artist_languages_map(
    conn: sqlite3.Connection,
    artist_ids: Sequence[int],
) -> dict[int, ResolvedArtistLanguage]:
    requested = list(dict.fromkeys(int(value) for value in artist_ids))
    resolved = {
        artist_id: ResolvedArtistLanguage(
            artist_id=artist_id,
            classification="unknown",
            primary_language_code=None,
            language_variant=None,
            origin="unknown",
            source_id=None,
        )
        for artist_id in requested
    }
    for offset in range(0, len(requested), 500):
        chunk = requested[offset : offset + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT source_id, artist_id, classification,
                       primary_language_code, language_variant, origin
                FROM artist_language_sources
                WHERE status='approved' AND artist_id IN ({placeholders})""",
            chunk,
        ).fetchall()
        for row in rows:
            resolved[int(row["artist_id"])] = ResolvedArtistLanguage(
                artist_id=int(row["artist_id"]),
                classification=str(row["classification"]),
                primary_language_code=row["primary_language_code"],
                language_variant=row["language_variant"],
                origin=str(row["origin"]),
                source_id=int(row["source_id"]),
            )
    return resolved
```

Implement `validate_approved_language_source(conn, artist_id, source_row, evidence_rows)` by normalizing evidence claim sets through `normalize_language_claim()`, checking `track_artists`, and enforcing the exact single/multilingual/instrumental rules from the spec. Return normalized `(source_values, evidence_values)` rather than mutating the database.

Implement `build_primary_artist_ms(conn, plays_df)` by joining only `tracks(track_id, artist_id)`, summing `ms_played` by `artist_id`, and returning excluded milliseconds separately. Put exact bucket allocation in `_compute_language_bucket_ms(conn, artist_ms_by_id)` and let `compute_artist_language_distribution()` format that integer-millisecond result into public hours/percentages. The public dict must not contain private/raw fields.

Implement the revision with deterministic JSON and SHA-256:

```python
def artist_language_fact_revision(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """SELECT artist_id, source_id, classification,
                  primary_language_code, language_variant, origin
           FROM artist_language_sources
           WHERE status='approved'
           ORDER BY artist_id, source_id"""
    ).fetchall()
    payload = {
        "registry": LANGUAGE_REGISTRY_VERSION,
        "facts": [tuple(row) for row in rows],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_artist_language_resolution.py -v
.venv/bin/pytest backend/tests/unit/test_artist_language_distribution.py -v
```

Expected: PASS, including no fan-out and exact millisecond conservation.

- [ ] **Step 7: Commit checkpoint after authorization**

```bash
git add backend/domains/metadata/artist_languages.py backend/tests/unit/test_artist_language_resolution.py backend/tests/unit/test_artist_language_distribution.py
git commit -m "feat: 实现艺人语言解析与统计"
```

---

### Task 4: Implement the Review State Machine

**Files:**

- Create: `backend/domains/metadata/artist_language_review.py`
- Create: `backend/tests/unit/test_artist_language_review.py`

- [ ] **Step 1: Write state-transition tests**

Cover: idempotent open review creation; saving and replacing suggested evidence; approve without evidence fails; reject closes source/review; insufficient review works without a source; approved replacement uses `replaces_source_id`; stale review raises conflict; failure between supersede and approve rolls back.

```python
def test_approve_replaces_existing_source_atomically(language_conn) -> None:
    existing_id = seed_approved_source(language_conn, artist_id=1, code="en")
    review = get_or_create_review(
        language_conn, artist_id=1, play_hours_snapshot=10.0, reason="manual_research"
    )
    saved = save_review_source(
        language_conn,
        review_id=review["review_id"],
        payload=valid_single_source("zh", "mandarin"),
    )
    result = decide_review(
        language_conn,
        review_id=review["review_id"],
        action="approve",
        resolution_note="Verified artist profile.",
        reviewed_by="local_user",
    )
    assert result["source_status"] == "approved"
    assert language_conn.execute(
        "SELECT status FROM artist_language_sources WHERE source_id=?", (existing_id,)
    ).fetchone()[0] == "superseded"
    assert saved["source_id"] != existing_id
```

- [ ] **Step 2: Run tests and confirm the service is missing**

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_review.py -v`

Expected: FAIL on missing imports.

- [ ] **Step 3: Implement explicit service exceptions and public functions**

```python
from contextlib import contextmanager


class ArtistLanguageNotFoundError(LookupError):
    pass


class ArtistLanguageConflictError(RuntimeError):
    pass


@contextmanager
def immediate_transaction(conn: sqlite3.Connection):
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
    else:
        if owns_transaction:
            conn.commit()


def get_or_create_review(
    conn: sqlite3.Connection,
    *,
    artist_id: int,
    play_hours_snapshot: float,
    reason: str,
) -> dict[str, Any]:
    with immediate_transaction(conn):
        artist = conn.execute(
            "SELECT artist_id, artist_name FROM artists WHERE artist_id=?", (artist_id,)
        ).fetchone()
        if artist is None:
            raise ArtistLanguageNotFoundError(f"artist {artist_id} not found")
        existing = conn.execute(
            """SELECT review_id FROM artist_language_review_queue
               WHERE artist_id=? AND status='open'""",
            (artist_id,),
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                """INSERT INTO artist_language_review_queue(
                       artist_id, play_hours_snapshot, reason
                   ) VALUES (?, ?, ?)""",
                (artist_id, max(0.0, play_hours_snapshot), reason.strip()),
            )
            review_id = int(cursor.lastrowid)
        else:
            review_id = int(existing["review_id"])
    return get_review(conn, review_id)
```

Implement `get_review()`, `list_reviews()`, `save_review_source()`, and `decide_review()` in the same module. Every mutation uses `immediate_transaction()`. The helper owns commit/rollback only when the caller has not already opened a transaction, so the importer can wrap an entire batch in one outer `BEGIN IMMEDIATE`. `save_review_source()` may edit only an open review and suggested source. Its public Settings path accepts only fact/evidence content, forces `origin="manual"`, generates `manual:<uuid4>` for a new candidate, stamps current UTC `evidence_accessed_at`, normalizes code/variant values, and replaces evidence rows in one transaction. Keep importer provenance in a separate internal payload/helper that may accept only validated `curated_seed`/`legacy_import` origin, deterministic `source_key`, and recorded `evidence_accessed_at`; never expose those fields through the FastAPI request model. `decide_review()` re-reads the review, calls `validate_approved_language_source()` for approve, sets any existing approved source to superseded, approves the candidate, and closes the review before the transaction exits. Reject and insufficient-evidence decisions set any attached suggested source to rejected; terminal rows cannot be edited through the service.

- [ ] **Step 4: Run review tests**

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_review.py -v`

Expected: PASS for all state and rollback cases.

- [ ] **Step 5: Commit checkpoint after authorization**

```bash
git add backend/domains/metadata/artist_language_review.py backend/tests/unit/test_artist_language_review.py
git commit -m "feat: 增加艺人语言人工审核状态流"
```

---

### Task 5: Expose Five FastAPI Endpoints and Reuse Music Search

**Files:**

- Create: `backend/api/artist_language_metadata.py`
- Modify: `backend/api/router.py`
- Modify: `backend/models/music_search.py`
- Modify: `backend/services/music_search_service.py`
- Create: `backend/tests/contract/test_artist_language_metadata_api.py`
- Modify: `backend/tests/contract/test_playback_filter_parameter_propagation.py`

- [ ] **Step 1: Write contract tests for all five endpoints**

Build an isolated database using `db_mod.init_db()` plus migrations. Seed artists, tracks, track_artists, plays, and one review. Test:

```python
def test_language_coverage_uses_play_filters(client, artist_language_db) -> None:
    response = client.get(
        "/api/metadata/artist-languages/coverage",
        params={
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible_hours"] > 0
    assert sum(row["hours"] for row in payload["buckets"]) == pytest.approx(
        payload["eligible_hours"], abs=0.2
    )


def test_review_api_supports_full_manual_flow(client, artist_language_db) -> None:
    started = client.post(
        "/api/metadata/artist-languages/reviews",
        json={"artist_id": 2, "reason": "manual_research"},
    )
    assert started.status_code == 200
    review_id = started.json()["review_id"]
    saved = client.put(
        f"/api/metadata/artist-languages/reviews/{review_id}/source",
        json=valid_single_payload(),
    )
    assert saved.status_code == 200
    approved = client.patch(
        f"/api/metadata/artist-languages/reviews/{review_id}",
        json={"action": "approve", "resolution_note": "Official profile reviewed."},
    )
    assert approved.status_code == 200
    assert approved.json()["source_status"] == "approved"
```

Add explicit 404, 409, and 422 assertions, review status/limit listing, and insufficient-evidence without source. Also assert that public PUT rejects `origin`, `source_key`, and evidence `evidence_accessed_at` as extra fields, while a successful Settings save returns server-generated `origin="manual"`, a `manual:` UUID source key, and a server-stamped evidence access time.

- [ ] **Step 2: Run contract tests and confirm routes return 404**

Run: `.venv/bin/pytest backend/tests/contract/test_artist_language_metadata_api.py -v`

Expected: FAIL because the router is absent.

- [ ] **Step 3: Implement the router with existing dependencies**

Create a router with prefix `/metadata/artist-languages`. Use `PlayFilters = Depends()` on coverage and review creation. Coverage calls `load_plays()` with all five filter fields, then `build_primary_artist_ms()` and `compute_artist_language_distribution()`.

```python
router = APIRouter(
    prefix="/metadata/artist-languages",
    tags=["Artist Language Metadata"],
)


def get_write_conn():
    conn = get_db(readonly=False)
    try:
        yield conn
    finally:
        conn.close()


def _filtered_plays(conn: Connection, filters: PlayFilters):
    return load_plays(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
```

Call `_filtered_plays(conn, filters)` with the request connection. `load_plays()` uses the repository cache internally but does not retain or close the request connection. Map service exceptions to 404/409 and validation errors to 422 with `{code, message}` detail.

For PUT source saves, pass only the validated fact/evidence request to the public Settings service path; do not derive provenance from request JSON. For PATCH decisions, ignore any client-supplied actor field: pass `reviewed_by="local_user"` and let the service set current UTC `reviewed_at`. The request model contains only `action` and `resolution_note`.

- [ ] **Step 4: Register the router and expose `artist_id` from music search**

Add `artist_language_metadata_router` to `backend/api/router.py`. Add `artist_id: int | None = None` to `MusicSearchResult` and set it in `_artist_result()`:

```python
return MusicSearchResult(
    kind="artist",
    label=str(artist_name),
    subtitle=_plays_text(play_events),
    href=f"/music/artists/{quote(str(artist_name), safe='')}",
    play_events=play_events,
    total_ms=_candidate_metric(candidate, "total_ms", metrics),
    artist_id=int(candidate["artist_id"]) if candidate.get("artist_id") is not None else None,
    artist_name=str(artist_name),
    cover_url=_cover_url("artists", candidate.get("artist_id")),
    chart=chart,
)
```

- [ ] **Step 5: Lock filter propagation**

Add a test to `test_playback_filter_parameter_propagation.py` that creates a short dynamic-threshold play and asserts the language coverage differs between `dynamic_threshold=false` and `true`. Also assert `max_merge_gap_minutes` reaches the endpoint dependency.

- [ ] **Step 6: Run contract and search tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_artist_language_metadata_api.py -v
.venv/bin/pytest backend/tests/contract/test_playback_filter_parameter_propagation.py -v
.venv/bin/pytest backend/tests/contract/test_music_search_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit checkpoint after authorization**

```bash
git add backend/api/artist_language_metadata.py backend/api/router.py backend/models/music_search.py backend/services/music_search_service.py backend/tests/contract/test_artist_language_metadata_api.py backend/tests/contract/test_playback_filter_parameter_propagation.py
git commit -m "feat: 提供艺人语言审核 API"
```

---

### Task 6: Add Reviewed Seed and Legacy-Suggestion Import

**Files:**

- Create: `scripts/import_artist_language_sources.py`
- Create: `data/artist_language_sources.seed.json`
- Create: `backend/tests/unit/test_artist_language_seed_import.py`

- [ ] **Step 1: Write importer tests**

Test dry-run/no writes, reviewed approved seed through the same approve service, idempotency, existing-approved conflict, unresolved artist, normalized-identical legacy merge, conflicting legacy skip, and rollback after a simulated second-row failure.

```python
def test_legacy_import_never_auto_approves(language_conn) -> None:
    report = import_legacy_suggestions(language_conn, dry_run=False)
    assert report["approved"] == 0
    assert language_conn.execute(
        "SELECT COUNT(*) FROM artist_language_sources WHERE status='approved'"
    ).fetchone()[0] == 0
    assert language_conn.execute(
        "SELECT COUNT(*) FROM artist_language_review_queue WHERE status='open'"
    ).fetchone()[0] == report["suggested"]


def test_conflicting_legacy_values_are_reported_not_chosen(language_conn) -> None:
    seed_conflicting_genre_languages(language_conn, artist_name="Artist", values=["english", "chinese"])
    report = import_legacy_suggestions(language_conn, dry_run=False)
    assert report["conflicted"] == 1
    assert language_conn.execute("SELECT COUNT(*) FROM artist_language_sources").fetchone()[0] == 0
```

- [ ] **Step 2: Run tests and confirm importer is missing**

Run: `.venv/bin/pytest backend/tests/unit/test_artist_language_seed_import.py -v`

Expected: FAIL on missing module.

- [ ] **Step 3: Implement one CLI with two input modes**

The CLI arguments are fixed:

```python
parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
parser.add_argument("--legacy-suggestions", action="store_true")
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--json-output", type=Path)
```

Reviewed seed rows contain `artist_name`, optional `spotify_artist_id`, source fields, evidence list, status, `reviewed_by`, and `resolution_note`. Resolve `artist_id` before writing. The importer owns a separate internal payload schema that may carry validated `origin`, deterministic `source_key`, and evidence `evidence_accessed_at`; these fields must never be reused as the public PUT request model. The importer opens one outer `BEGIN IMMEDIATE` for the batch, then approved seed rows call `get_or_create_review()`, the internal provenance-aware save path, and `decide_review()` rather than issuing direct approved INSERTs. Those services detect the outer transaction through `immediate_transaction()` and therefore cannot partially commit the batch. Dry-run must execute the same structural and foreign-key validation as the write path, so accepted dry-run rows cannot fail only when persisted.

Legacy mode reads approved rows from `artist_genre_sources` and all `artist_genre_overrides` with non-empty language. Normalize per artist; merge identical claims; emit `conflicted` without writes for disagreeing claims; create suggested source/review only for one unambiguous claim. Never fabricate evidence.

- [ ] **Step 4: Create the production seed file as valid empty JSON**

```json
[]
```

The repository must not ship invented evidence. Reviewed entries can be added later through the same schema.

- [ ] **Step 5: Run importer tests and a production dry-run**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_artist_language_seed_import.py -v
.venv/bin/python scripts/import_artist_language_sources.py --dry-run --json-output /tmp/artist-language-seed-dry-run.json
.venv/bin/python scripts/import_artist_language_sources.py --legacy-suggestions --dry-run --json-output /tmp/artist-language-legacy-dry-run.json
```

Expected: tests pass; seed dry-run reports zero rows; legacy dry-run reports suggested/unresolved/conflicted without changing `data/spotify_stats.db`.

- [ ] **Step 6: Stop before writing production legacy suggestions**

Review `/tmp/artist-language-legacy-dry-run.json`. The actual command without `--dry-run` is a separate, explicit deployment action after user approval:

```bash
.venv/bin/python scripts/import_artist_language_sources.py --legacy-suggestions --json-output /tmp/artist-language-legacy-import.json
```

- [ ] **Step 7: Commit checkpoint after authorization**

```bash
git add scripts/import_artist_language_sources.py data/artist_language_sources.seed.json backend/tests/unit/test_artist_language_seed_import.py
git commit -m "feat: 增加艺人语言种子与候选导入"
```

---

### Task 7: Integrate Language Distribution into Wrapped and Cache Revision

**Files:**

- Modify: `backend/models/wrapped.py`
- Modify: `backend/services/wrapped_service.py`
- Create: `backend/tests/contract/test_artist_language_consumers.py`
- Modify: `backend/tests/unit/test_wrapped_genre_panorama.py`

- [ ] **Step 1: Write consumer and cache tests**

Lock these behaviors: backend returns dynamic buckets; language uses primary artist while genre keeps fan-out semantics; bucket milliseconds conserve the year frame; language renders even when genre list is empty; approving a fact invalidates Wrapped LRU; editing suggested evidence does not.

```python
def test_wrapped_language_distribution_uses_primary_artist_and_unknown_bucket(language_db) -> None:
    result = get_wrapped_full(
        language_db, 30000, True, True, 2024,
        dynamic_threshold=True, max_merge_gap_minutes=None, merge_level=2,
    )
    language = result["genre_panorama"]["language_dist"]
    assert language["eligible_hours"] == pytest.approx(3.0)
    assert {row["key"] for row in language["buckets"]} == {"en", "unknown"}


def test_approved_language_fact_invalidates_wrapped_cache(language_db) -> None:
    first = get_wrapped_full(language_db, 30000, True, True, 2024)
    approve_language_for_artist(language_db, artist_id=2, code="zh")
    second = get_wrapped_full(language_db, 30000, True, True, 2024)
    assert first["genre_panorama"]["language_dist"] != second["genre_panorama"]["language_dist"]
```

- [ ] **Step 2: Run focused tests and confirm `language_dist` is still null**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_artist_language_consumers.py -v
.venv/bin/pytest backend/tests/unit/test_wrapped_genre_panorama.py -v
```

Expected: FAIL because Wrapped does not consume language facts.

- [ ] **Step 3: Replace fixed language fields with dynamic response models**

In `backend/models/wrapped.py`, import/reuse `ArtistLanguageBucket` and define:

```python
class LanguageDistribution(BaseModel):
    eligible_hours: float = 0.0
    excluded_unattributed_hours: float = 0.0
    classified_hours: float = 0.0
    unknown_hours: float = 0.0
    classified_pct: float = 0.0
    unknown_pct: float = 0.0
    buckets: list[ArtistLanguageBucket] = Field(default_factory=list)
    source_hours: dict[str, float] = Field(default_factory=dict)
    top_missing: list[ArtistLanguageMissingItem] = Field(default_factory=list)
    caveat: str = "艺人级估算，按主艺人归属。"
```

Set `GenrePanorama.language_dist: LanguageDistribution | None` and retain existing genre `coverage` and `caveat` fields.

- [ ] **Step 4: Compose a combined metadata revision**

Rename `_artist_genre_revision()` to `_artist_metadata_revision()` and append `artist_language_fact_revision(conn)` to the existing genre revision. Rename the cached argument to `artist_metadata_revision`; no other cache signature changes.

- [ ] **Step 5: Build language distribution before the genre empty return**

Inside `_build_genre_panorama(conn, year_df, artist_agg)`, call `build_primary_artist_ms(conn, year_df[["track_id", "ms_played"]])` and `compute_artist_language_distribution()`. The function must return this value both when genres are empty and when they are present. Do not use `artist_agg` for language.

- [ ] **Step 6: Run consumer and existing Wrapped tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_artist_language_consumers.py -v
.venv/bin/pytest backend/tests/unit/test_wrapped_genre_panorama.py -v
.venv/bin/pytest backend/tests/contract/test_artist_genre_consumers.py -v
.venv/bin/pytest backend/tests/integration/test_wrapped_full.py -v
```

Expected: PASS; existing genre behavior remains unchanged.

- [ ] **Step 7: Commit checkpoint after authorization**

```bash
git add backend/models/wrapped.py backend/services/wrapped_service.py backend/tests/contract/test_artist_language_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py
git commit -m "feat: 年度回顾接入真实语言分布"
```

---

### Task 8: Add Frontend Types, Query Keys, Hooks, and Dialog Primitive

**Files:**

- Create: `frontend/src/types/artist-language-metadata.ts`
- Create: `frontend/src/hooks/useArtistLanguageMetadata.ts`
- Create: `frontend/src/components/ui/dialog.tsx`
- Modify: `frontend/src/api/query-keys.ts`
- Modify: `frontend/src/types/music-search.ts`
- Create: `frontend/src/tests/artist-language-hooks.test.tsx`

- [ ] **Step 1: Write hook tests with mocked API calls**

Assert coverage query includes current play filters, review list keys include status/limit, start review POSTs `artist_id`, save source uses PUT, decision uses PATCH, and successful mutations invalidate only language metadata and yearly review keys.

- [ ] **Step 2: Run the hook test and confirm imports fail**

Run: `cd frontend && npm test -- --run src/tests/artist-language-hooks.test.tsx`

Expected: FAIL because the hook and query keys do not exist.

- [ ] **Step 3: Add exact query keys and UI types**

```typescript
artistLanguages: {
  all: ['metadata', 'artist-languages'] as const,
  coverage: (params: Record<string, unknown>) =>
    ['metadata', 'artist-languages', 'coverage', params] as const,
  reviews: (status = 'open', limit = 50) =>
    ['metadata', 'artist-languages', 'reviews', status, limit] as const,
},
```

Define TypeScript interfaces matching Task 2, including dynamic `LanguageBucket`, `ArtistLanguageCoverage`, evidence/source/review inputs, and mutation responses. The Settings evidence/source input interfaces contain only fact and evidence content: they must not expose `evidence_accessed_at`, `origin`, or `source_key`; read-only response interfaces retain those audit fields. Add `artist_id: number | null` to `MusicSearchResult`.

- [ ] **Step 4: Implement hooks around the five endpoints**

Expose:

```typescript
useArtistLanguageCoverage(filters)
useArtistLanguageReviews(status, limit)
useStartArtistLanguageReview()
useSaveArtistLanguageSource(reviewId)
useDecideArtistLanguageReview(reviewId)
```

Use `api.get/post/put/patch`. The save-source PUT must serialize only the public fact/evidence input and must not synthesize provenance in the browser. After successful mutation invalidate only `queryKeys.metadata.artistLanguages.all` and `queryKeys.yearlyReview.all`.

- [ ] **Step 5: Add a Base UI dialog wrapper**

Create `dialog.tsx` using `Dialog as DialogPrimitive` from `@base-ui/react/dialog`, following the focus trap, backdrop, title, description, close button, and `max-h-[90vh] overflow-y-auto` patterns already used by `sheet.tsx`. Export `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`, and `DialogClose`.

- [ ] **Step 6: Run hook tests and TypeScript build**

Run:

```bash
cd frontend && npm test -- --run src/tests/artist-language-hooks.test.tsx
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit checkpoint after authorization**

```bash
git add frontend/src/types/artist-language-metadata.ts frontend/src/hooks/useArtistLanguageMetadata.ts frontend/src/components/ui/dialog.tsx frontend/src/api/query-keys.ts frontend/src/types/music-search.ts frontend/src/tests/artist-language-hooks.test.tsx
git commit -m "feat: 增加艺人语言前端数据层"
```

---

### Task 9: Build the Settings Language Health and Review Experience

**Files:**

- Create: `frontend/src/features/settings/components/ArtistLanguageHealthSection.tsx`
- Create: `frontend/src/features/settings/components/ArtistLanguageReviewDialog.tsx`
- Modify: `frontend/src/features/settings/components/GenreDataHealthSection.tsx`
- Create: `frontend/src/tests/artist-language-health-section.test.tsx`
- Create: `frontend/src/tests/artist-language-review-dialog.test.tsx`
- Modify: `frontend/src/tests/genre-data-health-section.test.tsx`

- [ ] **Step 1: Write health-section interaction tests**

Assert the collapsed summary shows classified/unknown/open counts; expanding renders Top unknown; clicking “开始审核” starts/reuses a review and opens the dialog; the status menu can show terminal history; no campaign or AI controls appear.

- [ ] **Step 2: Write review-dialog tests**

Cover single language and variant selection, multiple evidence rows, artist/track search selection, approve/reject/insufficient actions, structured 422 display, replacement-chain display, accessible labels, and closing without mutation.

- [ ] **Step 3: Run tests and confirm components are missing**

Run:

```bash
cd frontend && npm test -- --run src/tests/artist-language-health-section.test.tsx
cd frontend && npm test -- --run src/tests/artist-language-review-dialog.test.tsx
```

Expected: FAIL on missing components.

- [ ] **Step 4: Implement `ArtistLanguageHealthSection` as an unframed subsection**

Use a local `CollapsibleSection` without a number, a three-value summary row, a compact unknown list, a standard status select, and text/icon buttons. Do not wrap it in `GlassCard`; the parent already owns the card. Limit visible unknown rows to 10 and let the API limit review history to 50.

- [ ] **Step 5: Implement the review dialog**

Use the new dialog primitive, existing Select and Button components, native labeled inputs/textareas, plus/minus icon buttons for evidence rows, and `useMusicSearch(..., 'artist')` / `useMusicSearch(..., 'track')`. Classification controls determine which language fields are visible. The approve button stays disabled until the client-side minimum shape is present, while the backend remains authoritative.

- [ ] **Step 6: Compose it into the existing card without restructuring genre**

Change the outer title to `流派与语言数据健康`, update the description, and render `<ArtistLanguageHealthSection />` after the existing genre panel content. Keep card number 6 and all current genre panel states/tests.

- [ ] **Step 7: Run Settings tests and build**

Run:

```bash
cd frontend && npm test -- --run src/tests/artist-language-health-section.test.tsx src/tests/artist-language-review-dialog.test.tsx src/tests/genre-data-health-section.test.tsx src/tests/settings-page-layout.test.tsx
cd frontend && npm run build
```

Expected: PASS with no nested cards or changed Settings numbering.

- [ ] **Step 8: Commit checkpoint after authorization**

```bash
git add frontend/src/features/settings/components/ArtistLanguageHealthSection.tsx frontend/src/features/settings/components/ArtistLanguageReviewDialog.tsx frontend/src/features/settings/components/GenreDataHealthSection.tsx frontend/src/tests/artist-language-health-section.test.tsx frontend/src/tests/artist-language-review-dialog.test.tsx frontend/src/tests/genre-data-health-section.test.tsx
git commit -m "feat: Settings 增加语言数据审核面板"
```

---

### Task 10: Replace Yearly Genre Inference with Backend Language Buckets

**Files:**

- Modify: `frontend/src/types/yearly-review.ts`
- Modify: `frontend/src/pages/yearly-review/GenrePanorama.tsx`
- Modify: `frontend/src/lib/genre-regions.ts`
- Create: `frontend/src/tests/yearly-language-distribution.test.tsx`

- [ ] **Step 1: Write yearly rendering tests**

Test dynamic buckets, classified/unknown copy, excluded-hours caveat, genre-empty/language-present rendering, and complete absence of `inferLanguageDist` imports.

```tsx
it('renders backend language buckets when genres are empty', () => {
  render(
    <GenrePanorama
      genrePanorama={{
        top_genres: [],
        monthly_genres: [],
        language_dist: {
          eligible_hours: 10,
          excluded_unattributed_hours: 0,
          classified_hours: 7,
          unknown_hours: 3,
          classified_pct: 70,
          unknown_pct: 30,
          buckets: [
            { key: 'en', label: '英文', classification: 'single_language', hours: 7, share_pct: 70, artist_count: 2 },
            { key: 'unknown', label: '未知', classification: 'unknown', hours: 3, share_pct: 30, artist_count: 1 },
          ],
          source_hours: { manual: 7 },
          top_missing: [],
          caveat: '艺人级估算，按主艺人归属。',
        },
      }}
    />,
  )
  expect(screen.getByText('英文')).toBeInTheDocument()
  expect(screen.getByText('未知')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the test and confirm the current early return fails it**

Run: `cd frontend && npm test -- --run src/tests/yearly-language-distribution.test.tsx`

Expected: FAIL because language is inferred from top genres and hidden when genres are empty.

- [ ] **Step 3: Replace the fixed interface and render backend buckets**

Define `LanguageDistribution` using the Task 8 types. Remove `useMemo`, `inferLanguageDist`, fixed label/color maps, and the genre-only early return. Render the genre card only when `top_genres.length > 0`; render the language card whenever `language_dist.buckets.length > 0`; render the section-level empty state only when both are absent.

- [ ] **Step 4: Delete the unused inference function**

Remove `inferLanguageDist()` and any constants used only by it from `frontend/src/lib/genre-regions.ts`. Verify repository search returns no production references.

- [ ] **Step 5: Run yearly tests and build**

Run:

```bash
cd frontend && npm test -- --run src/tests/yearly-language-distribution.test.tsx
rg -n "inferLanguageDist" frontend/src --glob '!tests/**'
cd frontend && npm run build
```

Expected: test/build PASS; `rg` prints no production match.

- [ ] **Step 6: Commit checkpoint after authorization**

```bash
git add frontend/src/types/yearly-review.ts frontend/src/pages/yearly-review/GenrePanorama.tsx frontend/src/lib/genre-regions.ts frontend/src/tests/yearly-language-distribution.test.tsx
git commit -m "fix: 年度页使用真实艺人语言数据"
```

---

### Task 11: Regenerate OpenAPI Types and Extend Verification Ownership

**Files:**

- Modify: `frontend/src/api/generated/openapi.json`
- Modify: `frontend/src/api/generated/api-types.ts`
- Modify: `scripts/api_smoke_probe.py`
- Modify: `scripts/openapi_operation_audit.py`
- Modify: `scripts/openapi_parameter_boundary_audit.py`
- Modify: `backend/tests/unit/test_openapi_operation_audit_script.py`
- Modify: `backend/tests/unit/test_openapi_parameter_boundary_audit_script.py`
- Modify: `scripts/frontend_interaction_smoke.mjs`
- Modify: `backend/tests/unit/test_frontend_interaction_smoke_script.py`

- [ ] **Step 1: Add audit tests before audit mappings**

Assert all five operations resolve to `targeted_contract` evidence in `test_artist_language_metadata_api.py`, and language `review_id`, `status`, `limit`, plus PlayFilters parameters have explicit ownership.

- [ ] **Step 2: Add safe GET cases and targeted operation mappings**

Add these smoke paths:

```python
SmokeCase("artist-language-coverage", "/api/metadata/artist-languages/coverage"),
SmokeCase("artist-language-reviews", "/api/metadata/artist-languages/reviews"),
```

Add all five endpoint keys to `TARGETED_OPERATION_EVIDENCE`, pointing at `backend/tests/contract/test_artist_language_metadata_api.py`. Add boundary evidence for `review_id`, `status`, and `limit`; reuse the existing playback propagation contract for PlayFilters.

- [ ] **Step 3: Regenerate types from a running backend**

Start the backend with warmup disabled, then generate:

```bash
SPOTIFY_STATS_WARMUP=0 .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run generate-types
```

Expected: both generated files update and contain `ArtistLanguageCoverageResponse`, review models, and `artist_id` on `MusicSearchResult`.

- [ ] **Step 4: Extend Settings interaction smoke without creating reviews**

The smoke must open Settings, expand “语言数据”, verify Top unknown or empty state, and verify the “开始审核” command is accessible. If an open review already exists, it may open that existing review dialog and close it; otherwise it must not click “开始审核”, because creating an open review is a database write. Component and contract tests cover the full mutation path.

- [ ] **Step 5: Run audit and smoke-script unit tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_openapi_operation_audit_script.py -v
.venv/bin/pytest backend/tests/unit/test_openapi_parameter_boundary_audit_script.py -v
.venv/bin/pytest backend/tests/unit/test_frontend_interaction_smoke_script.py -v
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/artist-language-openapi-operations.json
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/artist-language-openapi-parameters.json
```

Expected: zero unaccounted operations and parameters.

- [ ] **Step 6: Commit checkpoint after authorization**

```bash
git add frontend/src/api/generated/openapi.json frontend/src/api/generated/api-types.ts scripts/api_smoke_probe.py scripts/openapi_operation_audit.py scripts/openapi_parameter_boundary_audit.py backend/tests/unit/test_openapi_operation_audit_script.py backend/tests/unit/test_openapi_parameter_boundary_audit_script.py scripts/frontend_interaction_smoke.mjs backend/tests/unit/test_frontend_interaction_smoke_script.py
git commit -m "test: 补齐艺人语言全栈验收契约"
```

---

### Task 12: Documentation, Production Dry-Run, and Release Gate

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/CHANGELOG.md`
- Review: `docs/README.md`
- Include: `docs/superpowers/specs/2026-07-10-artist-language-resolution-design.md`
- Include: `docs/superpowers/plans/2026-07-11-artist-language-resolution-phase-a.md`

- [ ] **Step 1: Update durable documentation**

Document these stable rules in AGENTS/CLAUDE: language resolution is artist-ID based and independent from genre; statistics use primary artist attribution; legacy/LLM data cannot auto-approve; unknown/multilingual/instrumental remain visible. Add user-facing Settings and yearly behavior to README and a dated implementation entry to CHANGELOG. Add links to `docs/README.md` only if its current indexing policy includes active superpowers specs/plans.

- [ ] **Step 2: Run focused backend and frontend suites**

```bash
.venv/bin/pytest \
  backend/tests/unit/test_artist_language_migration.py \
  backend/tests/unit/test_language_registry.py \
  backend/tests/unit/test_artist_language_resolution.py \
  backend/tests/unit/test_artist_language_distribution.py \
  backend/tests/unit/test_artist_language_review.py \
  backend/tests/unit/test_artist_language_seed_import.py \
  backend/tests/contract/test_artist_language_metadata_api.py \
  backend/tests/contract/test_artist_language_consumers.py -v
cd frontend && npm test
cd frontend && npm run build
```

Expected: all pass.

- [ ] **Step 3: Run repository quality gates**

```bash
ruff check backend/
ruff format --check backend/
pre-commit run --all-files
.venv/bin/pytest backend/tests/ -v
sh scripts/phase5_check.sh
.venv/bin/python scripts/ci_baseline_parity.py
```

Expected: all pass.

- [ ] **Step 4: Start services and run non-destructive full-stack checks**

With backend 8000 and frontend 5173 running:

```bash
.venv/bin/python scripts/api_smoke_probe.py
.venv/bin/python scripts/api_boundary_probe.py
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport both --include-detail-routes
node scripts/frontend_route_smoke.mjs --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes
```

Expected: zero API coverage gaps, zero unnamed controls, zero horizontal overflow, and no console warning/error.

- [ ] **Step 5: Run and inspect the production legacy dry-run**

```bash
.venv/bin/python scripts/import_artist_language_sources.py \
  --legacy-suggestions \
  --dry-run \
  --json-output /tmp/artist-language-legacy-dry-run.json
```

Record suggested/unresolved/conflicted counts and affected play hours in the final implementation report. Do not remove `--dry-run` without explicit approval.

- [ ] **Step 6: Perform real browser acceptance against a disposable database**

Start the backend with `SPOTIFY_STATS_DB_PATH` or the repository's supported DB-path override pointed at a temporary database copy. Verify desktop and 390px Settings: card 06 title, existing genre panels, language collapsible summary, Top unknown, start review, artist search, evidence rows, terminal-history filter, dialog close, and no overflow. Exercise one approve and one insufficient-evidence path, then discard the temporary database. Verify a yearly page: backend buckets render, classified/unknown copy is accurate, genre and language render independently, and no heuristic language result remains. If the repository does not yet support a DB-path environment override, monkeypatch `backend.core.db.DB_PATH` in a dedicated browser harness rather than adding a production configuration feature to this scope.

- [ ] **Step 7: Final commit checkpoint after authorization**

Inspect `git log --format=fuller -n 5`, stage only this feature, then commit:

```bash
git add README.md AGENTS.md CLAUDE.md docs/README.md docs/CHANGELOG.md docs/superpowers/specs/2026-07-10-artist-language-resolution-design.md docs/superpowers/plans/2026-07-11-artist-language-resolution-phase-a.md
git commit -m "docs: 同步艺人语言解析与审核规则"
```

If `docs/README.md` did not require a change, omit it from `git add`.

---

## Completion Checklist

- [ ] Three tables and migration 24 are present and idempotent.
- [ ] Five API endpoints have response models, contract coverage, and audit ownership.
- [ ] Resolver reads only approved facts by artist ID.
- [ ] Single/multilingual/instrumental evidence rules are enforced centrally.
- [ ] Language distribution uses primary artist attribution and conserves eligible milliseconds.
- [ ] Legacy import creates suggestions only and has a reviewed dry-run report.
- [ ] Wrapped cache changes on approved language facts, not suggested edits.
- [ ] Settings preserves card number 06 and adds no new top-level card/tab.
- [ ] Yearly review has no production reference to `inferLanguageDist()`.
- [ ] Generated OpenAPI types, manual frontend types, docs, tests, and browser smoke agree.
