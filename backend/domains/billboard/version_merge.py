"""Album version merge utilities for Billboard computation."""

from backend.core.db import get_db
from backend.domains.billboard.data_loader import _get_album_canonical_map


def _normalize_album_column(df, album_col="album_name", artist_col="artist_name", dedup_cols=None):
    """将 DataFrame 中的 album_name 替换为 canonical_name，可选去重。

    dedup_cols: 替换后按这些列去重（如 ["track_id", "album_name", "artist_name"]）。
    """
    mapping = _get_album_canonical_map()
    if mapping.empty:
        return df

    # 去重（同一 album 不应属于多个 group，但防御）
    mapping = mapping.drop_duplicates(subset=["album_name", "artist_name"])

    # 重命名右表列避免合并时后缀冲突
    mapping = mapping.rename(
        columns={
            "album_name": "_rg_album",
            "artist_name": "_rg_artist",
        }
    )
    df = df.merge(
        mapping, left_on=[album_col, artist_col], right_on=["_rg_album", "_rg_artist"], how="left"
    )
    mask = df["canonical_name"].notna()
    df.loc[mask, album_col] = df.loc[mask, "canonical_name"]
    df = df.drop(columns=["canonical_name", "_rg_album", "_rg_artist"], errors="ignore")
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols)
    return df


def _resolve_album_members(album_name, artist_name):
    """返回 release group 所有成员的 album_name 列表（含自身）。

    如果 album_name 不在任何 group 中，返回 [album_name]。
    同时返回 canonical_name。
    """
    conn = get_db()
    row = conn.execute(
        """SELECT rg.canonical_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE al.album_name = ? AND a.artist_name = ?
           LIMIT 1""",
        [album_name, artist_name],
    ).fetchone()

    if not row:
        conn.close()
        return [album_name], album_name

    canonical = row[0]
    members = conn.execute(
        """SELECT al.album_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE rg.canonical_name = ? AND a.artist_name = ?""",
        [canonical, artist_name],
    ).fetchall()
    conn.close()
    return [m[0] for m in members], canonical


def _apply_album_release_groups(df):
    """将 release_group 成员的 album_name 替换为 canonical_name 并重新聚合。

    多版本专辑（豪华版、Acoustic版等）的周播放量被合并到 canonical name 下，
    使榜单排名反映合并后的成绩。
    """
    mapping = _get_album_canonical_map()
    if mapping.empty:
        return df

    df = df.merge(mapping, on=["album_name", "artist_name"], how="left")
    mask = df["canonical_name"].notna()
    df.loc[mask, "album_name"] = df.loc[mask, "canonical_name"]
    df = df.drop(columns=["canonical_name"])

    agg_cols = {"play_count": "sum", "total_ms": "sum", "tracks_count": "sum"}
    if "album_id" in df.columns:
        agg_cols["album_id"] = "min"

    df = df.groupby(["billboard_week", "album_name", "artist_name"], as_index=False).agg(agg_cols)

    return df
