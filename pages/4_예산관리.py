"""
pages/4_예산관리.py
예산 관리 페이지.
- 예산 대시보드(사용금액/남은예산/사용률/평균비용 + 진행바 + 초과 경고)
- 월 예산/1회 권장 예산/예산 초과 식당 처리 방식 설정
- AI 예산 조언, 월별 점심 리포트 생성
"""

import streamlit as st

from services import budget, settings as settings_service, ai_analyzer, statistics, ai_client
from components.budget_card import render_budget_dashboard
from utils import date_utils
from utils.ui import page_header

page_header("예산 관리", "개인 점심 예산과 지출을 관리하세요")

settings = settings_service.get_all()
ym = date_utils.year_month()
status = budget.get_monthly_budget_status(ym)

# ------------------------------------------------------------------
# 대시보드
# ------------------------------------------------------------------
render_budget_dashboard(status)

st.divider()

# ------------------------------------------------------------------
# 예산 설정
# ------------------------------------------------------------------
st.subheader("예산 설정")
with st.form("budget_form"):
    monthly = st.number_input("월 점심 예산 (개인)", min_value=0, value=int(status["monthly_budget"]), step=10000)
    meal = st.number_input("1인 1회 권장 예산", min_value=0, value=int(status["meal_budget"]), step=500)
    mode_options = ["추천 가능", "감점", "제외"]
    cur_mode = settings.get("budget_mode", "감점")
    mode = st.radio("예산 초과 식당 처리 방식", mode_options,
                    index=mode_options.index(cur_mode) if cur_mode in mode_options else 1,
                    horizontal=True)
    saved = st.form_submit_button("예산 설정 저장", type="primary")

if saved:
    budget.save_budget(ym, monthly, meal)
    settings_service.set_many({
        "monthly_budget": monthly, "meal_budget": meal, "budget_mode": mode,
    })
    st.success("예산 설정을 저장했습니다.")
    st.rerun()

st.divider()

# ------------------------------------------------------------------
# 지출 분석 (PRD 7.4)
# ------------------------------------------------------------------
import pandas as pd  # noqa: E402

st.subheader("📊 이번 달 지출 분석")
by_cat = statistics.spending_by_category(ym)
if not by_cat:
    st.caption("이번 달 방문 기록이 쌓이면 카테고리별 지출과 식당 TOP이 표시됩니다.")
else:
    cat_df = pd.DataFrame(by_cat).rename(
        columns={"category": "카테고리", "total": "지출", "cnt": "횟수"})
    st.markdown("**카테고리별 지출**")
    st.bar_chart(cat_df.set_index("카테고리")["지출"])

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("**💸 비싼 식당 TOP 5**")
        exp = statistics.expensive_restaurants(ym)
        if exp:
            st.dataframe(
                pd.DataFrame([{"식당": e["name"], "평균 결제": e["avg_paid"], "방문": e["cnt"]} for e in exp]),
                use_container_width=True, hide_index=True)
        else:
            st.caption("데이터 없음")
    with col_r:
        st.markdown("**💚 가성비 식당 TOP 5**")
        val = statistics.value_restaurants()
        if val:
            st.dataframe(
                pd.DataFrame([{"식당": v["name"], "가격": v["price"], "만족도": v["satisfaction"]} for v in val]),
                use_container_width=True, hide_index=True)
        else:
            st.caption("만족도 기록이 쌓이면 표시됩니다")

st.divider()

# ------------------------------------------------------------------
# AI 예산 조언
# ------------------------------------------------------------------
st.subheader("🤖 AI 예산 조언")
if not ai_client.is_available(settings):
    st.caption("AI를 사용하려면 설정에서 AI를 켜고 API Key를 등록하세요. (기본 예산 기능은 정상 동작합니다.)")
else:
    if st.button("AI 예산 조언 받기"):
        with st.spinner("AI 분석 중..."):
            advice = ai_analyzer.generate_budget_advice(status, settings)
        if advice:
            st.write(advice)
        else:
            st.info("AI 코멘트를 불러오지 못했습니다. 기본 추천 결과를 표시합니다.")

st.divider()

# ------------------------------------------------------------------
# 월별 점심 리포트
# ------------------------------------------------------------------
st.subheader("📊 월별 점심 리포트")
if st.button("이번 달 리포트 생성"):
    report_data = statistics.build_monthly_report_data(ym)
    if ai_client.is_available(settings):
        with st.spinner("AI 리포트 생성 중..."):
            report = ai_analyzer.generate_monthly_report(report_data, settings)
        if report:
            st.write(report)
        else:
            st.info("AI 코멘트를 불러오지 못했습니다. 아래 기본 통계를 표시합니다.")
            st.json(report_data)
    else:
        st.caption("AI 미사용: 기본 통계 데이터를 표시합니다.")
        st.json(report_data)
