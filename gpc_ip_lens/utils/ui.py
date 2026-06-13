# -*- coding: utf-8 -*-
"""GPC IP Lens - UI 디자인 시스템.

업무용 내부 도구에 맞는 정돈된 스타일을 제공한다.
- inject_theme(): 전역 CSS 주입 (한 번만 호출)
- app_header(): 상단 브랜드 헤더 바
- page_header(): 페이지별 제목 헤더
- grade_badge() / status_badge(): 색상 배지 HTML
- kpi_cards(): 카드형 핵심지표 행
"""
import html

import streamlit as st

# ---------------------------------------------------------------- 색상 팔레트
NAVY = "#15385F"        # 브랜드 딥네이비
NAVY_2 = "#1E4D80"      # 헤더 그라데이션 보조
BLUE = "#2E6FE0"        # 액센트(선택/포커스)
BLUE_SOFT = "#EAF1FC"   # 선택 배경
BG = "#F4F7FB"          # 페이지 보조 배경
CARD_BORDER = "#E3EAF2"
TEXT = "#1B2A3A"
MUTED = "#64788F"

# 기술군 색 (network_map 과 톤 통일)
GROUP_COLORS = {
    "접합부": "#2E6FE0", "전단키": "#E8833A", "생산방법": "#2BA86B",
    "몰드": "#D6493B", "배수": "#7E57C2", "방수": "#8D6E63",
    "품질관리": "#D356A6", "유지관리": "#6B7B8C", "센서": "#B0A12E",
    "시공장비": "#1AA0B0", "기타": "#9FB2C6",
}

# 유사도 등급 색
GRADE_STYLE = {
    "고유사/주의": ("#FBE6E6", "#C0392B"),
    "유사": ("#FDEEDD", "#C5701A"),
    "관련 있음": ("#FCF6DD", "#9A7B12"),
    "낮음": ("#E6F4EA", "#2A7D4F"),
}

# 특허 상태 색
STATUS_STYLE = {
    "등록": ("#E6F4EA", "#2A7D4F"),
    "공개": ("#EAF1FC", "#2E6FE0"),
    "소멸": ("#EEF1F5", "#6B7B8C"),
    "거절": ("#FBE6E6", "#C0392B"),
    "취하": ("#EEF1F5", "#6B7B8C"),
    "포기": ("#EEF1F5", "#6B7B8C"),
}


