"""
pages/3_방문기록.py
'기록 · 예산' 통합 페이지.
- 방문 기록 탭: 최근 방문 내역(삭제), AI 취향 분석, 식당별/카테고리별 통계
- 예산 탭: 예산 대시보드/설정/지출분석/AI조언/리포트 + 팀 회식비 계산기
"""

import pandas as pd
import streamlit as st

from services import db, statistics, ai_analyzer, ai_client, settings as settings_service
from components.budget_view import render_budget
from utils import date_utils, format_utils
from utils.ui import page_header

page_header("기록 · 예산", "방문 내역·통계·취향과 예산을 한 곳에서")

tab_visit, tab_budget = st.tabs(["📒 방문 기록", "💰 예산"])

# ==================================================================
# 방문 기록 탭
# ==================================================================
with tab_visit:
    logs = db.list_visit_logs()
    if not logs:
        st.info("아직 방문 기록이 없습니다. '오늘의 점심'에서 [여기로 방문]으로 기록을 남겨보세요.")
    else:
        ym = date_utils.year_month()
        month_stat = statistics.monthly_spending(ym)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{ym} 방문 횟수", f"{month_stat['count']}회")
        c2.metric("이번 달 식비 합계", format_utils.won(month_stat["total"]))
        c3.metric("평균 점심 비용", format_utils.won(month_stat["avg_price"]))
        c4.metric("만족도 평균", format_utils.rating(month_stat["avg_satisfaction"])
                  if month_stat["avg_satisfaction"] else "-")

        st.divider()

        # --- AI 취향 분석 ---
        st.subheader("🤖 내 점심 취향 분석")
        _settings = settings_service.get_all()
        by_cat_all = statistics.visits_by_category()
        if not ai_client.is_available(_settings):
            if by_cat_all:
                top = ", ".join(f"{c['category']}({c['visits']}회)" for c in by_cat_all[:3])
                st.caption(f"가장 자주 먹은 메뉴: {top} · (AI를 켜면 더 자세한 취향 분석을 제공합니다.)")
        elif st.button("AI 취향 분석 받기"):
            by_rest = statistics.visits_by_restaurant()
            taste_data = {
                "by_category": by_cat_all,
                "favorite_restaurants": [
                    {"name": r["name"], "visits": r["visits"], "satisfaction": r["avg_satisfaction"]}
                    for r in by_rest[:5]
                ],
            }
            with st.spinner("AI가 취향을 분석 중..."):
                report = ai_analyzer.analyze_taste(taste_data, _settings)
            st.write(report) if report else st.info("AI 코멘트를 불러오지 못했습니다.")

        st.divider()

        # --- 최근 방문 내역 ---
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

        # --- 식당별 / 카테고리별 통계 ---
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

# ==================================================================
# 예산 탭
# ==================================================================
with tab_budget:
    render_budget()
