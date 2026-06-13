# -*- coding: utf-8 -*-
"""IP³ (IP Cube) - UI 디자인 시스템 (professional SaaS).

전문 분석 제품 느낌: 깔끔한 산세리프, 일관된 컴포넌트, 넘침 방지.
- inject_theme(): 전역 CSS (main() 최상단 1회)
- sidebar_brand(): 사이드바 워드마크
- page_header(): 페이지 제목
- grade_badge / status_badge / group_badge / info_card
"""
import html

import streamlit as st

# ---------------------------------------------------------------- 팔레트
BG = "#F6F8FB"           # 앱 배경 (쿨 뉴트럴)
SURFACE = "#FFFFFF"
INK = "#16212E"          # 본문 강조
MUTED = "#5C6B7A"        # 보조 텍스트
FAINT = "#93A0AE"        # 3차 텍스트
BORDER = "#E4E8EF"       # 보더
PRIMARY = "#2D5BA0"      # 전문 블루(액션/포인트)
PRIMARY_DARK = "#234C88"
ACCENT_SOFT = "#EAF1FA"  # 선택/연한 배경

# 기술군 색 (절제된 카테고리)
GROUP_COLORS = {
    "접합부": "#3D6CB0", "전단키": "#C0894E", "생산방법": "#3F8E6E",
    "몰드": "#C25C4E", "배수": "#6E63B0", "방수": "#8C7B68",
    "품질관리": "#B05C95", "유지관리": "#6B7A8C", "센서": "#9A9356",
    "시공장비": "#3E97A8", "기타": "#9AA6B4",
}

# 유사도 등급 (bg, fg)
GRADE_STYLE = {
    "고유사/주의": ("#FBE7E4", "#C0392B"),
    "유사": ("#FDF0DD", "#B5701A"),
    "관련 있음": ("#E7EFFA", "#2D5BA0"),
    "낮음": ("#EAEFF1", "#5C6B7A"),
}

# 특허 상태 (bg, fg)
STATUS_STYLE = {
    "등록": ("#E4F0E6", "#2F7A45"),
    "공개": ("#E7EFFA", "#2D5BA0"),
    "소멸": ("#ECEFF2", "#6B7682"),
    "거절": ("#FBE7E4", "#C0392B"),
    "취하": ("#ECEFF2", "#6B7682"),
    "포기": ("#ECEFF2", "#6B7682"),
}

SANS = ("'Inter','Pretendard',-apple-system,'Segoe UI','Malgun Gothic',"
        "'Apple SD Gothic Neo','Nanum Gothic',sans-serif")


def inject_theme() -> None:
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
  --bg:{BG}; --surface:{SURFACE}; --ink:{INK}; --muted:{MUTED};
  --faint:{FAINT}; --border:{BORDER}; --primary:{PRIMARY};
  --primary-dark:{PRIMARY_DARK}; --accent-soft:{ACCENT_SOFT};
}}

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
  font-family:{SANS}; color:var(--ink);
  -webkit-font-smoothing:antialiased;
}}
.stApp {{ background:var(--bg); }}

[data-testid="stMainBlockContainer"] {{
  padding-top:2.2rem; padding-bottom:4rem; max-width:1280px;
}}
[data-testid="stHeader"] {{ background:transparent; }}

/* 타이포 계층 */
h1,h2,h3,h4 {{ font-family:{SANS}; letter-spacing:-.015em; color:var(--ink);
  font-weight:700; }}
h4 {{ font-weight:600; }}
p, span, div, label, li {{ font-family:{SANS}; }}

/* ---------- 페이지 헤더 ---------- */
.gpc-page-head {{ margin:0 0 1.6rem; padding-bottom:1rem;
  border-bottom:1px solid var(--border); }}
.gpc-page-head .t {{ font-size:1.6rem; font-weight:700; color:var(--ink);
  letter-spacing:-.02em; line-height:1.2; }}
.gpc-page-head .s {{ font-size:.88rem; color:var(--muted); margin-top:.35rem;
  max-width:70ch; line-height:1.5; }}

/* ---------- 지표 (st.metric) ---------- */
[data-testid="stMetric"] {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:12px; padding:1rem 1.15rem;
}}
[data-testid="stMetricLabel"] p {{ color:var(--muted); font-size:.78rem;
  font-weight:500; }}
[data-testid="stMetricValue"] {{ color:var(--ink); font-weight:700;
  font-size:1.7rem; letter-spacing:-.02em; }}

/* ---------- 버튼 ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius:8px; font-weight:600; font-size:.88rem;
  border:1px solid var(--border); background:var(--surface); color:var(--ink);
  padding:.5rem 1rem; min-height:2.5rem; transition:all .13s ease;
  box-shadow:0 1px 1px rgba(22,33,46,.03);
}}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {{
  border-color:var(--primary); color:var(--primary);
  background:var(--accent-soft);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background:var(--primary); border:1px solid var(--primary); color:#fff;
  box-shadow:0 1px 2px rgba(45,91,160,.25);
}}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {{
  background:var(--primary-dark); border-color:var(--primary-dark); color:#fff;
}}

/* ---------- 입력 위젯 ---------- */
.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input {{
  border-radius:8px; border-color:var(--border);
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
  border-color:var(--primary); box-shadow:0 0 0 2px var(--accent-soft);
}}

