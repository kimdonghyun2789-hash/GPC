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
from utils.ui import page_header, section

settings = settings_service.get_all()
today = date_utils.today()

page_header("오늘의 점심", "팀이 오늘 어디 갈지 — 1·2·3순위로 바로 정하세요")
render_today_summary(settings)

# 식당 DB 비어있는 경우 안내
if db.count_restaurants() == 0:
    st.warning("등록된 식당이 없습니다. '식당 DB 관리'에서 샘플 데이터를 추가하거나 식당을 등록해주세요.")
    if st.button("샘플 데이터 추가하기", type="primary"):
        from services import importer
        n = importer.add_sample_data()
        st.success(f"샘플 식당 {n}곳을 추가했습니다. 다시 추천을 받아보세요.")
        st.rerun()
    st.stop()

# ---- 점심 고르기: 팀/개인 + 모드/요청/태그/버튼을 하나의 카드로 묶는다 ----
st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
with st.container(border=True):
    # 누구랑 먹나 — 팀이 기본
    who_col, party_col = st.columns([0.5, 0.5])
    who_options = ["팀", "개인"]
    if hasattr(who_col, "segmented_control"):
        who = who_col.segmented_control("구분", who_options, default="팀",
                                        key="who_seg", label_visibility="collapsed")
    else:
        who = who_col.radio("구분", who_options, horizontal=True, label_visibility="collapsed")
    is_team = who != "개인"

    if is_team:
        party_size = party_col.number_input(
            "함께 먹는 인원", min_value=2, max_value=30, value=4, step=1,
            key="party_size_input", help="단체 가능·수용 인원에 맞는 식당만 추천합니다.",
        )
    else:
        party_size = 1
        party_col.caption("혼자 먹을 식당을 추천합니다.")

    section("오늘은 어떤 점심?")
    mode_options = list(recommender.RECOMMEND_MODES.keys())
    if hasattr(st, "pills"):
        mode = st.pills("모드", mode_options, selection_mode="single",
                        key="mode_pills", label_visibility="collapsed")
    else:
        mode = st.radio("모드", ["(선택 안 함)"] + mode_options, horizontal=True,
                        label_visibility="collapsed")
        mode = None if mode == "(선택 안 함)" else mode

    user_request = st.text_input(
        "자연어 요청", key="user_request_input",
        placeholder=("우리 팀 오늘 뭐 먹지? 예: 국물 있는 거, 멀지 않은 곳"
                     if is_team else "오늘 뭐 먹고 싶어? 예: 국물 있는 거, 멀지 않은 곳"),
        label_visibility="collapsed",
    )

    all_tags = db.all_tag_names()
    tag_filter = []
    if all_tags:
        tag_filter = st.multiselect("태그로 좁히기 (선택)", all_tags, default=[],
                                    placeholder="태그로 좁히기 — 예: 가성비, 해장")

    c_btn1, c_btn2 = st.columns([0.62, 0.38])
    recommend_clicked = c_btn1.button("오늘 점심 추천받기", type="primary", use_container_width=True)
    reset_clicked = c_btn2.button("다시 추천", use_container_width=True)

    # 팀이면 투표로 정하는 흐름을 안내
    if is_team:
        try:
            st.page_link("pages/6_팀점심.py", label="여럿이 의견이 갈리면 → 투표로 정하기", icon="👥")
        except Exception:
            st.caption("👥 여럿이 의견이 갈리면 사이드바의 '팀 점심 투표'에서 정할 수 있어요.")

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
st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
if "recommendations" in st.session_state:
    render_recommendation_group(st.session_state["recommendations"], settings, today)
else:
    st.caption("위의 [오늘 점심 추천받기] 버튼을 눌러 오늘의 1·2·3순위를 받아보세요.")
