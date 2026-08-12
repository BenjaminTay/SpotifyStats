"""发行版本合并 — 自动检测专辑版本家族并合并到主版本统计."""

import json
import re

import pandas as pd

from backend.core.db import get_db


def detect_collaboration_track_group_candidates() -> pd.DataFrame:
    """Find L3 collaboration/remix candidates that include the original primary artist."""
    conn = get_db()
    try:
        from backend.domains.metadata.track_credits import get_effective_track_credit_frame

        credits = get_effective_track_credit_frame(conn)
        tracks = pd.read_sql_query("SELECT track_id, track_name FROM tracks", conn)
        credited_tracks = credits.merge(tracks, on="track_id", how="inner")
        primary = credited_tracks[credited_tracks["role"] == "primary"].rename(
            columns={
                "track_id": "original_track_id",
                "track_name": "original_track_name",
                "artist_id": "primary_artist_id",
            }
        )
        candidates = credited_tracks.rename(
            columns={
                "track_id": "candidate_track_id",
                "track_name": "candidate_track_name",
                "artist_id": "primary_artist_id",
            }
        )
        merged = primary.merge(candidates, on="primary_artist_id", how="inner")
        merged = merged[merged["original_track_id"] != merged["candidate_track_id"]]
        original = merged["original_track_name"].str.casefold()
        simplified = original.str.replace(" - ", " ", regex=False)
        candidate = merged["candidate_track_name"].str.casefold()
        mask = [
            source in target or simple in target
            for source, simple, target in zip(original, simplified, candidate)
        ]
        return (
            merged.loc[
                mask,
                [
                    "original_track_id",
                    "original_track_name",
                    "candidate_track_id",
                    "candidate_track_name",
                    "primary_artist_id",
                ],
            ]
            .drop_duplicates()
            .sort_values(["original_track_name", "candidate_track_name"])
            .reset_index(drop=True)
        )
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Suffix patterns
# ═══════════════════════════════════════════════════════════════════════════

# 应被剥离的版本后缀（同一发行，不同包装）
MERGE_KEYWORDS = [
    "deluxe",
    "deluxe edition",
    "deluxe version",
    "expanded edition",
    "expanded",
    "bonus track version",
    "bonus edition",
    "bonus tracks",
    "special edition",
    "special version",
    "track by track",
    "track by track version",
    "commentary",
    "commentary version",
    "acoustic",
    "acoustic collection",
    "acoustic version",
    "remastered",
    "remastered edition",
    "anniversary",
    "anniversary edition",
    "sessions",
    "studio sessions",
    "radio release",
    "radio release special",
    "collector",
    "collector's edition",
    "collectors edition",
    "limited",
    "limited edition",
    "extended",
    "extended version",
    "clean",
    "clean version",
    "explicit",
    "explicit version",
]

# 不应被剥离的关键词（不同录音/表演）
EXCLUDE_KEYWORDS = [
    "taylor's version",
    "live",
    "live version",
    "live at",
    "remix",
    "remix version",
    "radio edit",
    "radio mix",
    "demo",
    "demo version",
    "instrumental",
    "instrumental version",
    "orchestral",
    "orchestral version",
    "a cappella",
    "acapella",
]


def _is_merge_suffix(suffix: str) -> bool:
    """检查后缀文本是否表示可合并的版本变体。"""
    s = suffix.lower().strip().rstrip(")").rstrip("]").strip()

    # 先检查排除关键词（优先级更高）
    for ex in EXCLUDE_KEYWORDS:
        if ex in s:
            return False

    # 检查是否精确匹配或以合并关键词开头
    for kw in MERGE_KEYWORDS:
        if s == kw or s.startswith(kw):
            return True

    # 包含 "edition" 或 "version"（非 excluded）→ 通常是命名版本变体
    # 如 "3am edition"、"the til dawn edition"、"clean version"
    if "edition" in s or "version" in s:
        return True

    # 包含合并关键词作为独立子串（如 "anniversary"）
    for kw in MERGE_KEYWORDS:
        if kw in s:
            return True

    return False


def normalize_album_name(name: str) -> str:
    """剥离版本后缀，返回 base name。

    例如：
      "The Life of a Showgirl (Deluxe Edition)" → "The Life of a Showgirl"
      "RED (Taylor's Version)" → "RED (Taylor's Version)"  （不剥离）
    """
    if not name:
        return name

    name = name.strip()

    patterns = [
        r"\s*\(([^)]+)\)\s*$",  # (Something) 结尾
        r"\s*\[([^\]]+)\]\s*$",  # [Something] 结尾
        r"\s*[-–:+]\s*(.+)\s*$",  # -/–/: Something 结尾
    ]

    changed = True
    while changed:
        changed = False
        for pat in patterns:
            m = re.search(pat, name)
            if m:
                suffix = m.group(1).strip()
                if _is_merge_suffix(suffix):
                    name = name[: m.start()].strip()
                    changed = True
                    break

        # 检查空格分隔的后缀（如 "Fearless Platinum Edition"）
        if not changed:
            words = name.split()
            for n in [3, 2, 1]:
                if len(words) <= n:
                    continue
                candidate = " ".join(words[-n:])
                # 跳过被 split() 破坏的括号/方括号内容（如 "Version)"）
                if candidate.count("(") != candidate.count(")") or candidate.count(
                    "["
                ) != candidate.count("]"):
                    continue
                if _is_merge_suffix(candidate):
                    name = " ".join(words[:-n])
                    changed = True
                    break

    return name


def normalize_track_name(name: str) -> str:
    """剥离歌曲版本后缀，返回 base name。

    例如：
      "Style" → "Style"
      "Style (Taylor's Version)" → "Style (Taylor's Version)"  （不剥离）
      "Song - Remix" → "Song - Remix"  （不剥离）
      "Song - Acoustic Version" → "Song"  （剥离，同一首歌的原声版）
    """
    if not name:
        return name

    name = name.strip()

    patterns = [
        r"\s*\(([^)]+)\)\s*$",
        r"\s*\[([^\]]+)\]\s*$",
        r"\s*[-–:]\s*(.+)\s*$",
    ]

    changed = True
    while changed:
        changed = False
        for pat in patterns:
            m = re.search(pat, name)
            if m:
                suffix = m.group(1).strip()
                if _is_merge_suffix(suffix):
                    name = name[: m.start()].strip()
                    changed = True
                    break

    return name


def _suffix_is_excluded(suffix: str) -> bool:
    """检查后缀是否包含排除关键词（如 Taylor's Version、Remix 等）。"""
    s = suffix.lower().strip().rstrip(")").rstrip("]").strip()
    for ex in EXCLUDE_KEYWORDS:
        if ex in s:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
# Group CRUD
# ═══════════════════════════════════════════════════════════════════════════


def _refresh_version_merge_dependents(conn=None) -> None:
    """Rebuild album projects and clear cached statistics after relation changes."""
    from backend.core.cache_manager import invalidate
    from backend.domains.playback.album_projects import rebuild_album_projects

    owns_conn = conn is None
    if owns_conn:
        conn = get_db(readonly=False)
    try:
        rebuild_album_projects(conn)
    finally:
        if owns_conn:
            conn.close()
    invalidate("analysis")
    invalidate("billboard")
    invalidate("yearly_review")


def get_all_groups() -> pd.DataFrame:
    """获取所有已保存的 release group（含成员详情）。"""
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT rg.group_id, rg.canonical_name, a.artist_name,
                  rg.primary_album_id, pa.album_name AS primary_album_name,
                  rg.scope, rg.is_manual, rg.created_at
           FROM release_groups rg
           JOIN artists a ON rg.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
           ORDER BY a.artist_name, rg.canonical_name""",
        conn,
    )
    conn.close()
    return df


def get_group_members(group_id: int) -> pd.DataFrame:
    """获取某个 group 的所有成员专辑。"""
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT al.album_id, al.album_name
           FROM release_group_members rgm
           JOIN albums al ON rgm.album_id = al.album_id
           WHERE rgm.group_id = ?""",
        conn,
        params=[group_id],
    )
    conn.close()
    return df


