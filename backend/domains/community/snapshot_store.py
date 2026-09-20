"""Community publications: indexed SQLite rows, atomic active/previous generations."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from backend.core import config, db
from backend.core.access_surface import public_readonly_db_guard_active
from backend.domains.community.post_types import HIGHLIGHT_POST_TYPES

SCHEMA_VERSION = 1
MAX_GENERATION_BYTES = 20 * 1024 * 1024


def path():
    return Path(
        config.SPOTIFY_STATS_COMMUNITY_CACHE_PATH
        or Path(db.DB_PATH).with_name("community_cache.db")
    )


def connect(*, write=False):
    target = path()
    if write:
        if public_readonly_db_guard_active():
            raise PermissionError("Public requests cannot write Community snapshots")
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, timeout=30)
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS generations (
          generation INTEGER PRIMARY KEY, request_key TEXT NOT NULL, revision TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(request_key,revision));
        CREATE TABLE IF NOT EXISTS active (
          request_key TEXT PRIMARY KEY, generation INTEGER NOT NULL, previous INTEGER,
          failed_revision TEXT);
        CREATE TABLE IF NOT EXISTS posts (
          generation INTEGER NOT NULL, ordinal INTEGER NOT NULL, post_id TEXT NOT NULL,
          account TEXT NOT NULL, posted_at TEXT NOT NULL, day TEXT NOT NULL,
          post_type TEXT NOT NULL, significance REAL NOT NULL, highlight INTEGER NOT NULL,
          search_text TEXT NOT NULL, payload TEXT NOT NULL,
          PRIMARY KEY(generation,ordinal));
        CREATE INDEX IF NOT EXISTS post_identity ON posts(generation,post_id,ordinal);
        CREATE INDEX IF NOT EXISTS post_account ON posts(generation,account,ordinal);
        CREATE INDEX IF NOT EXISTS post_date ON posts(generation,posted_at,ordinal);
        CREATE INDEX IF NOT EXISTS post_day ON posts(generation,day,account,ordinal);
        CREATE INDEX IF NOT EXISTS post_type ON posts(generation,post_type,ordinal);
        CREATE TABLE IF NOT EXISTS tags (
          generation INTEGER, ordinal INTEGER, tag TEXT,
          PRIMARY KEY(generation,tag,ordinal));
        CREATE TABLE IF NOT EXISTS entities (
          generation INTEGER, ordinal INTEGER, position INTEGER, posted_at TEXT,
          kind TEXT, name TEXT, entity_id TEXT,
          PRIMARY KEY(generation,ordinal,position));
        CREATE INDEX IF NOT EXISTS entity_name ON entities(generation,name,ordinal);
        CREATE INDEX IF NOT EXISTS entity_trending ON entities(generation,kind,posted_at,name);
        """)
    else:
        if not target.is_file():
            raise FileNotFoundError(target)
        conn = sqlite3.connect(f"{target.resolve().as_uri()}?mode=ro", uri=True, timeout=1)
        conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def reader(key):
    conn = connect()
    try:
        conn.execute("BEGIN")
        row = conn.execute(
            """SELECT g.*,a.failed_revision FROM active a JOIN generations g
          ON g.generation=a.generation WHERE a.request_key=?""",
            (key,),
        ).fetchone()
        yield conn, row
    finally:
        conn.close()


def publish(key, revision, posts, fence):
    conn = connect(write=True)
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute(
                "SELECT generation FROM active WHERE request_key=?", (key,)
            ).fetchone()
            existing = conn.execute(
                "SELECT generation FROM generations WHERE request_key=? AND revision=?",
                (key, revision),
            ).fetchone()
            if existing and old and existing[0] == old[0]:
                return False
            if existing:
                fence()
                conn.execute(
                    "UPDATE active SET generation=?,previous=?,failed_revision=NULL WHERE request_key=?",
                    (existing[0], old[0] if old else None, key),
                )
                return True
            generation = conn.execute(
                "INSERT INTO generations(request_key,revision) VALUES(?,?)", (key, revision)
            ).lastrowid
            size = 0
            for ordinal, post in enumerate(posts):
                payload = asdict(post)
                payload.pop("metrics")
                payload.pop("images")
                raw = json.dumps(
                    payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=str
                )
                search = "\n".join(
                    [
                        post.content,
                        post.account_handle,
                        *(e.get("name", "") for e in post.linked_entities),
                    ]
                ).lower()
                size += len(raw.encode()) + len(search.encode())
                conn.execute(
                    "INSERT INTO posts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        generation,
                        ordinal,
                        post.id,
                        post.account_handle,
                        post.posted_at,
                        post.posted_at[:10],
                        post.post_type,
                        post.significance,
                        int(post.post_type in HIGHLIGHT_POST_TYPES),
                        search,
                        raw,
                    ),
                )
                conn.executemany(
                    "INSERT INTO tags VALUES(?,?,?)",
                    [(generation, ordinal, t) for t in set(post.tags)],
                )
                conn.executemany(
                    "INSERT INTO entities VALUES(?,?,?,?,?,?,?)",
                    [
                        (
                            generation,
                            ordinal,
                            i,
                            post.posted_at,
                            e.get("type"),
                            e.get("name", ""),
                            json.dumps(e.get("id")),
                        )
                        for i, e in enumerate(post.linked_entities)
                    ],
                )
            if size > MAX_GENERATION_BYTES:
                raise ValueError("Community generation exceeds 20 MiB fact budget")
            fence()
            conn.execute(
                "INSERT OR REPLACE INTO active VALUES(?,?,?,NULL)",
                (key, generation, old[0] if old else None),
            )
            # Keep both active and previous for every semantic key.
            for table in ("posts", "tags", "entities", "generations"):
                conn.execute(
                    f"DELETE FROM {table} WHERE generation NOT IN (SELECT generation FROM active UNION SELECT previous FROM active WHERE previous IS NOT NULL)"
                )
        return True
    finally:
        conn.close()


