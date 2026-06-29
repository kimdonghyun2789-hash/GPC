"""
components/metrics.py
오늘의 추천 화면 상단의 '주요 설정 요약'을 칩(chip) 형태로 렌더링한다.
- st.metric의 글자 잘림 문제를 피하기 위해 utils.ui.summary_chips를 사용한다.
"""

from __future__ import annotations

import streamlit as st

from services import budget
from utils import date_utils, format_utils
from utils.ui import summary_chips


def render_today_summary(settings: dict) -> None:
    """오늘 날짜 + 주요 설정값 + 월 예산 사용률 요약(칩 UI)."""
    st.markdown(f"##### 📅 {date_utils.format_korean_date()}")

    status = budget.get_monthly_budget_status()
    summary_chips([
        ("최근 방문 제외", f"{settings.get('exclude_recent_days', 5)}일"),
        ("같은 메뉴 제외", f"{settings.get('exclude_category_days', 2)}일"),
        ("최대 도보", f"{settings.get('max_walk_minutes', 10)}분"),
        ("1회 예산", format_utils.won(settings.get("meal_budget", 12000))),
        ("월 예산 사용률", format_utils.percent(status["usage_rate"])),
    ])
