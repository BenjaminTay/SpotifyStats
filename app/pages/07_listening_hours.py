"""Listening hours analysis: DOW × Hour heatmap, trends, patterns."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.db import get_db, load_plays
from app.styles import inject_global_styles, page_header

inject_global_styles()

min_ms = st.session_state.get("min_ms", 30000)
music_only = st.session_state.get("music_only", True)
merge_enabled = st.session_state.get("merge_enabled", True)


@st.cache_data(ttl=3600)
def load_hours_data(_min_ms, _music_only, _merge_enabled):
    conn = get_db()
    df = load_plays(conn, join_albums=False, min_ms=_min_ms, music_only=_music_only, merge_enabled=_merge_enabled)
    conn.close()
    return df


df = load_hours_data(min_ms, music_only, merge_enabled)

dow_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
df["dow_label"] = df["ts_dow"].map(dow_names)

# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;margin-bottom:0.5rem;">'
        '<div style="font-size:2rem;margin-bottom:0.25rem;">⏰</div>'
        '<div style="font-size:1.05rem;font-weight:700;color:#2C2416;">时段分析</div>'
        f'<div style="font-size:0.7rem;color:#8B7355;margin-top:0.15rem;">最短={min_ms//1000}s</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    view = st.radio("视图", ["核心热力图", "逐年趋势", "周末vs工作日", "深夜听歌", "平台时段"])

hours = list(range(24))
hour_labels = [f"{h}:00" for h in hours]

# ── Core Heatmap ────────────────────────────────────────────────────
if view == "核心热力图":
    st.subheader("周几 × 小时 听歌热力图")

    heatmap_data = (
        df.groupby(["dow_label", "ts_hour"])
        .size()
        .reset_index(name="count")
    )
    pivot = heatmap_data.pivot(index="dow_label", columns="ts_hour", values="count").fillna(0)

    dow_order = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    pivot = pivot.reindex([d for d in dow_order if d in pivot.index])

    fig = px.imshow(
        pivot,
        labels={"x": "小时", "y": "", "color": "播放次数"},
        title="你是何时听歌的？",
        aspect="auto",
        color_continuous_scale="YlOrBr",
    )
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("颜色越深表示该时段播放次数越多。观察你的听歌高峰和低谷。")

    # Top 3 peak slots
    flat = heatmap_data.sort_values("count", ascending=False).head(3)
    st.subheader("听歌最高峰时段")
    cols = st.columns(3)
    for i, (_, row) in enumerate(flat.iterrows()):
        cols[i].metric(
            f"#{i+1}",
            f"{row['dow_label']} {row['ts_hour']}:00",
            delta=f"{row['count']:,} 次",
        )

# ── Yearly Trends ───────────────────────────────────────────────────
elif view == "逐年趋势":
    st.subheader("逐年各小时听歌趋势")

    years = sorted(df["ts_year"].unique().tolist())

    fig = go.Figure()
    for year in years:
        year_df = df[df["ts_year"] == year]
        hourly = year_df.groupby("ts_hour").size().reset_index(name="count")
        fig.add_trace(
            go.Scatter(
                x=hourly["ts_hour"],
                y=hourly["count"],
                mode="lines+markers",
                name=str(year),
            )
        )

    fig.update_layout(
        xaxis_title="小时",
        yaxis_title="播放次数",
        title="逐年各小时播放次数对比",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Which year had the most late-night listening?
    st.subheader("各年深夜听歌比例")
    late_night = df[df["ts_hour"].isin([23, 0, 1, 2, 3, 4, 5])]
    total_by_year = df.groupby("ts_year").size()
    late_by_year = late_night.groupby("ts_year").size()
    late_ratio = (late_by_year / total_by_year * 100).reset_index(name="ratio")
    late_ratio.columns = ["年份", "深夜比例(%)"]

    fig = px.bar(
        late_ratio,
        x="年份",
        y="深夜比例(%)",
        labels={"年份": "年份", "深夜比例(%)": "深夜听歌占比 (%)"},
        title="各年深夜 (23:00-5:00) 听歌比例",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Weekend vs Weekday ──────────────────────────────────────────────
elif view == "周末vs工作日":
    st.subheader("周末 vs 工作日 听歌模式对比")

    df["day_type"] = df["ts_dow"].apply(lambda d: "周末" if d >= 5 else "工作日")

    col1, col2 = st.columns(2)

    with col1:
        weekend_df = df[df["day_type"] == "周末"]
        weekend_hourly = weekend_df.groupby("ts_hour").size().reset_index(name="count")
        fig = px.bar(
            weekend_hourly,
            x="ts_hour",
            y="count",
            labels={"ts_hour": "小时", "count": "播放次数"},
            title="周末各小时播放分布",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        weekday_df = df[df["day_type"] == "工作日"]
        weekday_hourly = weekday_df.groupby("ts_hour").size().reset_index(name="count")
        fig = px.bar(
            weekday_hourly,
            x="ts_hour",
            y="count",
            labels={"ts_hour": "小时", "count": "播放次数"},
            title="工作日各小时播放分布",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Average hourly comparison
    st.subheader("时段对比")
    weekend_avg = weekend_df["ts_hour"].value_counts().mean()
    weekday_avg = weekday_df["ts_hour"].value_counts().mean()

    compare_hourly = pd.DataFrame({
        "小时": hour_labels,
        "周末": weekend_df.groupby("ts_hour").size().reindex(hours, fill_value=0).values,
        "工作日": weekday_df.groupby("ts_hour").size().reindex(hours, fill_value=0).values,
    })

    fig = px.line(
        compare_hourly,
        x="小时",
        y=["周末", "工作日"],
        labels={"value": "播放次数", "variable": "时段类型"},
        title="周末 vs 工作日 听歌曲线对比",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Late Night ──────────────────────────────────────────────────────
elif view == "深夜听歌":
    st.subheader("深夜听歌分析 (23:00 - 5:00)")

    late_night = df[df["ts_hour"].isin([23, 0, 1, 2, 3, 4, 5])]
    total_late = len(late_night)
    late_ratio = total_late / max(len(df), 1) * 100

    col1, col2 = st.columns(2)
    col1.metric("深夜播放次数", f"{total_late:,}")
    col2.metric("占总播放比例", f"{late_ratio:.1f}%")

    # Late night by month
    late_monthly = (
        late_night.groupby(["ts_year", "ts_month"]).size()
        / df.groupby(["ts_year", "ts_month"]).size()
        * 100
    ).reset_index(name="ratio")
    late_monthly["label"] = (
        late_monthly["ts_year"].astype(str)
        + "-"
        + late_monthly["ts_month"].astype(str).str.zfill(2)
    )

    fig = px.line(
        late_monthly,
        x="label",
        y="ratio",
        markers=True,
        labels={"label": "月份", "ratio": "深夜比例 (%)"},
        title="深夜听歌比例月度趋势",
    )
    fig.add_hline(
        y=late_ratio,
        line_dash="dash",
        line_color="red",
        annotation_text=f"平均 {late_ratio:.1f}%",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Late night hourly breakdown
    late_hourly = late_night.groupby("ts_hour").size().reset_index(name="count")
    late_hourly["hour_label"] = late_hourly["ts_hour"].apply(
        lambda h: f"{h}:00" if h >= 6 else f"凌晨{h}:00" if h < 6 else f"深夜{h}:00"
    )

    fig = px.bar(
        late_hourly,
        x="ts_hour",
        y="count",
        labels={"ts_hour": "小时", "count": "播放次数"},
        title="深夜各小时播放分布",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Platform by Hour ────────────────────────────────────────────────
elif view == "平台时段":
    st.subheader("各小时平台使用分布")

    platform_hourly = (
        df.groupby(["platform", "ts_hour"])
        .size()
        .reset_index(name="count")
    )

    fig = px.area(
        platform_hourly,
        x="ts_hour",
        y="count",
        color="platform",
        labels={"ts_hour": "小时", "count": "播放次数", "platform": "平台"},
        title="各小时平台使用堆叠图",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Platform preference by hour
    st.subheader("平台切换模式")

    # Normalize to percentage per hour
    hourly_total = platform_hourly.groupby("ts_hour")["count"].sum().reset_index()
    platform_pct = platform_hourly.merge(hourly_total, on="ts_hour", suffixes=("", "_total"))
    platform_pct["pct"] = platform_pct["count"] / platform_pct["count_total"] * 100

    fig = px.line(
        platform_pct,
        x="ts_hour",
        y="pct",
        color="platform",
        labels={"ts_hour": "小时", "pct": "占比 (%)", "platform": "平台"},
        title="各小时平台使用占比趋势",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Summary
    st.subheader("平台使用亮点")
    for platform in platform_hourly["platform"].unique():
        plat_df = platform_hourly[platform_hourly["platform"] == platform]
        if not plat_df.empty:
            peak = plat_df.loc[plat_df["count"].idxmax()]
            cols = st.columns(3)
            cols[0].metric(f"{platform} 使用高峰", f"{int(peak['ts_hour'])}:00")
            cols[1].metric(f"{platform} 高峰次数", f"{int(peak['count']):,}")
            cols[2].metric(
                f"{platform} 占比",
                f"{plat_df['count'].sum() / max(platform_hourly['count'].sum(), 1) * 100:.1f}%",
            )
