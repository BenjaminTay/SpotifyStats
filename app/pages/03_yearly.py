"""年度回顾 — 自定义年度总结 / Wrapped 2025 官方."""

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


tab1, tab2 = st.tabs(["年度总结", "Wrapped 2025"])

with tab1:
    m = _load_module("05_wrapped.py")
    m.render()

with tab2:
    m = _load_module("10_wrapped_hub.py")
    m.render()
