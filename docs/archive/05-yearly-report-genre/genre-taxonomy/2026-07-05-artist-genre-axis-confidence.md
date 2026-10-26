# Artist Genre Axis And Confidence Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** 让 genre 统计先按 `style / scene / context / role` 分轴展示，并把单艺人主导、低可信来源主导等风险传给 UI 和 AI 报告。

**Architecture:** 保留现有 artist-level genre resolution 和 taxonomy v2 canonical labels，不新增 album/era 数据层。本次只扩展 taxonomy audit 输出与消费者展示：后端负责计算 axis summary、risk flags、confidence/source tier；前端 Settings 负责按 axis 分组展示；AI/yearly caveat 负责避免把 scene/context/role 误说成 style 偏好。

**Tech Stack:** FastAPI + SQLite + Pydantic；React + TanStack Query + Vitest；pytest/ruff。

---

### Task 1: Extend Taxonomy Audit Contract

涉及文件：`backend/domains/metadata/artist_genres.py`、`backend/models/artist_genre_metadata.py`、`backend/tests/unit/test_artist_genre_resolution.py`、`backend/tests/contract/test_artist_genre_metadata_api.py`。

Add tests that assert:
- `compute_genre_taxonomy_audit()` returns `axis_summary` with grouped hours/share for `style`, `scene`, `context`, `role`.
- each top canonical row includes `interpretation` and `confidence_tier`.
- dominance-sensitive labels include `risk_flags` with `single_artist_dominance`.
- LLM-heavy labels include `risk_flags` with `source_confidence`.
- Implement minimal audit fields
- `source_confidence_tier(source_mix)` returns `high`, `medium`, or `low`.
- `interpretation_for_axis(axis)` returns concise Chinese copy for style/scene/context/role.
- `risk_flags_for_label(...)` returns structured risk flags, not only prose warnings.
- Update Pydantic models

Add model fields for:
- `axis_summary`
- canonical item `interpretation`
- canonical item `confidence_tier`
- canonical item `risk_flags`
- Verify backend tests

### Task 2: Render Axis-First Settings Audit

涉及文件：`frontend/src/types/artist-genre-metadata.ts`、`frontend/src/features/settings/components/GenreDataHealthSection.tsx`、`frontend/src/tests/genre-data-health-section.test.tsx`。

Assert Settings shows:
- axis sections named `风格`, `场景`, `语境`, `身份`
- `c-pop` under scene instead of mixed into the style list
- `singer-songwriter` under role
- dominance and source confidence risk text
- Implement grouped rendering

Group `taxonomy.top_canonical_genres` by axis in the component and render each axis as its own section with the axis interpretation. Keep the existing raw mapping audit below.

- Verify frontend tests

### Task 3: Update AI And Documentation Caveats

涉及文件：`backend/services/ai_insights_service.py`、`backend/domains/ai_reports/yearly_contract.py`、`backend/services/yearly_report_agent_service.py`、`docs/productization/2026-07-04-artist-genre-taxonomy.md`、`backend/tests/contract/test_artist_genre_consumers.py`、`backend/tests/unit/test_wrapped_genre_panorama.py`。

- Write or update tests for caveat copy

Assert AI/report payloads mention:
- statistical labels are axis-aware
- scene/context/role labels are not pure style preferences
- dominance-sensitive labels should be phrased as driven by top artists
- Update caveat strings

Use short Chinese caveats in user-facing payloads and concise English/Chinese contract language where existing files already use English.

- Verify consumer tests

### Task 4: Final Verification

- All modified files above
- Report semantic acceptance

Final response must separate:
- runtime-safe verification
- semantic improvements
- remaining album/era-level limitations
