"""Billboard 周榜 — entry point, delegates to app.pages.billboard package."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from app.styles import inject_global_styles

inject_global_styles()

from app.pages.billboard import run  # noqa: E402
run()
