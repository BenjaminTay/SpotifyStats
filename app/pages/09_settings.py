"""Application settings — centralized parameter controls."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st

from app.db import get_db, db_exists, ensure_schema
from app.import_data import import_data
from app.styles import inject_global_styles, page_header

inject_global_styles()

# Ensure schema is up-to-date (adds agg tables for existing DBs)
if db_exists():
    ensure_schema()

# ── Session state defaults ──────────────────────────────────────────────
if "min_ms" not in st.session_state:
    st.session_state.min_ms = 30000
if "music_only" not in st.session_state:
    st.session_state.music_only = True
if "merge_enabled" not in st.session_state:
    st.session_state.merge_enabled = True
if "bb_top_n" not in st.session_state:
    st.session_state.bb_top_n = 30
if "bb_week_start_dow" not in st.session_state:
    st.session_state.bb_week_start_dow = 4  # Friday
if "bb_week_start_hour" not in st.session_state:
    st.session_state.bb_week_start_hour = 0
if "bb_album_top_n" not in st.session_state:
    st.session_state.bb_album_top_n = 20
if "bb_artist_top_n" not in st.session_state:
    st.session_state.bb_artist_top_n = 20

# Track previous values for change detection
if "_prev_min_ms" not in st.session_state:
    st.session_state._prev_min_ms = st.session_state.min_ms
if "_prev_music_only" not in st.session_state:
    st.session_state._prev_music_only = st.session_state.music_only
if "_prev_merge_enabled" not in st.session_state:
    st.session_state._prev_merge_enabled = st.session_state.merge_enabled
if "_prev_bb_top_n" not in st.session_state:
    st.session_state._prev_bb_top_n = st.session_state.bb_top_n
if "_prev_bb_week_start_dow" not in st.session_state:
    st.session_state._prev_bb_week_start_dow = st.session_state.bb_week_start_dow
if "_prev_bb_week_start_hour" not in st.session_state:
    st.session_state._prev_bb_week_start_hour = st.session_state.bb_week_start_hour
if "_prev_bb_album_top_n" not in st.session_state:
    st.session_state._prev_bb_album_top_n = st.session_state.bb_album_top_n
if "_prev_bb_artist_top_n" not in st.session_state:
    st.session_state._prev_bb_artist_top_n = st.session_state.bb_artist_top_n

page_header("⚙️ 设置", description="集中管理数据过滤、Billboard 榜单和数据导入")

# ═══════════════════════════════════════════════════════════════════════════
# Data Filtering
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("数据过滤")
st.caption("应用于所有统计页面的数据过滤条件，修改后即时生效")

col1, col2 = st.columns(2)

with col1:
    _sec_options = [0, 10, 30, 60, 120]
    _default_sec = st.session_state.min_ms // 1000
    _sec_idx = _sec_options.index(_default_sec) if _default_sec in _sec_options else 2
    min_sec = st.selectbox(
        "最短播放时长",
        options=_sec_options,
        index=_sec_idx,
        format_func=lambda x: f"{x} 秒" if x > 0 else "不过滤",
        key="settings_min_sec",
        help="低于此值的播放不计入统计。播放错误的记录自动排除。",
    )
    st.session_state.min_ms = min_sec * 1000

with col2:
    st.session_state.music_only = st.checkbox(
        "仅音乐（排除播客/有声书）",
        value=st.session_state.music_only,
        key="settings_music",
        help="排除播客和有声书内容",
    )
    st.session_state.merge_enabled = st.checkbox(
        "合并连续播放",
        value=st.session_state.merge_enabled,
        key="settings_merge",
        help="将同一首歌的连续播放记录合并为逻辑播放次数。\n\n"
             "例如：一首歌被切分成 20s + 200s 两次记录，合并后计为 1 次完整播放。"
             "关闭后每条记录独立计数，仅保留 ≥ 最短时长的记录。",
    )

# Detect data filter changes → clear caches and rerun
_filter_changed = False
if st.session_state.min_ms != st.session_state._prev_min_ms:
    st.session_state._prev_min_ms = st.session_state.min_ms
    _filter_changed = True
if st.session_state.music_only != st.session_state._prev_music_only:
    st.session_state._prev_music_only = st.session_state.music_only
    _filter_changed = True
if st.session_state.merge_enabled != st.session_state._prev_merge_enabled:
    st.session_state._prev_merge_enabled = st.session_state.merge_enabled
    _filter_changed = True
if _filter_changed:
    st.cache_data.clear()
    st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Billboard
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("Billboard 周榜")
st.caption("Billboard 页面专属设置，修改后榜单统计即时重算")

DOW_OPTIONS = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

# Row 1: Top N sliders for 单曲/专辑/艺人
col_t1, col_t2, col_t3 = st.columns(3)

with col_t1:
    new_track_top_n = st.slider(
        "每周上榜歌曲数量 (单曲 Top N)",
        min_value=10,
        max_value=100,
        step=5,
        value=st.session_state.bb_top_n,
        key="settings_bb_top_n_widget",
        help="每期 Billboard 单曲周榜收录的歌曲数量上限",
    )

with col_t2:
    new_album_top_n = st.slider(
        "每周上榜专辑数量 (专辑 Top N)",
        min_value=5,
        max_value=100,
        step=5,
        value=st.session_state.bb_album_top_n,
        key="settings_bb_album_top_n_widget",
        help="每期 Billboard 专辑周榜收录的专辑数量上限",
    )

with col_t3:
    new_artist_top_n = st.slider(
        "每周上榜艺人数量 (艺人 Top N)",
        min_value=5,
        max_value=100,
        step=5,
        value=st.session_state.bb_artist_top_n,
        key="settings_bb_artist_top_n_widget",
        help="每期 Billboard 艺人周榜收录的艺人数量上限",
    )

# Row 2: Week boundary configuration
col_w1, col_w2, col_w3 = st.columns(3)

with col_w1:
    new_week_dow = st.selectbox(
        "统计周期起始日",
        options=list(DOW_OPTIONS.keys()),
        format_func=lambda x: DOW_OPTIONS[x],
        index=list(DOW_OPTIONS.keys()).index(st.session_state.bb_week_start_dow),
        key="settings_bb_week_dow_raw",
        help="每周榜单从周几开始计算",
    )
    st.session_state.bb_week_start_dow = new_week_dow

with col_w2:
    new_week_hour = st.selectbox(
        "起始时间",
        options=list(range(24)),
        format_func=lambda x: f"{x:02d}:00",
        index=st.session_state.bb_week_start_hour,
        key="settings_bb_week_hour_raw",
        help="起始日当天从几点开始划入新一周（北京时间）",
    )
    st.session_state.bb_week_start_hour = new_week_hour

with col_w3:
    st.caption(
        f"当前统计周期：每{DOW_OPTIONS[st.session_state.bb_week_start_dow]} "
        f"{st.session_state.bb_week_start_hour:02d}:00 — "
        f"下{DOW_OPTIONS[st.session_state.bb_week_start_dow]} "
        f"{st.session_state.bb_week_start_hour:02d}:00（北京时间）"
    )

# Detect changes and sync to canonical key
_bb_changed = False
if new_track_top_n != st.session_state._prev_bb_top_n:
    st.session_state.bb_top_n = new_track_top_n
    st.session_state._prev_bb_top_n = new_track_top_n
    _bb_changed = True
if new_album_top_n != st.session_state._prev_bb_album_top_n:
    st.session_state.bb_album_top_n = new_album_top_n
    st.session_state._prev_bb_album_top_n = new_album_top_n
    _bb_changed = True
if new_artist_top_n != st.session_state._prev_bb_artist_top_n:
    st.session_state.bb_artist_top_n = new_artist_top_n
    st.session_state._prev_bb_artist_top_n = new_artist_top_n
    _bb_changed = True
if st.session_state.bb_week_start_dow != st.session_state._prev_bb_week_start_dow:
    st.session_state._prev_bb_week_start_dow = st.session_state.bb_week_start_dow
    st.session_state.settings_bb_week_dow = st.session_state.bb_week_start_dow
    _bb_changed = True
if st.session_state.bb_week_start_hour != st.session_state._prev_bb_week_start_hour:
    st.session_state._prev_bb_week_start_hour = st.session_state.bb_week_start_hour
    st.session_state.settings_bb_week_hour = st.session_state.bb_week_start_hour
    _bb_changed = True
if _bb_changed:
    # Persist config to URL so it survives app restarts
    import json
    st.query_params["bb_cfg"] = json.dumps({
        "tn": st.session_state.bb_top_n,
        "an": st.session_state.bb_album_top_n,
        "arn": st.session_state.bb_artist_top_n,
        "dow": st.session_state.bb_week_start_dow,
        "hr": st.session_state.bb_week_start_hour,
    })
    st.cache_data.clear()
    st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Data Management
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("数据管理")

col_mgmt1, col_mgmt2 = st.columns([1, 3])

with col_mgmt1:
    if st.button("🔄 重新导入数据", use_container_width=True, type="primary"):
        with st.spinner("正在重新导入 Spotify 播放记录..."):
            try:
                result = import_data(
                    agg_min_ms=st.session_state.min_ms,
                    agg_music_only=st.session_state.music_only,
                    agg_week_start_dow=st.session_state.bb_week_start_dow,
                    agg_week_start_hour=st.session_state.bb_week_start_hour,
                )
                st.cache_data.clear()
                st.success(
                    f"导入完成！{result['total_records']:,} 条记录，"
                    f"{result['unique_artists']} 位艺人，{result['unique_tracks']} 首曲目"
                )
                st.rerun()
            except FileNotFoundError as e:
                st.error(f"找不到数据文件：{e}")
            except Exception as e:
                st.error(f"导入失败：{e}")

with col_mgmt2:
    if db_exists():
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        conn.close()
        st.metric("数据库记录数", f"{count:,}")
    else:
        st.warning("数据库未导入，请先导入数据")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Version Merge Management
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("🔗 版本合并管理")
st.caption("将同一专辑的不同版本（豪华版、Acoustic版等）合并统计。")

import pandas as pd
from app.version_merge import (
    detect_release_groups, apply_detected_groups, get_all_groups,
    get_group_members, delete_group, set_primary, get_ungrouped_albums,
    create_group, update_group_members, get_album_types, normalize_album_name,
    get_album_track_comparison,
)

tab_detect, tab_groups, tab_create = st.tabs(
    ["🔍 自动检测", "📋 已保存组", "➕ 手动创建"]
)

# ── Tab 1: Auto Detection ──────────────────────────────────────────────
with tab_detect:
    if st.button("🔄 运行自动检测", use_container_width=True, key="vm_detect_btn"):
        with st.spinner("正在分析专辑版本关系（含 Spotify API 查询）..."):
            st.session_state.vm_detection = detect_release_groups()
            if st.session_state.vm_detection.empty:
                st.info("未发现可合并的专辑版本组。")
            else:
                high = st.session_state.vm_detection[
                    st.session_state.vm_detection["confidence"] == "high"
                ]
                st.success(
                    f"发现 {len(st.session_state.vm_detection)} 个候选组"
                    f"（{len(high)} 个高置信度）"
                )

    detection_df = st.session_state.get("vm_detection")
    if detection_df is not None and not detection_df.empty:
        # Reset index so sequential position matches checkbox keys
        detection_df = detection_df.reset_index(drop=True)

        # ── Confidence filter ──────────────────────────────────────────
        has_group_type = "group_type" in detection_df.columns
        if has_group_type:
            album_mask = detection_df["group_type"] == "album"
            single_mask = detection_df["group_type"] == "single"
        else:
            album_mask = pd.Series([True] * len(detection_df))
            single_mask = pd.Series([False] * len(detection_df))

        high_count = len(detection_df[detection_df["confidence"] == "high"])
        low_count = len(detection_df[detection_df["confidence"] == "low"])

        conf_filter = st.radio(
            "筛选置信度",
            options=[f"全部 ({len(detection_df)})", f"🟢 高置信 ({high_count})", f"🟡 中置信 ({low_count})"],
            horizontal=True,
            key="vm_conf_filter",
        )

        st.divider()

        # ── Select/Deselect shortcuts ──────────────────────────────────
        col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
        with col_sel1:
            if st.button("全选高置信", key="vm_sel_all_high", use_container_width=True):
                for i, (_, row) in enumerate(detection_df.iterrows()):
                    st.session_state[f"vm_chk_{i}"] = (row["confidence"] == "high")
                st.rerun()
        with col_sel2:
            if st.button("取消全选", key="vm_desel_all", use_container_width=True):
                for i in range(len(detection_df)):
                    st.session_state[f"vm_chk_{i}"] = False
                st.rerun()

        # ── Render groups ──────────────────────────────────────────────
        def _render_detection_section(mask, label, icon):
            matched = detection_df[mask]
            if matched.empty:
                return
            st.caption(f"#### {icon} {label} ({len(matched)})")

            for seq_idx in matched.index:
                row = detection_df.iloc[seq_idx]

                conf_icon = "🟢" if row["confidence"] == "high" else "🟡"
                members = row["members"] if isinstance(row["members"], list) else []

                # Filter visibility
                if conf_filter.startswith("🟢") and row["confidence"] != "high":
                    continue
                if conf_filter.startswith("🟡") and row["confidence"] != "low":
                    continue

                with st.expander(
                    f"{conf_icon} **{row['canonical_name']}** "
                    f"({row['artist_name']}) — {len(members)} 成员"
                ):
                    # Reason
                    reason = row.get("reason", "")
                    st.caption(f"判定依据：{reason}" if reason else "判定依据：—")

                    # Overlap details (Phase 1 groups)
                    overlap_details = row.get("overlap_details", [])
                    if overlap_details and isinstance(overlap_details, list):
                        for od in overlap_details:
                            od_name = od.get("album_name", "?")
                            od_overlap = od.get("overlap", 0)
                            od_ok = "✅" if od_overlap >= 0.4 else "⚠️"
                            st.caption(
                                f"  {od_ok} **{od_name}** vs 主版本："
                                f"曲目重叠率 {od_overlap:.1%}"
                            )

                    # Member list
                    members_str = " ← ".join(
                        f"**{m['album_name']}**" for m in members
                    )
                    primary_id = int(row["primary_album_id"])
                    st.caption(f"⭐ 主版本：**{row['primary_album_name']}**")
                    st.caption(f"成员：{members_str}")

                    # Track comparison table — directly inline
                    non_primary = [m for m in members if m["album_id"] != primary_id]
                    if non_primary:
                        for m in non_primary:
                            cmp = get_album_track_comparison(primary_id, m["album_id"])
                            rows = []
                            # 主专辑曲目优先（共享 + 仅主专辑），按主专辑 track number 排序
                            for t_name, t_artist, disc_num, track_num in cmp.get("shared", []):
                                seq = f"{disc_num}-{track_num}" if disc_num and disc_num > 1 else str(track_num or "")
                                rows.append({"序号": seq, "曲目": t_name, "艺人": t_artist, "归属": "🔄 共享"})
                            for t_name, t_artist, disc_num, track_num in cmp.get("only_in_a", []):
                                seq = f"{disc_num}-{track_num}" if disc_num and disc_num > 1 else str(track_num or "")
                                rows.append({"序号": seq, "曲目": t_name, "艺人": t_artist, "归属": f"⭐ {row['primary_album_name'][:12]}"})
                            # 加曲按豪华版专辑 track number 排序
                            for t_name, t_artist, disc_num, track_num in cmp.get("only_in_b", []):
                                seq = f"{disc_num}-{track_num}" if disc_num and disc_num > 1 else str(track_num or "")
                                rows.append({"序号": seq, "曲目": t_name, "艺人": t_artist, "归属": f"➕ {m['album_name'][:12]}"})

                            if rows:
                                cmp_df = pd.DataFrame(rows)
                                shared_n = len(cmp.get("shared", []))
                                only_p = len(cmp.get("only_in_a", []))
                                only_m = len(cmp.get("only_in_b", []))
                                st.caption(
                                    f"**{row['primary_album_name']}** vs "
                                    f"**{m['album_name']}** · "
                                    f"🔄{shared_n} ⭐{only_p} ➕{only_m}"
                                )
                                st.dataframe(
                                    cmp_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=min(len(cmp_df) * 35 + 38, 250),
                                )
                            else:
                                st.caption(
                                    f"**{row['primary_album_name']}** vs "
                                    f"**{m['album_name']}** · 无曲目数据"
                                )

                    # Checkbox
                    st.checkbox(
                        "选中此组合并",
                        value=st.session_state.get(f"vm_chk_{seq_idx}", False),
                        key=f"vm_chk_{seq_idx}",
                    )

        _render_detection_section(album_mask, "专辑合并候选", "📀")
        _render_detection_section(single_mask, "单曲合并候选", "🎵")

        # ── Apply selected ─────────────────────────────────────────────
        st.divider()
        col_apply1, col_apply2 = st.columns([1, 3])
        with col_apply1:
            # Gather checked indices
            checked_count = sum(
                1 for i in range(len(detection_df))
                if st.session_state.get(f"vm_chk_{i}", False)
            )
            if st.button(
                f"✅ 应用选中组 ({checked_count})",
                type="primary",
                use_container_width=True,
                key="vm_apply_sel",
                disabled=checked_count == 0,
            ):
                # Build filtered DataFrame
                checked_indices = [
                    i for i in range(len(detection_df))
                    if st.session_state.get(f"vm_chk_{i}", False)
                ]
                filtered = detection_df.iloc[checked_indices]
                with st.spinner(f"正在写入 {len(filtered)} 个版本合并组..."):
                    count = apply_detected_groups(filtered, only_high_confidence=False)
                    st.cache_data.clear()
                    st.success(f"已创建 {count} 个版本合并组")
                    # Clean up checkbox states
                    for i in range(len(detection_df)):
                        st.session_state.pop(f"vm_chk_{i}", None)
                    del st.session_state.vm_detection
                    st.rerun()

        with col_apply2:
            if st.button("🗑️ 清除检测结果", key="vm_clear_detect", use_container_width=True):
                for i in range(len(detection_df)):
                    st.session_state.pop(f"vm_chk_{i}", None)
                del st.session_state.vm_detection
                st.rerun()

# ── Tab 2: Saved Groups Management ─────────────────────────────────────
with tab_groups:
    existing_groups = get_all_groups()
    if existing_groups.empty:
        st.info("暂无保存的版本合并组。请使用「自动检测」或「手动创建」标签页。")
    else:
        # Pre-load all album types
        all_member_ids = []
        for _, grp in existing_groups.iterrows():
            members = get_group_members(int(grp["group_id"]))
            all_member_ids.extend(members["album_id"].tolist())
        album_types = get_album_types(list(set(all_member_ids)))

        # Classify groups as album or single by primary member's type
        album_groups = []
        single_groups = []
        for _, grp in existing_groups.iterrows():
            gid = int(grp["group_id"])
            primary_id = int(grp["primary_album_id"]) if grp["primary_album_id"] is not None else None
            primary_type = album_types.get(primary_id, "unknown")
            if primary_type == "single":
                single_groups.append(grp)
            else:
                album_groups.append(grp)

        def _render_group(grp):
            gid = int(grp["group_id"])
            artist = grp["artist_name"]
            canonical = grp["canonical_name"]
            primary_id = int(grp["primary_album_id"]) if grp["primary_album_id"] is not None else None
            is_manual = bool(grp["is_manual"])
            manual_badge = " ✋人工" if is_manual else " 🤖自动"

            members = get_group_members(gid)

            with st.expander(
                f"📀 **{canonical}** ({artist}){manual_badge} — {len(members)} 成员"
            ):
                # Member list
                for _, m in members.iterrows():
                    aid = int(m["album_id"])
                    name = m["album_name"]
                    atype = album_types.get(aid, "unknown")
                    is_primary = (aid == primary_id)

                    badge_map = {"album": "🟤", "single": "🟡", "compilation": "🟠", "unknown": "⚪"}
                    badge = badge_map.get(atype, "⚪")
                    primary_mark = " ⭐" if is_primary else ""

                    col_info, col_act1, col_act2 = st.columns([4, 0.5, 0.5])
                    with col_info:
                        st.caption(f"{badge} **{name}**{primary_mark}  `{atype}`")
                    with col_act1:
                        if not is_primary:
                            if st.button("⭐", key=f"vm_setp_{gid}_{aid}",
                                         help="设为主版本"):
                                set_primary(gid, aid)
                                st.cache_data.clear()
                                st.rerun()
                    with col_act2:
                        if len(members) > 2:
                            if st.button("✕", key=f"vm_rm_{gid}_{aid}",
                                         help="移除此成员"):
                                update_group_members(gid, remove_ids=[aid])
                                st.cache_data.clear()
                                st.rerun()

                # Add member
                st.caption("**添加成员**")
                ungrouped = get_ungrouped_albums(artist_name=artist)
                if not ungrouped.empty:
                    options = {
                        f"{row['album_name']}": int(row["album_id"])
                        for _, row in ungrouped.iterrows()
                    }
                    selected_names = st.multiselect(
                        "选择要加入此组的专辑",
                        options=list(options.keys()),
                        key=f"vm_addm_{gid}",
                        label_visibility="collapsed",
                    )
                    if selected_names and st.button("加入组", key=f"vm_addb_{gid}"):
                        add_ids = [options[n] for n in selected_names]
                        update_group_members(gid, add_ids=add_ids)
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.caption("该艺人下所有专辑都已分组。")

                # Delete group
                if st.button("🗑️ 删除此组", key=f"vm_delg_{gid}", type="secondary"):
                    delete_group(gid)
                    st.cache_data.clear()
                    st.rerun()

        # ── Album groups ──────────────────────────────────────────────
        if album_groups:
            st.caption(f"📀 专辑合并 ({len(album_groups)})")
            for grp in album_groups:
                _render_group(grp)

        # ── Single groups ─────────────────────────────────────────────
        if single_groups:
            st.caption(f"🎵 单曲合并 ({len(single_groups)})")
            for grp in single_groups:
                _render_group(grp)

        # Clear all
        st.divider()
        if st.button("🗑️ 清除全部组合", key="vm_clear_all", type="secondary"):
            from app.db import get_db
            conn = get_db(readonly=False)
            conn.execute("DELETE FROM release_group_members")
            conn.execute("DELETE FROM release_groups")
            conn.commit()
            conn.close()
            st.cache_data.clear()
            st.success("已清除所有版本合并组")
            st.rerun()

# ── Tab 3: Manual Create ───────────────────────────────────────────────
with tab_create:
    # Get all artists
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT a.artist_name FROM artists a "
        "JOIN albums al ON al.artist_id = a.artist_id "
        "ORDER BY a.artist_name"
    ).fetchall()
    conn.close()
    all_artists = sorted(set(r[0] for r in rows))

    if not all_artists:
        st.info("数据库中暂无艺人数据。")
    else:
        selected_artist = st.selectbox(
            "选择艺人", options=all_artists, key="vm_create_artist"
        )

        ungrouped = get_ungrouped_albums(artist_name=selected_artist)
        if ungrouped.empty:
            st.info(f"**{selected_artist}** 下所有专辑都已分组。")
        else:
            album_options = {
                f"{row['album_name']}": int(row["album_id"])
                for _, row in ungrouped.iterrows()
            }
            selected_albums = st.multiselect(
                f"选择要合并的专辑（至少 2 个）",
                options=list(album_options.keys()),
                key="vm_create_albums",
            )

            if len(selected_albums) >= 2:
                selected_ids = [album_options[n] for n in selected_albums]

                primary_name = st.selectbox(
                    "选择主版本（排行榜以此为准）",
                    options=selected_albums,
                    key="vm_create_primary",
                    index=0,
                    help="主版本的发行日期和名称将作为合并后的代表。通常选最早发行的原始版本。",
                )
                primary_id = album_options[primary_name]

                suggested = normalize_album_name(primary_name)
                canonical_name = st.text_input(
                    "合并后的显示名称",
                    value=suggested,
                    key="vm_create_canonical",
                    help="排行榜上将以此名称显示该合并组。",
                )

                if canonical_name.strip():
                    if st.button("✅ 创建合并组", key="vm_create_btn", type="primary"):
                        conn2 = get_db()
                        artist_id_row = conn2.execute(
                            "SELECT artist_id FROM artists WHERE artist_name = ?",
                            [selected_artist],
                        ).fetchone()
                        conn2.close()

                        if artist_id_row:
                            group_id = create_group(
                                canonical_name=canonical_name.strip(),
                                artist_id=artist_id_row[0],
                                primary_album_id=primary_id,
                                member_ids=selected_ids,
                            )
                            if group_id:
                                st.cache_data.clear()
                                st.success(
                                    f"已创建合并组: **{canonical_name}** "
                                    f"({len(selected_ids)} 成员)"
                                )
                                st.rerun()
                            else:
                                st.error("创建失败。可能已存在同名的组。")
                else:
                    st.caption("显示名称不能为空。")
            elif len(selected_albums) == 1:
                st.caption("请至少选择 2 张专辑以创建合并组。")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# Account Data Import
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("账号数据")

col_acct1, col_acct2 = st.columns([1, 3])

with col_acct1:
    if st.button("📦 导入账号数据", use_container_width=True):
        from app.import_account_data import import_all
        with st.spinner("正在导入 Spotify 账号数据..."):
            try:
                result = import_all(
                    progress_callback=lambda msg, pct: None,
                )
                st.cache_data.clear()
                st.success("账号数据导入完成！")
                with st.expander("查看导入详情"):
                    st.json(result)
                st.rerun()
            except Exception as e:
                st.error(f"导入失败：{e}")

with col_acct2:
    conn = get_db()
    try:
        sc = conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]
        stc = conn.execute("SELECT COUNT(*) FROM saved_tracks").fetchone()[0]
        plc = conn.execute("SELECT COUNT(*) FROM playlists").fetchone()[0]
        pdc = conn.execute("SELECT COUNT(*) FROM podcast_plays").fetchone()[0]
        st.metric(
            "账号数据概况",
            f"搜索 {sc} 条 · 收藏 {stc} 首 · 歌单 {plc} 个 · 播客 {pdc} 次",
        )
    except Exception:
        st.caption("暂无账号数据，请点击左侧按钮导入")
    finally:
        conn.close()
