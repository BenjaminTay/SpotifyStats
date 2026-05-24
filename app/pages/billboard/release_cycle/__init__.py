"""发行周期分析 — 主入口，委派至子视图."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

import streamlit as st

from app.pages.billboard.release_cycle.shared import load_artist_list
from app.pages.billboard.release_cycle.artist_view import render_artist_overview
from app.pages.billboard.release_cycle.album_view import render_album_detail
from app.pages.billboard.release_cycle.compare_view import render_compare_view


def run(df_raw, weekly, weekly_artist, weekly_album):
    """渲染发行周期分析 Tab。

    由 08_billboard.py 在「发行周期」Tab 条件下调用，
    传入已加载的 df_raw 和预计算的 weekly 数据。
    """
    # ── Session state 初始化 ──────────────────────────────────────────
    if "rc_view" not in st.session_state:
        st.session_state.rc_view = "artist"
    if "rc_selected_album" not in st.session_state:
        st.session_state.rc_selected_album = None
    if "rc_compare_queue" not in st.session_state:
        st.session_state.rc_compare_queue = []
    if "rc_artist_search" not in st.session_state:
        st.session_state.rc_artist_search = ""

    # ── 艺人选择器 ────────────────────────────────────────────────────
    artist_list = load_artist_list(df_raw)

    if not artist_list:
        st.warning("当前过滤条件下无艺人数据。")
        return

    col_search, col_select = st.columns([1, 2])
    with col_search:
        search_term = st.text_input(
            "搜索艺人",
            placeholder="输入艺人名筛选...",
            key="rc_artist_search",
        )

    if search_term:
        term = search_term.lower()
        filtered = [a for a in artist_list if term in a.lower()]
    else:
        filtered = artist_list

    if not filtered:
        st.warning(f"没有匹配「{search_term}」的艺人")
        return

    with col_select:
        selected_artist = st.selectbox(
            "选择艺人",
            options=filtered,
            key="rc_artist_selector",
        )

    if not selected_artist:
        return

    # 艺人切换时重置视图
    if "rc_last_artist" not in st.session_state:
        st.session_state.rc_last_artist = selected_artist
    if st.session_state.rc_last_artist != selected_artist:
        st.session_state.rc_view = "artist"
        st.session_state.rc_selected_album = None
        st.session_state.rc_last_artist = selected_artist

    st.divider()

    # ── 视图路由 ──────────────────────────────────────────────────────
    view = st.session_state.rc_view

    if view == "artist":
        render_artist_overview(selected_artist, df_raw, weekly, weekly_artist, weekly_album)

    elif view == "album":
        album = st.session_state.rc_selected_album
        if album:
            render_album_detail(selected_artist, album, df_raw, weekly_artist, weekly_album, weekly)
        else:
            st.warning("未选择专辑，请从艺人总览中选择。")
            st.session_state.rc_view = "artist"
            st.rerun()

    elif view == "compare":
        render_compare_view(df_raw, weekly_artist, weekly_album)
