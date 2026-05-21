"""Tab: 单曲历史 (Track Chart History)."""

import html as _html
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .shared import _bb_url, _render_bb_table, compute_power_scores


def render(weekly, track_summary, top_n, all_weeks_str, all_weeks_desc):
    # Build track options sorted by peak DESC, weeks DESC
    track_options = track_summary.sort_values(
        ["peak_position", "weeks_on_chart"], ascending=[True, False]
    )

    # ── Search box ────────────────────────────────────────────────────
    search_term = st.text_input(
        "搜索曲目/艺人/专辑",
        placeholder="输入关键词筛选...",
        key="bb_track_search",
    )

    if search_term:
        term = search_term.lower()
        mask = (
            track_options["track_name"].str.lower().str.contains(term, na=False)
            | track_options["artist_name"].str.lower().str.contains(term, na=False)
            | track_options["album_name"].str.lower().str.contains(term, na=False)
        )
        filtered_options = track_options[mask].reset_index(drop=True)
    else:
        filtered_options = track_options.reset_index(drop=True)

    if filtered_options.empty:
        st.warning(f"没有匹配「{search_term}」的曲目")
    else:
        # Determine default index from session_state cross-tab nav
        default_idx = 0
        if st.session_state.bb_selected_track_id is not None:
            sel_id = st.session_state.bb_selected_track_id
            matches = filtered_options[filtered_options["track_id"] == sel_id]
            if not matches.empty:
                default_idx = int(matches.index[0])
                st.session_state.bb_selected_track_id = None
            else:
                # Track hidden by search filter — clear search and retry
                st.session_state.bb_track_search = ""
                st.rerun()

        track_labels = [
            f"{t['track_name']} — {t['artist_name']}  (Peak #{t['peak_position']}, {t['weeks_on_chart']}wks)"
            for _, t in filtered_options.iterrows()
        ]
        track_ids = filtered_options["track_id"].tolist()

        selected_track_idx = st.selectbox(
            "选择曲目",
            options=range(len(track_labels)),
            format_func=lambda i: track_labels[i],
            index=min(default_idx, len(track_labels) - 1),
        )
        selected_tid = track_ids[selected_track_idx]

        # Track history data
        track_hist = weekly[weekly["track_id"] == selected_tid].sort_values("billboard_week")
        ts_row = track_summary[track_summary["track_id"] == selected_tid].iloc[0]

        # ── Power Score ────────────────────────────────────────────────
        track_power_df = compute_power_scores(weekly, top_n)
        track_power_df = track_power_df.reset_index(drop=True)
        track_power_df.index = track_power_df.index + 1
        tp_row = track_power_df[track_power_df["track_id"] == selected_tid]
        power_score = int(tp_row.iloc[0]["power_score"]) if not tp_row.empty else 0
        power_rank = str(int(tp_row.iloc[0].name)) if not tp_row.empty else "—"

        # ── Summary Cards ─────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        peak_str = f"#{ts_row['peak_position']}"
        if ts_row["weeks_at_peak"] > 1:
            peak_str += f" ({ts_row['weeks_at_peak']}wks)"
        col1.metric("最高排名", peak_str)
        col2.metric("进榜周数", f"{ts_row['weeks_on_chart']} 周")
        col3.metric("首次入榜", str(ts_row["first_week"]))
        first_peak_str = str(ts_row["first_peak_week"]) if pd.notna(ts_row["first_peak_week"]) else "—"
        col4.metric("首次 Peak 周", first_peak_str)

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("总上榜播放", f"{int(ts_row['total_chart_plays']):,}")
        col6.metric("总播放次数", f"{int(ts_row['total_plays']):,}")
        col7.metric("走势点数", f"{power_score:,}")
        col8.metric("走势排名", f"#{power_rank}")

        st.divider()

        # ── History Table ─────────────────────────────────────────────
        st.subheader("榜单历史")

        track_hist_display = track_hist.copy()
        track_hist_display["prev_rank"] = track_hist_display["rank"].shift(1)
        track_hist_display["prev_week"] = track_hist_display["billboard_week"].shift(1)
        changes = []
        for _, r in track_hist_display.iterrows():
            p = r["prev_rank"]
            prev_wk = r["prev_week"]
            cur_wk = r["billboard_week"]
            cur = r["rank"]
            if pd.isna(p):
                changes.append("NEW")
            elif pd.notna(prev_wk) and (cur_wk - prev_wk).days > 8:
                changes.append("RE")
            else:
                diff = int(p) - int(cur)
                if diff > 0:
                    changes.append(f"▲{diff}")
                elif diff < 0:
                    changes.append(f"▼{abs(diff)}")
                else:
                    changes.append("─")
        track_hist_display["Change"] = changes

        display_hist = track_hist_display[["billboard_week", "rank", "play_count", "Change"]].copy()
        display_hist.columns = ["周", "排名", "播放次数", "升降"]

        _th_headers = ["周", "排名", "播放次数", "升降"]
        _th_rows = []
        for _, _r in display_hist.iterrows():
            _th_rows.append([
                (_html.escape(str(_r["周"])), _bb_url(bb_nav="week", bb_date=_r['周'], bb_tab="📋 周榜")),
                str(_r["排名"]),
                f"{int(_r['播放次数']):,}",
                _html.escape(str(_r["升降"])),
            ])
        _render_bb_table(_th_headers, _th_rows, col_formats={1: "num", 2: "num"})

        # ── Rank Trend Chart (gapped) ─────────────────────────────────
        st.subheader("排名趋势")

        chart_data = track_hist[["billboard_week", "rank", "play_count"]].copy()
        chart_data["week_num"] = pd.to_datetime(chart_data["billboard_week"])

        x_vals = []
        y_vals = []
        texts = []
        for i, (_, row) in enumerate(chart_data.iterrows()):
            if i > 0:
                gap_days = (row["week_num"] - chart_data.iloc[i - 1]["week_num"]).days
                if gap_days > 9:
                    x_vals.append(None)
                    y_vals.append(None)
                    texts.append(None)
            x_vals.append(row["week_num"])
            y_vals.append(row["rank"])
            texts.append(f"#{row['rank']} · {row['play_count']}次")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                name=filtered_options.iloc[selected_track_idx]["track_name"],
                line=dict(color="#B8860B", width=2),
                marker=dict(size=7, color="#B8860B"),
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                connectgaps=False,
            )
        )

        fig.add_hline(
            y=top_n,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"榜单边界 (Top {top_n})",
        )

        fig.add_hline(
            y=ts_row["peak_position"],
            line_dash="dot",
            line_color="#B8860B",
            annotation_text=f"Peak #{ts_row['peak_position']}",
        )

        fig.update_yaxes(autorange="reversed", title="排名", range=[top_n + 1, 1])
        fig.update_xaxes(title="周")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
