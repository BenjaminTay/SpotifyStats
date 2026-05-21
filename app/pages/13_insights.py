"""Fan tier analysis — listening-based tiers + Marquee promotion conversion."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


@st.cache_data(ttl=3600)
def load_insights_data():
    conn = get_db()

    # All artists ranked by listening time
    artist_listening = pd.read_sql_query(
        """SELECT a.artist_name,
                  COUNT(DISTINCT p.play_id) as play_count,
                  SUM(p.ms_played) / 3600000.0 as hours
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
           GROUP BY a.artist_name
           ORDER BY hours DESC""",
        conn,
    )

    # Marquee impressions
    marquee = pd.read_sql_query(
        "SELECT * FROM marquee_impressions", conn
    )

    # Marquee conversion with play stats
    marquee_conversion = pd.DataFrame()
    if not marquee.empty:
        marquee_conversion = pd.read_sql_query(
            """SELECT mi.artist_name, MAX(mi.segment) as segment,
                      COUNT(DISTINCT mi.id) as impressions,
                      COUNT(DISTINCT p.play_id) as actual_plays,
                      COALESCE(SUM(p.ms_played) / 3600000.0, 0) as actual_hours
               FROM marquee_impressions mi
               LEFT JOIN artists a ON mi.artist_name = a.artist_name
               LEFT JOIN tracks t ON t.artist_id = a.artist_id
               LEFT JOIN plays p ON p.track_id = t.track_id
               GROUP BY mi.artist_name
               ORDER BY impressions DESC""",
            conn,
        )

    conn.close()

    has_data = not artist_listening.empty
    return {
        "has_data": has_data,
        "artist_listening": artist_listening,
        "marquee": marquee,
        "marquee_conversion": marquee_conversion,
    }


TIER_COLORS = {
    "super": "#B8860B",
    "regular": "#7D8C4E",
    "casual": "#8B7355",
}

TIER_LABELS = {
    "super": "超级听众 🔥",
    "regular": "普通听众 🎧",
    "casual": "轻度听众 💡",
}

SUPER_N = 5
REGULAR_N = 10


def _tier_tag(tier: str) -> str:
    c = TIER_COLORS.get(tier, "#8B7355")
    label = TIER_LABELS.get(tier, tier)
    return f'<span style="display:inline-block;background:{c}15;border:1px solid {c}40;border-radius:12px;padding:0.1rem 0.55rem;font-size:0.68rem;color:{c};">{label}</span>'


def classify_tier(row, total_artists):
    """Assign tier based on rank position."""
    rank = row.name  # 0-indexed position
    if rank < SUPER_N:
        return "super"
    elif rank < SUPER_N + REGULAR_N:
        return "regular"
    else:
        return "casual"


def render():
    data = load_insights_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    page_header("音乐画像", description="听众类型 · 推广转化")

    artist_df = data["artist_listening"]
    total_artists = len(artist_df)
    total_hours = artist_df["hours"].sum()

    # Classify tiers
    artist_df["tier"] = [classify_tier(row, total_artists) for _, row in artist_df.iterrows()]

    super_df = artist_df[artist_df["tier"] == "super"]
    regular_df = artist_df[artist_df["tier"] == "regular"]
    casual_df = artist_df[artist_df["tier"] == "casual"]

    # ── KPI Row ─────────────────────────────────────────────────────────
    kpi_row([
        {"label": "超级听众", "value": f"{len(super_df)} 位"},
        {"label": "普通听众", "value": f"{len(regular_df)} 位"},
        {"label": "轻度听众", "value": f"{len(casual_df)} 位"},
        {"label": "总收听时长", "value": f"{total_hours:,.0f} 小时"},
    ])

    # ── Tier breakdown chart ─────────────────────────────────────────────
    tier_hours = artist_df.groupby("tier")["hours"].sum()
    tier_order = ["super", "regular", "casual"]
    tier_hours = tier_hours.reindex(tier_order).fillna(0)
    tier_colors = [TIER_COLORS[t] for t in tier_order]

    col_a, col_b = st.columns(2)

    with col_a:
        fig_pie = go.Figure()
        fig_pie.add_trace(go.Pie(
            labels=[TIER_LABELS.get(t, t) for t in tier_order],
            values=[tier_hours[t] for t in tier_order],
            marker={"colors": tier_colors},
            textinfo="label+percent",
            hole=0.4,
        ))
        fig_pie.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_pie.update_layout(height=320, title="收听时长分布")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        tier_counts = artist_df.groupby("tier").size().reindex(tier_order).fillna(0)
        fig_bar = px.bar(
            x=[TIER_LABELS.get(t, t) for t in tier_order],
            y=[tier_counts[t] for t in tier_order],
            color=[TIER_LABELS.get(t, t) for t in tier_order],
            color_discrete_map={TIER_LABELS.get(t, t): TIER_COLORS[t] for t in tier_order},
            labels={"x": "", "y": "艺人数量"},
        )
        fig_bar.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_bar.update_layout(height=320, title="各层艺人数量", showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Super fans ──────────────────────────────────────────────────────
    st.markdown("### 🔥 超级听众")
    st.caption(f"收听时长最高的 {SUPER_N} 位艺人")

    cols = st.columns(min(SUPER_N, len(super_df)))
    for i, (_, row) in enumerate(super_df.iterrows()):
        with cols[i]:
            pct = (row["hours"] / total_hours * 100) if total_hours > 0 else 0
            st.markdown(
                f"""<div style="background:var(--bg-card);border:1px solid var(--border-gold);
                border-radius:var(--radius);padding:1rem;text-align:center;height:100%;">
                <div style="font-size:1.3rem;font-weight:700;color:var(--gold);">{row['artist_name']}</div>
                <div style="font-size:1.8rem;font-weight:900;color:var(--text-primary);margin:0.5rem 0;">{row['hours']:.1f}h</div>
                <div style="font-size:0.75rem;color:var(--text-secondary);">{row['play_count']} 次 · {pct:.1f}%</div>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Regular listeners ───────────────────────────────────────────────
    if not regular_df.empty:
        st.markdown("### 🎧 普通听众")
        st.caption(f"收听时长第 {SUPER_N + 1}–{SUPER_N + len(regular_df)} 位")

        # Show as a compact horizontal bar
        fig_reg = px.bar(
            regular_df.sort_values("hours", ascending=True),
            x="hours", y="artist_name", orientation="h",
            color_discrete_sequence=[TIER_COLORS["regular"]],
            labels={"hours": "小时", "artist_name": ""},
            height=max(250, len(regular_df) * 25),
        )
        fig_reg.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_reg.update_layout(title="")
        st.plotly_chart(fig_reg, use_container_width=True)

    # ── Marquee analysis ────────────────────────────────────────────────
    marquee = data["marquee"]
    mc = data["marquee_conversion"]

    if not marquee.empty and not mc.empty:
        st.divider()
        st.markdown("### 📢 推广分析")
        st.caption("Spotify Marquee 推广给你的艺人，与你实际收听行为的对照")

        # Merge marquee conversion with artist tier
        artist_tier_map = artist_df.set_index("artist_name")["tier"].to_dict()
        mc["tier"] = mc["artist_name"].map(artist_tier_map).fillna("none")
        mc["has_played"] = mc["actual_plays"] > 0

        tier_display_order = ["super", "regular", "casual", "none"]
        mc["tier_order"] = mc["tier"].apply(
            lambda t: tier_display_order.index(t) if t in tier_display_order else 99
        )
        mc_show = mc.sort_values(["tier_order", "impressions"], ascending=[True, False])

        # Summary KPIs
        total_promoted = len(mc)
        converted = int(mc["has_played"].sum())
        super_converted = int(mc[mc["tier"] == "super"]["has_played"].sum())

        kpi_row([
            {"label": "推广艺人", "value": str(total_promoted)},
            {"label": "有收听", "value": f"{converted} 位"},
            {"label": "转化率", "value": f"{converted / max(total_promoted, 1) * 100:.0f}%"},
            {"label": "已成超级听众", "value": f"{super_converted} 位"},
        ])

        # Bar chart: promoted artists with tier coloring
        mc_bar = mc_show.copy()
        mc_bar["label"] = mc_bar.apply(
            lambda r: f"{r['artist_name']} ({r['actual_hours']:.0f}h)" if r["actual_hours"] > 0 else r["artist_name"],
            axis=1,
        )

        fig_mc = px.bar(
            mc_bar.sort_values("impressions", ascending=True).tail(25),
            x="impressions", y="artist_name", orientation="h",
            color="tier",
            color_discrete_map={
                "super": TIER_COLORS["super"],
                "regular": TIER_COLORS["regular"],
                "casual": TIER_COLORS["casual"],
                "none": "#CCCCCC",
            },
            labels={"impressions": "推广展示次数", "artist_name": ""},
            hover_data=["actual_plays", "actual_hours"],
            height=500,
        )
        fig_mc.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_mc.update_layout(title="推广艺人 × 你的听众类型", showlegend=True)
        st.plotly_chart(fig_mc, use_container_width=True)

        # Detail table
        with st.expander("查看全部推广艺人详情"):
            display_df = mc_show.copy()
            display_df = display_df.rename(columns={
                "artist_name": "艺人",
                "segment": "推广分群",
                "impressions": "展示次数",
                "actual_plays": "实际播放",
                "actual_hours": "收听小时",
            })
            display_df["听众类型"] = display_df["tier"].map(TIER_LABELS)
            display_df["转化"] = display_df["实际播放"].apply(lambda x: "✅" if x > 0 else "❌")
            st.dataframe(
                display_df[["艺人", "听众类型", "展示次数", "实际播放", "收听小时", "转化"]],
                use_container_width=True,
                hide_index=True,
            )
    elif not marquee.empty:
        st.divider()
        st.markdown("### 📢 推广数据")
        st.caption(f"共有 {len(marquee)} 条 Marquee 推广展示，但暂未与播放数据关联")
        seg_counts = marquee["segment"].value_counts()
        fig_pie = px.pie(
            values=seg_counts.values, names=seg_counts.index,
            color_discrete_sequence=COLORS,
        )
        fig_pie.update_layout(**PLOTLY_TEMPLATE["layout"])
        fig_pie.update_layout(height=300, title="推广分群分布")
        st.plotly_chart(fig_pie, use_container_width=True)
