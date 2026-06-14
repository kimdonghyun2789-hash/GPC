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

# 메뉴 (key, 한글 라벨, 아이콘) — 실무형 IP 검토 플랫폼 6메뉴
NAV_GROUPS = [
    ("", [
        ("Home", "홈", ":material/home:"),
        ("New Review", "새 아이디어 검토", ":material/lightbulb:"),
        ("Review Cases", "검토 결과함", ":material/folder_open:"),
        ("Watchlist", "관심 특허", ":material/bookmark:"),
        ("Monitoring", "모니터링", ":material/radar:"),
        ("Reports", "리포트 · 설정", ":material/description:")]),
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
        # 검토 상태 워크리스트
        app_no = p.get("application_no", "")
        opts = ["없음"] + db.REVIEW_STATUSES
        cur = db.get_review_status(app_no) or "없음"
        sel = st.selectbox(
            "검토 상태", opts, index=opts.index(cur) if cur in opts else 0,
            key=f"rs_{app_no}",
            help="관심/확인필요/주의/제외 — 기록·관심특허와 보고서에 반영됩니다.")
        if sel != cur:
            db.set_review_status(app_no, sel, p.get("title", ""),
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
                        per_query: int = 25, redirect: bool = True):
    """검색식 실행 → 중복제거 → 유사도 계산 → DB 저장 → 세션 반영.

    redirect=True 면 완료 후 아이디어 검토로 이동(rerun). False 면 결과만 채우고
    True/False 를 반환한다(통합 검토 플로우에서 후속 단계 진행용).
    """
    client = KiprisClient()
    queries = list(expansion.get("search_queries", []))[:5]
    if not queries:
        st.error("실행할 검색식이 없습니다. 검색어 확장을 먼저 실행하세요.")
        return False

    with st.spinner(f"KIPRIS 검색 실행 중 ({client.mode} 모드, "
                    f"검색식 {len(queries)}개)..."):
        try:
            patents = client.search_multi(
                queries, per_query=per_query,
                exclude_keywords=idea.get("exclude_keywords", ""))
        except Exception as exc:
            st.error(f"KIPRIS 검색 실패: {exc}")
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


# ============================================================ 0. Dashboard
def page_dashboard():
    df = get_results_df()
    try:
        worklist = db.list_bookmarks()
    except Exception:
        worklist = []
    s = monitoring.dashboard_stats(df if not df.empty else None, worklist)

    # 헤더 + 마지막 업데이트 + 새로고침
    hc1, hc2 = st.columns([3, 1])
    with hc1:
        ui.page_header("홈",
                       "검토 현황과 관심 기술·특허의 최신 변화를 한눈에 봅니다.")
    with hc2:
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.caption(f"마지막 업데이트 · {s['updated']}")
        if st.button("새로고침", icon=":material/refresh:",
                     use_container_width=True):
            st.rerun()

    # 핵심 지표 카드 (2행 4열)
    r1 = st.columns(4)
    r1[0].metric("전체 관심 특허", f"{s['watch_total']}건")
    r1[1].metric("신규 공개", f"{s['new_published']}건")
    r1[2].metric("신규 등록", f"{s['new_registered']}건")
    r1[3].metric("최근 신규 유사", f"{s['new_similar_30d']}건")
    r2 = st.columns(4)
    r2[0].metric("경쟁사 신규 출원", f"{s['competitor_new']}곳")
    r2[1].metric("위험도 높은 특허", f"{s['high_risk']}건")
    r2[2].metric("검토 필요", f"{s['review_needed']}건")
    ac = monitoring.alert_counts()
    r2[3].metric("신규 알림", f"{sum(ac.values())}건")

    # 차트 영역
    st.markdown("##### 관심 기술 동향")
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(px.line(monitoring.yearly_trend(), x="연도", y="건수",
                            markers=True, title="월별/연도별 신규 특허 추이"),
                    use_container_width=True)
    c2.plotly_chart(px.pie(monitoring.status_distribution(), names="상태",
                           values="건수", hole=0.55, title="상태별 분포"),
                    use_container_width=True)

    # 리스트 영역: 신규 유사 / 알림
    l1, l2 = st.columns(2)
    with l1:
        st.markdown("##### 내 아이디어와 유사한 신규 특허 Top 5")
        src = df.head(5) if not df.empty else pd.DataFrame(
            monitoring.recent_patents(5))
        if not df.empty:
            tbl = pd.DataFrame({"관련도": src["total_score"],
                                "특허명": src["title"],
                                "출원인": src["applicant"],
                                "상태": src["status"]})
        else:
            tbl = pd.DataFrame({"특허명": src["title"],
                                "출원인": src["applicant"],
                                "상태": src["status"],
                                "출원일": src["application_date"]})
        st.dataframe(tbl, hide_index=True, use_container_width=True)
        if st.button("새 아이디어 검토", icon=":material/lightbulb:"):
            goto("New Review")
    with l2:
        st.markdown("##### 최근 알림")
        for a in monitoring.alerts()[:6]:
            st.markdown(ui.alert_row(a), unsafe_allow_html=True)
        if st.button("모니터링 전체 보기", icon=":material/radar:"):
            goto("Monitoring")


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
            # 청구항 대비표(1위 특허) + 검토 목록 포함
            claim_rows = None
            if len(df):
                top1 = df.iloc[0].to_dict()
                claim_rows, _ = claim_chart.build_claim_chart(
                    idea, idea.get("idea_dna", {}), top1)
            try:
                worklist = db.list_bookmarks()
            except Exception:
                worklist = None
            pdf = pdf_exporter.export_pdf(df, idea, queries, timeline_lines,
                                          review, top_n, images=report_imgs,
                                          claim_rows=claim_rows,
                                          worklist=worklist)
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
    st.markdown("---")
    if st.button("브랜드 · UI 가이드 열기", icon=":material/palette:"):
        goto("Brand Guide")


# ===================================================== 새 아이디어 검토 (통합)
def run_full_review(idea: dict, top_n: int, scope: str):
    """[검토 시작] 한 번으로 검색어 확장 → 검색 → 유사도 → 케이스 저장."""
    with st.spinner("검색어 확장 중..."):
        expansion, method = keyword_expander.expand(
            idea.get("title", ""), idea.get("description", ""),
            idea.get("keywords", ""), idea.get("exclude_keywords", ""))
    st.session_state["expansion"] = expansion
    st.session_state["expansion_method"] = method
    st.session_state["idea"]["idea_dna"] = expansion.get("idea_dna", {})

    ok = run_search_pipeline(idea, expansion, top_n, redirect=False)
    if not ok:
        return

    df = get_results_df()
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
            "snapshot": {"idea_dna": idea.get("idea_dna", {}),
                         "expansion_method": method},
        })
        st.session_state["review_case_id"] = case_id
    except Exception as exc:
        st.warning(f"검토 케이스 저장 중 오류 (분석은 계속 진행됩니다): {exc}")

    st.success(f"검토 완료 · 유사특허 {len(df)}건 분석. 아래 탭에서 결과를 "
               "확인하세요.")
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

    k = st.columns(4)
    k[0].metric("유사특허", f"{len(df)}건")
    k[1].metric("최고 관련도", f"{sc.max():.0f}")
    k[2].metric("주의 (70+)", f"{int((sc >= 70).sum())}건")
    k[3].metric("평균 관련도", f"{sc.mean():.0f}")

    # 최종 판단 / 검토 상태
    case_id = ss_get("review_case_id")
    if case_id:
        cur = ss_get("case_status", "검토중")
        opts = db.REVIEW_STATUSES
        c1, c2 = st.columns([1, 2])
        sel = c1.selectbox("검토 상태", opts,
                           index=opts.index(cur) if cur in opts else 1,
                           key="summary_status")
        verdict = c2.text_input("최종 판단 메모", value=ss_get("case_verdict", ""),
                                key="summary_verdict",
                                placeholder="예: 차별 포인트 2개 확보, 종속항 보완 후 출원 검토")
        if st.button("검토 상태 저장", key="save_case_status"):
            db.update_review_case(case_id, status=sel, final_verdict=verdict)
            st.session_state["case_status"] = sel
            st.session_state["case_verdict"] = verdict
            st.success("저장했습니다. '검토 결과함'에 반영됩니다.")

    st.markdown("##### 리스크 특허 TOP 5 (관련도 순)")
    head = df.head(5)
    st.dataframe(pd.DataFrame({
        "관련도": head["total_score"], "특허명": head["title"],
        "출원인": head["applicant"], "상태": head["status"],
        "등급": head["total_score"].apply(sim_mod.grade)}),
        hide_index=True, use_container_width=True)
    st.caption("AI 검토는 최종 법률 판단이 아닌 1차 참고용입니다. 출원 전 변리사 "
               "검토를 권장합니다.")