def get_album_group_mapping() -> dict:
    """返回 {album_id: canonical_name} 映射，供 Billboard 排名使用。"""
    conn = get_db()
    rows = conn.execute(
        """SELECT rgm.album_id, rg.canonical_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id"""
    ).fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_primary_release_date(canonical_name: str, artist_name: str):
    """获取一个 canonical group 的主版本发行日期。"""
    conn = get_db()
    row = conn.execute(
        """SELECT rg.primary_album_id
           FROM release_groups rg
           JOIN artists a ON rg.artist_id = a.artist_id
           WHERE rg.canonical_name = ? AND a.artist_name = ?""",
        [canonical_name, artist_name],
    ).fetchone()
    if not row or row[0] is None:
        conn.close()
        return None

    primary_id = row[0]
    date_row = conn.execute(
        """SELECT MIN(sam.release_date)
           FROM albums al
           JOIN track_albums ta ON ta.album_id = al.album_id
           JOIN tracks t ON t.track_id = ta.track_id
           JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
           WHERE al.album_id = ?""",
        [primary_id],
    ).fetchone()
    conn.close()
    return date_row[0] if date_row else None


def create_group(
    canonical_name: str,
    artist_id: int,
    primary_album_id: int,
    member_ids: list[int],
    scope: str = "release",
):
    """手动创建 release group。返回 group_id，失败返回 None。"""
    if scope not in {"release", "composition"}:
        return None
    conn = get_db(readonly=False)
    try:
        if artist_id <= 0:
            row = conn.execute(
                "SELECT artist_id FROM albums WHERE album_id = ?",
                (primary_album_id,),
            ).fetchone()
            if row is None:
                return None
            artist_id = int(row["artist_id"])

        cur = conn.execute(
            """INSERT OR IGNORE INTO release_groups
               (canonical_name, artist_id, primary_album_id, scope, is_manual)
               VALUES (?, ?, ?, ?, 1)""",
            (canonical_name, artist_id, primary_album_id, scope),
        )
        conn.commit()
        group_id = cur.lastrowid

        if group_id == 0:
            # 已存在，查出现有 group_id
            row = conn.execute(
                """SELECT group_id FROM release_groups
                   WHERE canonical_name = ? AND artist_id = ? AND scope = ?""",
                (canonical_name, artist_id, scope),
            ).fetchone()
            group_id = row[0] if row else None

        if group_id:
            for aid in member_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO release_group_members(group_id, album_id) VALUES (?, ?)",
                    (group_id, aid),
                )
            conn.commit()
            _refresh_version_merge_dependents(conn)

        return group_id
    except Exception:
        return None
    finally:
        conn.close()


