"""
components/restaurant_card.py
추천 카드 1장을 렌더링하는 컴포넌트.
- 순위/식당명/메뉴분류/대표메뉴/도보/가격/선호도/혼잡도/최근방문일/점수/사유/예산상태/AI코멘트 표시
- [여기로 방문] / [방문 불가] / [상세보기] 버튼과 인라인 입력 폼 처리
- 방문 저장 시 AI 메모 분석을 수행하고 visit_logs에 저장한다.
"""

from __future__ import annotations

import streamlit as st

from services import db, ai_analyzer, naver_map
from utils import format_utils, date_utils
from utils.ui import match_meta

# 예산 상태 키 -> 점 색상 / 라벨
_BUDGET_DOT = {
    "ok": ("#1F6F54", "예산 적합"),
    "near": ("#E8722B", "예산 약간 초과"),
    "over": ("#C62828", "예산 초과"),
}

# 방문 불가 기본 사유 (PRD 14.2)
UNAVAILABLE_REASONS = [
    "만석", "휴무", "메뉴 품절", "너무 멀다", "오늘 안 땡김",
    "팀원 반대", "가격 부담", "날씨 때문에 어려움", "기타",
]


def _headline_reason(item: dict, meal_budget: int) -> str:
    """식당 속성에서 가장 변별력 있는 추천 이유 1~2개를 골라 자연어 한 줄로 만든다."""
    try:
        walk = float(item.get("walk_minutes") or 99)
    except (TypeError, ValueError):
        walk = 99
    try:
        price = float(item.get("avg_price") or 0)
    except (TypeError, ValueError):
        price = 0
    try:
        rating = float(item.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    crowd = item.get("crowd_level")

    points: list[str] = []
    avg_sat = item.get("avg_satisfaction")
    if avg_sat is not None and avg_sat >= 4.0:
        points.append(f"내가 만족했던 곳이에요 (★{avg_sat:.1f})")
    if walk <= 4:
        points.append(f"회사에서 가까운 편이에요 (도보 {int(walk)}분)")
    if rating >= 4.2:
        points.append(f"평이 좋은 편이에요 (★{rating:.1f})")
    if price and price <= 8000:
        points.append(f"가격이 부담 없어요 ({format_utils.won(price)})")
    if crowd == "여유":
        points.append("덜 붐벼서 빨리 먹기 좋아요")
    if not item.get("last_visited"):
        points.append("아직 안 가본 곳이라 새로 시도해볼 만해요")
    if price and meal_budget and price <= meal_budget and not points:
        points.append("오늘 예산에 잘 맞아요")
    if not points:
        points.append("오늘 조건에 두루 맞는 무난한 선택이에요")

    return " · ".join(points[:2])


def render_recommendation_card(item: dict, settings: dict, today=None) -> None:
    """추천 카드 한 장을 렌더링한다. item은 recommender 결과의 단일 dict."""
    today = date_utils.to_date(today)
    rid = item["id"]
    rank = item.get("rank", "-")
    meal_budget = settings.get("meal_budget", 12000)

    with st.container(border=True):
        rank_cls = f"r{rank}" if isinstance(rank, int) and rank in (1, 2, 3) else "r3"
        band_cls, band_label = match_meta(item.get("match", 70))

        # 예산 점
        bkey = format_utils.budget_status_label(item.get("avg_price"), meal_budget)
        bcolor, blabel = _BUDGET_DOT.get(bkey, _BUDGET_DOT["ok"])

        # 메타 라인
        sep = '<span class="sep">·</span>'
        meta = sep.join([
            f"<span>도보 <b>{int(item.get('walk_minutes') or 0)}분</b></span>",
            f"<span>1인 <b>{format_utils.won(item.get('avg_price'))}</b></span>",
            f"<span>{format_utils.rating(item.get('rating'))}</span>",
            f"<span>혼잡도 {item.get('crowd_level') or '-'}</span>",
            f'<span><span class="mml-bdot" style="background:{bcolor}"></span>{blabel}</span>',
        ])

        # 핵심 사유 한 줄 (AI 코멘트가 있으면 우선, 없으면 식당별 변별 문구)
        if item.get("ai_comment"):
            why = item["ai_comment"]
        else:
            why = _headline_reason(item, meal_budget)

        # 최근 방문 정보
        last = item.get("last_visited")
        vcount = item.get("visit_count", 0)
        if last:
            sublog = f"최근 방문 {last} · 누적 {vcount}회"
        else:
            sublog = "아직 방문한 적 없는 식당이에요"

        ribbon = '<div class="mml-ribbon">오늘의 1순위 추천</div>' if rank == 1 else ""

        # 상단 띠(헤더): 순위 배지 + 이름 + 매칭. 카드 가장자리까지 채운다.
        st.markdown(
            f"""<div class="mml-head {rank_cls}">
  {ribbon}
  <div class="mml-headrow">
    <div class="mml-rk">{rank}</div>
    <div class="mml-titlewrap">
      <div class="mml-name">{item['name']}</div>
      <div class="mml-sub">{item.get('category') or '-'} · {item.get('main_menu') or '-'}</div>
    </div>
    <div class="mml-match {band_cls}"><div class="p">{item.get('match', '-')}%</div><div class="l">{band_label}</div></div>
  </div>
</div>
<div class="mml-meta">{meta}</div>
<div class="mml-why">{why}</div>
<div class="mml-sublog">{sublog}</div>""",
            unsafe_allow_html=True,
        )

        # 버튼 3종 (카드 안에서 한 줄로)
        b1, b2, b3 = st.columns(3, gap="small")
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
            "실제 결제금액 (1인 기준 · 미입력 시 평균가격 저장)",
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
    """[상세보기]: 위치/지도 + 단체 정보 + 점수 분해 + 누적 메모 AI 요약."""
    # --- 위치 / 네이버 지도 ---
    if item.get("address"):
        st.caption(f"📍 {item['address']}")

    map_bytes = naver_map.static_map_bytes(item.get("latitude"), item.get("longitude"))
    if map_bytes:
        st.image(map_bytes, use_container_width=True)

    nlink = naver_map.map_link(item["name"], item.get("address"))
    links = [f"[네이버 지도에서 보기 · 길찾기]({nlink})"]
    if item.get("map_url"):
        links.append(f"[등록된 지도 링크]({item['map_url']})")
    st.markdown(" · ".join(links))

    # --- 단체/포장 정보 ---
    info_bits = []
    info_bits.append("단체 가능" if item.get("can_group") else "단체 어려움")
    if item.get("max_party"):
        info_bits.append(f"최대 {int(item['max_party'])}인")
    if item.get("can_takeout"):
        info_bits.append("포장 가능")
    st.caption(" · ".join(info_bits))

    # --- 점수 구성 ---
    breakdown = item.get("breakdown") or {}
    if breakdown:
        with st.expander("추천 점수 구성 보기"):
            st.json(breakdown, expanded=True)

    # --- 한동안 추천 제외(블랙리스트) ---
    if st.button("🚫 한동안 그만 보기 (30일 추천 제외)", key=f"bl_{item['id']}"):
        db.set_blacklist(item["id"], days=30)
        st.session_state.pop("recommendations", None)
        st.success(f"{item['name']}을(를) 30일간 추천에서 제외했습니다.")
        st.rerun()

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
