# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - 건설/PC 특화 특허 탐색·분석 프로그램 (Streamlit 메인 앱).

실행: streamlit run app.py
"""
import hashlib
import html as _html
import io
import json
from datetime import datetime

st_html_escape = _html.escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyzers import ai_review as review_mod
from analyzers import claim_chart
from analyzers import claim_draft as draft_mod
from analyzers import diff_compare
from analyzers import element_match
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
from utils import cache_utils, config, db, monitoring, ui
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

# 메뉴 (key, 한글 라벨, 아이콘) — 실무형 IP 1차 검토 도구 6메뉴
NAV_GROUPS = [
    ("", [
        ("New Review", "새 아이디어 검토", ":material/lightbulb:"),
        ("Review Cases", "검토 결과함", ":material/folder_open:"),
        ("Watchlist", "관심 특허", ":material/bookmark:"),
        ("Monitoring", "모니터링", ":material/radar:"),
        ("Reports", "리포트", ":material/description:"),
        ("Settings", "설정", ":material/settings:")]),
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
        st.info("아직 분석할 검색 결과가 없습니다. **새 아이디어 검토**에서 "
                "아이디어를 입력하고 [검토 시작]을 누르면 결과가 표시됩니다.")
        if st.button("새 아이디어 검토로 가기", type="primary",
                     icon=":material/lightbulb:", key="goto_idea_empty"):
            goto("New Review")
    return df


def review_confidence() -> tuple:
    """검토 신뢰도 배지 (라벨, 설명, 톤) 산출.

    Gemini=AI 신뢰도, KIPRIS 실데이터=검색 신뢰도, Mock=데모, fallback=누락가능.
    """
    gem = gemini_service.is_available()
    mock = config.use_mock_data()
    if gem and not mock:
        return ("검토 신뢰도 높음", "Gemini AI 분석 + KIPRIS 실데이터", "success")
    if gem and mock:
        return ("AI 분석 · 데모 데이터", "Gemini AI 분석 · 표본(데모) 특허", "primary")
    if not gem and not mock:
        return ("검색 신뢰도 (키워드 분석)", "KIPRIS 실데이터 · 키워드 기반 분석",
                "warn")
    return ("데모 모드 (누락 가능)", "표본 데이터 · 키워드 기반 분석", "warn")


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
        # 관심특허 관리상태 (검토 케이스 상태와 별개)
        app_no = p.get("application_no", "")
        opts = ["없음"] + db.WATCH_STATUSES
        cur = db.get_watch_status(app_no) or "없음"
        sel = st.selectbox(
            "관리상태", opts, index=opts.index(cur) if cur in opts else 0,
            key=f"rs_{app_no}",
            help="관심/확인필요/주의/제외/출원참고/회피필요/무효자료후보 — "
                 "'관심 특허'와 리포트에 반영됩니다.")
        if sel != cur:
            db.set_watch_status(app_no, sel, p.get("title", ""),
                                p.get("applicant", ""))
            st.rerun()
    # 분할 점수 (문헌/청구항/문제/해결수단/효과/특허리스크)
    try:
        sp = sim_mod.split_scores(p, idea_dna or {})
        sp_df = pd.DataFrame({"항목": list(sp.keys()),
                              "점수": list(sp.values())})
        fig_sp = px.bar(sp_df, x="점수", y="항목", orientation="h",
                        range_x=[0, 100], height=240, text="점수")
        fig_sp.update_layout(margin=dict(l=4, r=4, t=8, b=4),
                             yaxis_title="", xaxis_title="")
        st.markdown("###### 분할 점수")
        st.plotly_chart(fig_sp, use_container_width=True,
                        key=f"split_{p.get('application_no','')}")
    except Exception:
        pass

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
                        per_query: int = 25, redirect: bool = True,
                        scope: str = "국내"):
    """검색식 실행 → 중복제거 → 유사도 계산 → DB 저장 → 세션 반영.

    redirect=True 면 완료 후 검토 화면으로 이동(rerun). False 면 결과만 채우고
    True/False 를 반환한다(통합 검토 플로우에서 후속 단계 진행용).
    """
    client = KiprisClient()
    queries = list(expansion.get("search_queries", []))[:5]
    if not queries:
        st.error("실행할 검색식이 없습니다. 검색어 확장을 먼저 실행하세요.")
        return False

    with st.spinner(f"유사특허 검색 중 (검색식 {len(queries)}개, 범위 {scope})..."):
        try:
            patents = client.search_multi(
                queries, per_query=per_query,
                exclude_keywords=idea.get("exclude_keywords", ""), scope=scope)
        except Exception as exc:
            st.error(f"유사특허 검색 실패: {exc}")
            return False
    if not patents:
        st.warning("검색 결과가 없습니다. 검색식을 수정해 보세요.")
        return False

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
    for k in ("review", "timeline_lines", "claim_chart", "em_rows"):
        st.session_state.pop(k, None)
    if redirect:
        st.session_state["_goto"] = "New Review"
        st.success(f"검색 완료: {len(df)}건 수집.")
        st.rerun()
    return True


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
    st.caption("TOP N 은 '청구항 리스크'(청구항 일치도·해결수단 유사도 중심) 순으로 "
               "정렬됩니다. 종합은 문헌·DNA·키워드를 포함한 가중 유사도입니다.")
    # ---- TOP N 표 (청구항 리스크 우선)
    risk_col = (head["claim_risk"] if "claim_risk" in head
                else head["total_score"])
    table = pd.DataFrame({
        "순위": head["rank"],
        "청구항리스크": risk_col,
        "종합": head["total_score"],
        "문헌": head["vector_score"],
        "청구항": head["claim_score"],
        "키워드": head["keyword_score"],
        "DNA": head["dna_score"],
        "특허명": head["title"],
        "출원인": head["applicant"],
        "출원연도": head["application_year"],
        "상태": head["status"],
        "IPC/CPC": head["ipc"],
        "일치 키워드": head["matched_keywords"].apply(
            lambda v: ", ".join(v[:4]) if isinstance(v, list) else str(v)),
        "등급": head["total_score"].apply(sim_mod.grade),
        "KIPRIS": head["kipris_url"],
    })
    st.dataframe(
        table, use_container_width=True, hide_index=True,
        column_config={
            "KIPRIS": st.column_config.LinkColumn("KIPRIS", display_text="원문"),
            "청구항리스크": st.column_config.ProgressColumn(
                "청구항리스크", min_value=0, max_value=100, format="%.0f"),
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


def page_landscape(flat: bool = False):
    ui.page_header("통계 · 기술분석",
                   "검색 결과의 출원 동향·기술 발전·공백·네트워크를 한 곳에서 분석합니다.")
    df = require_results()
    if df.empty:
        return
    if flat:  # 탭 안에 임베드될 때: 중첩 탭 없이 섹션으로 펼침
        st.markdown("###### 출원 동향")
        _lc_trends(df)
        st.markdown("###### 기술 발전")
        _lc_timeline(df)
        st.markdown("###### 기술 공백 · 전략")
        _lc_strategy(df)
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
    st.caption("도면을 선택하면 '유사특허' 탭의 상세 패널에 반영됩니다.")


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


# ============================================================ 결과 복원 유틸
def _reconstruct_results(rows: list, idea_dna: dict = None) -> list:
    """DB 행(load_idea_results) → 앱 results 포맷으로 복원 (청구항 리스크 재정렬)."""
    idea_dna = idea_dna or {}
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
        p["claim_risk"] = sim_mod.split_scores(p, idea_dna)["특허리스크"]
        results.append(p)
    results.sort(key=lambda x: (x.get("claim_risk", 0),
                                x.get("total_score", 0)), reverse=True)
    for rank, p in enumerate(results, start=1):
        p["rank"] = rank
    return results


# ============================================================ 10. 리포트
REPORT_SECTIONS = ["1페이지 요약", "내 아이디어 구성요소", "유사특허 TOP 5",
                   "아이디어-유사특허 차이 비교", "구성요소 매칭표",
                   "청구항 대비표", "차별성·보완", "청구항 초안",
                   "통계·도면 이미지", "관심 특허"]


def _recent_reports():
    """data/exports 의 최근 리포트 파일 목록."""
    try:
        files = sorted(config.EXPORTS_DIR.glob("ip3_report_*.*"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:10]
    except Exception:
        return []


def _build_report_kwargs(df, idea, include):
    """세션/스냅샷에서 리포트에 넣을 데이터를 모은다(포함 항목 필터)."""
    idea_dna = idea.get("idea_dna", {})
    kwargs = {}
    if "내 아이디어 구성요소" in include:
        kwargs["idea_elements"] = (ss_get("idea_elements")
                                   or element_match.decompose_idea(idea, idea_dna))
    if "아이디어-유사특허 차이 비교" in include:
        rows = ss_get("diffc_rows")
        if not rows and len(df):
            rows = diff_compare.build_diff_table(
                idea, idea_dna, df.iloc[0].to_dict())
        kwargs["diff_rows"] = rows
    if "구성요소 매칭표" in include:
        rows = ss_get("em_rows")
        if not rows and len(df):
            rows, _ = element_match.match(idea, idea_dna, df.iloc[0].to_dict())
        kwargs["element_rows"] = rows
    if "청구항 대비표" in include and len(df):
        kwargs["claim_rows"], _ = claim_chart.build_claim_chart(
            idea, idea_dna, df.iloc[0].to_dict())
    if "청구항 초안" in include:
        draft = ss_get("draft_result")
        if not draft and len(df):
            d = draft_mod.build_differentiation(idea, idea_dna,
                                                df.head(5).to_dict("records"))
            draft, _ = draft_mod.draft(idea, idea_dna, d,
                                       df.head(5).to_dict("records"))
        kwargs["draft"] = draft
    if "관심 특허" in include:
        try:
            kwargs["worklist"] = db.list_bookmarks()
        except Exception:
            kwargs["worklist"] = None
    return kwargs


def page_reports():
    ui.page_header("리포트",
                   "검토 결과를 차이 비교 중심 리포트(PDF·Excel)로 내보냅니다.")

    # 1) 리포트 대상 선택 (현재 세션 / 저장된 케이스)
    src = st.radio("리포트 대상", ["현재 검토 결과", "저장된 검토 케이스"],
                   horizontal=True)
    if src == "저장된 검토 케이스":
        cases = db.list_review_cases()
        if not cases:
            st.info("저장된 검토 케이스가 없습니다.")
        else:
            labels = {f"[{str(c.get('created_at'))[:10]}] {c.get('title')} "
                      f"({c.get('status')})": c for c in cases}
            pick = st.selectbox("케이스 선택", list(labels.keys()))
            if st.button("이 케이스 불러오기", key="rep_load"):
                c = labels[pick]
                full = db.get_review_case(c["id"]) or {}
                if c.get("idea_id") and _load_case_into_session(
                        c["idea_id"], full.get("snapshot", {})):
                    st.session_state["review_case_id"] = c["id"]
                    st.session_state["case_status"] = c.get("status", "검토중")
                    st.session_state["case_verdict"] = c.get("final_verdict", "")
                    st.success("불러왔습니다. 아래에서 리포트를 생성하세요.")
                    st.rerun()
                else:
                    st.warning("이 케이스에는 복원할 결과가 없습니다.")

    df = get_results_df()
    if df.empty:
        st.info("리포트로 만들 검토 결과가 없습니다. '새 아이디어 검토'를 먼저 "
                "실행하거나 저장된 케이스를 불러오세요.")
        _render_recent_reports()
        return

    idea = ss_get("idea", {})
    review = ss_get("review")
    scope = idea.get("scope", "국내")
    basis = "샘플 데이터(데모)" if config.use_mock_data() else "KIPRIS 실데이터"
    st.caption(f"대상: {idea.get('title') or '-'} · 검색 범위 {scope} · "
               f"데이터 기준 {basis}")

    # 2) 포함 항목 선택
    include = st.multiselect("리포트 포함 항목", REPORT_SECTIONS,
                             default=REPORT_SECTIONS)
    rich = "통계·도면 이미지" in include

    queries = (ss_get("expansion") or {}).get("search_queries", [])
    top_n = ss_get("top_n", 10)
    timeline_lines = ss_get("timeline_lines")
    if timeline_lines is None:
        tl = timeline_mod.fallback_narrative(df)
        timeline_lines = tl if isinstance(tl, list) else []

    def _images():
        imgs = {"drawings": [
            (drawing_caption(r.to_dict()), placeholder_drawing(r.to_dict()))
            for _, r in df.head(6).iterrows()
            if not str(r.get("drawing_url") or "").startswith("http")]}
        fig = ss_get("network_fig") or netmap.make_time_network_figure(
            df, idea.get("title", ""))
        imgs["network"] = image_exporter.figure_to_png(fig)
        yfig = px.line(stats.yearly_counts(df), x="연도", y="건수",
                       markers=True, title="연도별 출원 추이")
        imgs["yearly"] = image_exporter.figure_to_png(yfig)
        return imgs

    # 3) 요약 payload
    conf_label, _, _ = review_confidence()
    diff_res = ss_get("diff_result") or {}
    rev = review or {}
    summary = {
        "confidence": conf_label,
        "final_verdict": ss_get("case_verdict", ""),
        "differentiators": (diff_res.get("differentiators")
                            or rev.get("key_differentiators") or []),
        "novelty_risk": rev.get("review_comment", ""),
        "design_around": (rev.get("design_around_points")
                          or (ss_get("draft_result") or {}).get("design_around")
                          or []),
    } if "1페이지 요약" in include else None

    extra = _build_report_kwargs(df, idea, include)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("PDF 리포트 생성", type="primary",
                     use_container_width=True):
            try:
                with st.spinner("PDF 생성 중..."):
                    pdf = pdf_exporter.export_pdf(
                        df, idea, queries, timeline_lines, review, top_n,
                        images=_images() if rich else None,
                        summary=summary, **extra)
                fname = f"ip3_report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
                try:
                    (config.EXPORTS_DIR / fname).write_bytes(pdf)
                except OSError:
                    pass
                st.download_button("PDF 다운로드", data=pdf, file_name=fname,
                                   mime="application/pdf",
                                   use_container_width=True)
            except Exception as exc:
                st.error(f"PDF 생성 실패: {exc}")
    with c2:
        if st.button("Excel 리포트 생성", use_container_width=True):
            try:
                xlsx = excel_exporter.export_excel(df, idea, review)
                fname = f"ip3_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
                try:
                    (config.EXPORTS_DIR / fname).write_bytes(xlsx)
                except OSError:
                    pass
                st.download_button(
                    "Excel 다운로드", data=xlsx, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet", use_container_width=True)
            except Exception as exc:
                st.error(f"Excel 생성 실패: {exc}")

    st.caption("구성요소 매칭표·청구항 초안은 PDF 리포트에 포함됩니다. "
               "리포트는 1차 검토 의견이며 최종 법률 판단이 아닙니다.")

    st.markdown("---")
    _render_recent_reports()


def _render_recent_reports():
    st.markdown("##### 최근 생성 리포트")
    files = _recent_reports()
    if not files:
        st.caption("아직 생성된 리포트가 없습니다.")
        return
    for f in files:
        col1, col2 = st.columns([3, 1])
        col1.write(f"{f.name}  ·  {datetime.fromtimestamp(f.stat().st_mtime):%Y-%m-%d %H:%M}")
        try:
            mime = ("application/pdf" if f.suffix == ".pdf"
                    else "application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet")
            col2.download_button("다운로드", data=f.read_bytes(),
                                 file_name=f.name, mime=mime, key=f"dl_{f.name}")
        except OSError:
            col2.caption("불러오기 실패")


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
    st.markdown("##### 환경 상태")
    st.markdown(
        f"- Gemini API: **{'사용 가능' if gemini_service.is_available() else '미설정 (키워드 기반 분석)'}**\n"
        f"- 검색 데이터: **{'샘플 데이터(데모)' if config.use_mock_data() else 'KIPRIS 실데이터 연동'}**\n"
        f"- DB 경로: `{config.DB_PATH}`\n"
        f"- 샘플 데이터: `{config.SAMPLE_CSV}`")


# ===================================================== 새 아이디어 검토 (통합)
ANALYSIS_KEYS = ("idea_elements", "diffc_rows", "diffc_for", "diffc_agg",
                 "em_rows", "em_for", "em_method", "diff_result",
                 "draft_result", "draft_method", "review", "review_method")


def _collect_snapshot(idea: dict, method: str, scope: str) -> dict:
    """현재 세션의 분석 결과를 케이스 snapshot 으로 수집(복원·리포트용)."""
    snap = {"idea_dna": idea.get("idea_dna", {}),
            "expansion_method": method, "scope": scope}
    for k in ANALYSIS_KEYS:
        v = ss_get(k)
        if v is not None:
            snap[k] = v
    return snap


def persist_case_snapshot():
    """버튼으로 생성된 분석(매칭표·차별성·초안 등)을 케이스에 저장."""
    case_id = ss_get("review_case_id")
    if not case_id:
        return
    idea = ss_get("idea", {})
    snap = _collect_snapshot(idea, ss_get("expansion_method", ""),
                             idea.get("scope", "국내"))
    try:
        db.update_review_case(case_id, snapshot=snap)
    except Exception:
        pass


def run_full_review(idea: dict, top_n: int, scope: str):
    """[검토 시작] 한 번으로 검색어 확장 → 검색 → 유사도 → 차이 비교 → 케이스 저장."""
    # 이전 분석 잔재 제거(새 검토 시작)
    for k in ANALYSIS_KEYS:
        st.session_state.pop(k, None)
    with st.spinner("검색어 확장 중..."):
        expansion, method = keyword_expander.expand(
            idea.get("title", ""), idea.get("description", ""),
            idea.get("keywords", ""), idea.get("exclude_keywords", ""))
    st.session_state["expansion"] = expansion
    st.session_state["expansion_method"] = method
    st.session_state["idea"]["idea_dna"] = expansion.get("idea_dna", {})

    ok = run_search_pipeline(idea, expansion, top_n, redirect=False, scope=scope)
    if not ok:
        return

    df = get_results_df()
    idea_dna = idea.get("idea_dna", {})
    results = ss_get("results", [])
    # 핵심: 아이디어 구성요소 분해 + 차이 비교(요약)를 자동 수행해 저장
    try:
        st.session_state["idea_elements"] = element_match.decompose_idea(
            idea, idea_dna)
        st.session_state["diffc_agg"] = diff_compare.aggregate(
            idea, idea_dna, results[:5])
    except Exception:
        pass

    conf_label, _, _ = review_confidence()
    high = int((df["total_score"] >= 70).sum()) if "total_score" in df else 0
    try:
        case_id = db.save_review_case({
            "idea_id": ss_get("idea_id"),
            "title": idea.get("title") or "(제목 없는 아이디어)",
            "description": idea.get("description", ""),
            "keywords": idea.get("keywords", ""),
            "scope": scope, "top_n": top_n,
            "status": "검토중", "confidence": conf_label,
            "n_results": len(df), "high_risk": high,
            "snapshot": _collect_snapshot(idea, method, scope),
        })
        st.session_state["review_case_id"] = case_id
    except Exception as exc:
        st.warning(f"검토 케이스 저장 중 오류 (분석은 계속 진행됩니다): {exc}")

    st.success(f"검토 완료 · 유사특허 {len(df)}건 비교. 아래 '아이디어-특허 차이 "
               "비교' 탭부터 확인하세요.")
    st.rerun()


def render_summary_tab():
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    sc = df["total_score"]
    label, desc, tone = review_confidence()

    top = st.columns([3, 2])
    with top[0]:
        st.markdown(f"#### {idea.get('title') or '(제목 없는 아이디어)'}")
        st.caption(idea.get("description", "") or "-")
    with top[1]:
        st.markdown(
            f"<div style='text-align:right;margin-top:6px'>{ui.badge_html(label, tone)}"
            f"<div style='font-size:.74rem;color:#64788F;margin-top:4px'>{desc}"
            f"</div></div>", unsafe_allow_html=True)

    scope = idea.get("scope", "국내")
    basis = "샘플 데이터(데모)" if config.use_mock_data() else "KIPRIS 실데이터"
    st.caption(f"검색 범위: {scope} · 데이터 기준: {basis}"
               + ("" if scope == "국내" else " · 해외는 데모 샘플 기준"))

    k = st.columns(4)
    k[0].metric("유사특허", f"{len(df)}건")
    k[1].metric("최고 관련도", f"{sc.max():.0f}")
    k[2].metric("주의 (70+)", f"{int((sc >= 70).sum())}건")
    k[3].metric("평균 관련도", f"{sc.mean():.0f}")

    # 최종 판단 / 검토 케이스 상태
    case_id = ss_get("review_case_id")
    if case_id:
        cur = ss_get("case_status", "검토중")
        opts = db.REVIEW_STATUSES
        c1, c2 = st.columns([1, 2])
        sel = c1.selectbox("검토 케이스 상태", opts,
                           index=opts.index(cur) if cur in opts else 1,
                           key="summary_status")
        verdict = c2.text_input("최종 판단 메모", value=ss_get("case_verdict", ""),
                                key="summary_verdict",
                                placeholder="예: 차별 포인트 2개 확보, 종속항 보완 후 출원 후보")
        if st.button("검토 상태 저장", key="save_case_status"):
            db.update_review_case(case_id, status=sel, final_verdict=verdict)
            st.session_state["case_status"] = sel
            st.session_state["case_verdict"] = verdict
            st.success("저장했습니다. '검토 결과함'에 반영됩니다.")

    st.markdown("##### 예비 리스크 특허 TOP 5")
    head = df.head(5)
    risk_col = head["claim_risk"] if "claim_risk" in head else head["total_score"]
    st.dataframe(pd.DataFrame({
        "예비 리스크": risk_col, "특허명": head["title"],
        "출원인": head["applicant"], "상태": head["status"],
        "관련도": head["total_score"]}),
        hide_index=True, use_container_width=True)
    st.caption("본 결과는 1차 검토 의견이며 최종 법률 판단이 아닙니다. 출원 전 변리사 "
               "검토를 권장합니다.")


def render_diff_compare_tab():
    """핵심 화면: 내 아이디어 ↔ 유사특허 항목별 차이 비교."""
    st.markdown("##### 아이디어 ↔ 유사특허 차이 비교")
    st.caption(diff_compare.DISCLAIMER)
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    idea_dna = idea.get("idea_dna", {})
    results = ss_get("results", [])

    # 1) TOP N 종합 요약 (공통점/차이점/위험요소/차별 포인트)
    agg = ss_get("diffc_agg") or diff_compare.aggregate(idea, idea_dna,
                                                        results[:5])
    a1, a2 = st.columns(2)
    a1.markdown("**공통 항목 (유사특허와 겹침 — 회피 검토 대상)**")
    a1.markdown("\n".join(f"- {x}" for x in (agg.get("공통_항목") or ["-"])))
    a2.markdown("**차이 항목 (차별 포인트 후보)**")
    a2.markdown("\n".join(f"- {x}" for x in (agg.get("차이_항목") or ["-"])))
    if agg.get("위험_요소"):
        st.warning("예비 리스크 높은 항목: " + ", ".join(agg["위험_요소"]))

    # 2) 특허별 항목 비교표
    st.markdown("---")
    st.markdown("**유사특허별 항목 비교** (내 아이디어와 어디가 같고 다른지)")
    options = {f"{int(r['rank'])}위 [{r.get('claim_risk', r['total_score']):.0f}] "
               f"{r['title']}": r["application_no"]
               for _, r in df.head(20).iterrows()}
    choice = st.selectbox("비교할 유사특허", list(options.keys()),
                          key="diffc_pick")
    app_no = options[choice]
    p = df[df["application_no"] == app_no].iloc[0].to_dict()
    rows = diff_compare.build_diff_table(idea, idea_dna, p)
    st.session_state["diffc_rows"] = rows
    st.session_state["diffc_for"] = app_no
    summ = diff_compare.summary(rows)
    m = st.columns(4)
    m[0].metric("일치", summ["일치"])
    m[1].metric("부분일치", summ["부분일치"])
    m[2].metric("차이(차별 후보)", summ["차이"])
    m[3].metric("미확인", summ["미확인"])
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if not str(p.get("representative_claim", "")).strip():
        st.caption("이 특허는 청구항 원문 미확보 — '청구항 구성'은 예비 검토입니다.")
    persist_case_snapshot()


def render_element_match():
    st.markdown("##### 구성요소 매칭표")
    st.caption("내 아이디어 구성요소가 유사특허 청구항/요약에 존재하는지 비교합니다. "
               "권리범위 충돌 단정이 아닌 1차 검토 의견입니다.")
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    idea_dna = idea.get("idea_dna", {})
    options = {f"{int(r['rank'])}위 [{r['total_score']:.0f}] {r['title']}":
               r["application_no"] for _, r in df.head(20).iterrows()}
    choice = st.selectbox("대상 특허", list(options.keys()), key="em_pick")
    app_no = options[choice]
    p = df[df["application_no"] == app_no].iloc[0].to_dict()
    if st.button("구성요소 매칭표 생성", key="gen_em"):
        with st.spinner("아이디어를 구성요소로 분해·매칭 중..."):
            rows, method = element_match.match(idea, idea_dna, p)
        st.session_state["em_rows"] = rows
        st.session_state["em_for"] = app_no
        st.session_state["em_method"] = method
        st.session_state["idea_elements"] = element_match.decompose_idea(
            idea, idea_dna)
        persist_case_snapshot()
    if ss_get("em_rows") and ss_get("em_for") == app_no:
        rows = ss_get("em_rows")
        summ = element_match.summary(rows)
        m = st.columns(4)
        m[0].metric("일치", summ["일치"])
        m[1].metric("부분일치", summ["부분일치"])
        m[2].metric("차이(차별 후보)", summ["차이"])
        m[3].metric("미확인", summ["미확인"])
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)
        if ss_get("em_method") == "fallback":
            st.caption("Gemini 미사용 — 키워드 기반 매칭 결과입니다.")


def render_diff_solution_tab():
    """차별성 · 보완안 (AI 1차 검토 + 차별 포인트). 청구항 초안은 별도 탭."""
    page_ai_review()
    st.markdown("---")
    st.markdown("##### 차별성 · 보완 아이디어")
    st.caption(draft_mod.DISCLAIMER)
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    idea_dna = idea.get("idea_dna", {})
    if st.button("차별성 · 보완 방향 도출", key="gen_diff"):
        top = df.head(5).to_dict("records")
        with st.spinner("차별 포인트 도출 중..."):
            st.session_state["diff_result"] = draft_mod.build_differentiation(
                idea, idea_dna, top)
        persist_case_snapshot()
    diff = ss_get("diff_result")
    if not diff:
        st.info("[차별성 · 보완 방향 도출]을 누르면 공통/차이 기반 차별 포인트를 "
                "제안합니다.")
        return
    c1, c2 = st.columns(2)
    c1.markdown("**핵심 차별 포인트 (보완 아이디어 후보)**")
    for d in (diff.get("differentiators") or ["-"]):
        c1.markdown(f"- {d}")
    if diff.get("stage_differentiators"):
        c1.markdown("**차별 공정단계**: " +
                    ", ".join(diff["stage_differentiators"]))
    c2.markdown("**유사특허와 공통 구성 (회피 검토 대상)**")
    for d in (diff.get("common_points") or ["-"]):
        c2.markdown(f"- {d}")


def render_claim_draft_tab():
    """청구항 초안 (독립항/종속항/방법항/회피설계)."""
    st.markdown("##### 청구항 초안")
    st.caption(draft_mod.DISCLAIMER)
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    idea_dna = idea.get("idea_dna", {})
    if st.button("청구항 초안 생성", key="gen_draft"):
        top = df.head(5).to_dict("records")
        diff = ss_get("diff_result") or draft_mod.build_differentiation(
            idea, idea_dna, top)
        st.session_state["diff_result"] = diff
        with st.spinner("청구항 초안 작성 중..."):
            draft, method = draft_mod.draft(idea, idea_dna, diff, top)
        st.session_state["draft_result"] = draft
        st.session_state["draft_method"] = method
        persist_case_snapshot()
    draft = ss_get("draft_result")
    if not draft:
        st.info("[청구항 초안 생성]을 누르면 차별 포인트를 반영한 독립항·종속항·"
                "방법항·회피설계 초안을 제안합니다.")
        return
    st.markdown("**독립항 초안**")
    st.code(draft.get("independent_claim", "-"), language=None)
    st.markdown("**종속항 초안**")
    for i, dc in enumerate(draft.get("dependent_claims", []), start=2):
        st.markdown(f"{i}. {dc}")
    st.markdown("**방법항 초안**")
    st.code(draft.get("method_claim", "-"), language=None)
    st.markdown("**회피설계 대체안**")
    for da in (draft.get("design_around") or ["-"]):
        st.markdown(f"- {da}")
    if draft.get("notes"):
        st.info(draft["notes"])
    if ss_get("draft_method") == "fallback":
        st.caption("Gemini 미사용 — 규칙 기반 초안입니다.")


def render_report_tab():
    df = get_results_df()
    if df.empty:
        return
    idea = ss_get("idea", {})
    label, desc, _ = review_confidence()
    sc = df["total_score"]
    st.markdown("##### 1페이지 요약")
    st.markdown(
        f"- **아이디어명**: {idea.get('title') or '-'}\n"
        f"- **검토일**: {pd.Timestamp.now():%Y-%m-%d}\n"
        f"- **검토 신뢰도**: {label} ({desc})\n"
        f"- **유사특허**: {len(df)}건 · 최고 관련도 {sc.max():.0f} · "
        f"주의(70+) {int((sc >= 70).sum())}건\n"
        f"- **최종 판단(메모)**: {ss_get('case_verdict', '') or '미작성'}")
    st.markdown("**예비 리스크 특허 TOP 5**")
    head = df.head(5)
    risk_col = head["claim_risk"] if "claim_risk" in head else head["total_score"]
    st.dataframe(pd.DataFrame({
        "예비 리스크": risk_col, "특허명": head["title"],
        "출원인": head["applicant"], "상태": head["status"]}),
        hide_index=True, use_container_width=True)
    st.info("Excel · PDF 전체 리포트는 **리포트** 메뉴에서 내보낼 수 있습니다.")
    if st.button("리포트로 이동", icon=":material/description:",
                 key="goto_reports_from_tab"):
        goto("Reports")


def render_review_tabs():
    tabs = st.tabs(["요약", "아이디어-특허 차이 비교", "구성요소 매칭표",
                    "유사특허", "청구항 대비", "차별성·보완안", "청구항 초안",
                    "리포트"])
    st.session_state["_no_header"] = True
    try:
        with tabs[0]:
            render_summary_tab()
        with tabs[1]:
            render_diff_compare_tab()
        with tabs[2]:
            render_element_match()
        with tabs[3]:
            page_patent_radar()
            with st.expander("통계 · 동향 (보조)"):
                page_landscape(flat=True)
            with st.expander("대표도면 (보조)"):
                page_drawing_intelligence()
        with tabs[4]:
            page_patent_dna()
        with tabs[5]:
            render_diff_solution_tab()
        with tabs[6]:
            render_claim_draft_tab()
        with tabs[7]:
            render_report_tab()
    finally:
        st.session_state["_no_header"] = False


def page_new_review():
    ui.page_header("새 아이디어 검토",
                   "아이디어를 입력하면 유사특허와의 차이 비교·차별화·청구항 초안까지 "
                   "한 번에 1차 검토합니다.")
    notes = []
    if not gemini_service.is_available():
        notes.append("Gemini API 미설정 — 키워드 기반 분석으로 동작 (설정에서 키 입력)")
    if config.use_mock_data():
        notes.append("KIPRIS 실데이터 미사용 — 샘플 데이터(데모) 기준")
    if notes:
        st.info(" · ".join(notes))

    idea = ss_get("idea", {})
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            title = st.text_input("아이디어명", value=idea.get("title", ""),
                                  placeholder=DEMO_IDEA["title"])
            description = st.text_area(
                "아이디어 설명", height=120,
                value=idea.get("description", ""),
                placeholder=DEMO_IDEA["description"])
            keywords = st.text_input(
                "핵심 키워드 (쉼표 구분)", value=idea.get("keywords", ""),
                placeholder=DEMO_IDEA["keywords"])
            exclude = st.text_input(
                "제외 키워드 (쉼표 구분)",
                value=idea.get("exclude_keywords", ""),
                placeholder=DEMO_IDEA["exclude_keywords"])
        with c2:
            scope = st.selectbox("검색 범위", ["국내", "해외", "국내+해외"],
                                 help="국내=KIPRIS 특허·실용신안 기준. 해외는 "
                                 "현재 샘플 데이터(데모) 기준이며 실 해외 API 연동은 "
                                 "향후 지원 예정입니다.")
            if scope != "국내":
                st.caption("※ 해외 검색은 데모 샘플 기준 (실 해외 API 미연동)")
            top_n = st.select_slider("유사특허 TOP N", options=[5, 10, 20, 50],
                                     value=ss_get("top_n", 10))
            st.markdown("<div style='height:6px'></div>",
                        unsafe_allow_html=True)
            start = st.button("검토 시작", type="primary",
                              use_container_width=True,
                              icon=":material/play_arrow:")
            demo = st.button("데모 아이디어 채우기", use_container_width=True,
                             icon=":material/auto_awesome:")

    if demo:
        st.session_state["idea"] = dict(DEMO_IDEA)
        st.rerun()

    st.session_state["idea"] = {
        "title": title, "description": description, "keywords": keywords,
        "exclude_keywords": exclude, "scope": scope,
        "idea_dna": idea.get("idea_dna", {}),
    }

    if start:
        if not (title or description or keywords):
            st.error("아이디어명/설명/키워드 중 하나는 입력해야 합니다.")
        else:
            run_full_review(st.session_state["idea"], top_n, scope)

    df = get_results_df()
    if not df.empty:
        st.markdown("---")
        render_review_tabs()


# ============================================================ 검토 결과함
def _load_case_into_session(idea_id: int, snapshot: dict = None):
    """검토 케이스(idea_id)의 저장된 검색 결과 + 분석 snapshot 을 세션으로 복원."""
    rows = db.load_idea_results(idea_id)
    if not rows:
        return False
    ideas = {i["id"]: i for i in db.list_ideas(200)}
    meta = ideas.get(idea_id, {})
    snapshot = snapshot or {}
    try:
        idea_dna = json.loads(meta.get("idea_dna_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        idea_dna = {}
    if not idea_dna:
        idea_dna = snapshot.get("idea_dna", {})
    results = _reconstruct_results(rows, idea_dna)
    st.session_state["idea"] = {
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "keywords": meta.get("keywords", ""),
        "exclude_keywords": meta.get("exclude_keywords", ""),
        "scope": snapshot.get("scope", "국내"),
        "idea_dna": idea_dna}
    st.session_state["results"] = results
    st.session_state["results_df"] = stats.to_dataframe(results)
    st.session_state["top_n"] = min(10, len(results))
    st.session_state["selected_patent"] = results[0]["application_no"]
    # 이전 세션 분석 제거 후, 저장된 snapshot 분석 복원
    for k in ("timeline_lines", "claim_chart") + ANALYSIS_KEYS:
        st.session_state.pop(k, None)
    for k in ANALYSIS_KEYS:
        if k in snapshot:
            st.session_state[k] = snapshot[k]
    return True


def page_review_cases():
    ui.page_header("검토 결과함",
                   "지난 아이디어 검토 케이스를 모아 보고, 다시 불러옵니다.")
    try:
        cases = db.list_review_cases()
    except Exception as exc:
        st.error(f"검토 케이스를 불러오지 못했습니다: {exc}")
        cases = []
    if not cases:
        st.info("저장된 검토 케이스가 없습니다. **새 아이디어 검토**에서 [검토 시작]을 "
                "누르면 케이스가 자동으로 기록됩니다.")
        if st.button("새 아이디어 검토로 가기", type="primary",
                     icon=":material/lightbulb:"):
            goto("New Review")
        return

    flt = st.multiselect("상태 필터", db.REVIEW_STATUSES,
                         default=db.REVIEW_STATUSES)
    view = [c for c in cases if (c.get("status") or "검토중") in flt]
    if not view:
        st.warning("선택한 상태의 케이스가 없습니다.")
        return

    table = pd.DataFrame([{
        "상태": c.get("status") or "검토중",
        "아이디어명": c.get("title") or "-",
        "유사특허": c.get("n_results") or 0,
        "주의(70+)": c.get("high_risk") or 0,
        "신뢰도": c.get("confidence") or "-",
        "최종 판단": c.get("final_verdict") or "-",
        "검토일": str(c.get("created_at"))[:16].replace("T", " "),
    } for c in view])
    st.dataframe(table, hide_index=True, use_container_width=True)

    labels = {f"[{str(c.get('created_at'))[:10]}] {c.get('title')} "
              f"({c.get('status')})": c for c in view}
    pick = st.selectbox("케이스 선택", list(labels.keys()))
    case = labels[pick]
    b1, b2, b3 = st.columns(3)
    if b1.button("이 케이스 불러오기", type="primary",
                 icon=":material/folder_open:"):
        full = db.get_review_case(case["id"]) or {}
        snapshot = full.get("snapshot", {})
        if case.get("idea_id") and _load_case_into_session(case["idea_id"],
                                                           snapshot):
            st.session_state["review_case_id"] = case["id"]
            st.session_state["case_status"] = case.get("status", "검토중")
            st.session_state["case_verdict"] = case.get("final_verdict", "")
            goto("New Review")
        else:
            st.warning("이 케이스에는 복원할 검색 결과가 없습니다.")
    new_status = b2.selectbox("상태 변경", db.REVIEW_STATUSES,
                              index=db.REVIEW_STATUSES.index(case.get("status"))
                              if case.get("status") in db.REVIEW_STATUSES else 1,
                              key="rc_status")
    if b2.button("상태 저장", key="rc_save"):
        db.update_review_case(case["id"], status=new_status)
        st.rerun()
    if b3.button("케이스 삭제", icon=":material/delete:", key="rc_del"):
        db.delete_review_case(case["id"])
        st.rerun()


# ============================================================ 관심 특허
def page_watchlist():
    ui.page_header("관심 특허",
                   "관리상태를 지정한 특허를 모아 기술군별로 봅니다.")
    try:
        marks = db.list_bookmarks()
    except Exception:
        marks = []
    if not marks:
        st.info("관심 특허가 없습니다. 검토 결과의 특허 상세에서 '관리상태'를 "
                "지정하면 여기에 모입니다.")
        return

    tab1, tab2 = st.tabs(["목록", "포트폴리오"])
    with tab1:
        flt = st.multiselect("관리상태 필터", db.WATCH_STATUSES,
                             default=db.WATCH_STATUSES)
        view = [m for m in marks
                if (m.get("watch_status") or "관심") in flt]
        bm = pd.DataFrame([{
            "관리상태": m.get("watch_status") or "관심",
            "특허명": m.get("title") or "-",
            "출원인": m.get("applicant") or "-",
            "출원번호": m.get("application_no"),
            "특허상태": m.get("status") or "-",
            "기술군": m.get("technology_group") or "-",
            "KIPRIS": m.get("kipris_url") or "",
        } for m in view])
        st.dataframe(
            bm, hide_index=True, use_container_width=True,
            column_config={"KIPRIS": st.column_config.LinkColumn(
                "KIPRIS", display_text="원문")})
        c1, c2 = st.columns([2, 1])
        rm = c1.selectbox("목록에서 제거할 특허",
                          [m["application_no"] for m in marks])
        if c2.button("목록에서 제거"):
            db.set_watch_status(rm, "없음")
            st.rerun()
        if len(bm):
            st.download_button(
                "관심 특허 CSV 다운로드",
                data=bm.to_csv(index=False).encode("utf-8-sig"),
                file_name="ip3_watchlist.csv", mime="text/csv")
    with tab2:
        pf = pd.DataFrame([{
            "기술군": m.get("technology_group") or "기타",
            "관리상태": m.get("watch_status") or "관심",
            "특허명": m.get("title") or "-",
            "출원인": m.get("applicant") or "-",
            "상태": m.get("status") or "-"} for m in marks])
        g = pf.groupby("기술군").size().reset_index(name="건수")
        cc1, cc2 = st.columns([2, 3])
        cc1.plotly_chart(px.pie(g, names="기술군", values="건수", hole=0.5,
                                title="기술군별 관심 특허"),
                         use_container_width=True)
        cc2.dataframe(pf, hide_index=True, use_container_width=True)


# ============================================================ 모니터링
def page_monitoring():
    ui.page_header("모니터링",
                   "관심 조건을 등록하고, 신규 출원·경쟁사·알림을 한 곳에서 봅니다.")
    tab1, tab2, tab3 = st.tabs(["현황", "경쟁사", "관심 조건 · 알림"])

    mock_note = ("샘플 데이터(데모) 기준" if config.use_mock_data()
                 else "KIPRIS 실데이터 기준")
    with tab1:
        st.caption(f"마지막 업데이트 · {monitoring.last_updated()} · {mock_note}")
        if config.use_mock_data():
            st.info("아래 현황/동향은 샘플 데이터(데모) 기반 참고용입니다. "
                    "관심 조건 등록·신규 감지는 '관심 조건 · 알림' 탭에서 동작합니다.")
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(monitoring.ipc_distribution(), x="IPC", y="건수",
                               title="IPC/CPC별 분포"),
                        use_container_width=True)
        c2.plotly_chart(px.line(monitoring.yearly_trend(), x="연도", y="건수",
                                markers=True, title="연도별 신규 출원 추이"),
                        use_container_width=True)
        st.markdown("##### 최근 신규 특허")
        rec = pd.DataFrame(monitoring.recent_patents(10))
        st.dataframe(pd.DataFrame({
            "특허명": rec["title"], "출원인": rec["applicant"],
            "상태": rec["status"], "출원일": rec["application_date"],
            "기술군": rec["technology_group"]}),
            hide_index=True, use_container_width=True)

    with tab2:
        st.caption(mock_note)
        comp = monitoring.competitor_table(10)
        st.plotly_chart(px.bar(comp.head(8), x="경쟁사", y="총 출원",
                               title="경쟁사별 출원 건수"),
                        use_container_width=True)
        st.dataframe(comp, hide_index=True, use_container_width=True)

    with tab3:
        st.markdown("##### 관심 조건 등록")
        st.caption("키워드·IPC·출원인을 등록하면 해당 조건의 신규 특허를 모아 "
                   "보여주는 구조입니다. (실데이터 연동 시 자동 갱신)")
        with st.form("mon_target_form"):
            mc1, mc2 = st.columns(2)
            name = mc1.text_input("조건명", placeholder="예: PC 기둥 접합부")
            scope = mc2.selectbox("범위", ["국내", "해외", "국내+해외"])
            kw = st.text_input("키워드 (쉼표 구분)",
                               placeholder="프리캐스트, 접합, 전단키")
            mc3, mc4 = st.columns(2)
            ipc = mc3.text_input("IPC (선택)", placeholder="E04B, E04C")
            applicant = mc4.text_input("출원인 (선택)")
            if st.form_submit_button("관심 조건 등록", type="primary"):
                if not (name or kw):
                    st.error("조건명 또는 키워드는 입력해야 합니다.")
                else:
                    db.save_monitoring_target({
                        "name": name, "keywords": kw, "ipc": ipc,
                        "applicant": applicant, "scope": scope})
                    st.success("관심 조건을 등록했습니다.")
                    st.rerun()

        targets = db.list_monitoring_targets()
        if targets:
            st.dataframe(pd.DataFrame([{
                "조건명": t.get("name") or "-",
                "키워드": t.get("keywords") or "-",
                "IPC": t.get("ipc") or "-",
                "출원인": t.get("applicant") or "-",
                "범위": t.get("scope") or "-",
                "등록일": str(t.get("created_at"))[:10],
            } for t in targets]), hide_index=True, use_container_width=True)
            dc1, dc2, dc3 = st.columns([2, 1, 1])
            opt = {f"{t.get('name') or t.get('keywords')}": t["id"]
                   for t in targets}
            rm = dc1.selectbox("삭제할 조건", list(opt.keys()))
            if dc2.button("조건 삭제"):
                db.delete_monitoring_target(opt[rm])
                st.rerun()
            if dc3.button("지금 점검", icon=":material/sync:", type="primary"):
                from jobs import monitor_runner
                with st.spinner("관심 조건 신규 특허 점검 중..."):
                    st.session_state["monitor_runs"] = monitor_runner.run_all()

            for r in (ss_get("monitor_runs") or []):
                if r["first_run"]:
                    st.info(f"**{r['target']}** · 최초 등록 (기준 {r['total']}건 "
                            "저장, 다음 점검부터 신규 감지)")
                elif r["new_count"]:
                    st.warning(f"**{r['target']}** · 신규 {r['new_count']}건 "
                               f"감지 (총 {r['total']}건)")
                    nm = pd.DataFrame([{
                        "특허명": p.get("title", "-"),
                        "출원인": p.get("applicant", "-"),
                        "출원일": p.get("application_date", "-"),
                    } for p in r["new_patents"][:10]])
                    st.dataframe(nm, hide_index=True, use_container_width=True)
                else:
                    st.success(f"**{r['target']}** · 신규 없음 (총 {r['total']}건)")

        st.markdown("##### 알림")
        ac = monitoring.alert_counts()
        m = st.columns(3)
        m[0].metric("고위험", f"{ac['높음']}건")
        m[1].metric("주의", f"{ac['중간']}건")
        m[2].metric("참고", f"{ac['낮음']}건")
        for a in monitoring.alerts()[:8]:
            st.markdown(ui.alert_row(a), unsafe_allow_html=True)


# ============================================================ 메인
def main():
    ss = st.session_state
    valid_pages = {"New Review", "Review Cases", "Watchlist",
                   "Monitoring", "Reports", "Settings"}
    if "page" not in ss:
        qp = st.query_params.get("page")     # ?page=... 딥링크로 초기 화면 지정
        ss["page"] = qp if qp in valid_pages else "New Review"
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
        "New Review": page_new_review,
        "Review Cases": page_review_cases,
        "Watchlist": page_watchlist,
        "Monitoring": page_monitoring,
        "Reports": page_reports,
        "Settings": page_settings,
    }
    pages.get(ss["page"], page_new_review)()


def goto(page_key: str):
    """다른 화면으로 이동 (바로가기 버튼용)."""
    st.session_state["_goto"] = page_key
    st.rerun()


if __name__ == "__main__":
    main()