def render_element_match():
    st.markdown("---")
    st.markdown("##### 구성요소 매칭표")
    st.caption("내 아이디어 구성요소가 유사특허 청구항에 존재하는지 비교합니다. "
               "침해/유효성 판단이 아닌 1차 참고용입니다.")
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
            st.caption("Gemini 미사용 — 규칙 기반 구성요소 매칭 결과입니다.")


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
    st.markdown("**리스크 특허 TOP 5**")
    head = df.head(5)
    st.dataframe(pd.DataFrame({
        "관련도": head["total_score"], "특허명": head["title"],
        "출원인": head["applicant"], "상태": head["status"]}),
        hide_index=True, use_container_width=True)
    st.info("Excel · PDF 전체 리포트는 **리포트 · 설정** 메뉴에서 내보낼 수 있습니다.")
    if st.button("리포트 · 설정으로 이동", icon=":material/description:",
                 key="goto_reports_from_tab"):
        goto("Reports")


def render_review_tabs():
    tabs = st.tabs(["요약", "유사특허", "청구항 대비", "차별성·보완안",
                    "통계·동향", "도면", "리포트"])
    st.session_state["_no_header"] = True
    try:
        with tabs[0]:
            render_summary_tab()
        with tabs[1]:
            page_patent_radar()
        with tabs[2]:
            page_patent_dna()
            render_element_match()
        with tabs[3]:
            page_ai_review()
        with tabs[4]:
            page_landscape(flat=True)
        with tabs[5]:
            page_drawing_intelligence()
        with tabs[6]:
            render_report_tab()
    finally:
        st.session_state["_no_header"] = False


