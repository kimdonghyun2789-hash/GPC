"""
app.py
MML (머물래) 진입점.
- 페이지 설정/DB 초기화/사이드바 브랜딩을 수행하고
- st.navigation으로 5개 페이지(오늘의 추천 / 식당 DB 관리 / 방문 기록 / 예산 관리 / 설정)를 묶는다.

실행:
    pip install -r requirements.txt
    streamlit run app.py
"""

import streamlit as st

from services import db
from components.sidebar import render_sidebar_header

# 1) 페이지 설정 (반드시 첫 Streamlit 호출)
st.set_page_config(
    page_title="MML · 머물래",
    page_icon="🍱",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 2) DB 자동 생성/초기화 (최초 실행 시 data/mml.db 생성)
db.init_db()

# 3) 사이드바 브랜딩 + AI 상태
render_sidebar_header()

# 4) 멀티페이지 네비게이션
pages = [
    st.Page("pages/1_오늘의_추천.py", title="오늘의 추천", icon="🍽️", default=True),
    st.Page("pages/2_식당_DB관리.py", title="식당 DB 관리", icon="🏪"),
    st.Page("pages/3_방문기록.py", title="방문 기록", icon="📒"),
    st.Page("pages/4_예산관리.py", title="예산 관리", icon="💰"),
    st.Page("pages/5_설정.py", title="설정", icon="⚙️"),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
