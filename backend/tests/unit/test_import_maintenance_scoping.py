from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.services.import_maintenance_service import _auto_group_tracks_by_spotify_id

pytestmark = pytest.mark.unit


def test_same_spotify_id_never_creates_a_version_group() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            spotify_track_id TEXT
        );
        CREATE TABLE track_groups(group_id INTEGER PRIMARY KEY);
        INSERT INTO tracks VALUES
            (1, '同一曲目', 10, 'spotify-a'),
            (2, '同一曲目', 10, 'spotify-a');
        """
    )

    assert _auto_group_tracks_by_spotify_id(conn) == (0, 0)
    assert conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0] == 0


def test_retired_grouping_ignores_target_scopes() -> None:
    conn = sqlite3.connect(":memory:")
    assert _auto_group_tracks_by_spotify_id(
        conn,
        track_ids=frozenset({1, 2}),
        spotify_track_ids=frozenset({"spotify-a"}),
    ) == (0, 0)


def test_import_maintenance_blocks_on_played_l3_issue(monkeypatch) -> None:
    import backend.domains.metadata.track_identity as track_identity
    import backend.services.import_maintenance_service as maintenance

    conn = Mock()
    monkeypatch.setattr(maintenance, "get_db", lambda readonly=False: conn)
    monkeypatch.setattr(
        maintenance,
        "SpotifyProvider",
        lambda: SimpleNamespace(get_cc_token=lambda: "token"),
    )
    monkeypatch.setattr(
        maintenance,
        "refresh_missing_spotify_metadata",
        lambda *args, **kwargs: SimpleNamespace(
            local_album_ids_relinked=frozenset(),
            local_album_ids_updated=frozenset(),
            local_artist_ids_updated=frozenset(),
            spotify_album_ids_updated=frozenset(),
            spotify_track_ids_updated=frozenset(),
            provider_available=True,
            errors=(),
            impact_scope_exact=True,
        ),
    )
    monkeypatch.setattr(maintenance, "enqueue_missing_cover_downloads", lambda *a, **k: {})
    monkeypatch.setattr(
        track_identity,
        "synchronize_track_identity_projection",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(maintenance, "_auto_group_tracks_by_spotify_id", lambda *a, **k: (0, 0))
    monkeypatch.setattr(maintenance, "rebuild_album_projects_for_impact", lambda *a, **k: {})
    monkeypatch.setattr(maintenance, "plan_album_project_auto_merges", lambda *a, **k: ())
    monkeypatch.setattr(maintenance, "apply_album_project_auto_merge_plan", lambda *a, **k: {})
    monkeypatch.setattr(maintenance, "plan_album_composition_merges", lambda *a, **k: ())
    monkeypatch.setattr(maintenance, "apply_album_composition_plan", lambda *a, **k: {})
    observed: dict[str, bool] = {}

    def reconcile(_conn, *, include_unplayed):
        observed["include_unplayed"] = include_unplayed
        return SimpleNamespace(issues=(SimpleNamespace(issue_kind="uncovered"),))

    monkeypatch.setattr(maintenance, "reconcile_l3_album_attribution_dependencies", reconcile)

    with pytest.raises(
        RuntimeError,
        match="post-import L3 album attribution has unresolved issues: 1",
    ):
        maintenance.run_post_streaming_import_maintenance()

    assert observed == {"include_unplayed": False}
    conn.close.assert_called_once_with()