/* ---------- 탭 ---------- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap:1.6rem; border-bottom:1px solid var(--border);
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  padding:.6rem .1rem; font-weight:600; font-size:.92rem; color:var(--muted);
}}
[data-testid="stTabs"] [aria-selected="true"] {{
  color:var(--primary); border-bottom-color:var(--primary) !important;
}}

/* ---------- 컨테이너 ---------- */
[data-testid="stExpander"] {{
  border:1px solid var(--border); border-radius:12px; background:var(--surface);
}}
[data-testid="stExpander"] summary {{ font-weight:500; }}
[data-testid="stDataFrame"] {{
  border:1px solid var(--border); border-radius:12px; overflow:hidden;
}}
[data-testid="stAlert"] {{ border-radius:10px; border:1px solid var(--border); }}
hr {{ border-color:var(--border); margin:1.4rem 0; }}

/* ---------- 사이드바 ---------- */
section[data-testid="stSidebar"] {{
  background:var(--surface); border-right:1px solid var(--border);
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
  padding:1.4rem .9rem;
}}
.gpc-brand {{ padding:.2rem .4rem 1rem; margin-bottom:.5rem;
  border-bottom:1px solid var(--border); display:flex; align-items:center;
  gap:.6rem; }}
.gpc-brand .mark {{ width:30px; height:30px; border-radius:8px; flex:none;
  background:linear-gradient(135deg,#2D5BA0,#16335B); color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:700;
  font-size:.95rem; }}
.gpc-brand .w {{ font-size:1.06rem; font-weight:700; color:var(--ink);
  letter-spacing:-.02em; line-height:1.1; }}
.gpc-brand .k {{ font-size:.62rem; color:var(--faint); letter-spacing:.12em;
  text-transform:uppercase; }}

section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:2px; margin-top:.5rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
  border-radius:8px; padding:.5rem .7rem; margin:0; cursor:pointer;
  font-size:.9rem; color:var(--muted); font-weight:500;
  transition:all .12s ease; white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
  color:var(--ink); background:#F1F4F8;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
  color:var(--primary); font-weight:600; background:var(--accent-soft);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{
  display:none;
}}

/* ---------- 배지 (넘침 방지) ---------- */
.gpc-badge {{ display:inline-block; padding:2px 9px; border-radius:6px;
  font-size:.74rem; font-weight:600; line-height:1.6; white-space:nowrap;
  max-width:100%; overflow:hidden; text-overflow:ellipsis; vertical-align:middle; }}

/* ---------- 정보 카드 (넘침 방지) ---------- */
.gpc-card {{ background:var(--surface); border:1px solid var(--border);
  border-radius:12px; padding:.95rem 1.1rem; height:100%;
  overflow-wrap:anywhere; word-break:break-word; }}
.gpc-card .ct {{ font-size:.68rem; color:var(--faint); font-weight:700;
  letter-spacing:.08em; text-transform:uppercase; margin-bottom:.45rem; }}
.gpc-card .cv {{ font-size:.88rem; color:var(--ink); line-height:1.6; }}

/* ---------- IP³ 로고 / 상단 헤더 ---------- */
.ip3-word {{ font-weight:800; letter-spacing:-.02em; color:var(--ink);
  font-family:{SANS}; white-space:nowrap; }}
.ip3-word sup {{ font-size:.52em; font-weight:800; color:var(--primary);
  vertical-align:super; margin-left:1px; }}
.ip3-topbar {{ display:flex; align-items:center; gap:16px;
  padding:.1rem .1rem 1rem; margin-bottom:1.4rem;
  border-bottom:1px solid var(--border); }}
.ip3-topbar .logo {{ font-size:1.7rem; line-height:1; }}
.ip3-topbar .tag {{ font-size:.82rem; color:var(--muted); line-height:1.35;
  border-left:2px solid var(--border); padding-left:14px; }}
.ip3-topbar .tag b {{ color:var(--primary); font-weight:600; }}
.gpc-brand {{ display:block; }}
.gpc-brand .bw {{ font-size:1.55rem; }}
</style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.markdown(
        '<div class="gpc-brand">'
        '<div class="ip3-word bw">IP<sup>3</sup></div>'
        '<div class="k">IP Cube · Patent Intelligence</div></div>',
        unsafe_allow_html=True)


def app_header() -> None:
    """메인 영역 상단 브랜드 헤더 (IP³ + 태그라인)."""
    st.markdown(
        '<div class="ip3-topbar">'
        '<div class="logo ip3-word">IP<sup>3</sup></div>'
        '<div class="tag"><b>Intellectual Property</b> · '
        '<b>Idea to Patent</b> · <b>Intelligence Platform</b></div>'
        '</div>',
        unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="s">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="gpc-page-head"><div class="t">{html.escape(title)}</div>'
        f'{sub}</div>',
        unsafe_allow_html=True)


def _badge(text: str, bg: str, fg: str) -> str:
    return (f'<span class="gpc-badge" style="background:{bg};color:{fg}">'
            f'{html.escape(str(text))}</span>')


def grade_badge(grade: str) -> str:
    bg, fg = GRADE_STYLE.get(grade, ("#ECEFF2", "#6B7682"))
    return _badge(grade, bg, fg)


def status_badge(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("#ECEFF2", "#6B7682"))
    return _badge(status, bg, fg)


def _tint(hex_color: str, amt: float = 0.88) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amt); g = int(g + (255 - g) * amt)
    b = int(b + (255 - b) * amt)
    return f"#{r:02X}{g:02X}{b:02X}"


def group_badge(group: str) -> str:
    color = GROUP_COLORS.get(group, "#9AA6B4")
    return _badge(group, _tint(color), color)


def info_card(title: str, value_html: str) -> str:
    return (f'<div class="gpc-card"><div class="ct">{html.escape(title)}</div>'
            f'<div class="cv">{value_html}</div></div>')
