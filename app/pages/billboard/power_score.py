"""Tab: 走势总榜 (Power Score Rankings) — 3 sub-tabs: 单曲/专辑/艺人."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .shared import (
    _bb_url,
    _render_bb_table,
    compute_power_scores,
    compute_album_power_scores,
    compute_artist_power_scores,
)


def render(weekly, weekly_album, weekly_artist, top_n, bb_album_top_n, bb_artist_top_n):
    st.subheader("⭐ 走势总榜")
    st.caption(
        "综合衡量最高排名、在榜周数、竞争强度（播放量相对当周大盘）、"
        "稳定性及冠军奖励的复合评分"
    )

    # Compute all three power score DataFrames
    power_df = compute_power_scores(weekly, top_n)
    album_power_df = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_df = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    ptabs = st.tabs(["🎵 歌曲走势", "💿 专辑走势", "🎤 艺人走势"])

    # ═════════════════════════════════════════════════════════════════════════
    # Sub-tab 0: Track Power Scores
    # ═════════════════════════════════════════════════════════════════════════
    with ptabs[0]:
        if power_df.empty:
            st.info("暂无足够数据计算歌曲走势评分")
        else:
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            with col_p1:
                st.metric("上榜歌曲数", f"{len(power_df):,}")
            with col_p2:
                top10_avg = power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{top10_avg:,.0f}")
            with col_p3:
                st.metric("最高 走势点数", f"{power_df.iloc[0]['power_score']:,}")
            with col_p4:
                no1_count = int((power_df["peak_position"] == 1).sum())
                st.metric("冠单数量", f"{no1_count}")

            st.divider()

            _ps_headers = ["#", "曲目", "艺人", "Power", "Peak", "Wks", "Top5", "#1 Wks"]
            _ps_rows = []
            for _i, _r in power_df.iterrows():
                _track_url = _bb_url(bb_nav="track", bb_id=_r['track_id'], bb_tab="🎵 单曲历史")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _ps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["track_name"])), _track_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top5"]),
                    str(_r["weeks_at_no1"]),
                ])
            _render_bb_table(_ps_headers, _ps_rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num", 7: "num"})

            st.divider()

            with st.expander("📐 走势点数 计算方式"):
                st.markdown(f"""
                **核心公式**：

                **1. 周基础分**（归一化到 rank ÷ Top N，保证调整 Top N 后分数可比）：
                - #1 = 200 分
                - Top 10%（排名 ≤ {int(top_n * 0.1)}）：200 × (0.75 − 2.5 × rank/N)，约 150 → 85 分
                - 10%−20%（排名 ≤ {int(top_n * 0.2)}）：85 × 0.85^(排名−{int(top_n * 0.1)})，约 72 → 40 分
                - 20%−100%：线性衰减至 1 分

                **2. 播放量加权**：，范围 1−4
                - 播放量 = 中位数 → ×1.0；2× 中位数 → ×2.0；8×+ 中位数 → ×4.0（上限）

                **3. 奖励**：Peak #1 +100 · #2 +50 · #3 +30 | 每在前五一周 +20 | 每在前十一周 +5

                **总分 {top_n} 首歌曲**，已从高到低排序
                """)

            st.subheader("Top 20 走势点数")
            top20 = power_df.head(20).iloc[::-1]
            fig_ps = px.bar(
                top20,
                x="power_score",
                y="track_name",
                orientation="h",
                hover_data=["artist_name", "peak_position", "weeks_on_chart"],
                labels={
                    "power_score": "走势点数",
                    "track_name": "",
                    "artist_name": "艺人",
                },
                height=600,
            )
            fig_ps.update_yaxes(autorange="reversed")
            fig_ps.update_traces(
                marker_color=top20["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_ps, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════════
    # Sub-tab 1: Album Power Scores
    # ═════════════════════════════════════════════════════════════════════════
    with ptabs[1]:
        if album_power_df.empty:
            st.info("暂无足够数据计算专辑走势评分")
        else:
            col_a1, col_a2, col_a3, col_a4 = st.columns(4)
            with col_a1:
                st.metric("上榜专辑数", f"{len(album_power_df):,}")
            with col_a2:
                a_top10_avg = album_power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{a_top10_avg:,.0f}")
            with col_a3:
                st.metric("最高 走势点数", f"{album_power_df.iloc[0]['power_score']:,}")
            with col_a4:
                a_no1_count = int((album_power_df["peak_position"] == 1).sum())
                st.metric("冠军专辑数", f"{a_no1_count}")

            st.divider()

            _aps_headers = ["#", "专辑", "艺人", "Power", "Peak", "Wks", "#1 Wks"]
            _aps_rows = []
            for _i, _r in album_power_df.iterrows():
                _album_url = _bb_url(bb_nav="album", bb_name=str(_r['album_name']), bb_art=str(_r['artist_name']), bb_tab="💿 专辑榜单")
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _aps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["album_name"])), _album_url),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top1"]),
                ])
            _render_bb_table(_aps_headers, _aps_rows,
                col_formats={0: "rank", 3: "num", 4: "num", 5: "num", 6: "num"})

            st.divider()

            st.subheader("Top 20 专辑 走势点数")
            top20_alb = album_power_df.head(20).iloc[::-1]
            fig_aps = px.bar(
                top20_alb,
                x="power_score",
                y="album_name",
                orientation="h",
                hover_data=["artist_name", "peak_position", "weeks_on_chart"],
                labels={"power_score": "走势点数", "album_name": "", "artist_name": "艺人"},
                height=600,
            )
            fig_aps.update_yaxes(autorange="reversed")
            fig_aps.update_traces(
                marker_color=top20_alb["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20_alb['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_aps, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════════
    # Sub-tab 2: Artist Power Scores
    # ═════════════════════════════════════════════════════════════════════════
    with ptabs[2]:
        if artist_power_df.empty:
            st.info("暂无足够数据计算艺人走势评分")
        else:
            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                st.metric("上榜艺人总数", f"{len(artist_power_df):,}")
            with col_r2:
                r_top10_avg = artist_power_df.head(10)["power_score"].mean()
                st.metric("Top 10 平均分", f"{r_top10_avg:,.0f}")
            with col_r3:
                st.metric("最高 走势点数", f"{artist_power_df.iloc[0]['power_score']:,}")
            with col_r4:
                r_no1_count = int((artist_power_df["peak_position"] == 1).sum())
                st.metric("冠军艺人人数", f"{r_no1_count}")

            st.divider()

            _rps_headers = ["#", "艺人", "Power", "Peak", "Wks", "#1 Wks"]
            _rps_rows = []
            for _i, _r in artist_power_df.iterrows():
                _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['artist_name']), bb_tab="🎤 艺人榜单")
                _rps_rows.append([
                    str(_i + 1),
                    (_html.escape(str(_r["artist_name"])), _artist_url),
                    f"{_r['power_score']:,.0f}",
                    str(_r["peak_position"]),
                    str(_r["weeks_on_chart"]),
                    str(_r["weeks_top1"]),
                ])
            _render_bb_table(_rps_headers, _rps_rows,
                col_formats={0: "rank", 2: "num", 3: "num", 4: "num", 5: "num"})

            st.divider()

            st.subheader("Top 20 艺人 走势点数")
            top20_art = artist_power_df.head(20).iloc[::-1]
            fig_rps = px.bar(
                top20_art,
                x="power_score",
                y="artist_name",
                orientation="h",
                hover_data=["peak_position", "weeks_on_chart"],
                labels={"power_score": "走势点数", "artist_name": ""},
                height=600,
            )
            fig_rps.update_yaxes(autorange="reversed")
            fig_rps.update_traces(
                marker_color=top20_art["power_score"].apply(
                    lambda x: f"rgba(184,134,11,{max(0.3, min(1, x / top20_art['power_score'].max()))})"
                )
            )
            st.plotly_chart(fig_rps, use_container_width=True)
