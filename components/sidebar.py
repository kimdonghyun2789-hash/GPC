"""
components/sidebar.py
사이드바 상단의 MML 브랜딩과 AI 상태 표시.
- 실제 페이지 네비게이션은 Streamlit의 pages/ 멀티페이지가 담당한다.
- 여기서는 앱명(MML)과 현재 AI 사용 가능 여부만 보여준다.
"""

from __future__ import annotations

import streamlit as st

from services import ai_client, settings as settings_service


def render_sidebar_header() -> None:
    """사이드바에 슬로건과 AI 상태를 표시한다(브랜드 로고는 st.logo가 최상단에 고정)."""
    with st.sidebar:
        st.caption("make my lunch")

        settings = settings_service.get_all()
        if ai_client.is_available(settings):
            dot, text = "#1F6F54", f"AI 사용 중 · {settings.get('ai_provider')}"
        elif settings.get("ai_enabled"):
            dot, text = "#E8722B", "AI 설정 ON · API Key 없음"
        else:
            dot, text = "#9AA3AF", "AI 사용 안 함"
        st.markdown(
            f'<div style="font-size:0.82rem;color:#6B7280;">'
            f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            f'background:{dot};margin-right:6px;"></span>{text}</div>',
            unsafe_allow_html=True,
        )
        st.divider()
