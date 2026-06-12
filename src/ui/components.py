"""화면 공통 컴포넌트: chip, badge, 통계 카드, 표, 상세보기."""
import html

import pandas as pd
import streamlit as st

from src import config, favorites


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def keyword_chips(keywords) -> None:
    """핵심 키워드를 chip 형태로 표시한다."""
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keywords:
        return
    chips = "".join(f"<span class='gpc-chip'>{_esc(k)}</span>" for k in keywords)
    st.markdown(chips, unsafe_allow_html=True)


def source_badge(source: str) -> str:
    """국가/출처 badge HTML."""
    css = "gpc-badge-kr" if str(source) == "국내" else "gpc-badge-foreign"
    return f"<span class='gpc-badge {css}'>{_esc(source)}</span>"


def search_error(error) -> None:
    """짧은 한국어 안내 + 상세 오류 expander."""
    st.error(config.SEARCH_UNAVAILABLE_MESSAGE)
    detail = getattr(error, "detail", "") or str(error)
    with st.expander(config.ERROR_EXPANDER_TITLE):
        st.code(detail)


def stat_cards(stats: dict) -> None:
    grade_df = stats.get("grade_df")
    very_similar = 0
    if grade_df is not None and not grade_df.empty:
        match = grade_df[grade_df["유사도 등급"] == "매우 유사"]["건수"]
        very_similar = int(match.iloc[0]) if not match.empty else 0
    items = [
        ("검색 결과 총 건수", stats.get("total_results", 0)),
        ("유사특허 후보 수", stats.get("candidate_count", 0)),
        ("매우 유사 건수", very_similar),
    ]
    columns = st.columns(len(items))
    for column, (label, value) in zip(columns, items):
        column.markdown(
            f"<div class='gpc-card'><div class='gpc-stat-label'>{_esc(label)}</div>"
            f"<div class='gpc-stat-value'>{_esc(value)}</div></div>",
            unsafe_allow_html=True,
        )


def statistics_section(stats: dict) -> None:
    """요약 카드 + 간단한 차트 중심의 기본 통계."""
    stat_cards(stats)

    left, right = st.columns(2)
    with left:
        country_df = stats.get("country_df")
        if country_df is not None and not country_df.empty:
            st.markdown("**국가/출처별 건수**")
            st.bar_chart(country_df.set_index("국가/출처"), height=220)
        grade_df = stats.get("grade_df")
        if grade_df is not None and not grade_df.empty:
            st.markdown("**유사도 등급 분포**")
            st.bar_chart(grade_df.set_index("유사도 등급"), height=220)
    with right:
        year_df = stats.get("year_df")
        if year_df is not None and not year_df.empty:
            st.markdown("**연도별 공개/출원 추이**")
            st.line_chart(year_df, height=220)

    with st.expander("주요 출원인 / 분류 보기"):
        left, right = st.columns(2)
        applicant_df = stats.get("applicant_df")
        ipc_df = stats.get("ipc_df")
        with left:
            st.markdown("**주요 출원인 TOP 10**")
            if applicant_df is not None and not applicant_df.empty:
                st.dataframe(applicant_df, hide_index=True, width="stretch")
            else:
                st.caption("해당 없음")
        with right:
            st.markdown("**분류(IPC/CPC) TOP 10**")
            if ipc_df is not None and not ipc_df.empty:
                st.dataframe(ipc_df, hide_index=True, width="stretch")
            else:
                st.caption("해당 없음")


def candidates_table(candidates: list) -> None:
    """유사특허 기본 표 — 핵심 컬럼만 표시한다."""
    rows = [
        {
            "순위": p.get("rank", ""),
            "국가/출처": p.get("source", ""),
            "유사도 등급": p.get("grade", ""),
            "발명의 명칭": p.get("title", ""),
            "출원인": p.get("applicant", ""),
            "공개번호": p.get("pub_number", ""),
            "핵심 유사 키워드": p.get("matched_keywords", ""),
            "검토 필요 사유": p.get("review_reason", ""),
        }
        for p in candidates
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def patent_detail(patent: dict, idea_id: str = "") -> None:
    """상세보기: 자세한 항목 + 원문 열기 + 관심특허 추가."""
    st.markdown(
        f"{source_badge(patent.get('source', ''))} "
        f"**{_esc(patent.get('title', ''))}**",
        unsafe_allow_html=True,
    )

    fields = [
        ("출원인", patent.get("applicant")),
        ("국가/출처", patent.get("source")),
        ("출원번호", patent.get("app_number")),
        ("공개번호", patent.get("pub_number")),
        ("등록번호", patent.get("reg_number")),
        ("출원일", patent.get("app_date")),
        ("공개일", patent.get("pub_date")),
        ("IPC/CPC", patent.get("ipc")),
        ("권리상태", patent.get("status")),
    ]
    info = pd.DataFrame(
        [(label, str(value or "-")) for label, value in fields],
        columns=["항목", "내용"],
    )
    st.dataframe(info, hide_index=True, width="stretch")

    abstract = str(patent.get("abstract") or "").strip()
    st.markdown("**요약**")
    st.write(abstract if abstract else "제공된 요약이 없습니다.")

    claims = str(patent.get("claims") or "").strip()
    st.markdown("**대표 청구항**")
    if claims:
        st.write(claims.split("\n")[0])
        with st.expander("전체 청구항 보기"):
            st.write(claims)
    else:
        st.caption("청구항 원문은 아래 원문 열기에서 확인할 수 있습니다.")

    link = str(patent.get("link") or "").strip()
    if link:
        st.markdown(f"[원문 열기]({link})")

    matched = str(patent.get("matched_keywords") or "").strip()
    if matched:
        st.markdown("**핵심 유사 키워드**")
        keyword_chips(matched)

    reason = str(patent.get("review_reason") or "").strip()
    if reason:
        st.markdown("**검토 필요 사유**")
        st.write(reason)

    if idea_id:
        comment = st.text_input(
            "검토의견",
            key=f"fav_comment_{idea_id}_{patent.get('rank', patent.get('pub_number', ''))}",
            placeholder="이 특허에 대한 검토의견을 입력하세요",
        )
        if favorites.is_favorite(idea_id, patent):
            st.caption("이미 관심특허에 저장된 특허입니다.")
        elif st.button(
            "관심특허 추가",
            key=f"fav_add_{idea_id}_{patent.get('rank', patent.get('pub_number', ''))}",
        ):
            favorites.add_favorite(idea_id, patent, comment)
            st.success("관심특허에 추가했습니다.")
            st.rerun()
