"""Application settings — centralized parameter controls."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from app.db import get_db, db_exists, ensure_schema
from app.import_data import import_data
from app.styles import inject_global_styles, page_header

inject_global_styles()

# Ensure schema is up-to-date (adds agg tables for existing DBs)
if db_exists():
    ensure_schema()

# ── Session state defaults ──────────────────────────────────────────────
if "min_ms" not in st.session_state:
    st.session_state.min_ms = 30000
if "music_only" not in st.session_state:
    st.session_state.music_only = True
if "merge_enabled" not in st.session_state:
    st.session_state.merge_enabled = True
if "bb_top_n" not in st.session_state:
    st.session_state.bb_top_n = 30
if "bb_week_start_dow" not in st.session_state:
    st.session_state.bb_week_start_dow = 4  # Friday
if "bb_week_start_hour" not in st.session_state:
    st.session_state.bb_week_start_hour = 0
if "bb_album_top_n" not in st.session_state:
    st.session_state.bb_album_top_n = 20
if "bb_artist_top_n" not in st.session_state:
    st.session_state.bb_artist_top_n = 20

# Track previous values for change detection
if "_prev_min_ms" not in st.session_state:
    st.session_state._prev_min_ms = st.session_state.min_ms
if "_prev_music_only" not in st.session_state:
    st.session_state._prev_music_only = st.session_state.music_only
if "_prev_merge_enabled" not in st.session_state:
    st.session_state._prev_merge_enabled = st.session_state.merge_enabled
if "_prev_bb_top_n" not in st.session_state:
    st.session_state._prev_bb_top_n = st.session_state.bb_top_n
if "_prev_bb_week_start_dow" not in st.session_state:
    st.session_state._prev_bb_week_start_dow = st.session_state.bb_week_start_dow
if "_prev_bb_week_start_hour" not in st.session_state:
    st.session_state._prev_bb_week_start_hour = st.session_state.bb_week_start_hour
if "_prev_bb_album_top_n" not in st.session_state:
    st.session_state._prev_bb_album_top_n = st.session_state.bb_album_top_n
if "_prev_bb_artist_top_n" not in st.session_state:
    st.session_state._prev_bb_artist_top_n = st.session_state.bb_artist_top_n

page_header("⚙️ 设置", description="集中管理数据过滤、Billboard 榜单和数据导入")

# ═══════════════════════════════════════════════════════════════════════════
# Data Filtering
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("数据过滤")
st.caption("应用于所有统计页面的数据过滤条件，修改后即时生效")

col1, col2 = st.columns(2)

with col1:
    _sec_options = [0, 10, 30, 60, 120]
    _default_sec = st.session_state.min_ms // 1000
    _sec_idx = _sec_options.index(_default_sec) if _default_sec in _sec_options else 2
    min_sec = st.selectbox(
        "最短播放时长",
        options=_sec_options,
        index=_sec_idx,
        format_func=lambda x: f"{x} 秒" if x > 0 else "不过滤",
        key="settings_min_sec",
        help="低于此值的播放不计入统计。已主动跳过（按上一首/下一首按钮）和播放错误的记录自动排除。",
    )
    st.session_state.min_ms = min_sec * 1000

with col2:
    st.session_state.music_only = st.checkbox(
        "仅音乐（排除播客/有声书）",
        value=st.session_state.music_only,
        key="settings_music",
        help="排除播客和有声书内容",
    )
    st.session_state.merge_enabled = st.checkbox(
        "合并连续播放",
        value=st.session_state.merge_enabled,
        key="settings_merge",
        help="将同一首歌的连续播放记录合并为逻辑播放次数。\n\n"
             "例如：一首歌被切分成 20s + 200s 两次记录，合并后计为 1 次完整播放。"
             "关闭后每条记录独立计数，仅保留 ≥ 最短时长的记录。",
    )

# Detect data filter changes → clear caches and rerun
_filter_changed = False
if st.session_state.min_ms != st.session_state._prev_min_ms:
    st.session_state._prev_min_ms = st.session_state.min_ms
    _filter_changed = True
if st.session_state.music_only != st.session_state._prev_music_only:
    st.session_state._prev_music_only = st.session_state.music_only
    _filter_changed = True
if st.session_state.merge_enabled != st.session_state._prev_merge_enabled:
    st.session_state._prev_merge_enabled = st.session_state.merge_enabled
    _filter_changed = True
if _filter_changed:
    st.cache_data.clear()
    st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Billboard
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("Billboard 周榜")
st.caption("Billboard 页面专属设置，修改后榜单统计即时重算")

DOW_OPTIONS = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

# Row 1: Top N sliders for 单曲/专辑/艺人
col_t1, col_t2, col_t3 = st.columns(3)

with col_t1:
    new_track_top_n = st.slider(
        "每周上榜歌曲数量 (单曲 Top N)",
        min_value=10,
        max_value=100,
        step=5,
        value=st.session_state.bb_top_n,
        key="settings_bb_top_n_widget",
        help="每期 Billboard 单曲周榜收录的歌曲数量上限",
    )

with col_t2:
    new_album_top_n = st.slider(
        "每周上榜专辑数量 (专辑 Top N)",
        min_value=5,
        max_value=100,
        step=5,
        value=st.session_state.bb_album_top_n,
        key="settings_bb_album_top_n_widget",
        help="每期 Billboard 专辑周榜收录的专辑数量上限",
    )

with col_t3:
    new_artist_top_n = st.slider(
        "每周上榜艺人数量 (艺人 Top N)",
        min_value=5,
        max_value=100,
        step=5,
        value=st.session_state.bb_artist_top_n,
        key="settings_bb_artist_top_n_widget",
        help="每期 Billboard 艺人周榜收录的艺人数量上限",
    )

# Row 2: Week boundary configuration
col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    new_week_dow = st.selectbox(
        "统计周期起始日",
        options=list(DOW_OPTIONS.keys()),
        format_func=lambda x: DOW_OPTIONS[x],
        index=list(DOW_OPTIONS.keys()).index(st.session_state.bb_week_start_dow),
        key="settings_bb_week_dow_raw",
        help="每周榜单从周几开始计算",
    )
    st.session_state.bb_week_start_dow = new_week_dow

with col_w2:
    new_week_hour = st.selectbox(
        "起始时间",
        options=list(range(24)),
        format_func=lambda x: f"{x:02d}:00",
        index=st.session_state.bb_week_start_hour,
        key="settings_bb_week_hour_raw",
        help="起始日当天从几点开始划入新一周（北京时间）",
    )
    st.session_state.bb_week_start_hour = new_week_hour

with col_w3:
    st.caption(
        f"当前统计周期：每{DOW_OPTIONS[st.session_state.bb_week_start_dow]} "
        f"{st.session_state.bb_week_start_hour:02d}:00 — "
        f"下{DOW_OPTIONS[st.session_state.bb_week_start_dow]} "
        f"{st.session_state.bb_week_start_hour:02d}:00（北京时间）"
    )

# Detect changes and sync to canonical key
_bb_changed = False
if new_track_top_n != st.session_state._prev_bb_top_n:
    st.session_state.bb_top_n = new_track_top_n
    st.session_state._prev_bb_top_n = new_track_top_n
    _bb_changed = True
if new_album_top_n != st.session_state._prev_bb_album_top_n:
    st.session_state.bb_album_top_n = new_album_top_n
    st.session_state._prev_bb_album_top_n = new_album_top_n
    _bb_changed = True
if new_artist_top_n != st.session_state._prev_bb_artist_top_n:
    st.session_state.bb_artist_top_n = new_artist_top_n
    st.session_state._prev_bb_artist_top_n = new_artist_top_n
    _bb_changed = True
if st.session_state.bb_week_start_dow != st.session_state._prev_bb_week_start_dow:
    st.session_state._prev_bb_week_start_dow = st.session_state.bb_week_start_dow
    st.session_state.settings_bb_week_dow = st.session_state.bb_week_start_dow
    _bb_changed = True
if st.session_state.bb_week_start_hour != st.session_state._prev_bb_week_start_hour:
    st.session_state._prev_bb_week_start_hour = st.session_state.bb_week_start_hour
    st.session_state.settings_bb_week_hour = st.session_state.bb_week_start_hour
    _bb_changed = True
if _bb_changed:
    # Persist config to URL so it survives app restarts
    import json
    st.query_params["bb_cfg"] = json.dumps({
        "tn": st.session_state.bb_top_n,
        "an": st.session_state.bb_album_top_n,
        "arn": st.session_state.bb_artist_top_n,
        "dow": st.session_state.bb_week_start_dow,
        "hr": st.session_state.bb_week_start_hour,
    })
    st.cache_data.clear()
    st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Data Management
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("数据管理")

col_mgmt1, col_mgmt2 = st.columns([1, 3])

with col_mgmt1:
    if st.button("🔄 重新导入数据", use_container_width=True, type="primary"):
        with st.spinner("正在重新导入 Spotify 播放记录..."):
            try:
                result = import_data(
                    agg_min_ms=st.session_state.min_ms,
                    agg_music_only=st.session_state.music_only,
                    agg_week_start_dow=st.session_state.bb_week_start_dow,
                    agg_week_start_hour=st.session_state.bb_week_start_hour,
                )
                st.cache_data.clear()
                st.success(
                    f"导入完成！{result['total_records']:,} 条记录，"
                    f"{result['unique_artists']} 位艺人，{result['unique_tracks']} 首曲目"
                )
                st.rerun()
            except FileNotFoundError as e:
                st.error(f"找不到数据文件：{e}")
            except Exception as e:
                st.error(f"导入失败：{e}")

with col_mgmt2:
    if db_exists():
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        conn.close()
        st.metric("数据库记录数", f"{count:,}")
    else:
        st.warning("数据库未导入，请先导入数据")
