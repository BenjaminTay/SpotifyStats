# Artist Genre Axis And Confidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让 genre 统计先按 `style / scene / context / role` 分轴展示，并把单艺人主导、低可信来源主导等风险传给 UI 和 AI 报告。

**Architecture:** 保留现有 artist-level genre resolution 和 taxonomy v2 canonical labels，不新增 album/era 数据层。本次只扩展 taxonomy audit 输出与消费者展示：后端负责计算 axis summary、risk flags、confidence/source tier；前端 Settings 负责按 axis 分组展示；AI/yearly caveat 负责避免把 scene/context/role 误说成 style 偏好。

**Tech Stack:** FastAPI + SQLite + Pydantic；React + TanStack Query + Vitest；pytest/ruff。

---

### Task 1: Extend Taxonomy Audit Contract

**Files:**
- Modify: `backend/domains/metadata/artist_genres.py`
- Modify: `backend/models/artist_genre_metadata.py`
- Test: `backend/tests/unit/test_artist_genre_resolution.py`
- Test: `backend/tests/contract/test_artist_genre_metadata_api.py`

- [x] **Step 1: Write failing backend tests**

Add tests that assert:
- `compute_genre_taxonomy_audit()` returns `axis_summary` with grouped hours/share for `style`, `scene`, `context`, `role`.
- each top canonical row includes `interpretation` and `confidence_tier`.
- dominance-sensitive labels include `risk_flags` with `single_artist_dominance`.
- LLM-heavy labels include `risk_flags` with `source_confidence`.

- [x] **Step 2: Implement minimal audit fields**

Add deterministic helpers in `artist_genres.py`:
- `source_confidence_tier(source_mix)` returns `high`, `medium`, or `low`.
- `interpretation_for_axis(axis)` returns concise Chinese copy for style/scene/context/role.
- `risk_flags_for_label(...)` returns structured risk flags, not only prose warnings.

- [x] **Step 3: Update Pydantic models**

Add model fields for:
- `axis_summary`
- canonical item `interpretation`
- canonical item `confidence_tier`
- canonical item `risk_flags`

- [x] **Step 4: Verify backend tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/contract/test_artist_genre_metadata_api.py -q
```

Expected: all tests pass.

### Task 2: Render Axis-First Settings Audit

**Files:**
- Modify: `frontend/src/types/artist-genre-metadata.ts`
- Modify: `frontend/src/features/settings/components/GenreDataHealthSection.tsx`
- Test: `frontend/src/tests/genre-data-health-section.test.tsx`

- [x] **Step 1: Write failing frontend tests**

Assert Settings shows:
- axis sections named `风格`, `场景`, `语境`, `身份`
- `c-pop` under scene instead of mixed into the style list
- `singer-songwriter` under role
- dominance and source confidence risk text

- [x] **Step 2: Implement grouped rendering**

Group `taxonomy.top_canonical_genres` by axis in the component and render each axis as its own section with the axis interpretation. Keep the existing raw mapping audit below.

- [x] **Step 3: Verify frontend tests**

Run:

```bash
cd frontend && npm test -- genre-data-health-section
```

Expected: all tests pass.

### Task 3: Update AI And Documentation Caveats

**Files:**
- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/domains/ai_reports/yearly_contract.py`
- Modify: `backend/services/yearly_report_agent_service.py`
- Modify: `docs/productization/2026-07-04-artist-genre-taxonomy.md`
- Test: `backend/tests/contract/test_artist_genre_consumers.py`
- Test: `backend/tests/unit/test_wrapped_genre_panorama.py`

- [x] **Step 1: Write or update tests for caveat copy**

Assert AI/report payloads mention:
- statistical labels are axis-aware
- scene/context/role labels are not pure style preferences
- dominance-sensitive labels should be phrased as driven by top artists

- [x] **Step 2: Update caveat strings**

Use short Chinese caveats in user-facing payloads and concise English/Chinese contract language where existing files already use English.

- [x] **Step 3: Verify consumer tests**

Run:

```bash
.venv/bin/python -m pytest backend/tests/contract/test_artist_genre_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py -q
```

Expected: all tests pass.

### Task 4: Final Verification

**Files:**
- All modified files above

- [x] **Step 1: Run focused backend verification**

```bash
.venv/bin/python -m pytest backend/tests/unit/test_artist_genre_resolution.py backend/tests/contract/test_artist_genre_metadata_api.py backend/tests/contract/test_artist_genre_consumers.py backend/tests/unit/test_wrapped_genre_panorama.py -q
```

- [x] **Step 2: Run focused frontend verification**

```bash
cd frontend && npm test -- genre-data-health-section
```

- [x] **Step 3: Run lint on touched backend files**

```bash
.venv/bin/ruff check backend/domains/metadata/artist_genres.py backend/models/artist_genre_metadata.py backend/api/artist_genre_metadata.py backend/services/ai_insights_service.py backend/domains/ai_reports/yearly_contract.py backend/services/yearly_report_agent_service.py
```

- [x] **Step 4: Report semantic acceptance**

Final response must separate:
- runtime-safe verification
- semantic improvements
- remaining album/era-level limitations
