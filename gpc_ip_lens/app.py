# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 건설/PC 특화 특허 탐색·분석 프로그램 (Streamlit 메인 앱).

실행: streamlit run app.py
"""
import hashlib
import html as _html
import io
import json

st_html_escape = _html.escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyzers import ai_review as review_mod
from analyzers import claim_chart
from analyzers import keyword_expander
from analyzers import network_map as netmap
from analyzers import patent_dna as dna_mod
from analyzers import similarity as sim_mod
from analyzers import statistics as stats
from analyzers import technology_timeline as timeline_mod
from analyzers.classifier import TECH_GROUPS
from exporters import excel_exporter, image_exporter, pdf_exporter
from services import gemini_service
from services.kipris_client import KiprisClient
from utils import cache_utils, config, db, ui
from utils.text_utils import split_keywords

_ICON_PATH = config.BASE_DIR / "assets" / "brand" / "ip3-logo.png"
st.set_page_config(
    page_title="IP³ · IP Cube",
    page_icon=str(_ICON_PATH) if _ICON_PATH.exists() else "◼",
    layout="wide", initial_sidebar_state="expanded")
ui.inject_theme()

try:
    db.init_db()
except Exception as exc:  # DB 오류 시 사용자 안내
    st.error(f"데이터베이스 초기화 오류: {exc}. db 폴더 권한을 확인하세요.")

MENU = [
    "Idea Canvas", "Patent Radar", "Patent DNA", "Landscape",
    "Drawing Intelligence", "AI Patent Review", "History",
    "Export Center", "Settings",
]
# 사이드바 표시용 한글 라벨 (내부 키는 영문 유지 — 페이지 매핑/로직 불변)
MENU_KO = {
    "Idea Canvas": "아이디어 입력",
    "Patent Radar": "유사특허 분석",
    "Patent DNA": "특허 DNA 비교",
    "Landscape": "통계 · 기술분석",
    "Drawing Intelligence": "도면 분석",
    "AI Patent Review": "AI 검토",
    "History": "기록 · 관심특허",
    "Export Center": "보고서 · 내보내기",
    "Settings": "설정",
}

# 단계별 내비게이션 그룹 (key, 한글 라벨, 아이콘) — 사용 흐름이 보이도록 구성
NAV_GROUPS = [
    ("", [("Dashboard", "대시보드", ":material/dashboard:")]),
    ("STEP 1 · 입력", [
        ("Idea Canvas", "아이디어 입력", ":material/lightbulb:")]),
    ("STEP 2 · 분석 결과", [
        ("Patent Radar", "유사특허 분석", ":material/radar:"),
        ("Patent DNA", "특허 DNA 비교", ":material/compare_arrows:"),
        ("Landscape", "통계 · 기술분석", ":material/insights:"),
        ("Drawing Intelligence", "도면 분석", ":material/image:"),
        ("AI Patent Review", "AI 검토", ":material/smart_toy:")]),
    ("STEP 3 · 활용", [
        ("History", "기록 · 관심특허", ":material/bookmark:"),
        ("Export Center", "보고서 · 내보내기", ":material/description:")]),
    ("", [("Settings", "설정", ":material/settings:")]),
]

DEMO_IDEA = {
    "title": "중공 PC 기둥 하부 배수 및 점검 일체형 구조",
    "description": ("프리캐스트 중공기둥 내부에 유입된 우수와 결로수를 기둥 "
                    "하단의 배수 포트로 배출하고, 동일 포트를 통해 내시경 "
                    "점검이 가능하도록 한 배수·유지관리 일체형 구조. 포트에는 "
                    "이물질 유입 방지 필터 마개를 적용한다."),
    "keywords": "중공기둥, 배수, 점검, 프리캐스트, 포트",
    "exclude_keywords": "교량 상판",
}


# ============================================================ 공통 유틸
def ss_get(key, default=None):
    return st.session_state.get(key, default)


def get_results_df() -> pd.DataFrame:
    df = ss_get("results_df")
    return df if df is not None else pd.DataFrame()


def require_results() -> pd.DataFrame:
    df = get_results_df()
    if df.empty:
        st.info("아직 분석할 검색 결과가 없습니다. **STEP 1 · 아이디어 입력**에서 "
                "아이디어를 한 번 입력·검색하면, 그 결과가 이 화면에 표시됩니다.")
        if st.button("아이디어 입력으로 가기", type="primary",
                     icon=":material/lightbulb:", key="goto_idea_empty"):
            goto("Idea Canvas")
    return df


def placeholder_drawing(patent: dict) -> bytes:
    """도면 이미지가 없을 때 표시할 placeholder PNG 생성 (PIL).

    기술군별로 간단한 라인 스케치를 다르게 그려 갤러리에서 구분되게 한다.
    """
    from PIL import Image, ImageDraw

    app_no = str(patent.get("application_no", ""))
    group = str(patent.get("technology_group", "기타"))
    cache_file = config.DRAWINGS_DIR / f"ph_{app_no.replace('-', '')}.png"
    if cache_file.exists():
        return cache_file.read_bytes()

    img = Image.new("RGB", (420, 300), "#f5f7fa")
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 411, 291], outline="#9aa7b5", width=2)
    seed = int(hashlib.md5(app_no.encode()).hexdigest()[:6], 16)

    # 기둥 단면 형태의 간단한 스케치
    cx = 210
    d.rectangle([cx - 60, 50, cx + 60, 240], outline="#33475e", width=3)
    if "배수" in group:
        d.ellipse([cx - 12, 215, cx + 12, 239], outline="#1f77b4", width=3)
        d.line([cx, 90, cx, 210], fill="#1f77b4", width=2)
    elif "접합" in group or "전단" in group:
        for y in (110, 150, 190):
            d.line([cx - 60, y, cx + 60, y], fill="#d62728", width=2)
            d.polygon([(cx - 8, y - 8), (cx + 8, y), (cx - 8, y + 8)],
                      outline="#d62728")
    elif "몰드" in group or "생산" in group:
        d.rectangle([cx - 80, 60, cx + 80, 230], outline="#2ca02c", width=2)
        d.line([cx - 80, 145, cx + 80, 145], fill="#2ca02c", width=2)
    elif "센서" in group or "품질" in group:
        d.ellipse([cx - 10, 130, cx + 10, 150], outline="#e377c2", width=3)
        for i in range(3):
            r = 18 + i * 12
            d.arc([cx - r, 120 - r // 2, cx + r, 160 + r // 2], 300, 60,
                  fill="#e377c2", width=2)
    else:
        d.line([cx - 60, 50, cx + 60, 240], fill="#7f7f7f", width=2)
        d.line([cx + 60, 50, cx - 60, 240], fill="#7f7f7f", width=2)
    # 치수선 느낌의 장식 (seed 로 위치 변화)
    off = seed % 30
    d.line([60 + off, 270, 360 - off, 270], fill="#9aa7b5", width=1)
    d.text((20, 18), f"No. {app_no}", fill="#33475e")
    d.text((20, 272), "IP3 (IP Cube) - representative drawing (mock)",
           fill="#9aa7b5")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    try:
        cache_file.write_bytes(data)
    except OSError:
        pass
    return data


def get_drawing(patent: dict):
    """대표도면: 실제 URL 이 있으면 URL, 없으면 placeholder bytes."""
    url = str(patent.get("drawing_url") or "").strip()
    if url.startswith("http"):
        return url
    return placeholder_drawing(patent)


def drawing_caption(patent: dict) -> str:
    """도면 캡션: 캐시 → Gemini → 규칙 기반 fallback."""
    app_no = str(patent.get("application_no", ""))
    cache_key = f"caption::{app_no}"
    cached = cache_utils.cache_get(cache_key)
    if cached:
        return cached
    caption = None
    if gemini_service.is_available():
        caption = gemini_service.caption_drawing(
            patent.get("title", ""), patent.get("abstract", ""))
    if not caption:
        title = str(patent.get("title", ""))
        group = str(patent.get("technology_group", "기타"))
        caption = (title[:18] + "…") if len(title) > 18 else title
        caption = f"[{group}] {caption}"
    cache_utils.cache_set(cache_key, caption)
    return caption


def select_patent(app_no: str):
    st.session_state["selected_patent"] = app_no


def get_selected_patent(df: pd.DataFrame):
    sel = ss_get("selected_patent")
    if sel and not df.empty:
        rows = df[df["application_no"] == sel]
        if len(rows):
            return rows.iloc[0].to_dict()
    return df.iloc[0].to_dict() if not df.empty else None


def render_patent_detail(p: dict, idea_dna: dict):
    """특허 상세 패널 (Patent Radar / Drawing Intelligence 공용)."""
    col_img, col_info = st.columns([1, 2])
    with col_img:
        st.image(get_drawing(p), caption=drawing_caption(p),
                 use_container_width=True)
    with col_info:
        st.markdown(f"#### {p.get('title','')}")
        score = p.get("total_score", 0)
        badges = " ".join([
            ui.status_badge(p.get("status", "-")),
            ui.group_badge(p.get("technology_group", "기타")),
            ui.grade_badge(p.get("grade", sim_mod.grade(score))),
            f"<span class='gpc-badge' style='background:#E3EDFF;color:#0057FF'>"
            f"유사도 {score:.0f}</span>",
        ])
        st.markdown(f"<div style='margin:2px 0 10px'>{badges}</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"- **출원번호**: {p.get('application_no','-')} | "
            f"**출원일**: {p.get('application_date','-')}\n"
            f"- **공개번호/일**: {p.get('publication_no','-') or '-'} / "
            f"{p.get('publication_date','-') or '-'}\n"
            f"- **등록번호/일**: {p.get('registration_no','-') or '-'} / "
            f"{p.get('registration_date','-') or '-'}\n"
            f"- **출원인**: {p.get('applicant','-')}\n"
            f"- **IPC**: {p.get('ipc','-')} | **CPC**: {p.get('cpc','-')}")
        url = p.get("kipris_url") or ""
        if url:
            st.markdown(f"[KIPRIS 원문 보기]({url})")
        app_no = p.get("application_no", "")
        marked = db.is_bookmarked(app_no) if app_no else False
        blabel = "★ 관심 특허 해제" if marked else "☆ 관심 특허 추가"
        if st.button(blabel, key=f"bm_{app_no}"):
            if marked:
                db.remove_bookmark(app_no)
            else:
                db.add_bookmark(app_no, p.get("title", ""),
                                p.get("applicant", ""))
            st.rerun()
    with st.expander("요약", expanded=True):
        st.write(p.get("abstract", "-"))
    with st.expander("대표청구항"):
        st.write(p.get("representative_claim", "-"))
    with st.expander("특허 DNA / 내 아이디어와 비교"):
        p_dna = p.get("patent_dna") or {}
        if isinstance(p_dna, str):
            try:
                p_dna = json.loads(p_dna)
            except json.JSONDecodeError:
                p_dna = {}
        st.json(p_dna)
        common, diff = dna_mod.common_and_diff(idea_dna or {}, p_dna)
        c1, c2 = st.columns(2)
        c1.markdown("**공통점**: " + (", ".join(common) or "-"))
        c2.markdown("**차이점(내 아이디어에만)**: " + (", ".join(diff) or "-"))


# ============================================================ 검색 파이프라인
def run_search_pipeline(idea: dict, expansion: dict, top_n: int,
                        per_query: int = 25):
    """검색식 실행 → 중복제거 → 유사도 계산 → DB 저장 → 세션 반영."""
    client = KiprisClient()
    queries = list(expansion.get("search_queries", []))[:5]
    if not queries:
        st.error("실행할 검색식이 없습니다. 검색어 확장을 먼저 실행하세요.")
        return

    with st.spinner(f"KIPRIS 검색 실행 중 ({client.mode} 모드, "
                    f"검색식 {len(queries)}개)..."):
        try:
            patents = client.search_multi(
                queries, per_query=per_query,
                exclude_keywords=idea.get("exclude_keywords", ""))
        except Exception as exc:
            st.error(f"KIPRIS 검색 실패: {exc}")
            return
    if not patents:
        st.warning("검색 결과가 없습니다. 검색식을 수정해 보세요.")
        return

    with st.spinner(f"{len(patents)}건 유사도 분석 중..."):
        results = sim_mod.score_patents(idea, patents, expansion,
                                        use_gemini_dna=False)
    df = stats.to_dataframe(results)

    # DB 저장 (오류가 나도 화면 동작은 유지)
    try:
        idea_id = db.save_idea(idea.get("title", ""), idea.get("description", ""),
                               idea.get("keywords", ""),
                               idea.get("exclude_keywords", ""),
                               idea.get("idea_dna", {}))
        for r in results:
            patent_id = db.upsert_patent(r)
            db.save_search_result(idea_id, patent_id, {
                "search_query": r.get("search_query", ""),
                "vector_score": r["vector_score"],
                "keyword_score": r["keyword_score"],
                "dna_score": r["dna_score"],
                "claim_score": r["claim_score"],
                "ipc_score": r["ipc_score"],
                "ai_risk_score": r["ai_risk_score"],
                "total_score": r["total_score"],
                "matched_keywords": r["matched_keywords"],
                "technology_group": r["technology_group"],
                "patent_dna": r["patent_dna"],
            })
        st.session_state["idea_id"] = idea_id
    except Exception as exc:
        st.warning(f"DB 저장 중 오류 (분석은 계속 진행됩니다): {exc}")

    st.session_state["results"] = results
    st.session_state["results_df"] = df
    st.session_state["top_n"] = top_n
    st.session_state["selected_patent"] = (
        df.iloc[0]["application_no"] if len(df) else None)
    st.session_state.pop("review", None)
    st.session_state.pop("timeline_lines", None)
    st.success(f"검색 완료: {len(df)}건 수집. Patent Radar 에서 "
               "결과를 확인하세요.")


# ============================================================ 0. Dashboard
def page_dashboard():
    ui.page_header("대시보드",
                   "아이디어 한 번 입력 → 여러 화면에서 결과 분석 → 보고서. "
                   "아이디어는 한 번만 입력하면 됩니다.")

    # 사용 흐름 3단계
    st.markdown(
        "<div class='flow'>"
        "<div class='step'><div class='n'>1</div><div><b>아이디어 입력</b>"
        "<span>아이디어·키워드를 한 번 입력하고 검색을 실행합니다.</span></div></div>"
        "<div class='arr'>→</div>"
        "<div class='step'><div class='n'>2</div><div><b>결과 분석</b>"
        "<span>유사특허·DNA·통계·도면·AI 검토를 같은 결과로 살펴봅니다.</span></div></div>"
        "<div class='arr'>→</div>"
        "<div class='step'><div class='n'>3</div><div><b>보고서 활용</b>"
        "<span>관심 특허를 모으고 Excel·PDF로 내보냅니다.</span></div></div>"
        "</div>", unsafe_allow_html=True)

    df = get_results_df()
    idea = ss_get("idea", {})
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if df.empty:
        st.info("아직 분석한 아이디어가 없습니다. **STEP 1 · 아이디어 입력**에서 "
                "아이디어를 입력하고 검색을 실행하면, 그 결과가 모든 분석 화면에 "
                "표시됩니다.")
        if st.button("아이디어 입력 시작하기", type="primary"):
            goto("Idea Canvas")
        return

    # 현재 분석 상태 카드
    cards = stats.summary_cards(df)
    scores = df["total_score"]
    st.markdown(f"#### 현재 분석 — {idea.get('title','(제목 없음)')}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("검색 유사특허", f"{len(df)}건")
    m2.metric("최고 관련도", f"{scores.max():.0f}")
    m3.metric("주의(70+)", f"{int((scores >= 70).sum())}건")
    m4.metric("등록률", f"{cards['registered_rate']:.0f}%")

    st.markdown("##### 바로가기")
    g1, g2, g3, g4 = st.columns(4)
    if g1.button("유사특허 분석", icon=":material/radar:",
                 use_container_width=True):
        goto("Patent Radar")
    if g2.button("통계 · 기술분석", icon=":material/insights:",
                 use_container_width=True):
        goto("Landscape")
    if g3.button("AI 검토", icon=":material/smart_toy:",
                 use_container_width=True):
        goto("AI Patent Review")
    if g4.button("보고서 내보내기", icon=":material/description:",
                 use_container_width=True):
        goto("Export Center")

    st.markdown("##### 관련도 상위 특허")
    top = df.head(5)
    table = pd.DataFrame({
        "순위": top["rank"], "관련도": top["total_score"],
        "특허명": top["title"], "출원인": top["applicant"],
        "상태": top["status"], "등급": top["grade"],
    })
    st.dataframe(table, hide_index=True, use_container_width=True,
                 column_config={"관련도": st.column_config.ProgressColumn(
                     "관련도", min_value=0, max_value=100, format="%.0f")})


# ============================================================ 1. Idea Canvas
def page_idea_canvas():
    ui.page_header("아이디어 입력",
                   "아이디어를 입력하고 검색어를 확장한 뒤 KIPRIS 검색을 실행합니다.")
    if not gemini_service.is_available():
        st.info("Gemini API Key 가 설정되어 있지 않습니다. 검색어 확장과 AI "
                "분석은 키워드 기반으로 동작합니다. (Settings 에서 키 입력)")

    idea = ss_get("idea", {})
    col1, col2 = st.columns([2, 1])
    with col1:
        title = st.text_input("아이디어명", value=idea.get("title", ""),
                              placeholder=DEMO_IDEA["title"])
        description = st.text_area("아이디어 설명", height=140,
                                   value=idea.get("description", ""),
                                   placeholder=DEMO_IDEA["description"])
        keywords = st.text_input("핵심 키워드 (쉼표 구분)",
                                 value=idea.get("keywords", ""),
                                 placeholder=DEMO_IDEA["keywords"])
        exclude = st.text_input("제외 키워드 (쉼표 구분)",
                                value=idea.get("exclude_keywords", ""),
                                placeholder=DEMO_IDEA["exclude_keywords"])
    with col2:
        scope = st.selectbox("검색 범위", ["국내 특허+실용신안", "국내 특허", "국내 실용신안"])
        top_n = st.slider("유사특허 TOP N", 5, 30, ss_get("top_n", 10))
        per_query = st.slider("검색식당 수집 건수", 10, 30, 25)
        uploaded = st.file_uploader("아이디어 이미지/도면 업로드 (선택)",
                                    type=["png", "jpg", "jpeg"])
        if uploaded is not None:
            st.image(uploaded, caption="업로드한 도면", use_container_width=True)
            if gemini_service.is_available() and st.button("Gemini Vision 구성요소 추출"):
                with st.spinner("이미지 분석 중..."):
                    result = gemini_service.analyze_uploaded_image(
                        uploaded.getvalue(), uploaded.type or "image/png")
                st.markdown(result or "이미지 분석에 실패했습니다.")

    st.session_state["idea"] = {
        "title": title, "description": description, "keywords": keywords,
        "exclude_keywords": exclude, "scope": scope,
        "idea_dna": ss_get("idea", {}).get("idea_dna", {}),
    }

    b1, b2 = st.columns(2)
    if b1.button("Gemini 검색어 확장", type="secondary",
                 use_container_width=True):
        if not (title or description or keywords):
            st.error("아이디어명/설명/키워드 중 하나는 입력해야 합니다.")
        else:
            with st.spinner("검색어 확장 중..."):
                expansion, method = keyword_expander.expand(
                    title, description, keywords, exclude)
            st.session_state["expansion"] = expansion
            st.session_state["expansion_method"] = method
            st.session_state["idea"]["idea_dna"] = expansion.get("idea_dna", {})
            if method == "fallback":
                st.warning("Gemini 호출 불가/실패 — 키워드 기반 fallback 검색식을 "
                           "생성했습니다.")
            else:
                st.success("Gemini 검색어 확장 완료.")

    expansion = ss_get("expansion")
    if expansion:
        st.markdown("---")
        method = ss_get("expansion_method", "-")
        st.markdown(f"#### 검색어 확장 결과 &nbsp;<span style='font-size:.8rem;"
                    f"color:#93A0AE;font-weight:500'>({method})</span>",
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.markdown(ui.info_card(
            "국문 키워드",
            ", ".join(expansion.get("korean_keywords", [])) or "-"),
            unsafe_allow_html=True)
        c2.markdown(ui.info_card(
            "영문 키워드",
            ", ".join(expansion.get("english_keywords", [])) or "-"),
            unsafe_allow_html=True)
        c3.markdown(ui.info_card(
            "동의어 / 제외어",
            (", ".join(expansion.get("synonyms", [])) or "-")
            + "<br><span style='color:#64788F'>제외: "
            + (", ".join(expansion.get("exclude_keywords", [])) or "-")
            + "</span>"),
            unsafe_allow_html=True)
        groups_html = " ".join(ui.group_badge(g)
                               for g in expansion.get("technology_groups", []))
        st.markdown(f"<div style='margin-top:10px'><b>기술군 후보</b> &nbsp;"
                    f"{groups_html or '-'}</div>", unsafe_allow_html=True)
        with st.expander("아이디어 DNA", expanded=False):
            st.json(expansion.get("idea_dna", {}))

        st.markdown("**KIPRIS 검색식 후보** (직접 수정 가능, 한 줄에 1개, 최대 5개 실행)")
        edited = st.text_area(
            "검색식", value="\n".join(expansion.get("search_queries", [])),
            height=120, label_visibility="collapsed")
        expansion["search_queries"] = [
            q.strip() for q in edited.splitlines() if q.strip()][:5]
        st.session_state["expansion"] = expansion

    if b2.button("KIPRIS 검색 실행", type="primary", use_container_width=True):
        if not ss_get("expansion"):
            # 확장 없이 바로 실행하면 자동으로 fallback 확장 수행
            expansion, method = keyword_expander.expand(
                title, description, keywords, exclude)
            st.session_state["expansion"] = expansion
            st.session_state["expansion_method"] = method
            st.session_state["idea"]["idea_dna"] = expansion.get("idea_dna", {})
        run_search_pipeline(st.session_state["idea"],
                            st.session_state["expansion"], top_n, per_query)


# ============================================================ 2. Patent Radar
def page_patent_radar():
    ui.page_header("유사특허 분석",
                   "유사특허 TOP N 표와 대표도면 갤러리를 한 화면에서 살펴봅니다.")
    df = require_results()
    if df.empty:
        return
    top_n = ss_get("top_n", 10)

    # ---- 요약 카드 4개
    _cards = stats.summary_cards(df)
    _sc = df["total_score"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("전체 유사특허", f"{len(df)}건")
    k2.metric("최고 관련도", f"{_sc.max():.0f}")
    k3.metric("주의 (70+)", f"{int((_sc >= 70).sum())}건")
    k4.metric("평균 관련도", f"{_sc.mean():.0f}")

    # ---- 필터
    with st.expander("필터", expanded=False):
        f1, f2, f3 = st.columns(3)
        years = sorted(df[df["application_year"] > 0]["application_year"].unique())
        year_range = f1.slider(
            "출원연도", int(min(years)), int(max(years)),
            (int(min(years)), int(max(years)))) if len(years) > 1 else None
        applicants = f2.multiselect("출원인", sorted(df["applicant"].unique()))
        statuses = f3.multiselect("상태", sorted(df["status"].unique()))
        f4, f5, f6 = st.columns(3)
        ipcs = sorted({c.strip()[:4] for s in df["ipc"].astype(str)
                       for c in s.split(",") if c.strip()})
        ipc_sel = f4.multiselect("IPC/CPC", ipcs)
        groups = f5.multiselect("기술군", sorted(df["technology_group"].unique()))
        sim_range = f6.slider("유사도 구간", 0, 100, (0, 100))

    fdf = df.copy()
    if year_range:
        fdf = fdf[(fdf["application_year"] >= year_range[0])
                  & (fdf["application_year"] <= year_range[1])]
    if applicants:
        fdf = fdf[fdf["applicant"].isin(applicants)]
    if statuses:
        fdf = fdf[fdf["status"].isin(statuses)]
    if groups:
        fdf = fdf[fdf["technology_group"].isin(groups)]
    if ipc_sel:
        fdf = fdf[fdf["ipc"].astype(str).apply(
            lambda s: any(i in s for i in ipc_sel))]
    fdf = fdf[(fdf["total_score"] >= sim_range[0])
              & (fdf["total_score"] <= sim_range[1])]
    if fdf.empty:
        st.warning("필터 조건에 맞는 특허가 없습니다.")
        return

    head = fdf.head(top_n)
    # ---- TOP N 표
    table = pd.DataFrame({
        "순위": head["rank"],
        "종합": head["total_score"],
        "벡터": head["vector_score"],
        "키워드": head["keyword_score"],
        "DNA": head["dna_score"],
        "특허명": head["title"],
        "출원인": head["applicant"],
        "출원연도": head["application_year"],
        "상태": head["status"],
        "IPC/CPC": head["ipc"],
        "일치 키워드": head["matched_keywords"].apply(
            lambda v: ", ".join(v[:4]) if isinstance(v, list) else str(v)),
        "AI 위험도": head["total_score"].apply(sim_mod.grade),
        "KIPRIS": head["kipris_url"],
    })
    st.dataframe(
        table, use_container_width=True, hide_index=True,
        column_config={
            "KIPRIS": st.column_config.LinkColumn("KIPRIS", display_text="원문"),
            "종합": st.column_config.ProgressColumn(
                "종합", min_value=0, max_value=100, format="%.0f"),
        })

    # ---- 대표도면 갤러리 + 상세
    st.markdown("##### 대표도면 갤러리 (클릭하여 상세 보기)")
    cols = st.columns(5)
    for i, (_, p) in enumerate(head.iterrows()):
        with cols[i % 5]:
            st.image(get_drawing(p.to_dict()), use_container_width=True)
            st.button(
                f"{int(p['rank'])}위 · {p['total_score']:.0f}점",
                key=f"radar_sel_{p['application_no']}",
                on_click=select_patent, args=(p["application_no"],),
                use_container_width=True)
            st.caption(str(p["title"])[:28])

    st.markdown("---")
    st.markdown("##### 선택 특허 상세")
    selected = get_selected_patent(fdf)
    if selected:
        render_patent_detail(selected, ss_get("idea", {}).get("idea_dna", {}))


# ============================================================ 3. Patent DNA
def page_patent_dna():
    ui.page_header("특허 DNA 비교",
                   "내 아이디어와 선택한 특허의 구성을 항목별로 비교합니다.")
    df = require_results()
    if df.empty:
        return
    idea_dna = ss_get("idea", {}).get("idea_dna", {})
    if not idea_dna:
        st.warning("아이디어 DNA 가 없습니다. Idea Canvas 에서 검색어 확장을 "
                   "실행하면 생성됩니다.")

    options = {f"{int(r['rank'])}위 [{r['total_score']:.0f}] {r['title']}":
               r["application_no"] for _, r in df.head(20).iterrows()}
    choice = st.selectbox("비교할 특허 선택", list(options.keys()))
    select_patent(options[choice])
    p = get_selected_patent(df)
    if not p:
        return

    use_gemini = st.toggle("Gemini 로 특허 DNA 재추출",
                           value=False,
                           help="끄면 키워드 기반 기본 DNA 를 사용합니다.")
    p_dna = p.get("patent_dna") or {}
    if use_gemini:
        with st.spinner("Gemini DNA 추출 중..."):
            p_dna = dna_mod.extract_dna(p, use_gemini=True)
        if not gemini_service.is_available():
            st.warning("Gemini 미설정 — 키워드 기반 기본 DNA 를 사용합니다.")

    rows = dna_mod.compare_table(idea_dna, p_dna, drawing_caption(p))
    cmp_df = pd.DataFrame(rows)
    st.dataframe(
        cmp_df, use_container_width=True, hide_index=True,
        column_config={"일치도(%)": st.column_config.ProgressColumn(
            "일치도(%)", min_value=0, max_value=100, format="%d")})
    avg = cmp_df[cmp_df["일치도(%)"] > 0]["일치도(%)"].mean()
    st.metric("DNA 평균 일치도", f"{avg:.0f}%" if pd.notna(avg) else "-")

    # ----- 청구항 대비표 (Claim Chart)
    st.markdown("---")
    st.markdown("##### 청구항 대비표")
    st.caption(claim_chart.DISCLAIMER)
    if st.button("청구항 대비표 생성", key="gen_claimchart"):
        with st.spinner("대표청구항을 구성요소로 분해·비교 중..."):
            rows_cc, method = claim_chart.build_claim_chart(
                ss_get("idea", {}), idea_dna, p)
        st.session_state["claim_chart"] = rows_cc
        st.session_state["claim_chart_for"] = p.get("application_no")
        st.session_state["claim_chart_method"] = method
    if (ss_get("claim_chart") and
            ss_get("claim_chart_for") == p.get("application_no")):
        rows_cc = ss_get("claim_chart")
        summ = claim_chart.summary(rows_cc)
        m1, m2, m3 = st.columns(3)
        m1.metric("일치 가능", summ["일치 가능"])
        m2.metric("부분", summ["부분"])
        m3.metric("차이(차별 후보)", summ["차이"])
        st.dataframe(pd.DataFrame(rows_cc), use_container_width=True,
                     hide_index=True)
        if ss_get("claim_chart_method") == "fallback":
            st.caption("Gemini 미사용 — 규칙 기반 구성요소 분해 결과입니다.")


# ============================================================ Landscape
def _lc_trends(df):
    cards = stats.summary_cards(df)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("검색 특허 수", f"{cards['total']}건")
    m2.metric("등록률", f"{cards['registered_rate']}%")
    m3.metric("소멸·거절률", f"{cards['expired_rate']}%")
    m4.metric("최근 3년 증가율", f"{cards['recent_growth']:+.1f}%")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(stats.yearly_counts(df), x="연도", y="건수",
                            markers=True, title="연도별 출원 추이"),
                    use_container_width=True)
    c2.plotly_chart(px.bar(stats.group_growth(df), x="기술군", y="성장지수",
                           color="성장지수", color_continuous_scale="Blues",
                           title="기술군별 성장지수 (최근 3년)"),
                    use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(px.bar(stats.applicant_top(df), x="건수", y="출원인",
                           orientation="h", title="출원인 TOP 10"),
                    use_container_width=True)
    c4.plotly_chart(px.pie(stats.status_counts(df), names="상태", values="건수",
                           title="상태별 분포"), use_container_width=True)
    c5, c6 = st.columns(2)
    ipc_df = stats.ipc_counts(df); ipc_df.columns = ["IPC", "건수"]
    c5.plotly_chart(px.bar(ipc_df, x="IPC", y="건수", title="IPC/CPC 분포"),
                    use_container_width=True)
    c6.plotly_chart(px.bar(stats.keyword_top(df), x="빈도", y="키워드",
                           orientation="h", title="키워드 빈도 TOP 20", height=520),
                    use_container_width=True)


def _lc_timeline(df):
    matrix = timeline_mod.group_year_matrix(df)
    if not matrix.empty:
        fig = go.Figure()
        for group in matrix.index:
            fig.add_trace(go.Scatter(x=matrix.columns, y=matrix.loc[group],
                                     mode="lines+markers", name=group,
                                     stackgroup="one"))
        fig.update_layout(title="기술군별 출원 추이 (누적)", xaxis_title="출원연도",
                          yaxis_title="건수", height=420)
        st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    c1.markdown("##### 기술군 최초 등장 연도")
    c1.dataframe(timeline_mod.first_appearance(df), hide_index=True,
                 use_container_width=True)
    c2.markdown("##### 연도별 주요 키워드")
    c2.dataframe(timeline_mod.yearly_keywords(df), hide_index=True,
                 use_container_width=True)
    rising = timeline_mod.rising_groups(df)
    if rising:
        st.success("최근 증가 기술군: " + ", ".join(rising))
    st.markdown("##### 기술발전 흐름 요약")
    if st.button("흐름 문장 생성/갱신") or ss_get("timeline_lines") is None:
        with st.spinner("기술발전 흐름 분석 중..."):
            lines, method = timeline_mod.narrative(df)
        st.session_state["timeline_lines"] = lines
        st.session_state["timeline_method"] = method
    for line in ss_get("timeline_lines", []):
        st.markdown(f"- {line}")
    if ss_get("timeline_method") == "fallback":
        st.caption("Gemini 미사용 — 데이터 기반 자동 생성 문장입니다.")


def _lc_strategy(df):
    st.markdown("##### 기술 공백/포화 영역 분석")
    for line in stats.gap_analysis(df):
        st.markdown(f"- {line}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 기술 성장성 점수")
        gg = stats.group_growth(df)
        st.dataframe(gg, hide_index=True, use_container_width=True,
                     column_config={"성장지수": st.column_config.ProgressColumn(
                         "성장지수", min_value=0,
                         max_value=float(max(gg["성장지수"].max(), 1)),
                         format="%.2f")})
        st.markdown("##### 특허 생존성 분석")
        st.dataframe(stats.survival_analysis(df), hide_index=True,
                     use_container_width=True)
    with c2:
        st.markdown("##### 출원인 전략 분석")
        st.dataframe(stats.applicant_strategy(df), hide_index=True,
                     use_container_width=True)
        heat = stats.tech_combination_heatmap(df)
        st.plotly_chart(px.imshow(heat, text_auto=True, aspect="auto",
                                  color_continuous_scale="Blues",
                                  title="기술 조합 히트맵 (대상 × 응용 기술)"),
                        use_container_width=True)
    gg = stats.group_growth(df)
    rising = gg[gg["성장지수"] >= 1.5]["기술군"].tolist()
    falling = gg[gg["성장지수"] < 0.8]["기술군"].tolist()
    st.markdown("##### 기술 진화 예측 (데이터 기반)")
    if rising:
        st.markdown(f"- **{', '.join(rising)}** 영역은 최근 출원이 늘어 향후 "
                    "경쟁 심화 가능성이 있습니다.")
    if falling:
        st.markdown(f"- **{', '.join(falling)}** 영역은 출원이 둔화되는 추세로, "
                    "기존 등록특허의 존속 여부 모니터링이 중요합니다.")
    st.markdown("- 공백 영역이면서 내 아이디어 유사도도 낮은 조합이 차별화 "
                "R&D 후보입니다. (네트워크맵 탭의 음영 구간 참조)")


def _lc_network(df):
    f1, f2, f3 = st.columns(3)
    applicants = f1.multiselect("출원인 필터", sorted(df["applicant"].unique()))
    years = sorted(df[df["application_year"] > 0]["application_year"].unique())
    year_range = f2.slider("연도 범위", int(min(years)), int(max(years)),
                           (int(min(years)), int(max(years)))) \
        if len(years) > 1 else None
    highlight = f3.selectbox("기술군 하이라이트",
                             ["(전체)"] + sorted(df["technology_group"].unique()))
    fdf = df.copy()
    if applicants:
        fdf = fdf[fdf["applicant"].isin(applicants)]
    if year_range:
        fdf = fdf[(fdf["application_year"] >= year_range[0])
                  & (fdf["application_year"] <= year_range[1])]
    fig = netmap.make_time_network_figure(
        fdf, ss_get("idea", {}).get("title", "내 아이디어"),
        similarity_threshold=40.0,
        highlight_group=None if highlight == "(전체)" else highlight,
        show_patent_edges=True)
    st.plotly_chart(fig, use_container_width=True)
    st.session_state["network_fig"] = fig
    st.caption("노드 크기=관련도 · 색=기술군 · 테두리=상태 · 회색 음영=3년 이상 "
               "공백 구간(차별화 후보 영역). 범례 클릭으로 기술군 표시/숨김.")
    risky = fdf[fdf["total_score"] >= 70]
    if len(risky):
        st.warning(f"관련도 70 이상 주의 특허 {len(risky)}건: "
                   + " / ".join(risky["title"].head(5)))


def page_landscape():
    ui.page_header("통계 · 기술분석",
                   "검색 결과의 출원 동향·기술 발전·공백·네트워크를 한 곳에서 분석합니다.")
    df = require_results()
    if df.empty:
        return
    t1, t2, t3, t4 = st.tabs(["출원 동향", "기술 발전", "기술 공백·전략", "네트워크맵"])
    with t1:
        _lc_trends(df)
    with t2:
        _lc_timeline(df)
    with t3:
        _lc_strategy(df)
    with t4:
        _lc_network(df)


# ============================================================ Drawing / AI Review
def page_drawing_intelligence():
    ui.page_header("도면 분석",
                   "대표도면을 중심으로 특허를 검토합니다. 도면 클릭 시 상세로 이동합니다.")
    df = require_results()
    if df.empty:
        return

    sort_by = st.radio("정렬/보기", ["유사도순", "연도순", "출원인별", "기술군별"],
                       horizontal=True)
    if sort_by == "유사도순":
        view = df.sort_values("total_score", ascending=False)
        sections = [("전체", view)]
    elif sort_by == "연도순":
        view = df.sort_values("application_year", ascending=False)
        sections = [("전체 (최신순)", view)]
    elif sort_by == "출원인별":
        sections = [(a, g.sort_values("total_score", ascending=False))
                    for a, g in df.groupby("applicant")]
    else:
        sections = [(t, g.sort_values("total_score", ascending=False))
                    for t, g in df.groupby("technology_group")]

    for name, sub in sections:
        if len(sections) > 1:
            st.markdown(f"##### {name} ({len(sub)}건)")
        cols = st.columns(4)
        for i, (_, p) in enumerate(sub.head(12).iterrows()):
            with cols[i % 4]:
                st.image(get_drawing(p.to_dict()),
                         caption=drawing_caption(p.to_dict()),
                         use_container_width=True)
                st.button(
                    f"상세 · {p['total_score']:.0f}점",
                    key=f"draw_{name}_{p['application_no']}",
                    on_click=select_patent, args=(p["application_no"],),
                    use_container_width=True)

    st.markdown("---")
    p = get_selected_patent(df)
    if p:
        st.markdown("##### 선택 특허 상세")
        render_patent_detail(p, ss_get("idea", {}).get("idea_dna", {}))


# ============================================================ 8. AI Review
def page_ai_review():
    ui.page_header("AI 검토",
                   "Gemini 기반 1차 검토 결과입니다. 최종 법률 판단이 아닌 참고용입니다.")
    df = require_results()
    if df.empty:
        return
    st.warning(review_mod.DISCLAIMER)

    n = st.slider("검토 대상 TOP N", 5, 10, 5)
    if st.button("AI 1차 검토 실행", type="primary") or ss_get("review"):
        if not ss_get("review") or st.session_state.get("review_n") != n:
            top = df.head(n).to_dict("records")
            for p in top:
                p["drawing_caption"] = drawing_caption(p)
            with st.spinner("AI 검토 중..."):
                review, method = review_mod.run_review(
                    ss_get("idea", {}),
                    ss_get("idea", {}).get("idea_dna", {}), top)
            st.session_state["review"] = review
            st.session_state["review_method"] = method
            st.session_state["review_n"] = n

        review = ss_get("review", {})
        if ss_get("review_method") == "fallback":
            st.caption("Gemini 미사용 — 규칙 기반 1차 검토 결과입니다.")

        def _section(title, items):
            lis = "".join(
                f"<li>{st_html_escape(str(x))}</li>" for x in (items or ["-"]))
            return (f"<div class='gpc-card' style='margin-bottom:14px'>"
                    f"<div class='ct'>{title}</div>"
                    f"<ul class='rev'>{lis}</ul></div>")

        secs = [
            ("가장 유사한 특허", review.get("most_risky_patents", [])),
            ("공통 구성", review.get("common_points", [])),
            ("차이 구성", review.get("different_points", [])),
            ("핵심 차별 포인트", review.get("key_differentiators", [])),
            ("청구항 확인 필요", review.get("claim_check_points", [])),
            ("회피설계 검토", review.get("design_around_points", [])),
        ]
        col_l, col_r = st.columns(2)
        for i, (t, items) in enumerate(secs):
            (col_l if i % 2 == 0 else col_r).markdown(
                _section(t, items), unsafe_allow_html=True)
        st.markdown(
            f"<div class='gpc-card' style='background:#EAF1FF;"
            f"border-color:#CFE0FF'><div class='ct' style='color:#0057FF'>"
            f"출원 검토 참고 의견</div><div class='cv'>"
            f"{st_html_escape(review.get('review_comment','-'))}</div></div>",
            unsafe_allow_html=True)


# ============================================================ History
def _reconstruct_results(rows: list) -> list:
    """DB 행(load_idea_results) → 앱 results 포맷으로 복원."""
    results = []
    for r in rows:
        p = dict(r)
        try:
            p["matched_keywords"] = json.loads(r.get("matched_keywords") or "[]")
        except (json.JSONDecodeError, TypeError):
            p["matched_keywords"] = []
        try:
            p["patent_dna"] = json.loads(r.get("patent_dna_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            p["patent_dna"] = {}
        p["grade"] = sim_mod.grade(p.get("total_score", 0))
        p["comparison_text"] = sim_mod.build_patent_text(p)
        results.append(p)
    for rank, p in enumerate(results, start=1):
        p["rank"] = rank
    return results


def page_history():
    ui.page_header("기록 · 관심특허",
                   "지난 분석을 다시 불러오거나 관심 특허를 모아 봅니다.")
    tab1, tab2 = st.tabs(["검색 이력", "관심 특허"])

    with tab1:
        ideas = db.list_ideas()
        if not ideas:
            st.info("저장된 검색 이력이 없습니다. Idea Canvas 에서 검색을 "
                    "실행하면 자동으로 기록됩니다.")
        else:
            hist = pd.DataFrame([{
                "id": i["id"], "아이디어": i["title"],
                "키워드": i["keywords"], "결과 수": i["n_results"],
                "생성일시": str(i["created_at"])[:16].replace("T", " "),
            } for i in ideas])
            st.dataframe(hist.drop(columns=["id"]), hide_index=True,
                         use_container_width=True)
            labels = {f"[{i['created_at'][:10]}] {i['title']} "
                      f"({i['n_results']}건)": i["id"] for i in ideas}
            pick = st.selectbox("불러올 분석 선택", list(labels.keys()))
            if st.button("이 분석 불러오기", type="primary"):
                idea_id = labels[pick]
                rows = db.load_idea_results(idea_id)
                if not rows:
                    st.warning("이 검색에는 저장된 결과가 없습니다.")
                else:
                    meta = next(i for i in ideas if i["id"] == idea_id)
                    try:
                        idea_dna = json.loads(meta.get("idea_dna_json") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        idea_dna = {}
                    results = _reconstruct_results(rows)
                    st.session_state["idea"] = {
                        "title": meta["title"], "description": meta["description"],
                        "keywords": meta["keywords"],
                        "exclude_keywords": meta["exclude_keywords"],
                        "idea_dna": idea_dna}
                    st.session_state["results"] = results
                    st.session_state["results_df"] = stats.to_dataframe(results)
                    st.session_state["top_n"] = min(10, len(results))
                    st.session_state["selected_patent"] = \
                        results[0]["application_no"]
                    for k in ("review", "timeline_lines", "claim_chart"):
                        st.session_state.pop(k, None)
                    st.success(f"'{meta['title']}' 분석을 불러왔습니다 "
                               f"({len(results)}건). 다른 메뉴에서 확인하세요.")

    with tab2:
        marks = db.list_bookmarks()
        if not marks:
            st.info("관심 특허가 없습니다. Patent Radar 등에서 특허 상세의 "
                    "'관심 특허 추가'로 담을 수 있습니다.")
        else:
            bm = pd.DataFrame([{
                "특허명": m.get("title") or "-",
                "출원인": m.get("applicant") or "-",
                "출원번호": m.get("application_no"),
                "상태": m.get("status") or "-",
                "기술군": m.get("technology_group") or "-",
                "KIPRIS": m.get("kipris_url") or "",
            } for m in marks])
            st.dataframe(
                bm, hide_index=True, use_container_width=True,
                column_config={"KIPRIS": st.column_config.LinkColumn(
                    "KIPRIS", display_text="원문")})
            c1, c2 = st.columns([2, 1])
            rm = c1.selectbox("해제할 특허",
                              [m["application_no"] for m in marks])
            if c2.button("관심 특허 해제"):
                db.remove_bookmark(rm)
                st.rerun()
            st.download_button(
                "관심 특허 Excel 다운로드",
                data=bm.to_csv(index=False).encode("utf-8-sig"),
                file_name="gpc_bookmarks.csv", mime="text/csv")


# ============================================================ 10. Export Center
def page_export_center():
    ui.page_header("보고서 · 내보내기",
                   "분석 결과를 Excel · PDF · 이미지로 내보냅니다.")
    df = require_results()
    if df.empty:
        return
    idea = ss_get("idea", {})
    review = ss_get("review")
    timeline_lines = ss_get("timeline_lines")
    if timeline_lines is None:
        timeline_lines, _ = timeline_mod.fallback_narrative(df), "fallback"
        timeline_lines = timeline_lines if isinstance(timeline_lines, list) else []
    queries = (ss_get("expansion") or {}).get("search_queries", [])
    top_n = ss_get("top_n", 10)

    rich = st.toggle("PDF에 도면·네트워크맵·차트 이미지 포함", value=True,
                     help="이미지 변환(kaleido)이 없으면 도면만 포함됩니다.")

    def build_report_images():
        imgs = {}
        # 대표도면은 PIL 로 항상 생성 가능
        imgs["drawings"] = [
            (drawing_caption(r.to_dict()), placeholder_drawing(r.to_dict()))
            for _, r in df.head(6).iterrows()
            if not str(r.get("drawing_url") or "").startswith("http")
        ]
        # 네트워크맵 / 차트는 kaleido 필요 (없으면 None → 건너뜀)
        fig = ss_get("network_fig") or netmap.make_time_network_figure(
            df, idea.get("title", ""))
        imgs["network"] = image_exporter.figure_to_png(fig)
        yfig = px.line(stats.yearly_counts(df), x="연도", y="건수",
                       markers=True, title="연도별 출원 추이")
        imgs["yearly"] = image_exporter.figure_to_png(yfig)
        return imgs

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("##### Excel")
        try:
            xlsx = excel_exporter.export_excel(df, idea, review)
            st.download_button(
                "Excel 다운로드", data=xlsx,
                file_name="gpc_ip_lens_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet", use_container_width=True)
        except Exception as exc:
            st.error(f"Excel 생성 실패: {exc}")
    with c2:
        st.markdown("##### PDF 리포트")
        try:
            report_imgs = build_report_images() if rich else None
            pdf = pdf_exporter.export_pdf(df, idea, queries, timeline_lines,
                                          review, top_n, images=report_imgs)
            st.download_button("PDF 다운로드", data=pdf,
                               file_name="gpc_ip_lens_report.pdf",
                               mime="application/pdf",
                               use_container_width=True)
        except Exception as exc:
            st.error(f"PDF 생성 실패: {exc}")
    with c3:
        st.markdown("##### 네트워크맵 / 그래프")
        fig = ss_get("network_fig")
        if fig is None:
            fig = netmap.make_time_network_figure(df, idea.get("title", ""))
        data, fname, mime = image_exporter.export_figure(fig, "network_map")
        if mime != "image/png":
            st.caption("kaleido 미설치 — PNG 대신 HTML 로 내보냅니다.")
        st.download_button("네트워크맵 다운로드", data=data, file_name=fname,
                           mime=mime, use_container_width=True)
        yearly_fig = px.line(stats.yearly_counts(df), x="연도", y="건수",
                             markers=True, title="연도별 출원 추이")
        data2, fname2, mime2 = image_exporter.export_figure(yearly_fig,
                                                            "yearly_trend")
        st.download_button("통계 그래프 다운로드", data=data2, file_name=fname2,
                           mime=mime2, use_container_width=True)

    st.markdown("---")
    st.markdown("##### 미리보기 — 유사특허 TOP N / AI 검토 요약")
    st.dataframe(df.head(top_n)[["rank", "total_score", "title", "applicant",
                                 "application_year", "status",
                                 "technology_group"]],
                 hide_index=True, use_container_width=True)
    if review:
        st.info(review.get("review_comment", "-"))
    else:
        st.caption("AI 검토를 실행하면 PDF/Excel 에 검토 요약이 포함됩니다.")


# ============================================================ 11. Settings
def page_settings():
    ui.page_header("설정",
                   "API Key · 데이터 모드 · 데이터베이스/캐시를 관리합니다.")
    st.caption("입력한 키는 로컬 SQLite settings 테이블에만 저장되며 외부로 "
               "전송되지 않습니다. (외부 전송은 Gemini/KIPRIS 호출에 한정)")

    with st.form("settings_form"):
        gemini_key = st.text_input("Gemini API Key", type="password",
                                   value=config.get_gemini_api_key())
        kipris_key = st.text_input("KIPRIS API Key", type="password",
                                   value=config.get_kipris_api_key())
        kipris_url = st.text_input(
            "KIPRIS BASE URL", value=config.get_kipris_base_url(),
            placeholder="http://plus.kipris.or.kr/openapi/rest")
        mock = st.checkbox("Mock Data 사용", value=config.use_mock_data(),
                           help="해제하려면 KIPRIS Key/URL 이 필요합니다.")
        if st.form_submit_button("저장", type="primary"):
            try:
                config.set_setting("GEMINI_API_KEY", gemini_key.strip())
                config.set_setting("KIPRIS_API_KEY", kipris_key.strip())
                config.set_setting("KIPRIS_BASE_URL", kipris_url.strip())
                config.set_setting("USE_MOCK_DATA",
                                   "true" if mock else "false")
                st.success("저장되었습니다.")
            except Exception as exc:
                st.error(f"설정 저장 실패: {exc}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("데이터베이스 초기화", use_container_width=True):
        try:
            db.reset_db()
            for key in ("results", "results_df", "review", "timeline_lines",
                        "selected_patent", "idea_id"):
                st.session_state.pop(key, None)
            st.success("데이터베이스를 초기화했습니다 (설정은 유지).")
        except Exception as exc:
            st.error(f"DB 초기화 실패: {exc}")
    if c2.button("캐시 삭제", use_container_width=True):
        n = cache_utils.clear_cache()
        st.success(f"캐시 {n}건을 삭제했습니다.")

    # ----- 유사도 가중치 조정
    st.markdown("---")
    st.markdown("##### 유사도 기준 (가중치) 조정")
    st.caption("종합 유사도 산정 비중입니다. 합계는 자동 정규화되며, "
               "저장 후 새로 검색할 때 적용됩니다.")
    w = sim_mod.load_weights()
    labels = {"vector": "벡터 의미", "dna": "특허 DNA", "keyword": "키워드",
              "claim": "대표청구항", "ipc": "IPC/CPC", "ai_risk": "AI 위험도"}
    with st.form("weights_form"):
        cols = st.columns(3)
        new_w = {}
        for i, (key, label) in enumerate(labels.items()):
            new_w[key] = cols[i % 3].slider(
                label, 0, 50, int(round(w[key] * 100)), step=5)
        wc1, wc2 = st.columns(2)
        if wc1.form_submit_button("가중치 저장", type="primary"):
            import json as _json
            if sum(new_w.values()) == 0:
                st.error("가중치 합이 0일 수 없습니다.")
            else:
                config.set_setting("SIMILARITY_WEIGHTS",
                                   _json.dumps(new_w))
                st.success("저장했습니다. 다음 검색부터 적용됩니다.")
        if wc2.form_submit_button("기본값으로 복원"):
            config.set_setting("SIMILARITY_WEIGHTS", "")
            st.success("기본 가중치로 복원했습니다.")

    st.markdown("---")
    st.markdown(
        f"- Gemini 사용 가능: **{'예' if gemini_service.is_available() else '아니오 (fallback 동작)'}**\n"
        f"- 동작 모드: **{'Mock Data' if config.use_mock_data() else 'KIPRIS 실연동'}**\n"
        f"- DB 경로: `{config.DB_PATH}`\n"
        f"- 샘플 데이터: `{config.SAMPLE_CSV}`")


# ============================================================ 메인
def main():
    ss = st.session_state
    if "page" not in ss:
        ss["page"] = "Dashboard"
    if ss.get("_goto"):                      # 바로가기 버튼이 설정한 이동
        ss["page"] = ss.pop("_goto")

    with st.sidebar:
        ui.sidebar_brand()
        for gtitle, items in NAV_GROUPS:
            if gtitle:
                st.markdown(f"<div class='nav-sec'>{gtitle}</div>",
                            unsafe_allow_html=True)
            for key, label, icon in items:
                active = ss["page"] == key
                if st.button(label, icon=icon, key=f"nav_{key}",
                             use_container_width=True,
                             type="primary" if active else "secondary"):
                    ss["page"] = key
                    st.rerun()
        df = get_results_df()
        if not df.empty:
            st.markdown("<div style='height:12px'></div>",
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("검색 결과", f"{len(df)}")
            c2.metric("최고 관련도", f"{df['total_score'].max():.0f}")

    ui.app_header()
    pages = {
        "Dashboard": page_dashboard,
        "Idea Canvas": page_idea_canvas, "Patent Radar": page_patent_radar,
        "Patent DNA": page_patent_dna, "Landscape": page_landscape,
        "Drawing Intelligence": page_drawing_intelligence,
        "AI Patent Review": page_ai_review, "History": page_history,
        "Export Center": page_export_center, "Settings": page_settings,
    }
    pages.get(ss["page"], page_dashboard)()


def goto(page_key: str):
    """다른 화면으로 이동 (바로가기 버튼용)."""
    st.session_state["_goto"] = page_key
    st.rerun()


if __name__ == "__main__":
    main()
