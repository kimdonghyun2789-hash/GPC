"""
components/metrics.py
오늘의 추천 화면 상단의 '주요 설정 요약' 지표 줄을 렌더링한다.
"""

from __future__ import annotations

import streamlit as st

from services import budget
from utils import date_utils, format_utils


def render_today_summary(settings: dict) -> None:
    """오늘 날짜 + 주요 설정값 + 월 예산 사용률 요약."""
    st.markdown(f"#### 🍱 오늘의 점심 추천 — {date_utils.format_korean_date()}")

    status = budget.get_monthly_budget_status()
    cols = st.columns(5)
    cols[0].metric("최근 방문 제외", f"{settings.get('exclude_recent_days', 5)}일")
    cols[1].metric("같은 메뉴 제외", f"{settings.get('exclude_category_days', 2)}일")
    cols[2].metric("최대 도보", f"{settings.get('max_walk_minutes', 10)}분")
    cols[3].metric("1회 예산", format_utils.won(settings.get("meal_budget", 12000)))
    cols[4].metric("월 예산 사용률", format_utils.percent(status["usage_rate"]))
