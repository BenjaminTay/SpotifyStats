"""Global CSS injection for Spotify Stats — Neon Vinyl theme."""

import streamlit as st


def inject_global_styles():
    st.markdown(
        """
<style>
/* ══════════════════════════════════════════════════════════════════════
   Neon Vinyl — Global Styles
   ══════════════════════════════════════════════════════════════════════ */

/* ── CSS Variables ───────────────────────────────────────────────── */
:root {
  --green: #1DB954;
  --green-glow: rgba(29, 185, 84, 0.35);
  --green-dim: rgba(29, 185, 84, 0.12);
  --coral: #FF6B6B;
  --gold: #FFD93D;
  --teal: #4ECDC4;
  --purple: #A78BFA;
  --bg-deep: #0A0A0F;
  --bg-card: #12121A;
  --bg-elevated: #181825;
  --text-primary: #F0F0F5;
  --text-secondary: #8888A0;
  --border: rgba(255, 255, 255, 0.06);
  --radius: 12px;
  --radius-sm: 8px;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(29, 185, 84, 0.25);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(29, 185, 84, 0.45); }

/* ── Body & Typography ───────────────────────────────────────────── */
body {
  color: var(--text-primary);
}

h1, h2, h3 {
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
}

h1 { font-size: 1.75rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D0D18 0%, #0A0A0F 100%);
  border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stMetric {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
}

/* ── Main content area ───────────────────────────────────────────── */
.main .block-container {
  padding-top: 2rem;
}

/* ── Metric / KPI Cards ──────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

[data-testid="stMetric"]:hover {
  border-color: rgba(29, 185, 84, 0.3);
  box-shadow: 0 0 20px var(--green-dim);
}

[data-testid="stMetric"] label {
  color: var(--text-secondary) !important;
  font-size: 0.75rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--text-primary) !important;
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
  background: var(--bg-elevated) !important;
  color: var(--text-secondary) !important;
  font-size: 0.7rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border) !important;
}

[data-testid="stDataFrame"] td {
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  border-bottom: 1px solid rgba(255,255,255,0.03) !important;
}

[data-testid="stDataFrame"] tr:hover td {
  background: var(--bg-elevated) !important;
}

/* ── Select boxes & inputs ────────────────────────────────────────── */
[data-testid="stSelectbox"] > div,
[data-testid="stSlider"] > div,
.stTextInput > div {
  border-radius: var(--radius-sm) !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"] {
  background: var(--bg-card) !important;
  border-color: var(--border) !important;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
.stButton > button {
  border-radius: var(--radius-sm) !important;
  font-weight: 600 !important;
  transition: all 0.2s ease !important;
}

.stButton > button[kind="primary"] {
  background: var(--green) !important;
  border: none !important;
  color: #000 !important;
}

.stButton > button[kind="primary"]:hover {
  box-shadow: 0 0 24px var(--green-glow) !important;
  transform: translateY(-1px);
}

/* ── Radio / Checkbox ─────────────────────────────────────────────── */
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label {
  color: var(--text-primary) !important;
}

/* ── Dividers ─────────────────────────────────────────────────────── */
hr, [data-testid="stDivider"] {
  border-color: var(--border) !important;
}

/* ── Caption text ─────────────────────────────────────────────────── */
.stCaption, .st-caption, small {
  color: var(--text-secondary) !important;
}

/* ── Plotly chart wrappers ────────────────────────────────────────── */
[data-testid="stPlotlyChart"] > div {
  background: transparent !important;
}

.js-plotly-plot .plotly .bg {
  fill: transparent !important;
}

/* ── Expander ─────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background: var(--bg-card) !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0;
  border-bottom: 1px solid var(--border) !important;
}

.stTabs [data-baseweb="tab"] {
  color: var(--text-secondary) !important;
  font-weight: 500;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color: var(--green) !important;
  background: var(--bg-card) !important;
}

/* ── Success / Warning / Error ────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--radius-sm) !important;
}

/* ── Tooltip ──────────────────────────────────────────────────────── */
[data-testid="stTooltip"] {
  background: var(--bg-elevated) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
}

/* ── Mobile tweaks ────────────────────────────────────────────────── */
@media (max-width: 768px) {
  [data-testid="stMetric"] {
    padding: 0.75rem 1rem;
  }
  [data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.15rem !important;
  }
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
            <h1 style="margin:0;color:var(--text-primary);">{display}</h1>
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
    bb_n = st.session_state.get("bb_top_n", 50)

    badges = [
        f"最短 {min_ms // 1000}s",
        "跳过排除" if exclude else "跳过包含",
        "仅音乐" if music else "含播客",
        f"Billboard Top {bb_n}",
    ]
    html = "".join(
        f'<span style="display:inline-block;background:var(--bg-elevated);border:1px solid var(--border);'
        f'border-radius:20px;padding:0.2rem 0.75rem;font-size:0.7rem;color:var(--text-secondary);'
        f'margin-right:0.4rem;">{b}</span>'
        for b in badges
    )
    st.markdown(f'<div style="margin:0.5rem 0;">{html}</div>', unsafe_allow_html=True)
