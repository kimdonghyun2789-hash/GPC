"""
components/restaurant_card.py
추천 카드 1장을 렌더링하는 컴포넌트.
- 순위/식당명/메뉴분류/대표메뉴/도보/가격/선호도/혼잡도/최근방문일/점수/사유/예산상태/AI코멘트 표시
- [여기로 방문] / [방문 불가] / [상세보기] 버튼과 인라인 입력 폼 처리
- 방문 저장 시 AI 메모 분석을 수행하고 visit_logs에 저장한다.
"""

from __future__ import annotations

import streamlit as st

from services import db, ai_analyzer
from utils import format_utils, date_utils

# 방문 불가 기본 사유 (PRD 14.2)
UNAVAILABLE_REASONS = [
    "만석", "휴무", "메뉴 품절", "너무 멀다", "오늘 안 땡김",
    "팀원 반대", "가격 부담", "날씨 때문에 어려움", "기타",
]


def render_recommendation_card(item: dict, settings: dict, today=None) -> None:
    """추천 카드 한 장을 렌더링한다. item은 recommender 결과의 단일 dict."""
    today = date_utils.to_date(today)
    rid = item["id"]
    rank = item.get("rank", "-")
    meal_budget = settings.get("meal_budget", 12000)

    with st.container(border=True):
        # 헤더: 순위 배지 + 식당명 + 점수
        rank_cls = f"r{rank}" if isinstance(rank, int) and rank in (1, 2, 3) else "r3"
        st.markdown(
            f"""<div class="mml-card-head">
  <div class="mml-rank {rank_cls}">{rank}</div>
  <div class="mml-card-title">
    <div class="name">{item['name']}</div>
    <div class="sub">{item.get('category') or '-'} · {item.get('main_menu') or '-'}</div>
  </div>
  <div class="mml-score"><span class="s">{item.get('score', 0)}</span><span class="l">추천점수</span></div>
</div>""",
            unsafe_allow_html=True,
        )

        # 정보 라인
        budget_text = format_utils.budget_status_text(item.get("avg_price"), meal_budget)
        last = item.get("last_visited") or "방문 이력 없음"
        d = '<span class="dot">·</span>'
        st.markdown(
            f'<div class="mml-info">{format_utils.walk(item.get("walk_minutes"))}{d}'
            f'{format_utils.won(item.get("avg_price"))}{d}'
            f'{format_utils.rating(item.get("rating"))}{d}'
            f'혼잡도 {item.get("crowd_level") or "-"}{d}'
            f'{budget_text}</div>'
            f'<div class="mml-info" style="color:#9AA3AF;font-size:0.8rem;">'
            f'최근방문일 {last}{d}누적 방문 {item.get("visit_count", 0)}회</div>',
            unsafe_allow_html=True,
        )

        # 추천 사유 (배지)
        reasons = item.get("reasons") or []
        if reasons:
            badges = "".join(f'<span class="mml-reason">{r}</span>' for r in reasons)
            st.markdown(f'<div style="margin:4px 0 2px;">{badges}</div>', unsafe_allow_html=True)

        # AI 코멘트
        if item.get("ai_comment"):
            st.info(f"🤖 {item['ai_comment']}")

        # 버튼 3종
        b1, b2, b3 = st.columns(3)
        visit_key = f"visit_form_{rid}"
        unavail_key = f"unavail_form_{rid}"
        detail_key = f"detail_{rid}"

        if b1.button("여기로 방문", key=f"btn_visit_{rid}", use_container_width=True, type="primary"):
            st.session_state[visit_key] = True
        if b2.button("방문 불가", key=f"btn_unavail_{rid}", use_container_width=True):
            st.session_state[unavail_key] = True
        if b3.button("상세보기", key=f"btn_detail_{rid}", use_container_width=True):
            st.session_state[detail_key] = not st.session_state.get(detail_key, False)

        # --- 방문 저장 폼 ---
        if st.session_state.get(visit_key):
            _render_visit_form(item, settings, today, visit_key)

        # --- 방문 불가 폼 ---
        if st.session_state.get(unavail_key):
            _render_unavailable_form(item, today, unavail_key)

        # --- 상세보기 ---
        if st.session_state.get(detail_key):
            _render_detail(item, settings)


