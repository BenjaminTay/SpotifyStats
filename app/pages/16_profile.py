"""Personal Profile — account identity, milestones, social network."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from app.db import get_db
from app.styles import inject_global_styles, page_header, kpi_row, PLOTLY_TEMPLATE, COLORS

inject_global_styles()


@st.cache_data(ttl=3600)
def load_profile_data():
    conn = get_db()
    profile = {}
    rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
    for r in rows:
        profile[r["key"]] = r["value"]

    follows = {"following": [], "followed_by": [], "blocking": []}
    frows = conn.execute("SELECT relationship_type, display_name FROM user_follows").fetchall()
    for r in frows:
        t = r["relationship_type"]
        if t in follows:
            follows[t].append(r["display_name"])

    prompts = conn.execute("SELECT message, created_timestamp FROM user_prompts").fetchall()

    # Milestones from plays table
    first_play = conn.execute("SELECT MIN(ts_date) FROM plays").fetchone()[0]
    total_plays = conn.execute("SELECT COUNT(*) FROM plays WHERE content_type='audio'").fetchone()[0]
    conn.close()

    has_data = bool(profile) or bool(follows["following"]) or bool(prompts)
    return {
        "has_data": has_data,
        "profile": profile,
        "follows": follows,
        "prompts": [dict(r) for r in prompts],
        "first_play": first_play,
        "total_plays": total_plays,
    }


def render():
    data = load_profile_data()

    if not data["has_data"]:
        st.warning("请先在「设置」页面导入账号数据")
        return

    page_header("个人档案", description="你的 Spotify 账号画像")

    profile = data["profile"]
    follows = data["follows"]
    prompts = data["prompts"]

    # ── Section 1: Identity Card ──────────────────────────────────────────
    st.markdown("### 个人信息")

    display_name = profile.get("identity_displayName", "未知")
    image_url = profile.get("identity_imageUrl", "")
    country = profile.get("attr_country", "未知")
    birthdate = profile.get("attr_birthdate", "未知")
    gender = profile.get("attr_gender", "未知")

    col_img, col_info = st.columns([1, 3])
    with col_img:
        if image_url:
            st.image(image_url, width=120)
        else:
            st.markdown(
                '<div style="width:120px;height:120px;border-radius:50%;'
                'background:linear-gradient(135deg,#B8860B,#D4A84B);'
                'display:flex;align-items:center;justify-content:center;'
                'font-size:3rem;">🎵</div>',
                unsafe_allow_html=True,
            )

    with col_info:
        st.markdown(f"## {display_name}")
        info_items = []
        if country:
            info_items.append(f"🇺🇸 {country}")
        if birthdate:
            info_items.append(f"🎂 {birthdate}")
        if gender:
            info_items.append(f"👤 {gender}")
        st.markdown(" · ".join(info_items))

    # Account stats
    kpi_row([
        {"label": "总播放次数", "value": f"{data['total_plays']:,}"},
        {"label": "首次播放", "value": str(data["first_play"] or "未知")},
        {"label": "关注人数", "value": str(len(follows["following"]))},
        {"label": "粉丝数", "value": str(len(follows["followed_by"]))},
    ])

    # ── Section 2: Account Timeline ───────────────────────────────────────
    st.markdown("### 账号里程碑")

    milestones = []
    if data["first_play"]:
        milestones.append({"date": str(data["first_play"]), "event": "首次播放记录"})

    # Wrapped listening age
    la_age = profile.get("wrapped_listening_age", "")
    if la_age:
        milestones.append({"date": f"收听年龄 {la_age} 年", "event": "音乐品味跨度"})

    # Payment
    pm = profile.get("payment_method", "")
    if pm:
        milestones.append({"date": "订阅方案", "event": pm})

    # Address
    addr = profile.get("family_address", "")
    if addr:
        milestones.append({"date": "所在地区", "event": addr})

    if milestones:
        for m in milestones:
            st.markdown(
                f"""<div style="display:flex;gap:1rem;align-items:baseline;margin-bottom:0.5rem;
                border-left:2px solid var(--gold);padding-left:1rem;">
                <span style="font-weight:600;color:var(--text-primary);min-width:8rem;">{m['date']}</span>
                <span style="color:var(--text-secondary);">{m['event']}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    # ── Section 3: Social Network ─────────────────────────────────────────
    st.markdown("### 社交网络")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown("**关注**")
        for name in follows["following"]:
            st.markdown(f"- {name}")

    with col_f2:
        st.markdown("**粉丝**")
        if follows["followed_by"]:
            for name in follows["followed_by"]:
                st.markdown(f"- {name}")
        else:
            st.caption("无粉丝")

    # ── Section 4: Fun Corner ─────────────────────────────────────────────
    st.markdown("### 趣味角落")

    fun_items = []

    # Banned items check
    conn = get_db()
    banned = conn.execute("SELECT item_name, item_type FROM banned_items").fetchall()
    conn.close()
    for b in banned:
        fun_items.append(f"屏蔽的{'艺人' if b['item_type']=='artist' else '歌曲'}：**{b['item_name']}**")

    # AI prompts
    for p in prompts:
        msg = p.get("message", "")
        if msg:
            fun_items.append(f'你对 AI 说过：**"{msg}"**')

    # Wrapped club
    club = profile.get("wrapped_club", "")
    if club:
        fun_items.append(f"Wrapped 俱乐部：**{club}**")

    if fun_items:
        for item in fun_items:
            st.markdown(
                f'<div style="background:var(--bg-card);border:1px solid var(--border);'
                f'border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem;">{item}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("暂无特殊数据")
