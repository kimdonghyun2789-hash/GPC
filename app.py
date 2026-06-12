"""GPC IP Lens — 아이디어별 특허 검토 관리 도구."""
import io

import pandas as pd
import streamlit as st

from src import config, favorites, ideas, patent_search, synonyms
from src.claim_mapping import build_claim_mapping
from src.differentiation import DIFF_FIELDS, build_draft
from src.keyword_analysis import (
    build_foreign_queries,
    build_search_queries,
    extract_keywords,
)
from src.patent_sources import kipris_source
from src.patent_sources.kipris_source import PatentSearchError
from src.report_generator import generate_report
from src.similarity import analyze
from src.statistics import build_statistics
from src.ui import components
from src.ui.styles import apply_styles

st.set_page_config(page_title=config.APP_TITLE, layout="wide")
apply_styles()
config.ensure_dirs()
synonyms.ensure_file()

MENU_ITEMS = ["아이디어 검토", "특허 검색", "아이디어 관리", "관심특허", "보고서"]


# ---------------------------------------------------------------------------
# 검토 파이프라인
# ---------------------------------------------------------------------------
def run_review_pipeline(idea_text: str, scope: str, top_n: int):
    """[검토 시작] 클릭 시 전체 흐름을 순서대로 실행한다."""
    with st.status("검토를 진행하고 있습니다...", expanded=True) as status:
        st.write("아이디어 등록 중...")
        idea_id = ideas.next_idea_id()
        keywords = extract_keywords(idea_text)
        ideas.save_idea(
            {
                "idea_id": idea_id,
                "idea_text": idea_text,
                "keywords": ", ".join(keywords),
                "search_scope": scope,
                "top_n": top_n,
                "status": "아이디어 등록",
            }
        )
        st.write(f"Idea ID 생성: **{idea_id}**")

        st.write("핵심 키워드 추출 및 검색어 후보 생성 중...")
        queries = build_search_queries(keywords)
        foreign_queries = build_foreign_queries(keywords)

        st.write("특허 검색 중...")
        try:
            search_result = patent_search.run_search(scope, queries, foreign_queries)
        except PatentSearchError as error:
            status.update(label="특허 검색에 실패했습니다.", state="error")
            return {"idea_id": idea_id, "error": error}

        patents = search_result["patents"]
        if not patents:
            status.update(label="검색 결과가 없습니다.", state="error")
            return {"idea_id": idea_id, "empty": True}

        st.write(f"검색 완료: {len(patents)}건 수집")
        st.write("유사특허 분석 중...")
        candidates = analyze(idea_text, keywords, patents, top_n)

        if kipris_source.claims_lookup_configured():
            st.write("주요 유사특허 청구항 원문 조회 중...")
            kipris_source.enrich_claims(candidates)

        st.write("기본 통계 생성 중...")
        stats = build_statistics(patents, candidates)

        st.write("청구항 키워드 매칭 중...")
        claim_df = build_claim_mapping(keywords, candidates)

        st.write("차별화 포인트 초안 생성 중...")
        diff_draft = build_draft(idea_text, keywords, claim_df)

        ideas.save_collected(idea_id, candidates)
        ideas.update_idea(
            idea_id,
            status="검색 완료",
            total_results=len(patents),
            candidate_count=len(candidates),
            **diff_draft,
        )
        status.update(label="검토가 완료되었습니다.", state="complete", expanded=False)

    return {
        "idea_id": idea_id,
        "idea_text": idea_text,
        "scope": scope,
        "top_n": top_n,
        "keywords": keywords,
        "used_queries": search_result["used_queries"],
        "candidates": candidates,
        "stats": stats,
        "claim_df": claim_df,
        "diff_draft": diff_draft,
    }


