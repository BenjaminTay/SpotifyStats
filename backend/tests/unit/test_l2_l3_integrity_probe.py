from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from backend.core.db import SCHEMA
from scripts.l2_l3_integrity_probe import (
    main,
    open_readonly_connection,
    run_probe,
)

PARAMETERS = {
    "min_ms": 30_000,
    "music_only": True,
    "merge_enabled": False,
    "dynamic_threshold": True,
    "max_merge_gap_minutes": 5,
    "include_compilations": False,
    "year_start": 2026,
    "year_end": 2026,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.executescript(
            """
            CREATE TABLE album_project_revision_state (
                state_id INTEGER PRIMARY KEY CHECK(state_id=1),
                current_revision INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO album_project_revision_state(state_id, current_revision)
            VALUES (1, 7);

            INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Probe Artist');
            INSERT INTO albums(album_id, album_name, artist_id) VALUES
                (1, 'Studio Album', 1),
                (2, 'Live Album', 1);
            INSERT INTO tracks(
                track_id, track_name, artist_id, album_id, spotify_track_id
            ) VALUES
                (1, 'Song', 1, 1, 'spotify-original'),
                (2, 'Song (Live)', 1, 2, 'spotify-live'),
                (3, 'Uncovered Song', 1, 2, 'spotify-uncovered');
            INSERT INTO track_artists(track_id, artist_id, role) VALUES
                (1, 1, 'primary'), (2, 1, 'primary'), (3, 1, 'primary');

            INSERT INTO track_l1_identities(
                l1_id, provider, external_track_id, fallback_track_id,
                representative_track_id
            ) VALUES
                (1, 'spotify', 'spotify-original', 1, 1),
                (2, 'spotify', 'spotify-live', 2, 2),
                (3, 'spotify', 'spotify-uncovered', 3, 3);
            INSERT INTO track_l1_external_ids(
                provider, external_track_id, l1_id, is_primary
            ) VALUES
                ('spotify', 'spotify-original', 1, 1),
                ('spotify', 'spotify-live', 2, 1),
                ('spotify', 'spotify-uncovered', 3, 1);
            INSERT INTO track_l1_source_links(
                l1_id, track_id, evidence_type, observed_plays
            ) VALUES
                (1, 1, 'track_projection', 1),
                (2, 2, 'track_projection', 1),
                (3, 3, 'track_projection', 1);
            UPDATE track_identity_state SET current_revision=11 WHERE state_id=1;

            INSERT INTO track_groups(
                group_id, canonical_name, primary_track_id, scope,
                is_manual, primary_l1_id, group_status
            ) VALUES
                (1, 'Song recordings', 1, 'recording', 1, 1, 'active'),
                (2, 'Song', 1, 'composition', 1, 1, 'active');
            UPDATE track_groups SET parent_group_id=2 WHERE group_id=1;
            INSERT INTO track_group_l1_members(group_id, l1_id) VALUES
                (1, 1), (1, 2),
                (2, 1), (2, 2);

            INSERT INTO album_projects(
                project_id, canonical_name, artist_id, primary_album_id,
                scope, project_type, include_in_charts, is_manual
            ) VALUES
                (1, 'Studio Album', 1, 1, 'release', 'album', 1, 1),
                (2, 'Live Album', 1, 2, 'release', 'album', 1, 1);
            INSERT INTO album_project_albums(project_id, album_id, role) VALUES
                (1, 1, 'primary'), (2, 2, 'primary');

            INSERT INTO l3_song_album_attributions(
                canonical_song_key, representative_track_id,
                canonical_artist_key, target_project_id,
                origin_release_project_id, attribution_kind,
                decision_source, confidence, policy_version,
                track_identity_revision, album_project_revision
            ) VALUES (
                'composition:2', 1, 'artist:1', 1, 1,
                'native_release', 'automatic', 1.0,
                'l3_native_album_attribution_v2', 11, 7
            );
            UPDATE l3_album_attribution_revision_state
               SET current_revision=5,
                   status='ready',
                   policy_version='l3_native_album_attribution_v2',
                   track_identity_revision=11,
                   album_project_revision=7,
                   attributed_count=1,
                   conflict_count=0,
                   uncovered_count=0
             WHERE state_id=1;

            INSERT INTO spotify_track_meta(
                spotify_track_id, track_name, duration_ms, spotify_album_id
            ) VALUES
                ('spotify-original', 'Song', 180000, 'album-studio'),
                ('spotify-live', 'Song (Live)', 240000, 'album-live'),
                ('spotify-uncovered', 'Uncovered Song', 180000, 'album-live');

            INSERT INTO plays(
                play_id, ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                ts_date, platform, ms_played, track_id, source_album_id,
                spotify_track_id_at_play
            ) VALUES
                (1, '2026-01-01T00:03:00Z', 2026, 1, 1, 3, 8,
                 '2026-01-01', 'test', 180000, 1, 1, 'spotify-original'),
                (2, '2026-01-02T00:04:00Z', 2026, 1, 1, 4, 8,
                 '2026-01-02', 'test', 240000, 2, 2, 'spotify-live'),
                (3, '2026-01-03T00:03:00Z', 2026, 1, 1, 5, 8,
                 '2026-01-03', 'test', 180000, 3, 2, 'spotify-uncovered');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_probe_is_readonly_and_reports_integrity(tmp_path: Path) -> None:
    db_path = tmp_path / "probe.db"
    _seed_database(db_path)
    before_hash = _sha256(db_path)

    report = run_probe(db_path, dict(PARAMETERS))

    assert _sha256(db_path) == before_hash
    assert report["parameters"] == PARAMETERS
    assert report["database_fingerprint"]["resolved_path"] == str(db_path.resolve())
    assert report["schema_and_revisions"]["track_identity_revision"] == 11
    assert report["schema_and_revisions"]["album_project_revision"] == 7

    l2 = report["l2_recording_groups"]
    assert l2["active_group_count"] == 1
    assert l2["distinct_member_count"] == 2
    assert l2["membership_count"] == 2
    assert l2["member_overlap_count"] == 0
    assert l2["recording_split_across_l3_count"] == 0

    l3 = report["l3_work_attribution"]
    assert l3["work_count"] == 2
    assert l3["attributed_work_count"] == 1
    assert l3["uncovered_work_count"] == 1
    assert l3["silent_uncovered_work_count"] == 1
    assert l3["play_bearing_silent_uncovered_count"] == 1
    assert l3["state_stale"] is False
    assert l3["multi_owner_work_count"] == 0
    assert l3["logical_event_conservation"] == {
        "logical_event_count": 3,
        "attributed_event_count": 2,
        "uncovered_event_count": 1,
        "excluded_compilation_event_count": 0,
        "policy_excluded_event_count": 0,
        "multi_owner_event_count": 0,
        "assignment_row_count": 2,
        "conservation_delta": 0,
    }
    assert report["l1_strong_conflicts"]["strong_conflict_count"] == 0
    assert report["status"] == "warning"


def test_probe_digest_is_repeatable_and_cli_writes_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "probe.db"
    output_path = tmp_path / "result" / "probe.json"
    _seed_database(db_path)

    first = run_probe(db_path, dict(PARAMETERS))
    second = run_probe(db_path, dict(PARAMETERS))

    assert first == second
    assert first["core_digest"] == second["core_digest"]
    exit_code = main(
        [
            "--db-path",
            str(db_path),
            "--merge-enabled",
            "false",
            "--year-start",
            "2026",
            "--year-end",
            "2026",
            "--json-output",
            str(output_path),
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == first
    assert written["core_digest"] == first["core_digest"]


def test_probe_detects_orphan_projection_and_policy_drift(tmp_path: Path) -> None:
    db_path = tmp_path / "probe.db"
    _seed_database(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO l3_song_album_attributions(
                   canonical_song_key, representative_track_id,
                   canonical_artist_key, target_project_id,
                   origin_release_project_id, attribution_kind,
                   decision_source, confidence, policy_version,
                   track_identity_revision, album_project_revision
               ) VALUES (?, 3, 'artist:1', 2, 2, 'live_residual',
                         'automatic', 1.0, ?, 11, 7)""",
            ("composition:999", "l3_native_album_attribution_v1"),
        )
        conn.execute(
            "UPDATE l3_album_attribution_revision_state SET attributed_count=2 WHERE state_id=1"
        )
        conn.commit()
    finally:
        conn.close()

    report = run_probe(db_path, dict(PARAMETERS))
    l3 = report["l3_work_attribution"]

    assert l3["orphan_attribution_work_count"] == 1
    assert l3["orphan_attribution_work_keys"] == ["composition:999"]
    assert l3["row_policy_versions"] == [
        "l3_native_album_attribution_v1",
        "l3_native_album_attribution_v2",
    ]
    assert l3["policy_stale"] is True
    assert l3["state_stale"] is True
    assert report["status"] == "fail"


def test_readonly_connection_rejects_writes_and_missing_path(tmp_path: Path) -> None:
    db_path = tmp_path / "probe.db"
    _seed_database(db_path)

    conn = open_readonly_connection(db_path)
    try:
        assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE forbidden_write(value INTEGER)")
    finally:
        conn.close()

    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        open_readonly_connection(missing)
    assert not missing.exists()
