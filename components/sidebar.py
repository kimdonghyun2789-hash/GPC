"""
components/sidebar.py
사이드바 상단의 MML 브랜딩과 AI 상태 표시.
- 실제 페이지 네비게이션은 Streamlit의 pages/ 멀티페이지가 담당한다.
- 여기서는 앱명(MML)과 현재 AI 사용 가능 여부만 보여준다.
"""

from __future__ import annotations

import streamlit as st

from services import ai_client, settings as settings_service
from utils.ui import render_logo


def render_sidebar_header() -> None:
    """사이드바 상단에 MML 로고/슬로건과 AI 상태를 표시한다."""
    with st.sidebar:
        render_logo(width=168)
        st.caption("오늘 점심, 1·2·3순위로 바로 결정")
        st.divider()

        settings = settings_service.get_all()
        if ai_client.is_available(settings):
            st.success(f"🤖 AI 사용 중 · {settings.get('ai_provider')}")
        elif settings.get("ai_enabled"):
            st.caption("🤖 AI 설정 ON · API Key 없음 → 기본 추천만 동작")
        else:
            st.caption("🤖 AI 사용 안 함 · 기본 추천만 동작")
        st.divider()
