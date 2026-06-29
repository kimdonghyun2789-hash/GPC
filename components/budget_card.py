"""
components/budget_card.py
예산 대시보드 카드(지표 + 진행바 + 경고)를 렌더링한다.
"""

from __future__ import annotations

import streamlit as st

from utils import format_utils


def render_budget_dashboard(status: dict) -> None:
    """예산 상태 dict를 받아 대시보드를 렌더링한다."""
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 점심 예산", format_utils.won(status["monthly_budget"]))
    c2.metric("현재 사용금액", format_utils.won(status["spent"]))
    c3.metric("남은 예산", format_utils.won(status["remaining"]))

    c4, c5 = st.columns(2)
    c4.metric("예산 사용률", format_utils.percent(status["usage_rate"]))
    c5.metric("평균 점심 비용", format_utils.won(status["avg_price"]))

    # 진행바 (0~1)
    rate = max(0.0, min(1.0, status["usage_rate"] / 100.0))
    st.progress(rate, text=f"예산 사용률 {format_utils.percent(status['usage_rate'])}")

    # 초과 경고
    if status.get("is_over"):
        st.error("이번 달 점심 예산을 초과했습니다.\n다음 추천부터 예산 초과 식당을 자동 감점합니다.")
    elif status["usage_rate"] >= 80:
        st.warning("이번 달 점심 예산의 80% 이상을 사용했습니다. 지출에 주의하세요.")