def inject_theme() -> None:
    """전역 CSS 주입. main() 최상단에서 1회 호출한다."""
    st.markdown(
        """
<style>
:root {
  --navy:#15385F; --blue:#2E6FE0; --bg:#F4F7FB; --card-border:#E3EAF2;
  --text:#1B2A3A; --muted:#64788F;
}

/* ---------- 전역 폰트/배경 ---------- */
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
  font-family: 'Pretendard','Malgun Gothic','Apple SD Gothic Neo',
               -apple-system,'Segoe UI',sans-serif;
  color: var(--text);
}
.stApp { background: var(--bg); }

/* 메인 컨테이너 여백 정리 + 카드 느낌 */
[data-testid="stMainBlockContainer"] {
  padding-top: 1.1rem; padding-bottom: 3rem;
  max-width: 1500px;
}

/* ---------- 상단 헤더 바 ---------- */
.gpc-header {
  background: linear-gradient(100deg,#15385F 0%,#1E4D80 60%,#2E6FE0 130%);
  color:#fff; border-radius:14px; padding:16px 22px; margin-bottom:14px;
  display:flex; align-items:center; gap:14px;
  box-shadow:0 6px 18px rgba(21,56,95,.18);
}
.gpc-header .logo {
  width:42px; height:42px; border-radius:11px; background:rgba(255,255,255,.16);
  display:flex; align-items:center; justify-content:center; font-size:22px;
}
.gpc-header h1 { font-size:1.32rem; margin:0; font-weight:700; color:#fff; }
.gpc-header p { margin:2px 0 0; font-size:.82rem; color:#D6E4F5; }
.gpc-header .spacer { flex:1; }
.gpc-header .pill {
  background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.25);
  padding:5px 12px; border-radius:999px; font-size:.74rem; font-weight:500;
  white-space:nowrap;
}

/* ---------- 페이지 헤더 ---------- */
.gpc-page-head { margin:2px 0 14px; }
.gpc-page-head .t { font-size:1.32rem; font-weight:700; color:var(--navy);
  display:flex; align-items:center; gap:9px; }
.gpc-page-head .s { font-size:.86rem; color:var(--muted); margin-top:2px; }
.gpc-page-head .bar { height:3px; width:54px; border-radius:3px;
  background:linear-gradient(90deg,#2E6FE0,#15385F); margin-top:9px; }

/* ---------- 지표 카드 (st.metric) ---------- */
[data-testid="stMetric"] {
  background:#fff; border:1px solid var(--card-border); border-radius:13px;
  padding:14px 18px; box-shadow:0 1px 3px rgba(21,56,95,.05);
}
[data-testid="stMetricLabel"] { color:var(--muted); font-weight:500; }
[data-testid="stMetricValue"] { color:var(--navy); font-weight:700; }

/* ---------- 버튼 ---------- */
.stButton > button, .stDownloadButton > button {
  border-radius:9px; font-weight:600; border:1px solid var(--card-border);
  transition:all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color:var(--blue); color:var(--blue);
  transform:translateY(-1px); box-shadow:0 3px 10px rgba(46,111,224,.15);
}
.stButton > button[kind="primary"] {
  background:linear-gradient(95deg,#2E6FE0,#15385F); border:none; color:#fff;
}
.stButton > button[kind="primary"]:hover { color:#fff; opacity:.94; }

/* ---------- 탭 ---------- */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:4px; }
[data-testid="stTabs"] [data-baseweb="tab"] {
  border-radius:9px 9px 0 0; padding:8px 16px; font-weight:600;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background:var(--blue-soft,#EAF1FC); color:var(--blue);
}

/* ---------- 익스팬더 ---------- */
[data-testid="stExpander"] {
  border:1px solid var(--card-border); border-radius:11px; background:#fff;
}

/* ---------- 데이터프레임 ---------- */
[data-testid="stDataFrame"] {
  border:1px solid var(--card-border); border-radius:11px; overflow:hidden;
}

/* ---------- 알림 박스 살짝 둥글게 ---------- */
[data-testid="stAlert"] { border-radius:11px; }

/* ---------- 사이드바 ---------- */
section[data-testid="stSidebar"] {
  background:#fff; border-right:1px solid var(--card-border);
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  padding-top:1rem;
}
.gpc-side-brand {
  background:linear-gradient(135deg,#15385F,#1E4D80); color:#fff;
  border-radius:12px; padding:14px 16px; margin-bottom:14px;
}
.gpc-side-brand .b1 { font-size:1.05rem; font-weight:700; letter-spacing:.2px; }
.gpc-side-brand .b2 { font-size:.72rem; color:#C7DAF0; margin-top:1px; }

/* 사이드바 라디오 → 내비게이션 메뉴 스타일 */
section[data-testid="stSidebar"] div[role="radiogroup"] { gap:3px; }
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
  border-radius:9px; padding:8px 12px; margin:0; cursor:pointer;
  transition:all .12s ease; font-size:.93rem; font-weight:500;
  border:1px solid transparent;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
  background:#F1F5FB;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
  background:#EAF1FC; border-color:#CADcF7; color:#15385F; font-weight:700;
}
/* 라디오 동그라미 숨김 (메뉴처럼 보이게) */
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
  display:none;
}

/* 사이드바 상태 카드 */
.gpc-side-status {
  background:#F6F9FD; border:1px solid var(--card-border); border-radius:10px;
  padding:10px 12px; font-size:.78rem; color:var(--muted); line-height:1.7;
}
.gpc-side-status b { color:var(--text); }

/* 배지 */
.gpc-badge {
  display:inline-block; padding:2px 10px; border-radius:999px;
  font-size:.76rem; font-weight:700; line-height:1.5;
}

/* 정보 카드 (검색어 확장 결과 등) */
.gpc-card {
  background:#fff; border:1px solid var(--card-border); border-radius:12px;
  padding:14px 16px; height:100%;
}
.gpc-card .ct { font-size:.78rem; color:var(--muted); font-weight:600;
  text-transform:uppercase; letter-spacing:.4px; margin-bottom:6px; }
.gpc-card .cv { font-size:.9rem; color:var(--text); line-height:1.6; }
</style>
        """,
        unsafe_allow_html=True,
    )


def app_header(mode: str, gemini_ok: bool) -> None:
    """상단 브랜드 헤더 바."""
    mode_label = "Mock 데이터" if mode == "Mock" else "KIPRIS 실연동"
    gem_label = "Gemini 연결" if gemini_ok else "Gemini 미설정 · fallback"
    st.markdown(
        f"""
<div class="gpc-header">
  <div class="logo">🔍</div>
  <div>
    <h1>GPC IP Lens</h1>
    <p>건설 · PC 특화 특허 탐색 · 분석 플랫폼 &nbsp;|&nbsp; KIPRISPlus × Gemini</p>
  </div>
  <div class="spacer"></div>
  <div class="pill">📦 {mode_label}</div>
  <div class="pill">🤖 {gem_label}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """페이지별 제목 헤더."""
    sub = f'<div class="s">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
<div class="gpc-page-head">
  <div class="t">{icon} {html.escape(title)}</div>
  {sub}
  <div class="bar"></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _badge(text: str, bg: str, fg: str) -> str:
    return (f'<span class="gpc-badge" style="background:{bg};color:{fg}">'
            f'{html.escape(str(text))}</span>')


def grade_badge(grade: str) -> str:
    bg, fg = GRADE_STYLE.get(grade, ("#EEF1F5", "#6B7B8C"))
    return _badge(grade, bg, fg)


def status_badge(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("#EEF1F5", "#6B7B8C"))
    return _badge(status, bg, fg)


def group_badge(group: str) -> str:
    color = GROUP_COLORS.get(group, "#9FB2C6")
    return _badge(group, color + "22", color)


def info_card(title: str, value_html: str) -> str:
    """gpc-card HTML 문자열 반환 (st.columns 안에서 st.markdown 으로 출력)."""
    return (f'<div class="gpc-card"><div class="ct">{html.escape(title)}</div>'
            f'<div class="cv">{value_html}</div></div>')
