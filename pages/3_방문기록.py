"""
pages/3_방문기록.py
방문 기록 페이지.
- 최근 방문 내역(삭제 가능), AI 메모 요약/태그 표시
- 식당별/카테고리별 방문 횟수
- 월별 식비 합계/평균 점심 비용/만족도 평균
"""

import pandas as pd
import streamlit as st

from services import db, statistics
from utils import date_utils, format_utils

st.title("방문 기록")

logs = db.list_visit_logs()

if not logs:
    st.info("아직 방문 기록이 없습니다. '오늘의 추천'에서 [여기로 방문]으로 기록을 남겨보세요.")
    st.stop()

# ------------------------------------------------------------------
# 월별 요약 지표
# ------------------------------------------------------------------
ym = date_utils.year_month()
month_stat = statistics.monthly_spending(ym)
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{ym} 방문 횟수", f"{month_stat['count']}회")
c2.metric("이번 달 식비 합계", format_utils.won(month_stat["total"]))
c3.metric("평균 점심 비용", format_utils.won(month_stat["avg_price"]))
c4.metric("만족도 평균", format_utils.rating(month_stat["avg_satisfaction"])
          if month_stat["avg_satisfaction"] else "-")

st.divider()

# ------------------------------------------------------------------
# 최근 방문 내역
# ------------------------------------------------------------------
st.subheader("최근 방문 내역")
for v in logs[:50]:
    with st.container(border=True):
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            st.markdown(
                f"**{v['visited_date']} · {v['restaurant_name']}** "
                f"({v.get('category') or '-'})"
            )
            st.caption(
                f"{format_utils.won(v.get('actual_price'))} · "
                f"만족도 {format_utils.rating(v.get('satisfaction')) if v.get('satisfaction') else '-'}"
            )
            if v.get("memo"):
                st.write(f"📝 {v['memo']}")
            if v.get("ai_memo_summary"):
                st.info(f"🤖 {v['ai_memo_summary']}  ·  감정: {v.get('ai_sentiment') or '-'}")
            if v.get("ai_tags"):
                st.caption("태그: " + v["ai_tags"])
        with col2:
            if st.button("삭제", key=f"del_visit_{v['id']}", use_container_width=True):
                db.delete_visit_log(v["id"])
                st.session_state.pop("recommendations", None)
                st.rerun()

st.divider()

# ------------------------------------------------------------------
# 식당별 / 카테고리별 방문 통계
# ------------------------------------------------------------------
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("식당별 방문 횟수")
    by_rest = statistics.visits_by_restaurant()
    if by_rest:
        df = pd.DataFrame([{
            "식당명": r["name"], "방문": r["visits"],
            "평균만족도": round(r["avg_satisfaction"], 2) if r["avg_satisfaction"] else "-",
            "총지출": r["total_spent"],
        } for r in by_rest])
        st.dataframe(df, use_container_width=True, hide_index=True)
with col_b:
    st.subheader("카테고리별 방문 횟수")
    by_cat = statistics.visits_by_category()
    if by_cat:
        df = pd.DataFrame(by_cat).rename(columns={"category": "카테고리", "visits": "방문"})
        st.bar_chart(df.set_index("카테고리"))
