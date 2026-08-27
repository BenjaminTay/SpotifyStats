#!/usr/bin/env python3
"""Preview or apply the controlled cleanup of known historical FK debt."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.db import DB_PATH, enforce_sqlite_foreign_keys  # noqa: E402
from backend.domains.metadata.historical_fk_cleanup import (  # noqa: E402
    HistoricalForeignKeyCleanupError,
    apply_cleanup,
    build_cleanup_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="预览或执行历史 SQLite 外键债务的受控清理")
    parser.add_argument("--db", default=DB_PATH, help="SQLite 数据库路径")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="只读预览并输出确认令牌")
    mode.add_argument("--apply", action="store_true", help="执行已确认且未漂移的清理方案")
    parser.add_argument("--confirmation-token", help="--preview 输出的确认令牌")
    return parser


def main() -> int:
    args = _parser().parse_args()
    path = Path(args.db).resolve()
    if not path.is_file():
        print(json.dumps({"status": "error", "error": f"数据库不存在: {path}"}, ensure_ascii=False))
        return 2
    if args.preview:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=30)
    else:
        if not args.confirmation_token:
            print(
                json.dumps(
                    {"status": "error", "error": "--apply 必须提供 --confirmation-token"},
                    ensure_ascii=False,
                )
            )
            return 2
        conn = sqlite3.connect(path, timeout=30)
    try:
        enforce_sqlite_foreign_keys(conn)
        result = (
            build_cleanup_plan(conn)
            if args.preview
            else apply_cleanup(conn, args.confirmation_token)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("status") in {"ready", "completed"} else 1
    except (sqlite3.Error, HistoricalForeignKeyCleanupError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