def render_review_result(review: dict):
    """검토 결과 화면: 통계, 유사특허, 매칭표, 차별화 포인트, 보고서."""
    idea_id = review["idea_id"]
    top_n = review["top_n"]
    candidates = review["candidates"]

    st.markdown(f"#### 검토 결과 — {idea_id}")
    components.keyword_chips(review["keywords"])

    st.markdown("### 기본 통계")
    components.statistics_section(review["stats"])

    st.markdown(f"### 유사특허 TOP {top_n}")
    components.candidates_table(candidates)

    with st.expander("특허 상세보기"):
        options = {
            f"{p['rank']}. [{p.get('grade', '')}] {p.get('title', '')}": p
            for p in candidates
        }
        selected = st.selectbox(
            "상세보기할 특허 선택", list(options.keys()), key=f"detail_{idea_id}"
        )
        if selected:
            components.patent_detail(options[selected], idea_id=idea_id)

    st.markdown("### 청구항 키워드 매칭")
    st.dataframe(review["claim_df"], hide_index=True, width="stretch")
    st.caption(config.CLAIM_MAPPING_NOTICE)

    st.markdown("### 차별화 포인트")
    diff_values = {}
    for field, label in DIFF_FIELDS:
        key = f"diff_{idea_id}_{field}"
        if key not in st.session_state:
            st.session_state[key] = review["diff_draft"].get(field, "")
        diff_values[field] = st.text_area(label, key=key, height=90)
    ideas.update_idea(idea_id, **diff_values)

    # 보고서는 화면 내용(차별화 포인트 수정 포함)을 반영해 항상 새로 만든다.
    idea_record = ideas.get_idea(idea_id)
    favorites_df = favorites.load_favorites(idea_id)
    html_path, xlsx_path = generate_report(
        idea_record,
        candidates,
        review["stats"],
        review["claim_df"],
        diff_values,
        favorites_df,
    )
    ideas.update_idea(idea_id, report_html=html_path.name, results_xlsx=xlsx_path.name)

    st.markdown("### 보고서")
    st.caption("아래 보고서에는 현재 화면의 검토 내용이 반영되어 있습니다.")
    left, right = st.columns(2)
    left.download_button(
        "검토 보고서 내려받기",
        data=html_path.read_bytes(),
        file_name=html_path.name,
        mime="text/html",
        key=f"dl_html_{idea_id}",
    )
    right.download_button(
        "결과 파일 내려받기",
        data=xlsx_path.read_bytes(),
        file_name=xlsx_path.name,
        key=f"dl_xlsx_{idea_id}",
    )


# ---------------------------------------------------------------------------
# 1. 아이디어 검토
# ---------------------------------------------------------------------------
def page_idea_review():
    st.title(config.APP_TITLE)

    with st.container():
        idea_text = st.text_area(
            "기술 아이디어",
            placeholder=config.IDEA_PLACEHOLDER,
            height=120,
            key="idea_input",
        )
        left, right = st.columns(2)
        scope = left.selectbox("검색 범위", config.SEARCH_SCOPES, key="scope_select")
        top_n = right.selectbox(
            "유사특허 표시 개수",
            config.TOP_N_OPTIONS,
            index=config.TOP_N_OPTIONS.index(config.DEFAULT_TOP_N),
            key="topn_select",
        )
        start = st.button("검토 시작", type="primary")

    if start:
        if not idea_text.strip():
            st.warning("기술 아이디어를 입력하세요.")
        else:
            st.session_state["review"] = run_review_pipeline(
                idea_text.strip(), scope, int(top_n)
            )

    review = st.session_state.get("review")
    if not review:
        return
    if "error" in review:
        components.search_error(review["error"])
        return
    if review.get("empty"):
        st.warning("검색 결과가 없습니다. 아이디어 문장을 조금 더 구체적으로 입력해 보세요.")
        return
    render_review_result(review)


