"""Global CSS injection for Spotify Stats — Vinyl Archive theme."""

import traceback
from contextlib import contextmanager

import streamlit as st


def inject_global_styles():
    st.markdown(
        """
<style>
/* ══════════════════════════════════════════════════════════════════════
   Vinyl Archive — Global Styles
   ══════════════════════════════════════════════════════════════════════ */

/* ── CSS Variables ───────────────────────────────────────────────── */
:root {
  --gold: #B8860B;
  --gold-light: #D4A84B;
  --gold-glow: rgba(184, 134, 11, 0.18);
  --brown: #8B4513;
  --brown-dark: #5C3D2E;
  --bg-page: #FBF8F4;
  --bg-card: #FFFFFF;
  --bg-sidebar: #F2ECE0;
  --bg-elevated: #FDF8EF;
  --bg-header: #F5EDDA;
  --text-primary: #2C2416;
  --text-secondary: #8B7355;
  --text-muted: #B0A08A;
  --border: rgba(139, 115, 85, 0.12);
  --border-gold: rgba(184, 134, 11, 0.25);
  --radius: 12px;
  --radius-sm: 8px;
  --shadow-sm: 0 1px 3px rgba(139, 69, 19, 0.06);
  --shadow-md: 0 2px 8px rgba(139, 69, 19, 0.10);
  --font-display: Georgia, "Times New Roman", serif;
  --font-body: "Palatino", "Book Antiqua", serif;
}

/* ── Noise texture overlay ───────────────────────────────────────── */
body::before {
  content: "";
  position: fixed;
  top: 0; left: 0; width: 100%; height: 100%;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.035;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(184, 134, 11, 0.20);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(184, 134, 11, 0.40); }

/* ── Body & Typography ───────────────────────────────────────────── */
body {
  color: var(--text-primary);
  font-family: var(--font-body);
}

h1, h2, h3 {
  font-family: var(--font-display) !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
  color: var(--text-primary) !important;
}

h1 { font-size: 1.75rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }

p, span, div {
  font-family: var(--font-body);
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #F2ECE0 0%, #EDE5D3 100%);
  border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stMetric {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
  box-shadow: var(--shadow-sm);
}

[data-testid="stSidebar"] [data-testid="stMetric"]:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
  transition: all 0.2s ease;
}

/* Sidebar nav items */
[data-testid="stSidebar"] a {
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
}

[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
  border-left: 3px solid var(--gold) !important;
  background: rgba(184, 134, 11, 0.06) !important;
}

/* ── Main content area ───────────────────────────────────────────── */
.main .block-container {
  padding-top: 2rem;
}

/* ── Metric / KPI Cards ──────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--gold);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
}

[data-testid="stMetric"]:hover {
  border-color: var(--border-gold);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

[data-testid="stMetric"] label {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.72rem !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
  font-family: var(--font-display) !important;
  font-size: 1.5rem !important;
  font-weight: 700 !important;
}

/* ── DataFrames ──────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

[data-testid="stDataFrame"] th {
  background: var(--bg-header) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  font-size: 0.68rem !important;
  font-weight: 600 !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 2px solid var(--border-gold) !important;
}

[data-testid="stDataFrame"] td {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
  border-bottom: 1px solid rgba(139, 115, 85, 0.06) !important;
}

[data-testid="stDataFrame"] tr:hover td {
  background: var(--bg-elevated) !important;
  transition: background 0.15s ease;
}

/* ── Select boxes & inputs ───────────────────────────────────────── */
[data-testid="stSelectbox"] > div,
[data-testid="stSlider"] > div,
.stTextInput > div {
  border-radius: var(--radius-sm) !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] {
  background: var(--bg-card) !important;
  border-color: var(--border) !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"]:hover {
  border-color: var(--border-gold) !important;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton > button {
  border-radius: var(--radius-sm) !important;
  font-family: var(--font-body) !important;
  font-weight: 600 !important;
  transition: all 0.2s ease !important;
}

.stButton > button[kind="primary"] {
  background: var(--gold) !important;
  border: none !important;
  color: #FFF !important;
}

.stButton > button[kind="primary"]:hover {
  background: var(--brown) !important;
  box-shadow: 0 2px 12px var(--gold-glow) !important;
  transform: translateY(-1px);
}

/* ── Radio / Checkbox ────────────────────────────────────────────── */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label {
  color: var(--text-primary) !important;
  font-family: var(--font-body) !important;
}

/* ── Dividers ────────────────────────────────────────────────────── */
hr, [data-testid="stDivider"] {
  border-color: var(--border-gold) !important;
}

/* ── Caption text ────────────────────────────────────────────────── */
.stCaption, .st-caption, small, caption {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
}

/* ── Plotly chart wrappers ───────────────────────────────────────── */
[data-testid="stPlotlyChart"] > div {
  background: transparent !important;
}

.js-plotly-plot .plotly .bg {
  fill: transparent !important;
}

/* ── Expander ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background: var(--bg-card) !important;
  box-shadow: var(--shadow-sm);
}

/* ── Tabs ────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 1px solid var(--border-gold) !important;
}

.stTabs [data-baseweb="tab"] {
  color: var(--text-secondary) !important;
  font-family: var(--font-body) !important;
  font-weight: 500;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color: var(--gold) !important;
  background: var(--bg-card) !important;
  border-bottom: 2px solid var(--gold) !important;
}

/* ── Success / Warning / Error ───────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--radius-sm) !important;
  font-family: var(--font-body) !important;
}

/* ── Tooltip ─────────────────────────────────────────────────────── */
[data-testid="stTooltip"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  box-shadow: var(--shadow-md) !important;
}

/* ── Container with border ───────────────────────────────────────── */
[data-testid="stContainer"] {
  border-color: var(--border) !important;
  border-radius: var(--radius) !important;
}

/* ── Progress bars ───────────────────────────────────────────────── */
.stProgress > div > div {
  background: var(--gold) !important;
}

/* ── Metric delta ────────────────────────────────────────────────── */
[data-testid="stMetricDelta"] {
  font-family: var(--font-body) !important;
}

/* ── Mobile tweaks ───────────────────────────────────────────────── */
@media (max-width: 768px) {
  [data-testid="stMetric"] {
    padding: 0.75rem 1rem;
  }
  [data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.15rem !important;
  }
}

/* ── Skeleton shimmer ─────────────────────────────────────────── */
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.skeleton-card {
  box-shadow: var(--shadow-sm);
}
</style>
""",
        unsafe_allow_html=True,
    )