def page_new_review():
    ui.page_header("새 아이디어 검토",
                   "아이디어를 입력하면 유사특허 검색부터 청구항 리스크·차별성까지 "
                   "한 번에 검토합니다.")
    if not gemini_service.is_available():
        st.info("Gemini API Key 미설정 — 검색어 확장·AI 검토는 키워드 기반으로 "
                "동작합니다. (리포트·설정에서 키 입력)")

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
            scope = st.selectbox("검색 범위", ["국내", "해외", "국내+해외"])
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
def _load_case_into_session(idea_id: int):
    """검토 케이스(idea_id)의 저장된 검색 결과를 세션으로 복원."""
    rows = db.load_idea_results(idea_id)
    if not rows:
        return False
    ideas = {i["id"]: i for i in db.list_ideas(200)}
    meta = ideas.get(idea_id, {})
    try:
        idea_dna = json.loads(meta.get("idea_dna_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        idea_dna = {}
    results = _reconstruct_results(rows, idea_dna)
    st.session_state["idea"] = {
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "keywords": meta.get("keywords", ""),
        "exclude_keywords": meta.get("exclude_keywords", ""),
        "idea_dna": idea_dna}
    st.session_state["results"] = results
    st.session_state["results_df"] = stats.to_dataframe(results)
    st.session_state["top_n"] = min(10, len(results))
    st.session_state["selected_patent"] = results[0]["application_no"]
    for k in ("review", "timeline_lines", "claim_chart", "em_rows"):
        st.session_state.pop(k, None)
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
        if case.get("idea_id") and _load_case_into_session(case["idea_id"]):
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
                   "검토 상태를 지정한 특허를 모아 기술군별 포트폴리오로 봅니다.")
    try:
        marks = db.list_bookmarks()
    except Exception:
        marks = []
    if not marks:
        st.info("관심 특허가 없습니다. 검토 결과의 특허 상세에서 '검토 상태'를 "
                "지정하면 여기에 모입니다.")
        return

    tab1, tab2 = st.tabs(["목록", "포트폴리오"])
    with tab1:
        flt = st.multiselect("상태 필터", db.REVIEW_STATUSES,
                             default=db.REVIEW_STATUSES)
        view = [m for m in marks
                if (m.get("review_status") or "검토중") in flt]
        bm = pd.DataFrame([{
            "검토상태": m.get("review_status") or "검토중",
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
            db.set_review_status(rm, "없음")
            st.rerun()
        if len(bm):
            st.download_button(
                "관심 특허 CSV 다운로드",
                data=bm.to_csv(index=False).encode("utf-8-sig"),
                file_name="ip3_watchlist.csv", mime="text/csv")
    with tab2:
        pf = pd.DataFrame([{
            "기술군": m.get("technology_group") or "기타",
            "검토상태": m.get("review_status") or "검토중",
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

    with tab1:
        st.caption(f"마지막 업데이트 · {monitoring.last_updated()}")
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
            dc1, dc2 = st.columns([2, 1])
            opt = {f"{t.get('name') or t.get('keywords')}": t["id"]
                   for t in targets}
            rm = dc1.selectbox("삭제할 조건", list(opt.keys()))
            if dc2.button("조건 삭제"):
                db.delete_monitoring_target(opt[rm])
                st.rerun()

        st.markdown("##### 알림")
        ac = monitoring.alert_counts()
        m = st.columns(3)
        m[0].metric("고위험", f"{ac['높음']}건")
        m[1].metric("주의", f"{ac['중간']}건")
        m[2].metric("참고", f"{ac['낮음']}건")
        for a in monitoring.alerts()[:8]:
            st.markdown(ui.alert_row(a), unsafe_allow_html=True)


# ============================================================ 리포트 · 설정
def page_reports_settings():
    ui.page_header("리포트 · 설정",
                   "분석 결과를 내보내고, API Key·데이터 모드·기준을 관리합니다.")
    tab1, tab2 = st.tabs(["리포트", "설정"])
    with tab1:
        st.session_state["_no_header"] = True
        try:
            page_export_center()
        finally:
            st.session_state["_no_header"] = False
    with tab2:
        st.session_state["_no_header"] = True
        try:
            page_settings()
        finally:
            st.session_state["_no_header"] = False


# ============================================================ 브랜드 / UI 가이드
def page_brand_guide():
    if st.button("← 리포트 · 설정으로", key="bg_back"):
        goto("Reports")
    ui.page_header("브랜드 · UI 가이드",
                   "IP³ 디자인 시스템 — 로고·컬러·컴포넌트 가이드.")
    logo = ui._logo_uri(64, "color")
    if logo:
        st.markdown(f"<img src='{logo}' style='height:48px'/>",
                    unsafe_allow_html=True)
    st.markdown("##### 컬러 팔레트")
    pal = [("Primary", ui.PRIMARY), ("Bright", ui.BRIGHT),
           ("Deep Navy", ui.NAVY), ("Slate", ui.SLATE),
           ("Light Gray", ui.LIGHT_GRAY)]
    sw = " ".join(
        f"<div style='display:inline-block;text-align:center;margin-right:10px'>"
        f"<div style='width:64px;height:44px;border-radius:8px;background:{c};"
        f"border:1px solid #E4E8F0'></div><div style='font-size:.7rem;"
        f"color:#475569;margin-top:4px'>{n}<br>{c}</div></div>" for n, c in pal)
    st.markdown(sw, unsafe_allow_html=True)
    st.markdown("##### 배지")
    st.markdown(
        ui.badge_html("신규", "primary") + " " + ui.badge_html("등록", "success")
        + " " + ui.badge_html("검토중", "warn") + " " + ui.badge_html("위험", "danger")
        + " " + ui.status_badge("공개") + " " + ui.grade_badge("고유사/주의"),
        unsafe_allow_html=True)
    st.markdown("##### 버튼")
    b1, b2, b3 = st.columns(3)
    b1.button("Primary", type="primary", key="bg_p", use_container_width=True)
    b2.button("Secondary", key="bg_s", use_container_width=True)
    b3.button("아이콘", icon=":material/search:", key="bg_i",
              use_container_width=True)
    st.markdown("##### 카드 · 통계")
    cc = st.columns(3)
    cc[0].metric("통계 카드", "128", "예시")
    cc[1].markdown(ui.info_card("정보 카드", "카드형 정보 블록입니다."),
                   unsafe_allow_html=True)
    cc[2].markdown(ui.alert_row({"type": "알림", "level": "중간",
                                 "title": "알림 카드 예시", "message": "메시지",
                                 "date": "2026-06-14"}), unsafe_allow_html=True)


# ============================================================ 메인
def main():
    ss = st.session_state
    if "page" not in ss:
        ss["page"] = "Home"
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
        "Home": page_dashboard,
        "New Review": page_new_review,
        "Review Cases": page_review_cases,
        "Watchlist": page_watchlist,
        "Monitoring": page_monitoring,
        "Reports": page_reports_settings,
        "Brand Guide": page_brand_guide,
    }
    pages.get(ss["page"], page_dashboard)()


def goto(page_key: str):
    """다른 화면으로 이동 (바로가기 버튼용)."""
    st.session_state["_goto"] = page_key
    st.rerun()


if __name__ == "__main__":
    main()