# ---------------------------------------------------------------------------
# 2. 특허 검색
# ---------------------------------------------------------------------------
def page_patent_search():
    st.header("특허 검색")
    st.caption("아이디어 등록 없이 키워드로 빠르게 특허를 찾아봅니다.")

    query = st.text_input("검색어", placeholder="예: 중공기둥 배수")
    scope = st.selectbox("검색 범위", config.SEARCH_SCOPES, key="quick_scope")
    search = st.button("검색", type="primary")

    if search:
        if not query.strip():
            st.warning("검색어를 입력하세요.")
            return
        try:
            with st.spinner("검색 중..."):
                result = patent_search.run_search(scope, [query.strip()])
        except PatentSearchError as error:
            components.search_error(error)
            return
        st.session_state["quick_search"] = result["patents"]

    patents = st.session_state.get("quick_search")
    if patents is None:
        return
    if not patents:
        st.info("검색 결과가 없습니다.")
        return

    st.markdown(f"**검색 결과 {len(patents)}건**")
    table = pd.DataFrame(
        [
            {
                "국가/출처": p.get("source", ""),
                "발명의 명칭": p.get("title", ""),
                "출원인": p.get("applicant", ""),
                "공개번호": p.get("pub_number", ""),
                "출원일": p.get("app_date", ""),
                "권리상태": p.get("status", ""),
            }
            for p in patents
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")

    with st.expander("특허 상세보기"):
        options = {
            f"{i + 1}. {p.get('title', '')}": p for i, p in enumerate(patents[:50])
        }
        selected = st.selectbox("상세보기할 특허 선택", list(options.keys()))
        if selected:
            components.patent_detail(options[selected])


# ---------------------------------------------------------------------------
# 3. 아이디어 관리
# ---------------------------------------------------------------------------
def page_idea_management():
    st.header("아이디어 관리")
    idea_df = ideas.load_ideas()
    if idea_df.empty:
        st.info("저장된 아이디어가 없습니다. 아이디어 검토에서 검토를 시작하세요.")
        return

    view = idea_df[
        ["idea_id", "created_at", "idea_text", "status", "candidate_count"]
    ].rename(
        columns={
            "idea_id": "Idea ID",
            "created_at": "등록일",
            "idea_text": "아이디어",
            "status": "검토상태",
            "candidate_count": "유사특허 후보 수",
        }
    )
    st.dataframe(view, hide_index=True, width="stretch")

    buffer = io.BytesIO()
    idea_df.to_excel(buffer, index=False)
    st.download_button(
        "아이디어 목록 내려받기 (Excel)",
        data=buffer.getvalue(),
        file_name="idea_database.xlsx",
    )

    st.markdown("---")
    selected_id = st.selectbox("아이디어 열기", idea_df["idea_id"].tolist()[::-1])
    if not selected_id:
        return
    idea = ideas.get_idea(selected_id)

    st.markdown(f"#### {selected_id}")
    st.write(idea.get("idea_text", ""))
    components.keyword_chips(idea.get("keywords", ""))

    left, right = st.columns(2)
    with left:
        current_status = idea.get("status", config.IDEA_STATUSES[0])
        status_index = (
            config.IDEA_STATUSES.index(current_status)
            if current_status in config.IDEA_STATUSES
            else 0
        )
        new_status = st.selectbox(
            "검토상태", config.IDEA_STATUSES, index=status_index,
            key=f"status_{selected_id}",
        )
        if new_status != current_status:
            ideas.update_idea(selected_id, status=new_status)
            st.toast("검토상태를 변경했습니다.")
    with right:
        comment = st.text_area(
            "검토의견",
            value=idea.get("review_comment", ""),
            key=f"comment_{selected_id}",
            height=90,
        )
        if comment != idea.get("review_comment", ""):
            ideas.update_idea(selected_id, review_comment=comment)
            st.toast("검토의견을 저장했습니다.")

    collected = ideas.load_collected(selected_id)
    if not collected.empty:
        with st.expander(f"수집된 유사특허 보기 ({len(collected)}건)"):
            st.dataframe(
                collected[
                    [
                        "rank", "source", "grade", "title", "applicant",
                        "pub_number", "matched_keywords",
                    ]
                ].rename(
                    columns={
                        "rank": "순위",
                        "source": "국가/출처",
                        "grade": "유사도 등급",
                        "title": "발명의 명칭",
                        "applicant": "출원인",
                        "pub_number": "공개번호",
                        "matched_keywords": "핵심 유사 키워드",
                    }
                ),
                hide_index=True,
                width="stretch",
            )

    html_name = idea.get("report_html", "")
    xlsx_name = idea.get("results_xlsx", "")
    html_path = config.REPORTS_DIR / html_name if html_name else None
    xlsx_path = config.REPORTS_DIR / xlsx_name if xlsx_name else None
    left, right = st.columns(2)
    if html_path and html_path.exists():
        left.download_button(
            "보고서 열기 (HTML)",
            data=html_path.read_bytes(),
            file_name=html_path.name,
            mime="text/html",
            key=f"mgmt_html_{selected_id}",
        )
    if xlsx_path and xlsx_path.exists():
        right.download_button(
            "결과 파일 열기 (Excel)",
            data=xlsx_path.read_bytes(),
            file_name=xlsx_path.name,
            key=f"mgmt_xlsx_{selected_id}",
        )

    with st.expander("아이디어 삭제"):
        st.warning("아이디어와 수집된 유사특허 기록이 함께 삭제됩니다.")
        if st.button("삭제", key=f"delete_{selected_id}"):
            ideas.delete_idea(selected_id)
            st.success("삭제했습니다.")
            st.rerun()


# ---------------------------------------------------------------------------
# 4. 관심특허
# ---------------------------------------------------------------------------
def page_favorites():
    st.header("관심특허")
    favorites_df = favorites.load_favorites()
    if favorites_df.empty:
        st.info("저장된 관심특허가 없습니다. 특허 상세보기에서 관심특허를 추가하세요.")
        return

    idea_options = ["전체"] + sorted(favorites_df["idea_id"].unique().tolist())
    selected_idea = st.selectbox("Idea ID", idea_options)
    filtered = (
        favorites_df
        if selected_idea == "전체"
        else favorites_df[favorites_df["idea_id"] == selected_idea]
    )

    st.dataframe(
        filtered[
            [
                "idea_id", "source", "grade", "title", "applicant",
                "pub_number", "review_comment", "added_at",
            ]
        ].rename(
            columns={
                "idea_id": "Idea ID",
                "source": "국가/출처",
                "grade": "유사도 등급",
                "title": "발명의 명칭",
                "applicant": "출원인",
                "pub_number": "공개번호",
                "review_comment": "검토의견",
                "added_at": "저장일",
            }
        ),
        hide_index=True,
        width="stretch",
    )

    buffer = io.BytesIO()
    filtered.to_excel(buffer, index=False)
    st.download_button(
        "관심특허 내려받기 (Excel)",
        data=buffer.getvalue(),
        file_name="favorite_patents.xlsx",
    )

    with st.expander("관심특허 수정/삭제"):
        options = {
            f"[{row['idea_id']}] {row['title']}": row
            for _, row in filtered.iterrows()
        }
        selected = st.selectbox("특허 선택", list(options.keys()))
        if selected:
            row = options[selected]
            key = row["pub_number"] or row["title"]
            comment = st.text_area(
                "검토의견", value=row.get("review_comment", ""), height=90,
                key=f"fav_edit_{row['idea_id']}_{key}",
            )
            left, right = st.columns(2)
            if left.button("검토의견 저장"):
                favorites.update_comment(row["idea_id"], key, comment)
                st.success("저장했습니다.")
                st.rerun()
            if right.button("관심특허에서 삭제"):
                favorites.remove_favorite(row["idea_id"], key)
                st.success("삭제했습니다.")
                st.rerun()


# ---------------------------------------------------------------------------
# 5. 보고서
# ---------------------------------------------------------------------------
def page_reports():
    st.header("보고서")
    config.ensure_dirs()
    html_reports = sorted(config.REPORTS_DIR.glob("*_report.html"), reverse=True)
    if not html_reports:
        st.info("생성된 보고서가 없습니다. 아이디어 검토를 먼저 진행하세요.")
        return

    options = {path.stem.replace("_report", ""): path for path in html_reports}
    selected_id = st.selectbox("Idea ID", list(options.keys()))
    html_path = options[selected_id]
    xlsx_path = config.REPORTS_DIR / f"{selected_id}_results.xlsx"

    left, right = st.columns(2)
    left.download_button(
        "검토 보고서 내려받기 (HTML)",
        data=html_path.read_bytes(),
        file_name=html_path.name,
        mime="text/html",
    )
    if xlsx_path.exists():
        right.download_button(
            "결과 파일 내려받기 (Excel)",
            data=xlsx_path.read_bytes(),
            file_name=xlsx_path.name,
        )

    with st.expander("보고서 미리보기", expanded=True):
        st.iframe(html_path, height=800)


# ---------------------------------------------------------------------------
# 메뉴
# ---------------------------------------------------------------------------
def main():
    with st.sidebar:
        st.markdown(f"### {config.APP_TITLE}")
        menu = st.radio("메뉴", MENU_ITEMS, label_visibility="collapsed")

    pages = {
        "아이디어 검토": page_idea_review,
        "특허 검색": page_patent_search,
        "아이디어 관리": page_idea_management,
        "관심특허": page_favorites,
        "보고서": page_reports,
    }
    pages[menu]()


if __name__ == "__main__":
    main()