def mark_failed(key, revision):
    conn = connect(write=True)
    try:
        with conn:
            conn.execute("UPDATE active SET failed_revision=? WHERE request_key=?", (revision, key))
    finally:
        conn.close()


def _where(generation, filters):
    clauses, args = ["p.generation=?"], [generation]
    for name, column in [("accounts", "account"), ("post_types", "post_type")]:
        values = sorted({v.strip() for v in (filters.get(name) or "").split(",") if v.strip()})
        if values:
            clauses.append(f"p.{column} IN ({','.join('?' for _ in values)})")
            args.extend(values)
    tags = sorted({v.strip() for v in (filters.get("tags") or "").split(",") if v.strip()})
    if tags:
        clauses.append(
            f"EXISTS(SELECT 1 FROM tags t WHERE t.generation=p.generation AND t.ordinal=p.ordinal AND t.tag IN ({','.join('?' for _ in tags)}))"
        )
        args.extend(tags)
    for key, op in [("date_from", ">="), ("date_to", "<=")]:
        if filters.get(key):
            clauses.append(f"p.posted_at {op} ?")
            args.append(filters[key])
    clauses.append("p.significance>=?")
    args.append(filters.get("significance_min", 0))
    if filters.get("search"):
        clauses.append("instr(p.search_text,?)>0")
        args.append(filters["search"].lower())
    return " AND ".join(clauses), args


def feed(conn, generation, **filters):
    where, args = _where(generation, filters)
    total_all = conn.execute(f"SELECT count(*) FROM posts p WHERE {where}", args).fetchone()[0]
    if filters.get("highlights_only"):
        where += " AND p.highlight=1"
    total = conn.execute(f"SELECT count(*) FROM posts p WHERE {where}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT payload FROM posts p WHERE {where} ORDER BY ordinal LIMIT ? OFFSET ?",
        [*args, filters["limit"], filters["offset"]],
    ).fetchall()
    posts = [json.loads(r[0]) for r in rows]
    return {
        "meta": {
            "total": total,
            "total_all": total_all,
            "returned": len(posts),
            "limit": filters["limit"],
            "offset": filters["offset"],
        },
        "posts": posts,
    }


def detail(conn, generation, post_id):
    target = conn.execute(
        "SELECT * FROM posts WHERE generation=? AND post_id=? ORDER BY ordinal LIMIT 1",
        (generation, post_id),
    ).fetchone()
    if target is None:
        return None
    rows = conn.execute(
        """WITH candidates AS (
      SELECT p.ordinal,p.account,row_number() OVER (PARTITION BY p.account ORDER BY p.ordinal) AS n
      FROM posts p WHERE p.generation=? AND p.day=? AND p.account<>?
      AND EXISTS(SELECT 1 FROM entities e JOIN entities t ON t.generation=e.generation AND t.name=e.name
        WHERE e.generation=p.generation AND e.ordinal=p.ordinal AND t.ordinal=?))
      SELECT p.payload FROM candidates c JOIN posts p ON p.generation=? AND p.ordinal=c.ordinal
      WHERE c.n=1 ORDER BY p.ordinal LIMIT 4""",
        (generation, target["day"], target["account"], target["ordinal"], generation),
    ).fetchall()
    return {"post": json.loads(target["payload"]), "replies": [json.loads(r[0]) for r in rows]}


def trending(conn, generation, *, date_from=None, date_to=None, artist_limit=6, track_limit=3):
    dates, args = "", [generation]
    for value, op in [(date_from, ">="), (date_to, "<=")]:
        if value:
            dates += f" AND posted_at{op}?"
            args.append(value)
    result = {}
    for kind, limit in [("artist", artist_limit), ("track", track_limit)]:
        rows = conn.execute(
            f"""SELECT name,count(*) AS n,min(ordinal*10000+position) AS first
          FROM entities WHERE generation=? {dates} AND kind=? AND name<>''
          GROUP BY name ORDER BY n DESC,first LIMIT ?""",
            [*args, kind, limit],
        ).fetchall()
        items = []
        for row in rows:
            entity_id = None
            if kind == "track":
                ids = conn.execute(
                    f"""SELECT entity_id FROM entities WHERE generation=? {dates}
                  AND kind='track' AND name=? AND entity_id NOT IN ('null','0','""') ORDER BY ordinal,position LIMIT 1""",
                    [*args, row["name"]],
                ).fetchone()
                entity_id = json.loads(ids[0]) if ids else None
            items.append({"name": row["name"], "count": row["n"], "entity_id": entity_id})
        result[kind + "s"] = items
    for key, kind in [("latest_no1", "no1_announcement"), ("latest_debut", "debut")]:
        row = conn.execute(
            f"SELECT payload FROM posts WHERE generation=? {dates} AND post_type=? ORDER BY ordinal LIMIT 1",
            [*args, kind],
        ).fetchone()
        value = None
        if row:
            post = json.loads(row[0])
            entities = post["linked_entities"]
            value = {
                k: next((e.get("name") for e in entities if e.get("type") == k), None)
                for k in ("track", "artist")
            }
            value["post_id"] = post["id"]
        result[key] = value
    return result