def page_header(title: str, icon: str = "", description: str = ""):
    """Render a consistent page header with optional description."""
    display = f"{icon} {title}" if icon else title
    st.markdown(
        f"""
        <div style="margin-bottom:1.5rem;">
            <h1 style="margin:0;color:var(--text-primary);font-family:Georgia,serif;">{display}</h1>
            {f'<p style="margin:0.25rem 0 0;color:var(--text-secondary);font-size:0.85rem;">{description}</p>' if description else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(metrics: list[dict]):
    """Render a row of KPI cards. Each dict: {label, value, delta (optional)}."""
    cols = st.columns(len(metrics))
    for i, m in enumerate(metrics):
        with cols[i]:
            delta = m.get("delta")
            st.metric(label=m["label"], value=m["value"], delta=delta)


def filter_badge():
    """Show current filter settings as a styled badge row."""
    min_ms = st.session_state.get("min_ms", 30000)
    exclude = st.session_state.get("exclude_skipped", True)
    music = st.session_state.get("music_only", True)
    bb_n = st.session_state.get("bb_top_n", 30)
    bb_album_n = st.session_state.get("bb_album_top_n", 20)
    bb_artist_n = st.session_state.get("bb_artist_top_n", 20)

    badges = [
        f"最短 {min_ms // 1000}s",
        "跳过排除" if exclude else "跳过包含",
        "仅音乐" if music else "含播客",
        f"单曲 Top {bb_n}",
        f"专辑 Top {bb_album_n}",
        f"艺人 Top {bb_artist_n}",
    ]
    html = "".join(
        f'<span style="display:inline-block;background:var(--bg-card);border:1px solid var(--border-gold);'
        f'border-radius:20px;padding:0.2rem 0.75rem;font-size:0.7rem;color:var(--text-secondary);'
        f'margin-right:0.4rem;">{b}</span>'
        for b in badges
    )
    st.markdown(f'<div style="margin:0.5rem 0;">{html}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# Skeleton loading placeholders
# ═══════════════════════════════════════════════════════════════════════════

def render_skeleton(n: int = 3, height: str = "4rem"):
    """Render animated skeleton placeholder cards for loading states."""
    cards = ""
    for _ in range(n):
        cards += (
            f'<div class="skeleton-card" style="height:{height};border-radius:var(--radius);'
            f'background:linear-gradient(90deg,var(--bg-card) 25%,var(--bg-elevated) 50%,var(--bg-card) 75%);'
            f'background-size:200% 100%;animation:shimmer 1.5s infinite;'
            f'margin-bottom:0.75rem;border:1px solid var(--border);"></div>'
        )
    st.markdown(
        f"""<div>{cards}</div>""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Error boundary
# ═══════════════════════════════════════════════════════════════════════════

@contextmanager
def error_boundary(section_name: str = ""):
    """Catch and display errors with a styled message instead of crashing the page."""
    label = f"「{section_name}」" if section_name else "此模块"
    try:
        yield
    except Exception as e:
        st.error(
            f"加载{label}时发生错误：{e}",
        )
        with st.expander("错误详情"):
            st.code(traceback.format_exc())
