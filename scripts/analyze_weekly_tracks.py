"""Analyze unique track count per Billboard week to recommend a default Top N.

Usage:
    source .venv/bin/activate && python3 scripts/analyze_weekly_tracks.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from app.db import get_db, base_filters


def main():
    # ── Load filtered data ─────────────────────────────────────────────
    conn = get_db()
    _f, _fp = base_filters(min_ms=30000, music_only=True)
    _w = f"WHERE {_f}" if _f else ""

    df = pd.read_sql_query(
        f"""SELECT p.ts_date, p.ts_dow, p.ts_hour, p.track_id,
                   t.track_name, a.artist_name
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            {_w}""",
        conn,
        params=_fp,
    )
    conn.close()

    print(f"过滤后数据量: {len(df):,} 条播放记录")
    print()

    # ── Compute Billboard week ─────────────────────────────────────────
    df["days_back"] = (df["ts_dow"] - 4) % 7
    mask_fri_am = (df["ts_dow"] == 4) & (df["ts_hour"] < 12)
    df.loc[mask_fri_am, "days_back"] = 7

    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (
        df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")
    ).dt.date

    # ── Unique tracks per week ─────────────────────────────────────────
    weekly = df.groupby("billboard_week")["track_id"].nunique().reset_index(name="unique_tracks")
    weekly = weekly.sort_values("billboard_week")

    counts = weekly["unique_tracks"]

    print(f"Billboard 周数: {len(weekly)}")
    print(f"时间跨度: {weekly['billboard_week'].min()} → {weekly['billboard_week'].max()}")
    print()
    print("=== 每周独特曲目数分布 ===")
    print(f"  Min    : {counts.min():6.0f}")
    print(f"  P10    : {counts.quantile(0.10):6.0f}")
    print(f"  P25    : {counts.quantile(0.25):6.0f}")
    print(f"  Median : {counts.median():6.0f}")
    print(f"  Mean   : {counts.mean():6.1f}")
    print(f"  P75    : {counts.quantile(0.75):6.0f}")
    print(f"  P90    : {counts.quantile(0.90):6.0f}")
    print(f"  Max    : {counts.max():6.0f}")
    print()

    # ── Histogram buckets ──────────────────────────────────────────────
    buckets = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
               (50, 60), (60, 70), (70, 80), (80, 90), (90, 100),
               (100, 150), (150, 200), (200, 9999)]

    print("=== 每段区间周数分布 ===")
    max_count = 0
    rows = []
    for lo, hi in buckets:
        n = len(counts[(counts >= lo) & (counts < hi)])
        rows.append((lo, hi, n))
        if n > max_count:
            max_count = n

    bar_max = 40  # chars
    for lo, hi, n in rows:
        bar_len = int(n / max(max_count, 1) * bar_max)
        bar = "#" * bar_len
        label = f"{lo:>3}-{hi:>4}" if hi < 9999 else f"{lo:>3}+   "
        print(f"  [{label}): {n:3d} 周  {bar}")
    print()

    # ── Recommendation ─────────────────────────────────────────────────
    # P75 rounded up to nearest 5
    p75 = int(counts.quantile(0.75))
    rec_p75 = ((p75 + 4) // 5) * 5
    # Median rounded up to nearest 5
    med = int(counts.median())
    rec_med = ((med + 4) // 5) * 5

    print("=== 推荐默认 Top N ===")
    print(f"  P75 方案（覆盖 75% 的周）: {rec_p75:3d} 首")
    print(f"  中位数方案（一半周完整）  : {rec_med:3d} 首")
    print()
    print(f"  建议使用: {rec_med} 首（中位数方案，避免多数周出现大量空位）")
    print(f"  使用方式: 在 Billboard 页面侧边栏 slider 默认值设为 {rec_med}")
    print()

    # ── Detail: show smallest/largest weeks ────────────────────────────
    print("=== 曲目最少的前 5 周 ===")
    bottom5 = weekly.nsmallest(5, "unique_tracks")
    for _, row in bottom5.iterrows():
        print(f"  {row['billboard_week']} : {int(row['unique_tracks']):4d} 首")
    print()

    print("=== 曲目最多的前 5 周 ===")
    top5 = weekly.nlargest(5, "unique_tracks")
    for _, row in top5.iterrows():
        print(f"  {row['billboard_week']} : {int(row['unique_tracks']):4d} 首")


if __name__ == "__main__":
    main()
