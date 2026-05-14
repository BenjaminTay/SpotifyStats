"""Application settings — centralized parameter controls."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from app.db import get_db, db_exists
from app.import_data import import_data

st.set_page_config(page_title="设置", page_icon="⚙️", layout="wide")

# ── Session state defaults ──────────────────────────────────────────────
if "min_ms" not in st.session_state:
    st.session_state.min_ms = 30000
if "exclude_skipped" not in st.session_state:
    st.session_state.exclude_skipped = True
if "music_only" not in st.session_state:
    st.session_state.music_only = True
if "bb_top_n" not in st.session_state:
    st.session_state.bb_top_n = 50

# Sync widget keys from canonical values (first visit only)
if "settings_min_sec" not in st.session_state:
    st.session_state.settings_min_sec = st.session_state.min_ms // 1000
if "settings_skip" not in st.session_state:
    st.session_state.settings_skip = st.session_state.exclude_skipped
if "settings_music" not in st.session_state:
    st.session_state.settings_music = st.session_state.music_only
if "settings_bb_top_n_widget" not in st.session_state:
    st.session_state.settings_bb_top_n_widget = st.session_state.bb_top_n

# Track previous values for change detection
if "_prev_min_ms" not in st.session_state:
    st.session_state._prev_min_ms = st.session_state.min_ms
if "_prev_exclude_skipped" not in st.session_state:
    st.session_state._prev_exclude_skipped = st.session_state.exclude_skipped
if "_prev_music_only" not in st.session_state:
    st.session_state._prev_music_only = st.session_state.music_only
if "_prev_bb_top_n" not in st.session_state:
    st.session_state._prev_bb_top_n = st.session_state.bb_top_n

st.title("⚙️ 设置")

# ═══════════════════════════════════════════════════════════════════════════
# Data Filtering
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("数据过滤")
st.caption("应用于所有统计页面的数据过滤条件，修改后即时生效")

col1, col2, col3 = st.columns(3)

with col1:
    min_sec = st.selectbox(
        "最短播放时长",
        options=[0, 10, 30, 60, 120],
        index=2,
        format_func=lambda x: f"{x} 秒" if x > 0 else "不过滤",
        key="settings_min_sec",
        help="低于此值的播放不计入统计",
    )
    st.session_state.min_ms = min_sec * 1000

with col2:
    st.session_state.exclude_skipped = st.checkbox(
        "排除已跳过的播放",
        value=st.session_state.exclude_skipped,
        key="settings_skip",
        help="主动跳过的播放不计入排行和统计",
    )

with col3:
    st.session_state.music_only = st.checkbox(
        "仅音乐（排除播客/有声书）",
        value=st.session_state.music_only,
        key="settings_music",
        help="排除播客和有声书内容",
    )

# Detect data filter changes → clear caches and rerun
_filter_changed = False
if st.session_state.min_ms != st.session_state._prev_min_ms:
    st.session_state._prev_min_ms = st.session_state.min_ms
    _filter_changed = True
if st.session_state.exclude_skipped != st.session_state._prev_exclude_skipped:
    st.session_state._prev_exclude_skipped = st.session_state.exclude_skipped
    _filter_changed = True
if st.session_state.music_only != st.session_state._prev_music_only:
    st.session_state._prev_music_only = st.session_state.music_only
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

new_top_n = st.slider(
    "每周上榜歌曲数量 (Top N)",
    min_value=10,
    max_value=100,
    step=5,
    key="settings_bb_top_n_widget",
    help="每期 Billboard 周榜收录的歌曲数量上限",
)

# Detect changes and sync to canonical key
if new_top_n != st.session_state._prev_bb_top_n:
    st.session_state.bb_top_n = new_top_n
    st.session_state._prev_bb_top_n = new_top_n
    # Clear Billboard-related caches to force full recomputation on next visit
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
                result = import_data()
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
