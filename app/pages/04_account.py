"""账号中心 — 音乐库 / 搜索 / 画像 / 播客 / 视频 / 个人档案."""

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


tab1, tab2, tab3, tab4, tab5 = st.tabs(["音乐库", "音乐画像", "播客专区", "视频分析", "个人档案"])

with tab1:
    m = _load_module("11_library.py")
    m.render()

with tab2:
    m = _load_module("13_insights.py")
    m.render()

with tab3:
    m = _load_module("14_podcast.py")
    m.render()

with tab4:
    m = _load_module("15_video.py")
    m.render()

with tab5:
    m = _load_module("16_profile.py")
    m.render()