def _render_visit_form(item, settings, today, visit_key):
    """[여기로 방문] 인라인 입력 폼."""
    rid = item["id"]
    st.markdown(f"**{item['name']}을(를) 방문 기록으로 저장할까요?**")
    with st.form(key=f"form_visit_{rid}"):
        satisfaction = st.slider("만족도", 1.0, 5.0, 4.0, 0.5)
        actual_price = st.number_input(
            "실제 결제금액 (미입력 시 평균가격 저장)",
            min_value=0, value=int(item.get("avg_price") or 0), step=500,
        )
        memo = st.text_area("방문 메모", placeholder="예: 맛 괜찮은데 대기가 길었음")
        col_a, col_b = st.columns(2)
        save = col_a.form_submit_button("방문 저장", type="primary", use_container_width=True)
        cancel = col_b.form_submit_button("취소", use_container_width=True)

    if cancel:
        st.session_state[visit_key] = False
        st.rerun()

    if save:
        # AI 메모 분석 (실패해도 저장은 진행)
        ai_summary = ai_sentiment = ai_tags = None
        if memo:
            analysis = ai_analyzer.analyze_visit_memo_with_ai(
                item["name"], item.get("category"), memo, satisfaction, settings,
            )
            if analysis:
                ai_summary = analysis.get("summary")
                ai_sentiment = analysis.get("sentiment")
                ai_tags = ", ".join(analysis.get("tags", []))

        result = db.save_visit(
            restaurant_id=rid,
            visited_date=today,
            satisfaction=satisfaction,
            actual_price=actual_price if actual_price > 0 else None,
            memo=memo or None,
            ai_memo_summary=ai_summary,
            ai_sentiment=ai_sentiment,
            ai_tags=ai_tags,
        )
        st.session_state[visit_key] = False
        if result["ok"]:
            st.success(result["message"])
            # 추천 결과 무효화 -> 다음 추천에 반영
            st.session_state.pop("recommendations", None)
        else:
            st.warning(result["message"])
        st.rerun()


def _render_unavailable_form(item, today, unavail_key):
    """[방문 불가] 인라인 폼: 사유 선택 + 직접 입력."""
    rid = item["id"]
    with st.form(key=f"form_unavail_{rid}"):
        reason_sel = st.selectbox("방문 불가 사유", UNAVAILABLE_REASONS, key=f"reason_sel_{rid}")
        reason_text = st.text_input("직접 입력 (선택)", key=f"reason_text_{rid}",
                                    placeholder="예: 단체 손님이 많아 오래 걸림")
        col_a, col_b = st.columns(2)
        submit = col_a.form_submit_button("방문 불가 처리", type="primary", use_container_width=True)
        cancel = col_b.form_submit_button("취소", use_container_width=True)

    if cancel:
        st.session_state[unavail_key] = False
        st.rerun()

    if submit:
        reason = reason_sel
        if reason_text.strip():
            reason = f"{reason_sel} - {reason_text.strip()}"
        db.mark_unavailable_today(rid, reason, today)
        st.session_state[unavail_key] = False
        # 추천 재계산 위해 캐시 제거
        st.session_state.pop("recommendations", None)
        st.success(f"{item['name']}을(를) 오늘 추천에서 제외했습니다.")
        st.rerun()


def _render_detail(item, settings):
    """[상세보기]: 점수 분해 + 누적 메모 기반 AI 요약."""
    breakdown = item.get("breakdown") or {}
    if breakdown:
        st.markdown("**점수 구성**")
        st.json(breakdown, expanded=False)

    if item.get("map_url"):
        st.markdown(f"[지도에서 보기]({item['map_url']})")

    # 누적 메모 기반 AI 요약
    logs = [v for v in db.list_visit_logs() if v["restaurant_id"] == item["id"] and v.get("memo")]
    memos = [v["memo"] for v in logs]
    if memos and st.button("AI 요약 생성", key=f"ai_sum_{item['id']}"):
        with st.spinner("AI 요약 생성 중..."):
            summary = ai_analyzer.summarize_restaurant_memos(
                item["name"], item.get("category"), memos, settings,
            )
        if summary:
            st.markdown(f"**{item['name']} AI 요약**")
            if summary.get("summary"):
                st.write(summary["summary"])
            if summary.get("pros"):
                st.markdown("장점: " + ", ".join(summary["pros"]))
            if summary.get("cons"):
                st.markdown("단점: " + ", ".join(summary["cons"]))
            if summary.get("good_for"):
                st.markdown("추천 상황: " + ", ".join(summary["good_for"]))
            # 저장
            db.update_restaurant_ai(item["id"], summary.get("summary", ""),
                                    ", ".join(summary.get("tags", [])))
        else:
            st.info("AI 코멘트를 불러오지 못했습니다. 기본 추천 결과를 표시합니다.")
    elif not memos:
        st.caption("누적된 방문 메모가 없어 AI 요약을 생성할 수 없습니다.")
