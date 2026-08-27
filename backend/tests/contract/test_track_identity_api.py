from __future__ import annotations

import sqlite3


def test_canonical_identity_and_sources_are_explicit(client, use_seed_db: str) -> None:
    conn = sqlite3.connect(use_seed_db)
    try:
        row = conn.execute(
            """SELECT li.l1_id
                 FROM track_l1_identities li
                 JOIN track_l1_source_links links ON links.l1_id=li.l1_id
                GROUP BY li.l1_id
                ORDER BY COUNT(DISTINCT links.track_id) DESC, li.l1_id
                LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    l1_id = int(row[0])

    identity = client.get(f"/api/music/tracks/{l1_id}")
    assert identity.status_code == 200
    assert identity.json()["l1_id"] == l1_id
    assert identity.json()["source_record_count"] >= 1

    sources = client.get(f"/api/music/tracks/{l1_id}/sources")
    assert sources.status_code == 200
    assert sources.json()
    assert sum(bool(item["is_representative"]) for item in sources.json()) == 1
    assert all(item["evidence_types"] for item in sources.json())


def test_legacy_track_resolution_returns_the_same_track_id(client, use_seed_db: str) -> None:
    conn = sqlite3.connect(use_seed_db)
    try:
        artist_id = int(
            conn.execute("SELECT artist_id FROM artists ORDER BY artist_id LIMIT 1").fetchone()[0]
        )
        cursor = conn.execute(
            "INSERT INTO tracks(track_name, artist_id) VALUES ('Ambiguous legacy source', ?)",
            (artist_id,),
        )
        track_id = int(cursor.lastrowid)
        conn.execute(
            """INSERT INTO track_l1_identities(
                   l1_id, provider, fallback_track_id, representative_track_id
               ) VALUES (?, 'local', ?, ?)""",
            (track_id, track_id, track_id),
        )
        conn.execute(
            """INSERT INTO track_l1_source_links(
                   l1_id, track_id, evidence_type, observed_plays
               ) VALUES (?, ?, 'track_projection', 0)""",
            (track_id, track_id),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get(f"/api/music/tracks/legacy/{track_id}/identity")
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] == "unique"
    assert [item["l1_id"] for item in payload["items"]] == [track_id]


def test_public_canonical_merge_and_split_are_retired(client, use_seed_db: str) -> None:
    probe = sqlite3.connect(use_seed_db)
    try:
        before = probe.execute("SELECT COUNT(*) FROM track_identity_events").fetchone()[0]
    finally:
        probe.close()
    merged = client.post(
        "/api/version-merge/canonical-tracks/merge",
        json={
            "survivor_canonical_track_id": 1,
            "absorbed_canonical_track_ids": [2],
            "reason": "contract exact identity evidence",
        },
    )
    assert merged.status_code == 410

    split = client.post(
        "/api/version-merge/canonical-tracks/1/split",
        json={
            "provider": "spotify",
            "external_track_id": "contract-canonical-b",
            "reason": "contract correction evidence",
        },
    )
    assert split.status_code == 410

    conn = sqlite3.connect(use_seed_db)
    try:
        after = conn.execute("SELECT COUNT(*) FROM track_identity_events").fetchone()[0]
    finally:
        conn.close()
    assert after == before


def test_public_merge_level_rejects_l1(client) -> None:
    response = client.get("/api/analysis/overview?merge_level=1")
    assert response.status_code == 422
