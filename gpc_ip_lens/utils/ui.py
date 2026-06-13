# -*- coding: utf-8 -*-
"""GPC IP Lens - UI 디자인 시스템 (미니멀 / 에디토리얼).

따뜻한 페이퍼 배경, 절제된 클레이 포인트, 영문 제목 세리프.
- inject_theme(): 전역 CSS (main() 최상단 1회 호출)
- sidebar_brand(): 사이드바 워드마크
- page_header(): 페이지 제목 (이모지 없음)
- grade_badge / status_badge / group_badge: 절제된 색 배지
- info_card(): 정보 카드 HTML
"""
import html

import streamlit as st

# ---------------------------------------------------------------- 팔레트
PAPER = "#F4F6F9"        # 앱 배경 (쿨 라이트)
SURFACE = "#FFFFFF"
INK = "#1E2A38"          # 본문 (네이비 잉크)
MUTED = "#647281"        # 보조 텍스트
FAINT = "#97A2AF"        # 3차 텍스트
BORDER = "#E2E7EE"       # 쿨 보더
ACCENT = "#2E4B6B"       # 차분한 네이비 포인트
ACCENT_SOFT = "#E8EDF4"  # 선택 배경

# 기술군 색 (절제된 카테고리 팔레트 · network_map 공용)
GROUP_COLORS = {
    "접합부": "#4A6FA5", "전단키": "#C0894E", "생산방법": "#5E8B6E",
    "몰드": "#B36657", "배수": "#7A6CA0", "방수": "#8C7B68",
    "품질관리": "#A66B90", "유지관리": "#7E8893", "센서": "#9A9356",
    "시공장비": "#5E94A0", "기타": "#A9A294",
}

# 유사도 등급 (bg, fg) — 차분한 톤
GRADE_STYLE = {
    "고유사/주의": ("#F3E0DC", "#A4452F"),
    "유사": ("#EFE6D8", "#8A6526"),
    "관련 있음": ("#E7ECEF", "#4D6071"),
    "낮음": ("#E7EDE7", "#54664E"),
}

# 특허 상태 (bg, fg)
STATUS_STYLE = {
    "등록": ("#E5EDE6", "#4C654D"),
    "공개": ("#E5ECF4", "#34557E"),
    "소멸": ("#EAECEF", "#6B7682"),
    "거절": ("#F3E0DC", "#A4452F"),
    "취하": ("#EAECEF", "#6B7682"),
    "포기": ("#EAECEF", "#6B7682"),
}

SERIF = ("Georgia,'Times New Roman','Nanum Myeongjo','Batang',serif")
SANS = ("-apple-system,'Segoe UI','Pretendard','Malgun Gothic',"
        "'Nanum Gothic','Apple SD Gothic Neo',sans-serif")


