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

st.title("오늘의 추천")
st.markdown('<div class="page-sub">오늘 점심, 바로 결정하세요 — 1·2·3순위를 한 번에</div>',
            unsafe_allow_html=True)
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

# 상황별 추천 모드 (PRD 3.8)
st.markdown('<div class="sec-title">오늘은 어떤 점심?</div>', unsafe_allow_html=True)
mode_options = list(recommender.RECOMMEND_MODES.keys())
if hasattr(st, "pills"):
    mode = st.pills("모드", mode_options, selection_mode="single",
                    key="mode_pills", label_visibility="collapsed")
else:  # 구버전 폴백
    mode = st.radio("모드", ["(선택 안 함)"] + mode_options, horizontal=True,
                    label_visibility="collapsed")
    mode = None if mode == "(선택 안 함)" else mode

# 자연어 요청 + 인원 입력
st.markdown('<div class="sec-title">오늘 뭐 먹고 싶어?</div>', unsafe_allow_html=True)
req_col, party_col = st.columns([0.74, 0.26])
user_request = req_col.text_input(
    "자연어 요청 (선택)",
    key="user_request_input",
    placeholder="예: 국물 있는 거, 멀지 않은 곳, 예산 안 넘는 곳",
    label_visibility="collapsed",
)
party_size = party_col.number_input(
    "인원", min_value=1, max_value=30, value=1, step=1,
    key="party_size_input", help="2명 이상이면 단체 가능·수용 인원에 맞는 식당만 추천합니다.",
    label_visibility="collapsed",
)
party_col.caption(f"오늘 인원 {int(party_size)}명")

# 태그 필터 (선택) — 등록된 태그가 있을 때만 노출
all_tags = db.all_tag_names()
tag_filter = []
if all_tags:
    tag_filter = st.multiselect("태그로 좁히기 (선택)", all_tags, default=[],
                                placeholder="예: 가성비, 해장, 빠른 점심")

col1, col2 = st.columns([0.7, 0.3])
recommend_clicked = col1.button("오늘 점심 추천받기", type="primary", use_container_width=True)
reset_clicked = col2.button("다시 추천", use_container_width=True)

if recommend_clicked or reset_clicked:
    with st.spinner("오늘의 점심을 고르는 중..."):
        result = recommender.recommend_lunch(
            today=today, settings=settings,
            user_request=user_request or None,
            party_size=int(party_size),
            mode=mode,
            tag_filter=tag_filter or None,
        )
    st.session_state["recommendations"] = result

# 저장된 추천 결과 표시 (방문/방문불가 처리 후에도 유지)
st.divider()
if "recommendations" in st.session_state:
    render_recommendation_group(st.session_state["recommendations"], settings, today)
else:
    st.caption("위의 [오늘 점심 추천받기] 버튼을 눌러 오늘의 1·2·3순위를 받아보세요.")
