"""
components/recommendation_group.py
1·2·3순위를 하나의 묶음(컨테이너) 안에 세로로 붙여 렌더링한다.
- PRD 11: 순위를 절대 떨어뜨리지 않고 하나의 st.container 안에 표시한다.
- 후보 부족/식당 없음 등의 안내 메시지도 함께 처리한다.
"""

from __future__ import annotations

import streamlit as st

from components.restaurant_card import render_recommendation_card
from services import naver_map
from utils import date_utils, format_utils


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
        st.markdown('<div class="sec-title">오늘의 점심 추천</div>', unsafe_allow_html=True)
        if result.get("oneliner"):
            st.markdown(
                f'<div class="mml-oneliner">💬 {result["oneliner"]}</div>',
                unsafe_allow_html=True,
            )
        for item in result["items"]:
            render_recommendation_card(item, settings, today)
            st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)

        # 팀에 공유할 수 있는 텍스트(복사용)
        _render_share_text(result["items"], today)


def _render_share_text(items, today=None) -> None:
    """추천 결과를 팀 채팅에 붙여넣기 좋은 텍스트로 만들어 보여준다."""
    with st.expander("📋 결과 공유 (복사해서 팀 채팅에 붙여넣기)"):
        lines = [f"오늘 점심 추천 ({date_utils.format_korean_date(today)})"]
        for it in items:
            lines.append(
                f"{it['rank']}순위. {it['name']} "
                f"({it.get('category') or '-'} · 도보 {int(it.get('walk_minutes') or 0)}분 · "
                f"1인 {format_utils.won(it.get('avg_price'))})"
            )
            lines.append(f"   ↳ {naver_map.map_link(it['name'], it.get('address'))}")
        st.code("\n".join(lines), language=None)
