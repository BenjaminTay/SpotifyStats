"""播放分析 — 时间线 / 排行榜 / 行为分析 / 听歌时段 / 艺人深潜."""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()


def _load_module(filename):
    """Load a page module by filename, handling numeric-prefixed names."""
    path = os.path.join(os.path.dirname(__file__), filename)
    name = filename.replace(".py", "").lstrip("0123456789_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tab1, tab2, tab3, tab4, tab5 = st.tabs(["时间线", "排行榜", "行为分析", "听歌时段", "艺人深潜"])

with tab1:
    m = _load_module("02_timeline.py")
    m.render()

with tab2:
    m = _load_module("03_leaderboard.py")
    m.render()

with tab3:
    m = _load_module("04_behavior.py")
    m.render()

with tab4:
    m = _load_module("07_listening_hours.py")
    m.render()

with tab5:
    m = _load_module("06_artist_deep.py")
    m.render()
