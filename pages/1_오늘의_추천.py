"""
pages/1_오늘의_추천.py
오늘의 추천 페이지.
- 상단: 오늘 날짜 + 주요 설정 요약 + 월 예산 사용률
- 자연어 요청 입력창 + [오늘 점심 추천받기] 버튼
- 결과는 하나의 컨테이너 안에 1·2·3순위를 세로로 붙여 표시
"""

import streamlit as st

from services import db, recommender, settings as settings_service
from components.metrics import render_today_summary
from components.recommendation_group import render_recommendation_group
from utils import date_utils

settings = settings_service.get_all()
today = date_utils.today()

st.title("MML · 오늘의 추천")
render_today_summary(settings)
st.divider()

# 식당 DB 비어있는 경우 안내
if db.count_restaurants() == 0:
    st.warning("등록된 식당이 없습니다. '식당 DB 관리'에서 샘플 데이터를 추가하거나 식당을 등록해주세요.")
    if st.button("샘플 데이터 추가하기", type="primary"):
        from services import importer
        n = importer.add_sample_data()
        st.success(f"샘플 식당 {n}곳을 추가했습니다. 다시 추천을 받아보세요.")
        st.rerun()
    st.stop()

# 자연어 요청 입력
st.markdown("##### 오늘 뭐 먹고 싶어?")
user_request = st.text_input(
    "자연어 요청 (선택)",
    key="user_request_input",
    placeholder="예: 국물 있는 거, 멀지 않은 곳, 예산 안 넘는 곳",
    label_visibility="collapsed",
)

col1, col2 = st.columns([0.7, 0.3])
recommend_clicked = col1.button("🍽️ 오늘 점심 추천받기", type="primary", use_container_width=True)
reset_clicked = col2.button("🔄 다시 추천", use_container_width=True)

if recommend_clicked or reset_clicked:
    with st.spinner("오늘의 점심을 고르는 중..."):
        result = recommender.recommend_lunch(
            today=today, settings=settings,
            user_request=user_request or None,
        )
    st.session_state["recommendations"] = result

# 저장된 추천 결과 표시 (방문/방문불가 처리 후에도 유지)
st.divider()
if "recommendations" in st.session_state:
    render_recommendation_group(st.session_state["recommendations"], settings, today)
else:
    st.caption("위의 [오늘 점심 추천받기] 버튼을 눌러 오늘의 1·2·3순위를 받아보세요.")