def confirm_track_group_candidate(
    original_track_id: int,
    candidate_track_id: int,
    scope: str = "composition",
) -> dict:
    """Confirm a track candidate by writing it into a track group.

    Composition is the default so accepted feat/remix/acoustic/rerecord
    candidates only affect L3 aggregation.
    """
    if scope not in {"recording", "composition"}:
        return {"status": "error", "message": "Invalid scope"}
    if original_track_id == candidate_track_id:
        return {"status": "error", "message": "Tracks must differ"}

    conn = get_db(readonly=False)
    try:
        original = conn.execute(
            "SELECT track_id, track_name FROM tracks WHERE track_id = ?",
            (original_track_id,),
        ).fetchone()
        candidate = conn.execute(
            "SELECT track_id FROM tracks WHERE track_id = ?",
            (candidate_track_id,),
        ).fetchone()
        if original is None or candidate is None:
            return {"status": "error", "message": "Track not found"}

        group = conn.execute(
            """SELECT tg.group_id
               FROM track_groups tg
               JOIN track_group_members tgm ON tgm.group_id = tg.group_id
               WHERE tgm.track_id = ? AND tg.scope = ?
               ORDER BY tg.is_manual DESC, tg.group_id
               LIMIT 1""",
            (original_track_id, scope),
        ).fetchone()
        group_id = int(group["group_id"]) if group is not None else None

        if group_id is None:
            cur = conn.execute(
                """INSERT OR IGNORE INTO track_groups
                   (canonical_name, primary_track_id, scope, is_manual)
                   VALUES (?, ?, ?, 1)""",
                (original["track_name"], original_track_id, scope),
            )
            group_id = int(cur.lastrowid)
            if group_id == 0:
                row = conn.execute(
                    """SELECT group_id FROM track_groups
                       WHERE canonical_name = ? AND scope = ?""",
                    (original["track_name"], scope),
                ).fetchone()
                group_id = int(row["group_id"]) if row is not None else None

        if group_id is None:
            return {"status": "error", "message": "Failed to create track group"}

        for track_id in (original_track_id, candidate_track_id):
            conn.execute(
                "INSERT OR IGNORE INTO track_group_members(group_id, track_id) VALUES (?, ?)",
                (group_id, track_id),
            )
        conn.commit()
        _refresh_version_merge_dependents(conn)

        member_count = conn.execute(
            "SELECT COUNT(*) FROM track_group_members WHERE group_id = ?",
            (group_id,),
        ).fetchone()[0]
        return {
            "status": "ok",
            "group_id": group_id,
            "scope": scope,
            "member_count": int(member_count),
            "album_projects_rebuilt": True,
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
    finally:
        conn.close()


_RELATION_TRACK_VERSION_PATTERNS = (
    r"\([^)]*(?:taylor'?s version|rerecorded|re-recorded|re recorded|from the vault)[^)]*\)",
    r"\[[^\]]*(?:taylor'?s version|rerecorded|re-recorded|re recorded|from the vault)[^\]]*\]",
)

_RELATION_TRACK_VERSION_PHRASES = (
    "taylor's version",
    "taylors version",
    "rerecorded",
    "re-recorded",
    "re recorded",
    "from the vault",
)


def _normalize_relation_track_name(name: str) -> str:
    text = (name or "").lower().replace("’", "'").replace("‘", "'")
    for pattern in _RELATION_TRACK_VERSION_PATTERNS:
        text = re.sub(pattern, " ", text)
    for phrase in _RELATION_TRACK_VERSION_PHRASES:
        text = text.replace(phrase, " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tracks_for_relation_album(conn, album_id: int) -> list[dict]:
    rows = conn.execute(
        """SELECT DISTINCT t.track_id, t.track_name
           FROM (
               SELECT track_id FROM tracks WHERE album_id = ?
               UNION
               SELECT track_id FROM track_albums WHERE album_id = ?
           ) album_tracks
           JOIN tracks t ON t.track_id = album_tracks.track_id
           ORDER BY t.track_id""",
        (album_id, album_id),
    ).fetchall()
    return [{"track_id": int(row["track_id"]), "track_name": row["track_name"]} for row in rows]


def derive_album_relation_track_pairs(
    primary_album_id: int,
    member_album_ids: list[int],
) -> dict:
    """Derive same-composition track pairs from an album-level relation."""
    conn = get_db()
    try:
        primary_tracks = _tracks_for_relation_album(conn, primary_album_id)
        primary_by_key = {}
        for track in primary_tracks:
            key = _normalize_relation_track_name(track["track_name"])
            if key and key not in primary_by_key:
                primary_by_key[key] = track

        pairs = []
        exclusive_tracks = []
        for album_id in member_album_ids:
            for candidate in _tracks_for_relation_album(conn, album_id):
                key = _normalize_relation_track_name(candidate["track_name"])
                original = primary_by_key.get(key)
                if original and original["track_id"] != candidate["track_id"]:
                    pairs.append(
                        {
                            "original_track_id": original["track_id"],
                            "original_track_name": original["track_name"],
                            "candidate_track_id": candidate["track_id"],
                            "candidate_track_name": candidate["track_name"],
                            "candidate_album_id": album_id,
                        }
                    )
                else:
                    exclusive_tracks.append(
                        {
                            "track_id": candidate["track_id"],
                            "track_name": candidate["track_name"],
                            "source_album_id": album_id,
                        }
                    )

        deduped_pairs = []
        seen_pairs = set()
        for pair in pairs:
            pair_key = (pair["original_track_id"], pair["candidate_track_id"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            deduped_pairs.append(pair)

        deduped_exclusive = []
        seen_exclusive = set()
        for track in exclusive_tracks:
            if track["track_id"] in seen_exclusive:
                continue
            seen_exclusive.add(track["track_id"])
            deduped_exclusive.append(track)

        return {"track_pairs": deduped_pairs, "exclusive_tracks": deduped_exclusive}
    finally:
        conn.close()


def _expand_album_relation_member_ids(album_ids: list[int]) -> list[int]:
    conn = get_db()
    try:
        expanded = list(dict.fromkeys(int(album_id) for album_id in album_ids))
        if not expanded:
            return []
        placeholders = ",".join("?" for _ in expanded)
        rows = conn.execute(
            f"""SELECT DISTINCT rgm_member.album_id
                FROM release_group_members rgm_seed
                JOIN release_groups rg
                  ON rg.group_id = rgm_seed.group_id
                 AND rg.scope = 'release'
                JOIN release_group_members rgm_member
                  ON rgm_member.group_id = rg.group_id
               WHERE rgm_seed.album_id IN ({placeholders})
               ORDER BY rgm_member.album_id""",
            tuple(expanded),
        ).fetchall()
        for row in rows:
            album_id = int(row["album_id"])
            if album_id not in expanded:
                expanded.append(album_id)
        return expanded
    finally:
        conn.close()


def _attach_release_groups_to_composition_parent(
    composition_group_id: int,
    album_ids: list[int],
) -> None:
    if not album_ids:
        return
    conn = get_db(readonly=False)
    try:
        placeholders = ",".join("?" for _ in album_ids)
        conn.execute(
            f"""UPDATE release_groups
                   SET parent_group_id = ?
                 WHERE scope = 'release'
                   AND group_id IN (
                       SELECT DISTINCT group_id
                         FROM release_group_members
                        WHERE album_id IN ({placeholders})
                   )""",
            (composition_group_id, *album_ids),
        )
        conn.commit()
    finally:
        conn.close()


def confirm_album_relation_bundle(
    canonical_name: str,
    primary_album_id: int,
    member_album_ids: list[int],
    scope: str = "composition",
    relation_type: str = "rerecord",
    confirm_track_pairs: bool = True,
) -> dict:
    """Confirm an album relation and optionally materialize matching track relations."""
    if scope not in {"release", "composition"}:
        return {"status": "error", "message": "Invalid scope"}

    seed_member_ids = []
    for album_id in [primary_album_id] + list(member_album_ids or []):
        album_id = int(album_id)
        if album_id not in seed_member_ids:
            seed_member_ids.append(album_id)
    if len(seed_member_ids) < 2:
        return {"status": "error", "message": "At least two albums are required"}
    member_ids = _expand_album_relation_member_ids(seed_member_ids)

    conn = get_db()
    try:
        primary = conn.execute(
            "SELECT album_id, album_name, artist_id FROM albums WHERE album_id = ?",
            (primary_album_id,),
        ).fetchone()
        if primary is None:
            return {"status": "error", "message": "Primary album not found"}
        artist_id = int(primary["artist_id"])
    finally:
        conn.close()

    group_id = create_group(
        canonical_name=canonical_name or primary["album_name"],
        artist_id=artist_id,
        primary_album_id=primary_album_id,
        member_ids=member_ids,
        scope=scope,
    )
    if group_id is None:
        return {"status": "error", "message": "Failed to create album relation"}
    if scope == "composition":
        _attach_release_groups_to_composition_parent(group_id, member_ids)

    derived = derive_album_relation_track_pairs(
        primary_album_id=primary_album_id,
        member_album_ids=[album_id for album_id in seed_member_ids if album_id != primary_album_id],
    )
    track_scope = "composition" if scope == "composition" else "recording"
    confirmed_count = 0
    if confirm_track_pairs:
        for pair in derived["track_pairs"]:
            result = confirm_track_group_candidate(
                original_track_id=pair["original_track_id"],
                candidate_track_id=pair["candidate_track_id"],
                scope=track_scope,
            )
            if result.get("status") == "ok":
                confirmed_count += 1

    _refresh_version_merge_dependents()
    return {
        "status": "ok",
        "release_group_id": group_id,
        "scope": scope,
        "relation_type": relation_type,
        "candidate_track_pair_count": len(derived["track_pairs"]),
        "confirmed_track_pair_count": confirmed_count,
        "exclusive_track_count": len(derived["exclusive_tracks"]),
        "track_pairs": derived["track_pairs"],
        "exclusive_tracks": derived["exclusive_tracks"],
        "album_projects_rebuilt": True,
    }


def update_group_members(group_id: int, add_ids=None, remove_ids=None) -> bool:
    """增删 group 成员。"""
    conn = get_db(readonly=False)
    try:
        if add_ids:
            for aid in add_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO release_group_members(group_id, album_id) VALUES (?, ?)",
                    (group_id, aid),
                )
        if remove_ids:
            for aid in remove_ids:
                conn.execute(
                    "DELETE FROM release_group_members WHERE group_id = ? AND album_id = ?",
                    (group_id, aid),
                )
        conn.commit()
        _refresh_version_merge_dependents(conn)
        return True
    except Exception:
        return False
    finally:
        conn.close()


def set_primary(group_id: int, album_id: int) -> bool:
    """更改 group 的主版本。"""
    conn = get_db(readonly=False)
    try:
        conn.execute(
            "UPDATE release_groups SET primary_album_id = ? WHERE group_id = ?",
            (album_id, group_id),
        )
        conn.commit()
        _refresh_version_merge_dependents(conn)
        return True
    except Exception:
        return False
    finally:
        conn.close()


def delete_group(group_id: int) -> bool:
    """删除 release group 及其所有成员关系。"""
    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM release_group_members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM release_groups WHERE group_id = ?", (group_id,))
        conn.commit()
        _refresh_version_merge_dependents(conn)
        return True
    except Exception:
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Auto-detection
# ═══════════════════════════════════════════════════════════════════════════


def _compute_track_overlap(conn, album_id1: int, album_id2: int) -> float:
    """计算两张专辑的曲目重叠率（通过 track_albums）。"""
    shared = conn.execute(
        """SELECT COUNT(DISTINCT ta1.track_id) AS shared
           FROM track_albums ta1
           JOIN track_albums ta2 ON ta1.track_id = ta2.track_id
           WHERE ta1.album_id = ? AND ta2.album_id = ?""",
        (album_id1, album_id2),
    ).fetchone()[0]

    count1 = conn.execute(
        "SELECT COUNT(DISTINCT track_id) FROM track_albums WHERE album_id = ?",
        (album_id1,),
    ).fetchone()[0]
    count2 = conn.execute(
        "SELECT COUNT(DISTINCT track_id) FROM track_albums WHERE album_id = ?",
        (album_id2,),
    ).fetchone()[0]

    if count1 == 0 or count2 == 0:
        return 0.0

    return shared / min(count1, count2)


def _get_album_spotify_tracks(conn, album_id: int) -> set:
    """获取某张本地专辑对应的完整 Spotify 曲目 ID 集合。

    优先从 spotify_album_meta.track_list 缓存读取，缓存缺失时通过 API 补全。
    """
    import json

    # 查找该本地 album_id 对应的 Spotify album ID
    sid_rows = conn.execute(
        """SELECT DISTINCT sam.spotify_album_id
           FROM track_albums ta
           JOIN tracks t ON t.track_id = ta.track_id
           JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
           WHERE ta.album_id = ?""",
        (album_id,),
    ).fetchall()

    spotify_ids = [r[0] for r in sid_rows]
    if not spotify_ids:
        return set()

    # 查缓存
    placeholders = ",".join("?" for _ in spotify_ids)
    cached = {}
    rows = conn.execute(
        f"""SELECT spotify_album_id, track_list
            FROM spotify_album_meta
            WHERE spotify_album_id IN ({placeholders})
              AND track_list IS NOT NULL""",
        spotify_ids,
    ).fetchall()
    for sid, tl in rows:
        try:
            cached[sid] = set(json.loads(tl))
        except (json.JSONDecodeError, TypeError):
            pass

    # 检查已缓存的专辑是否需要重新获取（缺曲目名或缺艺人名）
    def _needs_refetch(sid, tracks):
        if not tracks:
            return False
        aa = conn.execute(
            "SELECT album_artists FROM spotify_album_meta WHERE spotify_album_id = ?",
            (sid,),
        ).fetchone()
        if not aa or not aa[0]:
            return True
        placeholders = ",".join("?" for _ in tracks)
        named = conn.execute(
            f"""SELECT COUNT(*) FROM spotify_track_meta
                WHERE spotify_track_id IN ({placeholders})
                  AND track_name IS NOT NULL AND track_name != ''""",
            list(tracks),
        ).fetchone()[0]
        return named < len(tracks) * 0.5

    missing = [sid for sid in spotify_ids if sid not in cached]
    needs_metadata = []
    if not missing:
        for sid in spotify_ids:
            if _needs_refetch(sid, cached.get(sid, set())):
                needs_metadata.append(sid)

    refetch_ids = missing + needs_metadata
    if refetch_ids:
        fetched = _fetch_album_tracks_from_api(refetch_ids)
        wconn = get_db(readonly=False)
        for sid, tracks in fetched.items():
            if tracks:
                tl_json = json.dumps(tracks, ensure_ascii=False)
                wconn.execute(
                    """UPDATE spotify_album_meta
                       SET track_list = ?, total_tracks = ?
                       WHERE spotify_album_id = ?""",
                    (tl_json, len(tracks), sid),
                )
                cached[sid] = set(tracks)
        wconn.commit()
        wconn.close()

    # 合并所有关联 Spotify 专辑的曲目，转换为归一化曲目名
    all_ids = set()
    for sid in spotify_ids:
        all_ids |= cached.get(sid, set())

    id_to_name = {}
    if all_ids:
        placeholders = ",".join("?" for _ in all_ids)
        name_rows = conn.execute(
            f"""SELECT spotify_track_id, track_name
                FROM spotify_track_meta
                WHERE spotify_track_id IN ({placeholders})
                  AND track_name IS NOT NULL AND track_name != ''""",
            list(all_ids),
        ).fetchall()
        for tid, tname in name_rows:
            id_to_name[tid] = normalize_track_name(tname.strip().lower())

    result = set()
    for tid in all_ids:
        name = id_to_name.get(tid)
        if name:
            result.add(name)
    return result


def _lookup_track_names(conn, spotify_track_ids: set) -> dict:
    """批量查询 Spotify track ID → (track_name, artist_name, disc_number, track_number)。"""
    if not spotify_track_ids:
        return {}
    placeholders = ",".join("?" for _ in spotify_track_ids)
    rows = conn.execute(
        f"""SELECT stm.spotify_track_id, stm.track_name, sam.album_artists,
                   stm.disc_number, stm.track_number
            FROM spotify_track_meta stm
            JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
            WHERE stm.spotify_track_id IN ({placeholders})""",
        list(spotify_track_ids),
    ).fetchall()
    return {r[0]: (r[1], r[2] or "", r[3], r[4]) for r in rows}


def get_album_track_comparison(album_id_a: int, album_id_b: int) -> dict:
    """对比两张专辑的完整曲目异同（基于 Spotify API 全量数据 + 曲目名匹配）。

    因为同一首歌在不同版本专辑中 Spotify track ID 不同，
    比较统一使用归一化曲目名（lower + 剥离版本后缀）。

    曲目顺序保留 Spotify 专辑原始曲目排列，去重时取首次出现位置。

    Returns:
        {"shared": [(track_name, artist_name, disc_number, track_number), ...],
         "only_in_a": [(track_name, artist_name, disc_number, track_number), ...],
         "only_in_b": [(track_name, artist_name, disc_number, track_number), ...]}
        disc_number/track_number 为 Spotify API 真实曲目号，缺失时为 None。
    """
    import json

    conn = get_db()

    def _get_ordered_tracks(aid):
        """获取本地专辑的曲目列表，按 Spotify track_number / disc_number 排序。

        若缓存的 track_number 大面积缺失（旧数据），自动触发 API 补全。
        Returns [(track_name, artist_name, disc_number, track_number), ...]
        """
        sid_rows = conn.execute(
            """SELECT DISTINCT sam.spotify_album_id
               FROM track_albums ta
               JOIN tracks t ON t.track_id = ta.track_id
               JOIN spotify_track_meta stm
                 ON t.spotify_track_id = stm.spotify_track_id
               JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
               WHERE ta.album_id = ?""",
            (aid,),
        ).fetchall()
        spotify_ids = [r[0] for r in sid_rows]
        if not spotify_ids:
            return []

        # 读取缓存 track_list
        placeholders = ",".join("?" for _ in spotify_ids)
        rows = conn.execute(
            f"""SELECT spotify_album_id, track_list
                FROM spotify_album_meta
                WHERE spotify_album_id IN ({placeholders})
                  AND track_list IS NOT NULL""",
            spotify_ids,
        ).fetchall()

        sid_to_tracks = {}
        all_track_ids = set()
        for sid, tl in rows:
            try:
                tracks = json.loads(tl)
                sid_to_tracks[sid] = tracks
                all_track_ids.update(tracks)
            except (json.JSONDecodeError, TypeError):
                pass

        if not all_track_ids:
            return []

        id_to_name = _lookup_track_names(conn, all_track_ids)

        # 自愈：若大部分曲目缺 track_number，从 API 重新获取
        named_count = sum(1 for v in id_to_name.values() if v[3] is not None)
        if named_count < len(id_to_name) * 0.7 and len(id_to_name) >= 4:
            refetched = _fetch_album_tracks_from_api(spotify_ids)
            if refetched:
                # 用 API 返回的正确顺序更新 sid_to_tracks + 持久化
                wconn = get_db(readonly=False)
                for sid, tracks in refetched.items():
                    if tracks:
                        sid_to_tracks[sid] = tracks
                        wconn.execute(
                            """UPDATE spotify_album_meta
                               SET track_list = ?, total_tracks = ?
                               WHERE spotify_album_id = ?""",
                            (json.dumps(tracks, ensure_ascii=False), len(tracks), sid),
                        )
                wconn.commit()
                wconn.close()
                # 重新查询 track_number（API 已写入 spotify_track_meta）
                all_ids = set()
                for tracks in sid_to_tracks.values():
                    all_ids.update(tracks)
                id_to_name = _lookup_track_names(get_db(), all_ids)

        # 按 (disc_number, track_number) 排序，缺失回退数组索引
        seen_norms = set()
        raw_items = []
        for sid in spotify_ids:
            tracks = sid_to_tracks.get(sid, [])
            for array_pos, tid in enumerate(tracks):
                if tid not in id_to_name:
                    continue
                tname, tartist, disc_num, track_num = id_to_name[tid]
                norm = normalize_track_name(tname.strip().lower())
                if norm not in seen_norms:
                    seen_norms.add(norm)
                    d = disc_num if disc_num is not None else 1
                    t = track_num if track_num is not None else array_pos + 1
                    raw_items.append(((d, t), tname, tartist, d, t))

        raw_items.sort(key=lambda x: x[0])
        return [
            (tname, tartist, disc_num, track_num)
            for _, tname, tartist, disc_num, track_num in raw_items
        ]

    ordered_a = _get_ordered_tracks(album_id_a)
    ordered_b = _get_ordered_tracks(album_id_b)

    # 构建归一化名 → (原名, 艺人, disc_number, track_number) 映射
    def _build_norm_map(ordered_tracks):
        norm_map = {}
        for tname, tartist, disc_num, track_num in ordered_tracks:
            norm = normalize_track_name(tname.strip().lower())
            if norm not in norm_map:
                norm_map[norm] = (tname, tartist, disc_num, track_num)
        return norm_map

    norm_a = _build_norm_map(ordered_a)
    norm_b = _build_norm_map(ordered_b)

    # 按归一化名比较
    shared_names = set(norm_a.keys()) & set(norm_b.keys())
    only_a_names = set(norm_a.keys()) - set(norm_b.keys())
    only_b_names = set(norm_b.keys()) - set(norm_a.keys())

    conn.close()

    def _pairs(norm_set, norm_map):
        result = [
            (tname, tartist, disc_num, track_num)
            for n, (tname, tartist, disc_num, track_num) in norm_map.items()
            if n in norm_set
        ]
        result.sort(key=lambda x: (x[2] or 1, x[3] or 0))
        return result

    return {
        "shared": _pairs(shared_names, norm_a),  # 用 album_a 的名称显示，按 A 顺序
        "only_in_a": _pairs(only_a_names, norm_a),  # 按 A 顺序
        "only_in_b": _pairs(only_b_names, norm_b),  # 按 B 顺序
    }


def _get_release_date(conn, album_id: int):
    """获取专辑的发行日期（通过 Spotify 元数据链）。"""
    row = conn.execute(
        """SELECT MIN(sam.release_date)
           FROM track_albums ta
           JOIN tracks t ON t.track_id = ta.track_id
           JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
           WHERE ta.album_id = ?""",
        (album_id,),
    ).fetchone()
    return row[0] if row else None


def _build_album_track_sets(conn, albums_df):
    """构建 {album_id: set(spotify_track_id)} 映射，优先用缓存的 track_list。

    对于 track_list 为空的专辑，通过 Spotify API 批量补全并持久化。
    比较使用 Spotify track ID（字符串），不依赖本地 track_id，
    确保检测基于真实专辑曲目而非用户播放记录。
    """
    import json

    # 收集 spotify_album_id → album_id 映射
    spotify_ids = set()
    album_spotify_map = {}  # album_id → spotify_album_id
    for _, row in albums_df.iterrows():
        aid = int(row["album_id"])
        if aid in album_spotify_map:
            continue
        # 通过 track_albums → tracks → spotify_track_meta → spotify_album_meta 链获取
        sam_rows = conn.execute(
            """SELECT DISTINCT sam.spotify_album_id
               FROM track_albums ta
               JOIN tracks t ON t.track_id = ta.track_id
               JOIN spotify_track_meta stm
                 ON t.spotify_track_id = stm.spotify_track_id
               JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
               WHERE ta.album_id = ?""",
            (aid,),
        ).fetchall()
        for r in sam_rows:
            sid = r[0]
            album_spotify_map[aid] = sid
            spotify_ids.add(sid)
            break  # 取第一个

    # 查询已有的 track_list
    placeholders = ",".join("?" for _ in spotify_ids) if spotify_ids else "''"
    cached = {}
    if spotify_ids:
        rows = conn.execute(
            f"""SELECT spotify_album_id, track_list
                FROM spotify_album_meta
                WHERE spotify_album_id IN ({placeholders})
                  AND track_list IS NOT NULL""",
            list(spotify_ids),
        ).fetchall()
        for sid, tl in rows:
            try:
                cached[sid] = set(json.loads(tl))
            except (json.JSONDecodeError, TypeError):
                pass

    # 检查已缓存的专辑是否需要重新获取（缺曲目名或缺艺人名）
    def _needs_refetch(sid, tracks):
        if not tracks:
            return False
        # 检查 album_artists 是否为空
        aa = conn.execute(
            "SELECT album_artists FROM spotify_album_meta WHERE spotify_album_id = ?",
            (sid,),
        ).fetchone()
        if not aa or not aa[0]:
            return True
        # 检查曲目名覆盖率
        placeholders = ",".join("?" for _ in tracks)
        named = conn.execute(
            f"""SELECT COUNT(*) FROM spotify_track_meta
                WHERE spotify_track_id IN ({placeholders})
                  AND track_name IS NOT NULL AND track_name != ''""",
            list(tracks),
        ).fetchone()[0]
        return named < len(tracks) * 0.5

    # 缺失的通过 API 补全；已缓存但缺元数据的也重新获取
    missing = [sid for sid in spotify_ids if sid not in cached]
    needs_metadata = []
    if not missing:
        for sid in spotify_ids:
            if _needs_refetch(sid, cached.get(sid, set())):
                needs_metadata.append(sid)

    refetch_ids = missing + needs_metadata
    if refetch_ids:
        fetched = _fetch_album_tracks_from_api(refetch_ids)
        # 持久化到 DB
        wconn = get_db(readonly=False)
        for sid, tracks in fetched.items():
            if tracks:
                tl_json = json.dumps(tracks, ensure_ascii=False)
                wconn.execute(
                    """UPDATE spotify_album_meta
                       SET track_list = ?, total_tracks = ?
                       WHERE spotify_album_id = ?""",
                    (tl_json, len(tracks), sid),
                )
                cached[sid] = set(tracks)
        wconn.commit()
        wconn.close()

    # 构建 album_id → set(spotify_track_id)，再转换为归一化曲目名
    id_result = {}
    for _, row in albums_df.iterrows():
        aid = int(row["album_id"])
        sid = album_spotify_map.get(aid)
        if sid and sid in cached:
            id_result[aid] = cached[sid]

    # 收集所有涉及到的 Spotify track ID，批量查询名称
    all_ids = set()
    for ids in id_result.values():
        all_ids |= ids

    id_to_name = {}
    if all_ids:
        placeholders = ",".join("?" for _ in all_ids)
        name_rows = conn.execute(
            f"""SELECT spotify_track_id, track_name
                FROM spotify_track_meta
                WHERE spotify_track_id IN ({placeholders})
                  AND track_name IS NOT NULL AND track_name != ''""",
            list(all_ids),
        ).fetchall()
        for tid, tname in name_rows:
            id_to_name[tid] = normalize_track_name(tname.strip().lower())

    # 转换为归一化曲目名集合（IDs 匹配不到名称的跳过）
    result = {}
    for aid, ids in id_result.items():
        names = set()
        for tid in ids:
            name = id_to_name.get(tid)
            if name:
                names.add(name)
        if names:
            result[aid] = names

    return result


def _is_superset_of(superset_tracks, subset_tracks, threshold=0.8):
    """判断 superset 是否包含了 subset 的 >= threshold 比例曲目。

    硬约束：
    - 超集曲目数必须严格大于子集
    - 子集至少 4 首歌（排除单曲被误识别为基准版）
    """
    if len(superset_tracks) <= len(subset_tracks):
        return False
    if len(subset_tracks) < 4:
        return False
    shared = len(superset_tracks & subset_tracks)
    return (shared / len(subset_tracks)) >= threshold


def _detect_superset_groups(
    conn, albums_df, album_tracks, already_grouped_ids, threshold=0.8, group_type="album"
):
    """对名称检测未覆盖的专辑，用超集关系发现候选组。

    通过 union-find 构建连通分量，每个分量形成一个候选组。
    主版本选择：最早发行日期，同日期选最短名称。
    """
    candidates = albums_df[~albums_df["album_id"].isin(already_grouped_ids)]
    if candidates.empty:
        return []

    results = []

    for artist_name, artist_group in candidates.groupby("artist_name"):
        artist_id = int(artist_group["artist_id"].iloc[0])
        album_rows = artist_group.to_dict("records")

        # 构建边：哪些专辑对存在超集关系
        n = len(album_rows)
        edges = set()  # (subset_id, superset_id)

        for i in range(n):
            aid_i = int(album_rows[i]["album_id"])
            tracks_i = album_tracks.get(aid_i, set())
            if not tracks_i:
                continue
            for j in range(n):
                if i == j:
                    continue
                aid_j = int(album_rows[j]["album_id"])
                tracks_j = album_tracks.get(aid_j, set())
                if not tracks_j:
                    continue
                if _is_superset_of(tracks_j, tracks_i, threshold):
                    edges.add((aid_i, aid_j))
                elif _is_superset_of(tracks_i, tracks_j, threshold):
                    edges.add((aid_j, aid_i))

        if not edges:
            continue

        # Union-find
        all_in_edges = set()
        for a, b in edges:
            all_in_edges.add(a)
            all_in_edges.add(b)

        parent = {aid: aid for aid in all_in_edges}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for a, b in edges:
            union(a, b)

        # 收集分量
        components = {}
        for aid in all_in_edges:
            root = find(aid)
            components.setdefault(root, set()).add(aid)

        for member_ids in components.values():
            if len(member_ids) < 2:
                continue

            # 获取成员信息
            members = []
            for aid in member_ids:
                match = artist_group[artist_group["album_id"] == aid]
                if match.empty:
                    continue
                row = match.iloc[0]
                rd = _get_release_date(conn, aid)
                members.append(
                    {
                        "album_id": aid,
                        "album_name": row["local_name"],
                        "release_date": rd,
                    }
                )

            # 主版本：最早发行日期 + 最短名称
            members.sort(key=lambda m: (m["release_date"] or "9999", len(m["album_name"])))
            primary = members[0]

            results.append(
                {
                    "artist_name": artist_name,
                    "artist_id": artist_id,
                    "canonical_name": primary["album_name"],
                    "primary_album_name": primary["album_name"],
                    "primary_album_id": primary["album_id"],
                    "member_count": len(members),
                    "confidence": "high",
                    "members": members,
                    "group_type": group_type,
                    "reason": f"曲目超集关系（Union-find 连通分量，阈值 {threshold:.0%}）",
                    "overlap_details": [],
                }
            )

    return results


def _detect_prefix_groups(
    conn,
    albums_df,
    album_tracks,
    already_grouped_ids,
    superset_threshold=0.8,
    overlap_threshold=0.95,
    group_type="album",
):
    """Phase 1.5 — 前缀重合检测。

    对名称归一化未覆盖的专辑，检测同艺人下是否存在「名称前缀重合 + 曲目包含」
    关系。例如 "THE TORTURED POETS DEPARTMENT" 是
    "THE TORTURED POETS DEPARTMENT: THE ANTHOLOGY" 的前缀，且后者曲目包含前者。

    使用本地专辑名（al.album_name）进行比较，确保同一 Spotify 专辑的
    不同本地名称也能被检测到。
    """

    def _get_local_name(aid, artist_group_df, albums_df_full):
        """获取 album_id 对应的本地专辑名（优先用 local_name 列）。"""
        match = artist_group_df[artist_group_df["album_id"] == aid]
        if not match.empty:
            if "local_name" in match.columns and pd.notna(match["local_name"].iloc[0]):
                return match["local_name"].iloc[0]
            return match["album_name"].iloc[0]
        # 回退到完整 DataFrame
        match2 = albums_df_full[albums_df_full["album_id"] == aid]
        if not match2.empty:
            if "local_name" in match2.columns and pd.notna(match2["local_name"].iloc[0]):
                return match2["local_name"].iloc[0]
            return match2["album_name"].iloc[0]
        return None

    candidates = albums_df[~albums_df["album_id"].isin(already_grouped_ids)]
    if candidates.empty:
        return []

    results = []

    for artist_name, artist_group in candidates.groupby("artist_name"):
        artist_id = int(artist_group["artist_id"].iloc[0])

        # 构建此艺人下 (album_id → 最佳本地名) 映射
        # 优先使用 local_name（来自 albums 表），回退到 album_name（来自 spotify）
        aid_to_name = {}
        for _, row in artist_group.iterrows():
            aid = int(row["album_id"])
            local = row.get("local_name")
            if pd.notna(local) and local:
                aid_to_name[aid] = local
            elif aid not in aid_to_name:
                aid_to_name[aid] = row["album_name"]

        # 按名称长度升序排列，确保短名在前（作为前缀候选）
        rows_by_len = sorted(aid_to_name.items(), key=lambda x: len(x[1]))

        used_ids = set()

        for i in range(len(rows_by_len)):
            aid_i, name_i = rows_by_len[i]
            if aid_i in used_ids:
                continue

            members = [
                {
                    "album_id": aid_i,
                    "album_name": name_i,
                    "release_date": _get_release_date(conn, aid_i),
                }
            ]

            for j in range(len(rows_by_len)):
                if i == j:
                    continue
                aid_j, name_j = rows_by_len[j]
                if aid_j in used_ids:
                    continue

                # 检查 name_i 是否是 name_j 的前缀
                if len(name_j) <= len(name_i):
                    continue
                if not name_j.lower().startswith(name_i.lower()):
                    continue

                # 提取后缀，去除前导分隔符
                suffix = name_j[len(name_i) :].strip()
                suffix = suffix.lstrip(":-–+[]() ").strip()
                if not suffix:
                    continue

                # 后缀包含排除关键词（Taylor's Version、Remix 等）→ 跳过
                if _suffix_is_excluded(suffix):
                    continue

                # 曲目验证
                tracks_i = album_tracks.get(aid_i, set())
                tracks_j = album_tracks.get(aid_j, set())
                include_ok = False

                if tracks_i and tracks_j:
                    if _is_superset_of(tracks_j, tracks_i, superset_threshold):
                        include_ok = True
                    elif _is_superset_of(tracks_i, tracks_j, superset_threshold):
                        include_ok = True
                    elif tracks_i == tracks_j:
                        # 相同曲目集 = 同一 Spotify 专辑的不同本地名
                        include_ok = True
                else:
                    # 无 API 数据时用本地 track_albums 验证
                    overlap = _compute_track_overlap(conn, aid_i, aid_j)
                    if overlap >= overlap_threshold:
                        include_ok = True

                if include_ok:
                    rd = _get_release_date(conn, aid_j)
                    members.append(
                        {
                            "album_id": aid_j,
                            "album_name": name_j,
                            "release_date": rd,
                        }
                    )
                    used_ids.add(aid_j)

            if len(members) < 2:
                continue

            # 选主版本：最早发行日期，同日期选最短名称
            members.sort(key=lambda m: (m["release_date"] or "9999", len(m["album_name"])))
            primary = members[0]

            # canonical_name 使用 base 名（最短的那个）
            canonical = min(m["album_name"] for m in members if m["album_name"])
            canonical = normalize_album_name(canonical)

            results.append(
                {
                    "artist_name": artist_name,
                    "artist_id": artist_id,
                    "canonical_name": canonical,
                    "primary_album_name": primary["album_name"],
                    "primary_album_id": primary["album_id"],
                    "member_count": len(members),
                    "confidence": "high",
                    "members": members,
                    "group_type": group_type,
                    "reason": "前缀重合 + 曲目包含验证",
                    "overlap_details": [],
                }
            )
            used_ids.add(primary["album_id"])

    return results


def _fetch_album_tracks_from_api(spotify_album_ids):
    """批量获取专辑完整元数据（通过 Spotify /v1/albums?ids= API）。

    每批最多 20 个 ID。成功后将全部曲目与专辑元数据持久化：
      - spotify_track_meta: id, name, duration_ms, popularity, explicit,
        disc_number, track_number, isrc, spotify_album_id
      - spotify_album_meta: popularity, label, genres, album_artists, total_tracks

    Returns {spotify_album_id: [spotify_track_id, ...]}  # list 保留原始曲目顺序
    """
    if not spotify_album_ids:
        return {}

    try:
        from backend.providers.spotify.client import SpotifyProvider

        provider = SpotifyProvider()
        token = provider.get_cc_token()
    except Exception:
        return {}

    if not token:
        return {}

    result = {}
    track_meta_rows = []  # 9 列全量
    album_meta_updates = {}  # {sid: {popularity, label, genres, album_artists, total_tracks, album_name}}

    ids_list = list(spotify_album_ids)

    for i in range(0, len(ids_list), 20):
        batch = ids_list[i : i + 20]
        try:
            data = provider.get_albums(batch, token)
            if not data:
                continue

            for album in data.get("albums", []):
                if album is None:
                    continue
                sid = album["id"]

                # ── 专辑级元数据 ──
                artist_names = [
                    a.get("name", "") for a in album.get("artists", []) if a.get("name")
                ]
                genres_list = album.get("genres", [])
                images = album.get("images", [])
                album_meta_updates[sid] = {
                    "album_name": album.get("name", ""),
                    "popularity": album.get("popularity"),
                    "label": album.get("label"),
                    "genres": json.dumps(genres_list, ensure_ascii=False) if genres_list else None,
                    "album_artists": ", ".join(artist_names) if artist_names else None,
                    "total_tracks": album.get("total_tracks"),
                    "release_date": album.get("release_date"),
                    "album_type": album.get("album_type"),
                    "image_url": images[0]["url"] if images else None,
                }

                # ── 曲目级元数据（保留原始顺序） ──
                tracks = []
                for t in album.get("tracks", {}).get("items", []):
                    tid = t.get("id")
                    if not tid:
                        continue
                    tracks.append(tid)
                    track_meta_rows.append(
                        (
                            tid,
                            t.get("name", ""),
                            t.get("duration_ms"),
                            t.get("popularity"),
                            1 if t.get("explicit") else 0,
                            t.get("disc_number", 1),
                            t.get("track_number", 0),
                            t.get("external_ids", {}).get("isrc")
                            if t.get("external_ids")
                            else None,
                            sid,
                        )
                    )
                result[sid] = tracks  # 保留 list 顺序！
        except Exception:
            pass

    # ── 持久化 ──
    if track_meta_rows or album_meta_updates:
        try:
            wconn = get_db(readonly=False)

            # 曲目元数据 — 全量 9 列 UPSERT
            if track_meta_rows:
                wconn.executemany(
                    """INSERT INTO spotify_track_meta
                       (spotify_track_id, track_name, duration_ms, popularity, explicit,
                        disc_number, track_number, isrc, spotify_album_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(spotify_track_id) DO UPDATE SET
                           track_name = excluded.track_name,
                           duration_ms = COALESCE(excluded.duration_ms, spotify_track_meta.duration_ms),
                           popularity = COALESCE(excluded.popularity, spotify_track_meta.popularity),
                           explicit = COALESCE(excluded.explicit, spotify_track_meta.explicit),
                           disc_number = COALESCE(excluded.disc_number, spotify_track_meta.disc_number),
                           track_number = COALESCE(excluded.track_number, spotify_track_meta.track_number),
                           isrc = COALESCE(excluded.isrc, spotify_track_meta.isrc),
                           spotify_album_id = COALESCE(excluded.spotify_album_id, spotify_track_meta.spotify_album_id)""",
                    track_meta_rows,
                )

            # 专辑元数据 — 补充 popularity/label/genres 等（不覆盖已有的 release_date/album_type）
            for sid, meta in album_meta_updates.items():
                wconn.execute(
                    """INSERT INTO spotify_album_meta
                       (spotify_album_id, album_name, album_type, release_date,
                        popularity, label, genres, album_artists, total_tracks, image_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(spotify_album_id) DO UPDATE SET
                           album_name = excluded.album_name,
                           album_type = COALESCE(excluded.album_type, spotify_album_meta.album_type),
                           release_date = COALESCE(excluded.release_date, spotify_album_meta.release_date),
                           popularity = COALESCE(excluded.popularity, spotify_album_meta.popularity),
                           label = COALESCE(excluded.label, spotify_album_meta.label),
                           genres = COALESCE(excluded.genres, spotify_album_meta.genres),
                           album_artists = COALESCE(excluded.album_artists, spotify_album_meta.album_artists),
                           total_tracks = COALESCE(excluded.total_tracks, spotify_album_meta.total_tracks),
                           image_url = COALESCE(excluded.image_url, spotify_album_meta.image_url)""",
                    (
                        sid,
                        meta["album_name"],
                        meta.get("album_type"),
                        meta.get("release_date"),
                        meta.get("popularity"),
                        meta.get("label"),
                        meta.get("genres"),
                        meta.get("album_artists"),
                        meta.get("total_tracks"),
                        meta.get("image_url"),
                    ),
                )
            wconn.commit()
            wconn.close()
        except Exception:
            pass

    return result


def _detect_groups_for_type(conn, album_type_filter, overlap_threshold, superset_threshold):
    """对指定类型的专辑（album 或 single）运行完整检测管线。

    管线包含三个 Phase：
      Phase 1  — 名称归一化
      Phase 1.5 — 前缀重合检测
      Phase 2  — 纯超集检测

    返回 results 列表，每项为 dict。
    """
    album_type_cond = "AND sam.album_type = ?" if album_type_filter else ""
    params = [album_type_filter] if album_type_filter else []

    # 单曲检测时排除同时关联到 album 类型 Spotify 条目的本地专辑，
    # 防止同一本地专辑在 album 和 single 两个管线中都被检测导致跨类型合并。
    exclude_mixed_sql = ""
    if album_type_filter == "single":
        exclude_mixed_sql = """AND al.album_id NOT IN (
            SELECT DISTINCT ta2.album_id
            FROM track_albums ta2
            JOIN tracks t2 ON t2.track_id = ta2.track_id
            JOIN spotify_track_meta stm2
              ON t2.spotify_track_id = stm2.spotify_track_id
            JOIN spotify_album_meta sam2 ON sam2.spotify_album_id = stm2.spotify_album_id
            WHERE sam2.album_type = 'album'
        )"""

    albums_df = pd.read_sql_query(
        f"""SELECT sam.spotify_album_id, sam.album_name, a.artist_id,
                  MIN(a.artist_name) AS artist_name,
                  al.album_id,
                  al.album_name AS local_name
           FROM spotify_album_meta sam
           JOIN spotify_track_meta stm ON stm.spotify_album_id = sam.spotify_album_id
           JOIN tracks t
             ON t.spotify_track_id = stm.spotify_track_id
           JOIN track_albums ta ON ta.track_id = t.track_id
           JOIN albums al ON al.album_id = ta.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE 1=1 {album_type_cond} {exclude_mixed_sql}
             AND EXISTS (SELECT 1 FROM track_albums ta2 WHERE ta2.album_id = al.album_id)
           GROUP BY sam.spotify_album_id, a.artist_id, al.album_id
           ORDER BY a.artist_name, sam.album_name""",
        conn,
        params=params,
    )

    if albums_df.empty:
        return []

    # 专辑检测管线：排除实际上是单曲的本地专辑。
    # 单曲的曲目也出现在专辑中时，SQL 链式 JOIN 会错误地将单曲本地专辑
    # 关联到专辑的 spotify_album_meta。通过名称匹配排除仅以单曲类型
    # 存在于 spotify_album_meta 的本地专辑。
    if album_type_filter == "album":
        all_meta = pd.read_sql_query(
            "SELECT DISTINCT album_name, album_type FROM spotify_album_meta",
            conn,
        )
        single_names = set(
            all_meta[all_meta["album_type"] == "single"]["album_name"].str.lower().dropna().tolist()
        )
        album_names = set(
            all_meta[all_meta["album_type"] == "album"]["album_name"].str.lower().dropna().tolist()
        )
        pure_single_names = single_names - album_names
        if pure_single_names:
            albums_df = albums_df[~albums_df["local_name"].str.lower().isin(pure_single_names)]

    if albums_df.empty:
        return []

    # Phase 1 使用本地专辑名做归一化（而非 Spotify 名），
    # 防止单曲被合并到同名 Spotify 专辑中（如 we can't be friends → eternal sunshine）
    albums_df["normalized_name"] = albums_df["local_name"].apply(normalize_album_name)
    album_tracks = _build_album_track_sets(conn, albums_df)

    results = []

    # ── Phase 1: 名称归一化 ──────────────────────────────────────────
    for artist_name, artist_group in albums_df.groupby("artist_name"):
        artist_id = int(artist_group["artist_id"].iloc[0])
        norm_groups = artist_group.groupby("normalized_name")

        for norm_name, group in norm_groups:
            if len(group) < 2:
                continue
            unique_names = group["album_name"].unique()
            if len(unique_names) < 2:
                continue

            members = []
            best_candidate = None
            best_score = (None, float("inf"))

            for _, row in group.iterrows():
                aid = int(row["album_id"])
                rd = _get_release_date(conn, aid)
                members.append(
                    {
                        "album_id": aid,
                        "album_name": row["local_name"],
                        "release_date": rd,
                    }
                )
                name_len = len(row["local_name"])
                if best_score[0] is None or (
                    rd is not None
                    and (best_score[0] is None or rd < best_score[0])
                    or (rd == best_score[0] and name_len < best_score[1])
                ):
                    best_score = (rd, name_len)
                    best_candidate = {"album_id": aid, "album_name": row["local_name"]}

            primary_id = best_candidate["album_id"]

            # 去重
            deduped = {}
            for m in members:
                aid = m["album_id"]
                if aid not in deduped:
                    deduped[aid] = m
                elif len(m["album_name"]) < len(deduped[aid]["album_name"]):
                    deduped[aid] = m
            members = list(deduped.values())

            if len(members) < 2:
                continue

            # 计算每对成员与 primary 的曲目重叠率
            overlap_details = []
            # 使用 Spotify API 全量曲目计算重叠率（fallback: 本地播放记录）
            all_high_confidence = True
            primary_spotify_tracks = album_tracks.get(primary_id, set())
            for m in members:
                if m["album_id"] == primary_id:
                    continue
                m_spotify_tracks = album_tracks.get(m["album_id"], set())
                if m_spotify_tracks or primary_spotify_tracks:
                    # 优先用 Spotify 全量数据
                    if m_spotify_tracks and primary_spotify_tracks:
                        overlap = len(m_spotify_tracks & primary_spotify_tracks) / min(
                            len(m_spotify_tracks), len(primary_spotify_tracks)
                        )
                    else:
                        overlap = 0.0
                else:
                    # 无 Spotify 数据时回退到本地播放记录
                    overlap = _compute_track_overlap(conn, m["album_id"], primary_id)
                overlap_details.append(
                    {
                        "album_name": m["album_name"],
                        "album_id": m["album_id"],
                        "overlap": round(overlap, 4),
                    }
                )
                if overlap < overlap_threshold:
                    all_high_confidence = False

            confidence = "high" if all_high_confidence else "low"
            reason = f"名称归一化 · Spotify 全量曲目重叠率阈值 {overlap_threshold:.0%}"

            if confidence == "low":
                superset_failures = []
                if primary_spotify_tracks:
                    all_superset = True
                    for m in members:
                        if m["album_id"] == primary_id:
                            continue
                        m_tracks = album_tracks.get(m["album_id"], set())
                        if not m_tracks:
                            all_superset = False
                            superset_failures.append(m["album_name"])
                            continue
                        is_superset = _is_superset_of(
                            m_tracks, primary_spotify_tracks, superset_threshold
                        )
                        if not is_superset:
                            all_superset = False
                            superset_failures.append(m["album_name"])
                    if all_superset:
                        confidence = "high"
                        reason = (
                            f"名称归一化 + Spotify 曲目超集验证（阈值 {superset_threshold:.0%}）"
                        )
                    else:
                        reason = (
                            f"曲目重叠率不足（< {overlap_threshold:.0%}），"
                            f"且 Spotify 超集验证未通过"
                            f"（{', '.join(superset_failures[:3])} 等非超集）"
                            if superset_failures
                            else f"曲目重叠率不足（< {overlap_threshold:.0%}），无 Spotify 曲目数据"
                        )
                else:
                    reason = f"曲目重叠率不足（< {overlap_threshold:.0%}），无 Spotify 曲目数据"

            if confidence == "high" and not all_high_confidence:
                pass  # 原本 low 但被 superset 升级
            elif confidence == "high":
                reason = f"名称归一化匹配 · Spotify 全量曲目重叠率 ≥ {overlap_threshold:.0%}"

            results.append(
                {
                    "artist_name": artist_name,
                    "artist_id": artist_id,
                    "canonical_name": norm_name,
                    "primary_album_name": best_candidate["album_name"],
                    "primary_album_id": best_candidate["album_id"],
                    "member_count": len(members),
                    "confidence": confidence,
                    "members": members,
                    "group_type": album_type_filter,
                    "reason": reason,
                    "overlap_details": overlap_details,
                }
            )

    # ── Phase 1.5: 前缀重合 ──────────────────────────────────────────
    already_grouped = set()
    for r in results:
        for m in r["members"]:
            already_grouped.add(m["album_id"])

    prefix_results = _detect_prefix_groups(
        conn,
        albums_df,
        album_tracks,
        already_grouped,
        superset_threshold,
        overlap_threshold=overlap_threshold,
        group_type=album_type_filter,
    )
    results.extend(prefix_results)
    for r in prefix_results:
        for m in r["members"]:
            already_grouped.add(m["album_id"])

    # ── Phase 2: 纯超集检测 ──────────────────────────────────────────
    superset_results = _detect_superset_groups(
        conn,
        albums_df,
        album_tracks,
        already_grouped,
        superset_threshold,
        group_type=album_type_filter,
    )
    results.extend(superset_results)

    return results


def detect_release_groups(
    overlap_threshold: float = 0.4, superset_threshold: float = 0.8
) -> pd.DataFrame:
    """三阶段自动检测可合并的专辑版本组（album 和 single 分别检测）。

    Phase 1  — 名称归一化：normalize_album_name() 剥离版本后缀
    Phase 1.5 — 前缀重合检测：名称前缀 + 曲目包含关系
    Phase 2  — 纯超集检测：Union-find 连通分量

    album 和 single 分别独立检测，避免跨类型合并。

    Returns DataFrame with columns:
      artist_name, artist_id, canonical_name, primary_album_name,
      primary_album_id, member_count, confidence ('high'/'low'), members
    """
    conn = get_db()

    # 分别检测 album 和 single，防止跨类型合并
    album_results = _detect_groups_for_type(conn, "album", overlap_threshold, superset_threshold)
    single_results = _detect_groups_for_type(conn, "single", overlap_threshold, superset_threshold)

    conn.close()

    results = album_results + single_results

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


def apply_detected_groups(detection_df: pd.DataFrame, only_high_confidence: bool = True) -> int:
    """将自动检测结果写入 release_groups 表。

    Args:
        detection_df: detect_release_groups() 的返回
        only_high_confidence: 仅写入高置信度组

    Returns:
        写入的组数量
    """
    if detection_df.empty:
        return 0

    conn = get_db(readonly=False)
    applied = 0

    for _, row in detection_df.iterrows():
        if only_high_confidence and row.get("confidence") != "high":
            continue

        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO release_groups
                   (canonical_name, artist_id, primary_album_id, scope, is_manual)
                   VALUES (?, ?, ?, 'release', 0)""",
                (row["canonical_name"], int(row["artist_id"]), int(row["primary_album_id"])),
            )
            group_id = cur.lastrowid
            if group_id == 0:
                row_existing = conn.execute(
                    """SELECT group_id FROM release_groups
                       WHERE canonical_name = ? AND artist_id = ? AND scope = 'release'""",
                    (row["canonical_name"], int(row["artist_id"])),
                ).fetchone()
                group_id = row_existing[0] if row_existing else None

            if group_id:
                for m in row["members"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO release_group_members(group_id, album_id) VALUES (?, ?)",
                        (group_id, int(m["album_id"])),
                    )
                applied += 1
        except Exception:
            pass

    conn.commit()
    if applied:
        _refresh_version_merge_dependents(conn)
    conn.close()
    return applied


def get_ungrouped_albums(artist_name=None) -> pd.DataFrame:
    """获取尚未被分组的专辑列表（供手动管理使用）。"""
    conn = get_db()
    if artist_name:
        df = pd.read_sql_query(
            """SELECT al.album_id, al.album_name, a.artist_name
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id
               WHERE a.artist_name = ?
                 AND al.album_id NOT IN (
                     SELECT album_id FROM release_group_members
                 )
               ORDER BY a.artist_name, al.album_name""",
            conn,
            params=[artist_name],
        )
    else:
        df = pd.read_sql_query(
            """SELECT al.album_id, al.album_name, a.artist_name
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id
               WHERE al.album_id NOT IN (
                   SELECT album_id FROM release_group_members
               )
               ORDER BY a.artist_name, al.album_name""",
            conn,
        )
    conn.close()
    return df


def get_groups_for_artist(artist_name: str) -> pd.DataFrame:
    """获取指定艺人的所有 release groups。"""
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT rg.group_id, rg.canonical_name, a.artist_name, rg.primary_album_id,
                  pa.album_name AS primary_album_name, rg.scope, rg.is_manual, rg.created_at
           FROM release_groups rg
           JOIN artists a ON rg.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
           WHERE a.artist_name = ?
           ORDER BY rg.canonical_name""",
        conn,
        params=[artist_name],
    )
    conn.close()
    return df


def get_album_types(album_ids):
    """批量获取 album 的类型信息。

    通过 track_albums → tracks → spotify_track_meta → spotify_album_meta
    链式 JOIN 获取 album_type。重复类型时优先 album > compilation > single。

    Returns {album_id: 'album'|'single'|'compilation'|'unknown'}
    """
    if not album_ids:
        return {}

    conn = get_db()
    placeholders = ",".join("?" for _ in album_ids)
    rows = conn.execute(
        f"""SELECT al.album_id, sam.album_type
            FROM albums al
            JOIN track_albums ta ON ta.album_id = al.album_id
            JOIN tracks t ON t.track_id = ta.track_id
            JOIN spotify_track_meta stm
              ON t.spotify_track_id = stm.spotify_track_id
            JOIN spotify_album_meta sam
              ON stm.spotify_album_id = sam.spotify_album_id
            WHERE al.album_id IN ({placeholders})
            GROUP BY al.album_id, sam.album_type""",
        list(album_ids),
    ).fetchall()
    conn.close()

    priority = {"album": 0, "compilation": 1, "single": 2}
    result = {}
    for album_id, album_type in rows:
        if album_id not in result:
            result[album_id] = album_type
        else:
            cur_pri = priority.get(result[album_id], 99)
            new_pri = priority.get(album_type, 99)
            if new_pri < cur_pri:
                result[album_id] = album_type

    for aid in album_ids:
        if aid not in result:
            result[aid] = "unknown"

    return result
