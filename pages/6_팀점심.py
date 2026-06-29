"""
pages/6_팀점심.py
팀 점심 모드 (PRD 3.7).
- 참석 인원 + 싫어하는 메뉴(카테고리) 제외 후 후보를 뽑는다(단체 가능 식당 우선).
- 후보에 좋아요/싫어요 투표를 하고, 빠른 결정(최고 득표) 또는 랜덤 결정으로 최종 식당을 고른다.
- 결정 결과는 recommendation_runs에 기록하고, 그 자리에서 방문 저장도 가능하다.
※ 단일 기기(세션) 기반 투표 — 여러 명이 한 화면에서 빠르게 정하는 용도.
"""

import random

import streamlit as st

from services import db, recommender, settings as settings_service
from utils import date_utils, format_utils

st.title("팀 점심")
st.markdown('<div class="page-sub">여럿이 모였을 때 — 투표로 빠르게 오늘 점심을 정하세요</div>',
            unsafe_allow_html=True)

settings = settings_service.get_all()
today = date_utils.today()

if db.count_restaurants() == 0:
    st.warning("등록된 식당이 없습니다. '식당 DB 관리'에서 먼저 식당을 추가해주세요.")
    st.stop()

categories = sorted({r.get("category") for r in db.list_restaurants() if r.get("category")})

c1, c2 = st.columns(2)
attendees = c1.number_input("참석 인원", min_value=2, max_value=30, value=4, step=1)
exclude = c2.multiselect("오늘 빼고 싶은 메뉴(싫어요)", categories)
names_raw = st.text_input("팀원 이름 (선택, 쉼표로 구분)", placeholder="예: 동현, 지민, 수아")
attendee_names = [n.strip() for n in names_raw.split(",") if n.strip()]

if st.button("후보 뽑기", type="primary", use_container_width=True):
    s2 = dict(settings)
    s2["top_n"] = 5  # 투표용으로 후보 5개
    res = recommender.recommend_lunch(
        today=today, settings=s2, party_size=int(attendees),
        exclude_categories=exclude or None, generate_comments=False,
    )
    st.session_state["team_candidates"] = res["items"]
    st.session_state["team_votes"] = {it["id"]: 0 for it in res["items"]}
    st.session_state["team_winner"] = None

cands = st.session_state.get("team_candidates")
if not cands:
    st.info("참석 인원과 제외 메뉴를 고른 뒤 [후보 뽑기]를 눌러주세요.")
    st.stop()

votes = st.session_state.setdefault("team_votes", {})

st.divider()
st.subheader("후보 / 투표")
for it in cands:
    with st.container(border=True):
        cols = st.columns([0.56, 0.16, 0.14, 0.14])
        cols[0].markdown(
            f"**{it['name']}** · {it.get('category') or '-'} · "
            f"1인 {format_utils.won(it.get('avg_price'))}"
        )
        cols[0].caption(
            f"도보 {int(it.get('walk_minutes') or 0)}분 · 득표 {votes.get(it['id'], 0)}표"
        )
        if cols[1].button(f"👍 {votes.get(it['id'], 0)}", key=f"up_{it['id']}",
                          use_container_width=True):
            votes[it["id"]] = votes.get(it["id"], 0) + 1
            st.rerun()
        if cols[2].button("👎", key=f"dn_{it['id']}", use_container_width=True):
            votes[it["id"]] = votes.get(it["id"], 0) - 1
            st.rerun()
        if cols[3].button("선택", key=f"pick_{it['id']}", use_container_width=True):
            st.session_state["team_winner"] = it
            st.rerun()

st.divider()
d1, d2, d3 = st.columns(3)
if d1.button("⚡ 빠른 결정 (최고 득표)", use_container_width=True):
    st.session_state["team_winner"] = max(cands, key=lambda x: votes.get(x["id"], 0))
    st.rerun()
if d2.button("🎲 랜덤 결정", use_container_width=True):
    st.session_state["team_winner"] = random.choice(cands)
    st.rerun()
if d3.button("초기화", use_container_width=True):
    for k in ("team_candidates", "team_votes", "team_winner"):
        st.session_state.pop(k, None)
    st.rerun()

winner = st.session_state.get("team_winner")
if winner:
    st.success(f"🎉 오늘 팀 점심은 **{winner['name']}** 으로 결정!")
    # 결정 기록 (참석자 포함)
    db.log_recommendation_run(
        mode="team", party_size=int(attendees), excluded_categories=exclude,
        result_ids=[c["id"] for c in cands], selected_id=winner["id"], run_date=today,
        attendees=attendee_names,
    )
    if st.button("이 식당 방문으로 저장", type="primary"):
        result = db.save_visit(winner["id"], today, actual_price=winner.get("avg_price"))
        st.session_state.pop("recommendations", None)
        (st.success if result["ok"] else st.warning)(result["message"])

# ------------------------------------------------------------------
# 팀 선호도 분석 (PRD 3.7)
# ------------------------------------------------------------------
st.divider()
st.subheader("팀 선호도 분석")
history = db.team_selection_history()
if not history:
    st.caption("팀 점심 결정이 쌓이면 자주 고른 식당·메뉴를 분석해 보여줍니다.")
else:
    from collections import Counter
    rest_counter = Counter(h["restaurant_name"] for h in history)
    cat_counter = Counter(h["category"] for h in history if h["category"])
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**자주 고른 식당 TOP**")
        for name, cnt in rest_counter.most_common(5):
            st.write(f"- {name} · {cnt}회")
    with col_b:
        st.markdown("**팀이 선호한 메뉴**")
        for cat, cnt in cat_counter.most_common(5):
            st.write(f"- {cat} · {cnt}회")
    with st.expander("최근 팀 점심 기록"):
        for h in history[:10]:
            who = f" ({h['attendees']})" if h.get("attendees") else ""
            st.write(f"{h['run_date']} · {h['restaurant_name']} [{h.get('category') or '-'}]{who}")
