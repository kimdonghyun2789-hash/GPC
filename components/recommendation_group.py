"""
components/recommendation_group.py
1·2·3순위를 하나의 묶음(컨테이너) 안에 세로로 붙여 렌더링한다.
- PRD 11: 순위를 절대 떨어뜨리지 않고 하나의 st.container 안에 표시한다.
- 후보 부족/식당 없음 등의 안내 메시지도 함께 처리한다.
"""

from __future__ import annotations

import streamlit as st

from components.restaurant_card import render_recommendation_card


def render_recommendation_group(result: dict, settings: dict, today=None) -> None:
    """추천 결과 묶음을 렌더링한다. result는 recommender.recommend_lunch 반환값."""
    # 식당 DB가 비었거나 후보가 없는 경우
    if result.get("empty"):
        st.warning(result.get("message", "추천할 식당이 없습니다."))
        return

    # 조건 완화 안내
    if result.get("relaxed") and result.get("message"):
        st.info(f"ℹ️ {result['message']}")

    # 하나의 컨테이너 안에 1·2·3순위를 세로로 붙여 표시 (PRD 11.3)
    with st.container():
        st.subheader("오늘의 점심 1·2·3")
        for item in result["items"]:
            render_recommendation_card(item, settings, today)
