"""
components/team_vote.py
팀 점심 투표 컴포넌트(홈의 팀 모드에서 사용).
- 추천된 후보 목록에 좋아요/싫어요 투표를 하고
- 빠른 결정(최고 득표) 또는 랜덤 결정으로 최종 식당을 고른다.
- 결정은 recommendation_runs에 기록하고 방문 저장도 가능하다.
- 팀 선호도(자주 고른 식당/메뉴)도 함께 보여준다.
"""

from __future__ import annotations

import random
from collections import Counter

import streamlit as st

from services import db
from utils import format_utils


def render_team_vote(items: list[dict], attendees: list[str], exclude: list[str],
                     today=None) -> None:
    """추천 후보(items)에 대한 팀 투표/결정 UI를 렌더링한다."""
    if not items:
        return

    # 후보가 바뀌면 투표 초기화
    sig = tuple(it["id"] for it in items)
    if st.session_state.get("team_sig") != sig:
        st.session_state["team_sig"] = sig
        st.session_state["team_votes"] = {it["id"]: 0 for it in items}
        st.session_state["team_winner"] = None
    votes = st.session_state.setdefault("team_votes", {it["id"]: 0 for it in items})

    st.markdown('<div class="sec-title">후보에 투표하기</div>', unsafe_allow_html=True)
    for it in items:
        with st.container(border=True):
            c0, c1, c2, c3 = st.columns([0.56, 0.16, 0.14, 0.14])
            c0.markdown(
                f"**{it['name']}** · {it.get('category') or '-'} · "
                f"1인 {format_utils.won(it.get('avg_price'))}"
            )
            c0.caption(f"도보 {int(it.get('walk_minutes') or 0)}분 · 득표 {votes.get(it['id'], 0)}표")
            if c1.button(f"👍 {votes.get(it['id'], 0)}", key=f"tup_{it['id']}", use_container_width=True):
                votes[it["id"]] = votes.get(it["id"], 0) + 1
                st.rerun()
            if c2.button("👎", key=f"tdn_{it['id']}", use_container_width=True):
                votes[it["id"]] = votes.get(it["id"], 0) - 1
                st.rerun()
            if c3.button("선택", key=f"tpick_{it['id']}", use_container_width=True):
                st.session_state["team_winner"] = it
                st.rerun()

    d1, d2, d3 = st.columns(3)
    if d1.button("⚡ 빠른 결정 (최고 득표)", use_container_width=True):
        st.session_state["team_winner"] = max(items, key=lambda x: votes.get(x["id"], 0))
        st.rerun()
    if d2.button("🎲 랜덤 결정", use_container_width=True):
        st.session_state["team_winner"] = random.choice(items)
        st.rerun()
    if d3.button("투표 초기화", use_container_width=True):
        st.session_state["team_votes"] = {it["id"]: 0 for it in items}
        st.session_state["team_winner"] = None
        st.rerun()

    winner = st.session_state.get("team_winner")
    if winner:
        st.success(f"🎉 오늘 팀 점심은 **{winner['name']}** 으로 결정!")
        db.log_recommendation_run(
            mode="team", party_size=len(attendees) or None, excluded_categories=exclude,
            result_ids=[c["id"] for c in items], selected_id=winner["id"],
            run_date=today, attendees=attendees,
        )
        if st.button("이 식당 방문으로 저장", type="primary"):
            result = db.save_visit(winner["id"], today, actual_price=winner.get("avg_price"))
            (st.success if result["ok"] else st.warning)(result["message"])

    _render_team_history()


def _render_team_history() -> None:
    """팀 선호도(자주 고른 식당/메뉴) + 최근 결정 기록."""
    history = db.team_selection_history()
    if not history:
        return
    with st.expander("팀 선호도 분석 · 최근 기록"):
        rest_counter = Counter(h["restaurant_name"] for h in history)
        cat_counter = Counter(h["category"] for h in history if h["category"])
        a, b = st.columns(2)
        with a:
            st.markdown("**자주 고른 식당**")
            for name, cnt in rest_counter.most_common(5):
                st.write(f"- {name} · {cnt}회")
        with b:
            st.markdown("**팀이 선호한 메뉴**")
            for cat, cnt in cat_counter.most_common(5):
                st.write(f"- {cat} · {cnt}회")
        st.divider()
        for h in history[:8]:
            who = f" ({h['attendees']})" if h.get("attendees") else ""
            st.caption(f"{h['run_date']} · {h['restaurant_name']} [{h.get('category') or '-'}]{who}")
