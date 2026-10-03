"""Version artwork follows known local identities without inventing missing covers."""

from __future__ import annotations

import pytest
from PIL import Image

from backend.core.db import get_db
from backend.core.json_helpers import df_to_json
from backend.domains.billboard.details import (
    _attach_album_release_group,
    _attach_track_version_group,
    _enrich_source_breakdown,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("merge_level", [2, 3])
@pytest.mark.parametrize("provider_fallback", [None, "https://provider.test/cover.jpg"])
def test_track_version_local_artwork_precedes_provider_and_missing_stays_none(
    use_seed_db, tmp_path, legacy, merge_level, provider_fallback
):
    source = tmp_path / "covers" / "albums" / "902.jpg"
    source.parent.mkdir(parents=True)
    Image.new("RGB", (640, 640), "green").save(source)
    before = source.read_bytes(), source.stat().st_mtime_ns
    conn = get_db(readonly=False)
    try:
        if legacy:
            conn.execute("DROP TABLE IF EXISTS track_group_l1_members")
        conn.execute(
            "UPDATE albums SET image_path='covers/albums/902.jpg', image_url=NULL WHERE album_id=902"
        )
        conn.execute("UPDATE albums SET image_path=NULL, image_url=NULL WHERE album_id=903")
        conn.execute(
            "UPDATE spotify_album_meta SET image_url='https://provider.test/local-alternative.jpg' "
            "WHERE album_name=(SELECT album_name FROM albums WHERE album_id=902)"
        )
        conn.execute(
            "UPDATE spotify_album_meta SET image_url=? "
            "WHERE album_name=(SELECT album_name FROM albums WHERE album_id=903)",
            (provider_fallback,),
        )
        conn.commit()
        before_db = tuple(conn.iterdump())
        meta: dict = {}
        _attach_track_version_group(conn, 905, meta, merge_level)
        versions = {row["track_id"]: row for row in meta["version_group"]["versions"]}
        assert versions[905]["album_cover_url"] == "/covers/albums/902.jpg"
        assert versions[906]["album_cover_url"] == provider_fallback
        unmerged: dict = {}
        _attach_track_version_group(conn, 905, unmerged, 1)
        assert "version_group" not in unmerged
        assert tuple(conn.iterdump()) == before_db
    finally:
        conn.close()
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert not (tmp_path / "covers" / "thumbnails").exists()


@pytest.mark.parametrize("merge_level", [2, 3])
def test_album_release_and_source_rows_use_local_cover_and_do_not_fabricate_missing(
    use_seed_db, merge_level
):
    import pandas as pd

    conn = get_db(readonly=False)
    try:
        conn.execute(
            "UPDATE albums SET image_path='covers/albums/903.jpg', image_url=NULL WHERE album_id=903"
        )
        conn.execute("UPDATE albums SET image_path=NULL, image_url=NULL WHERE album_id=904")
        conn.execute(
            "UPDATE spotify_album_meta SET image_url='https://provider.test/903.jpg' "
            "WHERE album_name=(SELECT album_name FROM albums WHERE album_id=903)"
        )
        conn.execute(
            "UPDATE spotify_album_meta SET image_url=NULL "
            "WHERE album_name=(SELECT album_name FROM albums WHERE album_id=904)"
        )
        conn.commit()
        before_db = tuple(conn.iterdump())
        meta: dict = {}
        _attach_album_release_group(
            conn, "Fixture Release Album", "Fixture Artist Alpha", meta, merge_level
        )
        versions = {row["album_id"]: row for row in meta["release_group"]["versions"]}
        assert versions[903]["album_cover_url"] == "/covers/albums/903.jpg"
        assert versions[904]["album_cover_url"] is None
        source_rows = _enrich_source_breakdown(
            conn, pd.DataFrame([{"source_album_id": 903}, {"source_album_id": 904}])
        )
        assert source_rows.iloc[0]["album_cover_url"] == "/covers/albums/903.jpg"
        assert df_to_json(source_rows)[1]["album_cover_url"] is None
        unmerged: dict = {}
        _attach_album_release_group(
            conn, "Fixture Release Album", "Fixture Artist Alpha", unmerged, 1
        )
        assert "release_group" not in unmerged
        assert tuple(conn.iterdump()) == before_db
    finally:
        conn.close()
