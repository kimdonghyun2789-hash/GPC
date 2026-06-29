"""
app.py
MML (머물래) 진입점.
- 페이지 설정/DB 초기화/사이드바 브랜딩을 수행하고
- st.navigation으로 5개 페이지(오늘의 추천 / 식당 DB 관리 / 방문 기록 / 예산 관리 / 설정)를 묶는다.

실행:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os

import streamlit as st

from services import db
from components.sidebar import render_sidebar_header
from utils.ui import inject_global_css

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# 1) 페이지 설정 (반드시 첫 Streamlit 호출)
st.set_page_config(
    page_title="MML · 머물래",
    page_icon="🍱",
    layout="centered",
    initial_sidebar_state="expanded",
)

# 2) 사이드바 최상단(좌측 맨 위)에 브랜드 로고 고정 (네비게이션 위)
st.logo(
    os.path.join(_ASSETS, "mml_logo.png"),
    icon_image=os.path.join(_ASSETS, "mml_icon.png"),
    size="large",
)

# 3) 전역 디자인(폰트/타이포/카드/버튼) 주입
inject_global_css()

# 3) DB 자동 생성/초기화 (최초 실행 시 data/mml.db 생성)
db.init_db()

# 4) 사이드바 브랜딩 + AI 상태
render_sidebar_header()

# 4) 멀티페이지 네비게이션
pages = [
    st.Page("pages/1_오늘의_추천.py", title="오늘의 추천", icon="🍽️", default=True),
    st.Page("pages/2_식당_DB관리.py", title="식당 DB 관리", icon="🏪"),
    st.Page("pages/3_방문기록.py", title="방문 기록", icon="📒"),
    st.Page("pages/4_예산관리.py", title="예산 관리", icon="💰"),
    st.Page("pages/6_팀점심.py", title="팀 점심", icon="👥"),
    st.Page("pages/5_설정.py", title="설정", icon="⚙️"),
]

navigation = st.navigation(pages, position="sidebar")
navigation.run()