def inject_theme() -> None:
    st.markdown(
        f"""
<style>
:root {{
  --paper:{PAPER}; --surface:{SURFACE}; --ink:{INK}; --muted:{MUTED};
  --faint:{FAINT}; --border:{BORDER}; --accent:{ACCENT}; --accent-soft:{ACCENT_SOFT};
}}

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
  font-family:{SANS}; color:var(--ink);
}}
.stApp {{ background:var(--paper); }}

/* 메인 컨테이너 — 넉넉한 여백 */
[data-testid="stMainBlockContainer"] {{
  padding-top:2.6rem; padding-bottom:4rem; max-width:1180px;
}}

/* Streamlit 기본 헤더/툴바 숨김 (미니멀) */
[data-testid="stHeader"] {{ background:transparent; }}
[data-testid="stToolbar"] {{ right:1rem; }}

/* 제목 — 세리프 에디토리얼 */
h1,h2,h3,h4 {{ font-family:{SERIF}; letter-spacing:-.01em; color:var(--ink); }}

/* ---------- 페이지 헤더 ---------- */
.gpc-page-head {{ margin:0 0 1.8rem; }}
.gpc-page-head .t {{
  font-family:{SERIF}; font-size:1.92rem; font-weight:600; color:var(--ink);
  line-height:1.15;
}}
.gpc-page-head .s {{ font-size:.92rem; color:var(--muted); margin-top:.45rem;
  max-width:60ch; }}

/* ---------- 지표 (st.metric) ---------- */
[data-testid="stMetric"] {{
  background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:1.05rem 1.2rem;
}}
[data-testid="stMetricLabel"] p {{ color:var(--muted); font-size:.8rem;
  font-weight:500; }}
[data-testid="stMetricValue"] {{ color:var(--ink); font-weight:600;
  font-family:{SERIF}; }}

/* ---------- 버튼 ---------- */
.stButton > button, .stDownloadButton > button {{
  border-radius:10px; font-weight:500; border:1px solid var(--border);
  background:var(--surface); color:var(--ink); transition:all .14s ease;
  box-shadow:none;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color:var(--accent); color:var(--accent); background:var(--surface);
}}
.stButton > button[kind="primary"] {{
  background:var(--accent); border:1px solid var(--accent); color:#fff;
}}
.stButton > button[kind="primary"]:hover {{
  background:#243B56; border-color:#243B56; color:#fff;
}}

/* ---------- 입력 위젯 ---------- */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
  border-radius:10px;
}}

/* ---------- 탭 ---------- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap:1.4rem; border-bottom:1px solid var(--border);
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  padding:.55rem .15rem; font-weight:500; color:var(--muted);
}}
[data-testid="stTabs"] [aria-selected="true"] {{
  color:var(--ink); border-bottom-color:var(--accent) !important;
}}

/* ---------- 익스팬더 / 데이터프레임 ---------- */
[data-testid="stExpander"] {{
  border:1px solid var(--border); border-radius:12px; background:var(--surface);
}}
[data-testid="stDataFrame"] {{
  border:1px solid var(--border); border-radius:12px; overflow:hidden;
}}
[data-testid="stAlert"] {{ border-radius:12px; }}
hr {{ border-color:var(--border); }}

/* ---------- 사이드바 ---------- */
section[data-testid="stSidebar"] {{
  background:var(--paper); border-right:1px solid var(--border);
}}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
  padding:1.6rem 1rem;
}}
.gpc-brand {{ padding:0 .35rem 1.1rem; margin-bottom:.5rem;
  border-bottom:1px solid var(--border); }}
.gpc-brand .w {{ font-family:{SERIF}; font-size:1.32rem; font-weight:600;
  color:var(--ink); letter-spacing:-.01em; }}
.gpc-brand .k {{ font-size:.7rem; color:var(--faint); letter-spacing:.16em;
  text-transform:uppercase; margin-top:.15rem; }}

/* 라디오 → 미니멀 내비게이션 */
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:1px; margin-top:.6rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
  border-radius:8px; padding:.5rem .7rem; margin:0; cursor:pointer;
  font-size:.92rem; color:var(--muted); font-weight:450;
  border-left:2px solid transparent; transition:all .12s ease;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
  color:var(--ink); background:rgba(0,0,0,.025);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
  color:var(--accent); font-weight:600; background:var(--accent-soft);
  border-left:2px solid var(--accent);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {{
  display:none;
}}

/* ---------- 배지 / 카드 ---------- */
.gpc-badge {{ display:inline-block; padding:2px 10px; border-radius:6px;
  font-size:.74rem; font-weight:600; line-height:1.55; }}
.gpc-card {{ background:var(--surface); border:1px solid var(--border);
  border-radius:13px; padding:1rem 1.15rem; height:100%; }}
.gpc-card .ct {{ font-size:.7rem; color:var(--faint); font-weight:600;
  letter-spacing:.1em; text-transform:uppercase; margin-bottom:.5rem; }}
.gpc-card .cv {{ font-size:.9rem; color:var(--ink); line-height:1.65; }}
</style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    """사이드바 상단 워드마크."""
    st.markdown(
        '<div class="gpc-brand"><div class="w">GPC IP Lens</div>'
        '<div class="k">Patent Intelligence</div></div>',
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
    bg, fg = GRADE_STYLE.get(grade, ("#ECEAE3", "#7C766A"))
    return _badge(grade, bg, fg)


def status_badge(status: str) -> str:
    bg, fg = STATUS_STYLE.get(status, ("#ECEAE3", "#7C766A"))
    return _badge(status, bg, fg)


def _tint(hex_color: str, amt: float = 0.86) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amt); g = int(g + (255 - g) * amt)
    b = int(b + (255 - b) * amt)
    return f"#{r:02X}{g:02X}{b:02X}"


def group_badge(group: str) -> str:
    color = GROUP_COLORS.get(group, "#A9A294")
    return _badge(group, _tint(color), color)


def info_card(title: str, value_html: str) -> str:
    return (f'<div class="gpc-card"><div class="ct">{html.escape(title)}</div>'
            f'<div class="cv">{value_html}</div></div>')
