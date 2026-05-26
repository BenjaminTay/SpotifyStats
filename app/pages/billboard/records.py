"""Tab: 榜单记录 (Billboard Records & Milestones)."""

import html as _html
import streamlit as st
import pandas as pd

from .shared import _bb_url, _render_bb_table, _render_record_table


def render(records):
    st.subheader("🏅 榜单历史记录")

    # ── Highlight Cards ─────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;color:#8B7355;margin-bottom:0.5rem;">'
        '里程碑纪录</div>',
        unsafe_allow_html=True,
    )

    highlight_cards = []

    # Card 1: Artist domination record (full chart)
    if "artist_simul" in records:
        dom_best = records["artist_simul"]
        highlight_cards.append({
            "emoji": "👑",
            "value": f"全榜 {dom_best['count']} 首",
            "label": "艺人霸榜纪录",
            "detail": f"{dom_best['artist']} · {dom_best['week']}",
        })

    # Card 2: Longest charting
    if "longest_charting" in records and len(records["longest_charting"]) > 0:
        lc = records["longest_charting"].iloc[0]
        highlight_cards.append({
            "emoji": "⏳",
            "value": f"{int(lc['weeks_on_chart'])} 周",
            "label": "最長在榜歌曲",
            "detail": f"{lc['track_name']} — {lc['artist_name']}",
        })

    # Card 3: Biggest jump
    if "biggest_jump" in records and len(records["biggest_jump"]) > 0:
        bj = records["biggest_jump"].iloc[0]
        highlight_cards.append({
            "emoji": "🚀",
            "value": f"#{int(bj['上周排名'])} → #{int(bj['本周排名'])}",
            "label": "最大排名跃升",
            "detail": f"{bj['track_name']} — {bj['artist_name']}",
        })

    # Card 4: Most #1s artist
    if "artist_most_no1" in records and len(records["artist_most_no1"]) > 0:
        an1 = records["artist_most_no1"].iloc[0]
        highlight_cards.append({
            "emoji": "🏆",
            "value": f"{int(an1['冠单数'])} 首冠单",
            "label": "最多冠单艺人",
            "detail": an1["artist_name"],
        })

    if highlight_cards:
        cols = st.columns(len(highlight_cards))
        for i, card in enumerate(highlight_cards):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background:#FFFFFF;border-left:3px solid #B8860B;border-radius:12px;
                                padding:1rem 1.2rem;box-shadow:0 1px 3px rgba(139,69,19,0.08);">
                        <div style="font-size:1.6rem;margin-bottom:0.3rem;">{card['emoji']}</div>
                        <div style="font-size:1.2rem;font-weight:700;color:#B8860B;font-family:Georgia,serif;">
                            {card['value']}</div>
                        <div style="font-size:0.7rem;color:#8B7355;text-transform:uppercase;letter-spacing:0.06em;
                                    margin-top:0.2rem;">{card['label']}</div>
                        <div style="font-size:0.78rem;color:#2C2416;margin-top:0.3rem;line-height:1.3;">
                            {card['detail']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Section 1: 霸榜记录 (Domination) ─────────────────────────────────
    st.subheader("👑 艺人霸榜记录")
    st.caption("单周同一艺人在全榜占据的席位数纪录")

    if "artist_simul" in records:
        rec = records["artist_simul"]
        st.markdown(
            f"**最高纪录：{rec['artist']}** 在 {rec['week']} 周 "
            f"同时有 **{rec['count']}** 首歌曲在榜"
        )
    if "artist_simul_list" in records and len(records["artist_simul_list"]) > 0:
        _render_record_table(records["artist_simul_list"], link_col_map={"billboard_week": "week", "artist_name": "artist"})
    else:
        st.info("暂无数据")

    st.divider()

    # ── Section 2: 冠单记录 ──────────────────────────────────────────────
    st.subheader("👑 冠单里程碑")

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**最多冠单艺人**")
        if "artist_most_no1" in records and len(records["artist_most_no1"]) > 0:
            _render_record_table(records["artist_most_no1"], link_col_map={"artist_name": "artist"})
        else:
            st.info("暂无数据")

    with col_b:
        st.markdown("**空降冠军歌曲**")
        if "debut_no1" in records and len(records["debut_no1"]) > 0:
            _render_record_table(records["debut_no1"], link_col_map={"track_name": "track", "artist_name": "artist", "first_week": "week"}, drop_cols=["track_id"])
            st.caption(f"共 {len(records['debut_no1'])} 首歌曲首周即登顶")
        else:
            st.info("暂无空降冠军歌曲")

    st.markdown("**回冠歌曲（跌出 #1 后再度登顶）**")
    if "return_to_no1" in records and len(records["return_to_no1"]) > 0:
        _render_record_table(records["return_to_no1"], link_col_map={"track_name": "track", "artist_name": "artist", "首次冠单": "week", "回冠日期": "week"}, drop_cols=["track_id"])
        st.caption(f"共 {len(records['return_to_no1'])} 次回冠记录")
    else:
        st.info("暂无回冠记录")

    st.divider()

    # ── Section 3: 在榜耐力 ──────────────────────────────────────────────
    st.subheader("⏳ 在榜耐力记录")

    long_tabs = st.tabs(["最長在榜 Top 20", "未进 Top 10 遗珠", "最长连续在榜"])
    with long_tabs[0]:
        if "longest_charting" in records and len(records["longest_charting"]) > 0:
            _render_record_table(records["longest_charting"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")
    with long_tabs[1]:
        if "longest_no_top10" in records and len(records["longest_no_top10"]) > 0:
            _render_record_table(records["longest_no_top10"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
            st.caption("这些歌曲虽从未进入前 10，但长期保持在榜——真正的 '慢热型' 选手")
        else:
            st.info("暂无数据")
    with long_tabs[2]:
        if "longest_streak" in records and len(records["longest_streak"]) > 0:
            _render_record_table(records["longest_streak"], link_col_map={"track_name": "track", "artist_name": "artist", "起始周": "week", "结束周": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    st.divider()

    # ── Section 4: 排名跃升 ──────────────────────────────────────────────
    st.subheader("📈 排名跃升记录")

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("**单周最大跃升 Top 15**")
        if "biggest_jump" in records and len(records["biggest_jump"]) > 0:
            _bj_df = records["biggest_jump"].rename(columns={"变化": "上升位数"})
            _render_record_table(_bj_df, link_col_map={"track_name": "track", "artist_name": "artist", "日期": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    with col_d:
        st.markdown("**单周最大跌幅 Top 15**")
        if "biggest_drop" in records and len(records["biggest_drop"]) > 0:
            _bd_df = records["biggest_drop"].rename(columns={"变化": "下跌位数"})
            _render_record_table(_bd_df, link_col_map={"track_name": "track", "artist_name": "artist", "日期": "week"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    st.divider()

    # ── Section 5: 专辑霸榜 ──────────────────────────────────────────────
    st.subheader("💿 专辑霸榜记录")
    st.caption("同一专辑在单周最多歌曲同时入榜")

    if "album_simul" in records:
        rec = records["album_simul"]
        st.markdown(
            f"**最高纪录：《{rec['album']}》** — {rec['artist']}，"
            f"{rec['week']} 周同时有 **{rec['count']}** 首歌曲在榜"
        )
    if "album_simul_list" in records and len(records["album_simul_list"]) > 0:
        _render_record_table(records["album_simul_list"], link_col_map={"billboard_week": "week", "album_name": "album", "artist_name": "artist"})

    st.divider()

    # ── Section 6: 历史总榜 ──────────────────────────────────────────────
    st.subheader("📜 历史总榜")

    alltime_tabs = st.tabs(["All-Time Greatest Top 20", "年度代表歌曲"])
    with alltime_tabs[0]:
        if "all_time_greatest" in records and len(records["all_time_greatest"]) > 0:
            st.caption("基于 走势点数 综合评分：Σ(每周归一化排名得分 × 播放强度权重) + Peak/冠单奖励")
            _render_record_table(records["all_time_greatest"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")
    with alltime_tabs[1]:
        if "year_end_no1" in records and len(records["year_end_no1"]) > 0:
            st.caption("各年度 走势点数 最高的年度代表歌曲")
            _render_record_table(records["year_end_no1"], link_col_map={"track_name": "track", "artist_name": "artist"}, drop_cols=["track_id"])
        else:
            st.info("暂无数据")

    st.divider()

    # ── Section 7: 双空冠 ─────────────────────────────────────────────────
    st.subheader("双空冠（同周歌曲+专辑同时空冠）")

    if "double_debut" in records and not records["double_debut"].empty:
        dd = records["double_debut"]
        st.metric("双空冠次数", f"{len(dd)} 次")
        _dd_headers = ["周", "艺人", "空冠歌曲", "空冠专辑"]
        _dd_rows = []
        for _, _r in dd.iterrows():
            _artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['debut_artist']), bb_tab="🎤 艺人榜单")
            _week_url = _bb_url(bb_nav="week", bb_date=str(_r['debut_week']), bb_tab="📋 周榜")
            _track_url = _bb_url(bb_nav="track", bb_id=int(_r['debut_track_id']), bb_tab="🎵 单曲历史")
            _album_url = _bb_url(bb_nav="album", bb_name=str(_r['debut_album']), bb_art=str(_r['debut_artist']), bb_tab="💿 专辑榜单")
            _dd_rows.append([
                (_html.escape(str(_r["debut_week"])), _week_url),
                (_html.escape(str(_r["debut_artist"])), _artist_url),
                (_html.escape(str(_r["debut_track"])), _track_url),
                (_html.escape(str(_r["debut_album"])), _album_url),
            ])
        _render_bb_table(_dd_headers, _dd_rows)
    else:
        st.info("暂无同时实现歌曲和专辑双空冠的艺人")

    st.divider()

    # ── Section 8: 大盘 ───────────────────────────────────────────────────
    st.subheader("周总播放次数排名（大盘）")

    if "week_total_plays" in records and not records["week_total_plays"].empty:
        wtp = records["week_total_plays"]
        _wtp_headers = ["#", "周", "总播放次数", "#1 曲目", "#1 曲目播放次数", "#1 专辑", "#1 专辑播放次数", "#1 艺人", "#1 艺人播放次数"]
        _wtp_rows = []
        for _i, _r in wtp.iterrows():
            _week_url = _bb_url(bb_nav="week", bb_date=_r['billboard_week'], bb_tab="📋 周榜")
            if pd.notna(_r.get("no1_track_id")):
                _no1_track_url = _bb_url(bb_nav="track", bb_id=int(_r['no1_track_id']), bb_tab="🎵 单曲历史")
                _no1_track_cell = (_html.escape(str(_r["no1_track"])), _no1_track_url)
            else:
                _no1_track_cell = "—"
            if pd.notna(_r.get("no1_album")):
                _no1_album_url = _bb_url(bb_nav="album", bb_name=str(_r['no1_album']), bb_art=str(_r.get('no1_album_artist', '')), bb_tab="💿 专辑榜单")
                _no1_album_cell = (_html.escape(str(_r["no1_album"])), _no1_album_url)
            else:
                _no1_album_cell = "—"
            if pd.notna(_r.get("no1_chart_artist")):
                _no1_artist_url = _bb_url(bb_nav="artist", bb_name=str(_r['no1_chart_artist']), bb_tab="🎤 艺人榜单")
                _no1_artist_cell = (_html.escape(str(_r["no1_chart_artist"])), _no1_artist_url)
            else:
                _no1_artist_cell = "—"
            _wtp_rows.append([
                str(_r.name),
                (_html.escape(str(_r["billboard_week"])), _week_url),
                f"{_r['total_plays']:,}",
                _no1_track_cell,
                f"{_r['no1_track_plays']:,.0f}" if pd.notna(_r.get("no1_track_plays")) else "—",
                _no1_album_cell,
                f"{_r['no1_album_plays']:,.0f}" if pd.notna(_r.get("no1_album_plays")) else "—",
                _no1_artist_cell,
                f"{_r['no1_chart_artist_plays']:,.0f}" if pd.notna(_r.get("no1_chart_artist_plays")) else "—",
            ])
        _render_bb_table(_wtp_headers, _wtp_rows,
            col_formats={0: "rank", 2: "num", 4: "num", 6: "num", 8: "num"}, height="500px")
    else:
        st.info("暂无大盘数据")
